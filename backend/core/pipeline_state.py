"""
Pipeline readiness check used by the batch runners and the full-size preview.

Second, independent check of the signed licence token: it reads the token straight from the
database and verifies the server signature itself, so changing the licence service alone does
not unlock processing.
"""
import base64
import json
import sqlite3
import threading
import time
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_PARTS = ("ng3XTGeTg7EgnGmm", "LbKqqGEOXgLEI6SA", "oInxccNPfV8=")
_verifier = Ed25519PublicKey.from_public_bytes(base64.b64decode("".join(_PARTS)))
_mid_lock = threading.Lock()
_mid: Optional[str] = None
_cache = {"at": 0.0, "ok": False}
_CACHE_SECONDS = 20


def _machine() -> str:
    global _mid
    with _mid_lock:
        if _mid is None:
            from backend.services.license_service import LicenseService
            _mid = LicenseService.get_machine_fingerprint()
        return _mid


def _decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _check() -> bool:
    from backend.db.database import DB_FILE
    try:
        conn = sqlite3.connect(DB_FILE, timeout=30.0)
        try:
            row = conn.execute("SELECT token, last_seen_ts FROM license_client WHERE id = 1").fetchone()
        finally:
            conn.close()
    except Exception:
        return False
    if not row or not row[0] or row[0].count(".") != 1:
        return False
    body, sig = row[0].split(".")
    try:
        _verifier.verify(_decode(sig), body.encode("ascii"))
        data = json.loads(_decode(body))
    except Exception:
        return False
    now = int(time.time())
    if not isinstance(data, dict) or data.get("mid") != _machine():
        return False
    if now + 3600 < int(data.get("iat") or 0) or now + 3600 < int(row[1] or 0):
        return False
    exp = data.get("exp")
    if exp and now >= int(exp):
        return False
    return now < int(data.get("rby") or 0)


def pipeline_ready() -> bool:
    """True while this computer holds a valid, unexpired signed token (a pass is cached for a few seconds)."""
    t = time.time()
    if _cache["ok"] and t - _cache["at"] < _CACHE_SECONDS:
        return True
    ok = _check()
    _cache.update(at=t, ok=ok)
    return ok
