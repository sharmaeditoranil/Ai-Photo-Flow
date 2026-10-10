"""
Ai PhotoFlow - licensing client.

All licenses, trials, prices, coupons and payments are decided by the online License Server
(https://aiphotoflow.in/license). The server signs a short license token with its Ed25519
private key; this app only contains the PUBLIC key, so a token cannot be forged or edited here.

A token is bound to this computer (machine id), carries the plan and expiry, and must be
refreshed online at least every `offline grace` days (set on the server, default 30).
Revoked / suspended / removed licenses stop working at the next online check.
"""
import base64
import hashlib
import json
import os
import platform
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.db.database import get_connection

LICENSE_SERVER = os.environ.get("APF_LICENSE_SERVER", "https://license.aiphotoflow.in").rstrip("/")
# Earlier address (inside the website folder); used only if the subdomain does not answer
LICENSE_SERVER_FALLBACKS = [u for u in ("https://aiphotoflow.in/license",) if u != LICENSE_SERVER]
# Public half of the server's signing key (safe to ship; it can only verify, never sign)
LICENSE_PUBLIC_KEY_B64 = "ng3XTGeTg7EgnGmmLbKqqGEOXgLEI6SAoInxccNPfV8="
APP_VERSION = "1.0.0"

REFRESH_EVERY = 12 * 3600          # online re-check interval while internet is available
FAILED_RETRY_AFTER = 60            # don't hammer the server when offline
_HTTP_TIMEOUT = 15
_USER_AGENT = "Mozilla/5.0 (compatible; AiPhotoFlow/%s)" % APP_VERSION

# Server error codes that mean "this license must stop working on this computer"
_DEAD_LICENSE_CODES = {"REVOKED", "SUSPENDED", "EXPIRED", "DEACTIVATED", "INVALID_KEY"}

_PUBLIC_KEY = Ed25519PublicKey.from_public_bytes(base64.b64decode(LICENSE_PUBLIC_KEY_B64))


class LicenseServerError(Exception):
    def __init__(self, message: str, code: str = "ERROR", offline: bool = False):
        super().__init__(message)
        self.code = code
        self.offline = offline


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        import certifi  # optional
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    if sys.platform == "darwin" and os.path.exists("/etc/ssl/cert.pem"):
        try:
            ctx.load_verify_locations("/etc/ssl/cert.pem")
        except Exception:
            pass
    return ctx


_SSL_CTX = _ssl_context()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Returns the payload if the server signature is valid, else None."""
    if not token or token.count(".") != 1:
        return None
    body, sig = token.split(".")
    try:
        _PUBLIC_KEY.verify(_b64url_decode(sig), body.encode("ascii"))
        payload = json.loads(_b64url_decode(body))
        return payload if isinstance(payload, dict) else None
    except (InvalidSignature, ValueError, UnicodeError, json.JSONDecodeError):
        return None


class LicenseService:
    _lock = threading.Lock()
    _refresh_running = False
    _last_failed_attempt = 0.0

    def __init__(self):
        self.machine_id = self.get_machine_fingerprint()
        self._init_tables()

    # ------------------------------------------------------------------ identity
    @staticmethod
    def get_machine_fingerprint() -> str:
        """Hardware-bound 16-char id (Mac IOPlatformUUID / Windows SMBIOS UUID)."""
        raw_hw = ""
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            if platform.system() == "Darwin":
                out = subprocess.check_output(["ioreg", "-d2", "-c", "IOPlatformExpertDevice"], timeout=3).decode(errors="ignore")
                for line in out.split("\n"):
                    if "IOPlatformUUID" in line or "IOPlatformSerialNumber" in line:
                        raw_hw += line.strip()
            elif platform.system() == "Windows":
                try:
                    # SMBIOS board UUID (survives app reinstall and Windows user changes)
                    raw_hw = subprocess.check_output(
                        ["powershell", "-NoProfile", "-Command", "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
                        timeout=8, creationflags=no_window).decode(errors="ignore").strip()
                except Exception:
                    out = subprocess.check_output(["wmic", "csproduct", "get", "uuid"], timeout=8,
                                                  creationflags=no_window).decode(errors="ignore")
                    for line in out.split("\n"):
                        line = line.strip()
                        if line and "UUID" not in line:
                            raw_hw = line
                            break
        except Exception:
            pass
        bad_uuids = {"", "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF", "00000000-0000-0000-0000-000000000000"}
        if platform.system() == "Windows" and raw_hw.strip().upper() in bad_uuids:
            try:
                # Windows installation id: stable across app reinstalls (wmic is removed on new Windows 11)
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                                    0, winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)) as k:
                    raw_hw = "WINGUID:" + str(winreg.QueryValueEx(k, "MachineGuid")[0])
            except Exception:
                raw_hw = ""
        if not raw_hw:
            raw_hw = f"{uuid.getnode()}:{platform.node()}:{platform.machine()}:{platform.processor()}"
        h = hashlib.sha256(raw_hw.encode()).hexdigest()[:16].upper()
        return f"{h[:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"

    @staticmethod
    def _machine_name() -> str:
        try:
            return socket.gethostname()[:80]
        except Exception:
            return ""

    @staticmethod
    def _os_name() -> str:
        return f"{platform.system()} {platform.release()}"[:60]

    # ------------------------------------------------------------------ storage
    def _init_tables(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS license_client (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            token TEXT DEFAULT '',
            license_key TEXT DEFAULT '',
            last_refresh_ts INTEGER DEFAULT 0,
            last_seen_ts INTEGER DEFAULT 0,
            last_error TEXT DEFAULT '',
            last_error_code TEXT DEFAULT '',
            pending_order_id TEXT DEFAULT ''
        )""")
        cur.execute("INSERT OR IGNORE INTO license_client (id) VALUES (1)")
        conn.commit()
        conn.close()

    def _row(self) -> Dict[str, Any]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM license_client WHERE id = 1")
        row = dict(cur.fetchone())
        conn.close()
        return row

    def _save(self, **fields):
        if not fields:
            return
        conn = get_connection()
        cur = conn.cursor()
        cols = ", ".join(f"{k} = ?" for k in fields)
        cur.execute(f"UPDATE license_client SET {cols} WHERE id = 1", list(fields.values()))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------ server calls
    def _call(self, route: str, body: Optional[Dict[str, Any]] = None, timeout: int = _HTTP_TIMEOUT) -> Dict[str, Any]:
        payload = dict(body or {})
        payload.setdefault("machine_id", self.machine_id)
        payload.setdefault("machine_name", self._machine_name())
        payload.setdefault("os", self._os_name())
        payload.setdefault("app_version", APP_VERSION)
        data = None
        servers = [LICENSE_SERVER] + LICENSE_SERVER_FALLBACKS
        for i, server in enumerate(servers):
            req = urllib.request.Request(
                f"{server}/api.php?r={route}", data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT}, method="POST")
            try:
                data = self._post(req, timeout)
                break
            except LicenseServerError as e:
                # Only "server not there" moves on to the next address; real answers (refusals) never do
                if i + 1 < len(servers) and e.code in ("OFFLINE", "NOT_FOUND", "BAD_ANSWER", "SERVER"):
                    continue
                raise
        if not isinstance(data, dict) or not data.get("ok"):
            data = data if isinstance(data, dict) else {}
            raise LicenseServerError(data.get("error") or "License server refused the request.", data.get("code") or "ERROR")
        return data

    @staticmethod
    def _post(req, timeout: int) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8", "replace"))
            except Exception:
                if e.code == 404:
                    raise LicenseServerError("License server not reachable at the moment.", "NOT_FOUND", offline=True)
                raise LicenseServerError(f"License server error (HTTP {e.code}). Please try again.", "SERVER")
            return data
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError):
            raise LicenseServerError("No internet connection to the license server.", "OFFLINE", offline=True)
        except Exception:
            # e.g. a parking / maintenance page instead of the API: treated like being offline (grace period)
            raise LicenseServerError("License server returned an invalid answer.", "BAD_ANSWER", offline=True)

    def _accept_token(self, token: str, license_key: Optional[str]) -> Dict[str, Any]:
        payload = verify_token(token)
        if not payload or payload.get("mid") != self.machine_id:
            raise LicenseServerError("Received an invalid license token.", "BAD_TOKEN")
        now = int(time.time())
        self._save(token=token, license_key=license_key or "", last_refresh_ts=now,
                   last_seen_ts=max(now, int(self._row().get("last_seen_ts") or 0)), last_error="", last_error_code="")
        return payload

    # ------------------------------------------------------------------ refresh
    def refresh(self) -> None:
        """Re-validates online. Network problems keep the current token; server rejections clear it."""
        row = self._row()
        key = row.get("license_key") or ""
        try:
            if key:
                data = self._call("refresh", {"license_key": key})
                self._accept_token(data["token"], key)
            else:
                data = self._call("trial")
                self._accept_token(data["token"], None)
        except LicenseServerError as e:
            if e.offline or e.code in ("SERVER", "RATE_LIMIT", "BAD_TOKEN"):
                LicenseService._last_failed_attempt = time.time()
                self._save(last_error=str(e), last_error_code=e.code)
                return
            if key and e.code in _DEAD_LICENSE_CODES:
                # Revoked / expired / removed from this PC: drop it; the trial state (usually ended) applies again
                self._save(token="", license_key="", last_error=str(e), last_error_code=e.code)
                return
            # Trial ended or blocked by the owner
            self._save(token="", last_error=str(e), last_error_code=e.code, last_refresh_ts=int(time.time()))

    def _refresh_in_background(self):
        if LicenseService._refresh_running:
            return
        LicenseService._refresh_running = True

        def run():
            try:
                self.refresh()
            finally:
                LicenseService._refresh_running = False

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------ status
    def _locked(self, status: str, message: str, plan: str = "FREE_TRIAL") -> Dict[str, Any]:
        return {
            "plan": plan, "status": status, "is_active": False, "is_vip": False, "days_left": 0,
            "expires_at": None, "user_name": "", "user_email": "", "license_key": "", "machine_id": self.machine_id,
            "max_devices": 1, "message": message, "tamper_alert": message if status == "TAMPER_DETECTED" else None,
            "server_url": LICENSE_SERVER,
            "features": {"unlimited_photos": False, "high_res_export": False, "indian_skin_tone": False,
                         "multi_device": False, "batch_auto_edit": False, "all_culling_rules": False},
        }

    def get_license_status(self) -> Dict[str, Any]:
        with LicenseService._lock:
            row = self._row()
            now = int(time.time())
            can_retry = time.time() - LicenseService._last_failed_attempt > FAILED_RETRY_AFTER
            if not row.get("token"):
                # First start / after a dead license: get a token now (needs internet). A finished trial is
                # re-checked only every REFRESH_EVERY so an owner extension is picked up without hammering.
                ended = row.get("last_error_code") in ("TRIAL_EXPIRED", "TRIAL_BLOCKED")
                if can_retry and (not ended or now - int(row.get("last_refresh_ts") or 0) > REFRESH_EVERY):
                    self.refresh()
                    row = self._row()
            elif now - int(row.get("last_refresh_ts") or 0) > REFRESH_EVERY and can_retry:
                self._refresh_in_background()

        token = row.get("token") or ""
        if not token:
            code = row.get("last_error_code") or ""
            msg = row.get("last_error") or "Please connect to the internet once to start your free trial."
            status = "OFFLINE" if code in ("OFFLINE", "SERVER", "RATE_LIMIT", "BAD_TOKEN", "") else "EXPIRED"
            return self._locked(status, msg)

        payload = verify_token(token)
        if not payload or payload.get("mid") != self.machine_id:
            self._save(token="")
            return self._locked("TAMPER_DETECTED", "License data is invalid on this computer. Please activate again.")

        # Clock set back? (token issued in the "future", or clock earlier than the last time we saw)
        last_seen = int(row.get("last_seen_ts") or 0)
        if now + 3600 < int(payload.get("iat") or 0) or now + 3600 < last_seen:
            return self._locked("TAMPER_DETECTED", "Your computer's date/time is wrong. Please correct it and restart the app.")
        if now > last_seen + 60:
            self._save(last_seen_ts=now)

        plan = payload.get("plan") or "FREE_TRIAL"
        exp = payload.get("exp")
        rby = int(payload.get("rby") or 0)
        if exp and now >= int(exp):
            msg = "Your free trial has ended. Please buy a plan to continue." if payload.get("typ") == "trial" \
                else "Your license has expired. Please renew your plan."
            return self._locked("EXPIRED", msg, plan=plan)
        if now >= rby:
            return self._locked("OFFLINE", "Please connect to the internet so the app can verify your license.", plan=plan)

        days_left = 9999 if not exp else max(0, int((int(exp) - now) // 86400))
        hours_left = None if not exp else max(0, int((int(exp) - now) // 3600))
        paid = plan in ("PRO", "STUDIO", "VIP_LIFETIME")
        return {
            "plan": plan, "status": "ACTIVE", "is_active": True, "is_vip": plan == "VIP_LIFETIME", "days_left": days_left,
            "hours_left": hours_left, "activated_at": payload.get("act"), "user_phone": payload.get("phone") or "",
            "expires_at": datetime.fromtimestamp(int(exp)).strftime("%Y-%m-%d %H:%M:%S") if exp else None,
            "user_name": payload.get("name") or "", "user_email": payload.get("email") or "",
            "license_key": payload.get("lic") or "", "machine_id": self.machine_id,
            "max_devices": int(payload.get("dev") or 1), "security_verified": True,
            "offline_days_left": max(0, (rby - now) // 86400), "server_url": LICENSE_SERVER, "message": None,
            "features": {"unlimited_photos": paid, "high_res_export": True, "indian_skin_tone": True,
                         "multi_device": plan in ("STUDIO", "VIP_LIFETIME"), "batch_auto_edit": True, "all_culling_rules": True},
        }

    def current_token(self) -> Optional[str]:
        """Valid signed token for this computer (used to authenticate with the album server)."""
        if not self.get_license_status().get("is_active"):
            return None
        return self._row().get("token") or None

    def verify_operational_permission(self, action: str = "EXPORT") -> Tuple[bool, str]:
        status = self.get_license_status()
        if status.get("is_active"):
            return True, "Authorized"
        return False, status.get("message") or "Please activate a license to continue."

    # ------------------------------------------------------------------ user actions
    def activate_key(self, key: str, user_name: str = "", user_email: str = "") -> Tuple[bool, str, Dict[str, Any]]:
        clean = "".join(ch for ch in (key or "").upper() if ch.isalnum() or ch == "-")
        if not clean:
            return False, "Please enter your license key.", {}
        try:
            data = self._call("activate", {"license_key": clean})
            self._accept_token(data["token"], clean)
        except LicenseServerError as e:
            return False, str(e), {}
        return True, "License activated on this computer!", self.get_license_status()

    def deactivate(self) -> Tuple[bool, str]:
        row = self._row()
        if not row.get("license_key"):
            return False, "No license is active on this computer."
        try:
            self._call("deactivate", {"license_key": row["license_key"], "token": row.get("token") or ""})
        except LicenseServerError as e:
            return False, str(e)
        self._save(token="", license_key="", last_error="", last_error_code="", last_refresh_ts=0)
        LicenseService._last_failed_attempt = 0.0
        self.refresh()  # back to this computer's trial state right away
        return True, "License removed from this computer. You can now activate it on another computer."

    def get_profile(self) -> Dict[str, Any]:
        """Plan, dates, computers and purchases for the My Profile screen (server data, token fallback offline)."""
        status = self.get_license_status()
        row = self._row()
        payload = verify_token(row.get("token") or "") or {}
        fmt = lambda ts: datetime.fromtimestamp(int(ts)).strftime("%d %b %Y, %I:%M %p") if ts else None
        exp = payload.get("exp")
        profile = {
            "status": status, "is_trial": payload.get("typ") == "trial" or not row.get("license_key"),
            "plan": status.get("plan"), "license_key": row.get("license_key") or "",
            "name": payload.get("name") or "", "email": payload.get("email") or "", "phone": payload.get("phone") or "",
            "activated_at": fmt(payload.get("act")), "expires_at": fmt(exp) if exp else ("Lifetime" if payload else None),
            "days_left": status.get("days_left"), "hours_left": status.get("hours_left"),
            "max_devices": int(payload.get("dev") or 1), "machine_id": self.machine_id,
            "machine_name": self._machine_name(), "devices": [], "orders": [], "online": False,
            "last_checked": fmt(row.get("last_refresh_ts")),
            "left_pct": None,
        }
        act = payload.get("act")
        if exp and act and int(exp) > int(act):
            profile["left_pct"] = round(max(0.0, min(100.0, (int(exp) - time.time()) * 100.0 / (int(exp) - int(act)))), 1)
        if row.get("license_key") and row.get("token"):
            try:
                data = self._call("profile", {"license_key": row["license_key"], "token": row["token"]})
                lic = data["license"]
                profile.update({
                    "online": True, "name": lic.get("customer_name") or profile["name"],
                    "email": lic.get("customer_email") or profile["email"], "phone": lic.get("customer_phone") or profile["phone"],
                    "activated_at": fmt(lic.get("activated_at")) or profile["activated_at"], "cycle": lic.get("cycle"),
                    "max_devices": lic.get("max_devices") or profile["max_devices"],
                    "devices": [{**d, "first_seen": fmt(d.get("first_seen")), "last_seen": fmt(d.get("last_seen"))} for d in data.get("devices", [])],
                    "orders": [{**o, "date": fmt(o.get("date"))} for o in data.get("orders", [])],
                })
            except LicenseServerError:
                pass
        return profile

    def get_plans(self) -> Dict[str, Any]:
        try:
            return self._call("plans", {}, timeout=10)
        except LicenseServerError as e:
            return {"ok": False, "error": str(e)}

    def verify_coupon(self, code: str, plan_id: str, billing_cycle: str, currency: str = "INR") -> Dict[str, Any]:
        try:
            q = self._call("quote", {"plan": plan_id.upper(), "cycle": billing_cycle.lower(), "currency": currency.upper(), "coupon": code})
        except LicenseServerError as e:
            return {"valid": False, "message": str(e)}
        return {"valid": True, "code": q["coupon"], "discount_percent": q["discount_percent"], "original_price": q["original_price"],
                "discount_amount": q["discount_amount"], "final_price": q["final_price"], "currency": q["currency"],
                "message": f"{q['discount_percent']:g}% discount applied!"}

    def create_order(self, plan_id: str, billing_cycle: str, name: str, email: str, phone: str,
                     coupon: Optional[str], currency: str) -> Dict[str, Any]:
        """Raises LicenseServerError on failure."""
        data = self._call("order", {"plan": plan_id.upper(), "cycle": billing_cycle.lower(), "currency": currency.upper(),
                                    "coupon": coupon or "", "name": name, "email": email, "phone": phone})
        if data.get("free"):
            self._accept_token(data["token"], data["license"]["license_key"])
            return {"free": True, "license": self.get_license_status(), "message": "License activated (100% coupon)!"}
        self._save(pending_order_id=data["order_id"])
        return data

    def verify_payment(self, order_id: str, payment_id: str, signature: str) -> Tuple[bool, str, Dict[str, Any]]:
        try:
            data = self._call("verify", {"order_id": order_id, "payment_id": payment_id, "signature": signature})
            self._accept_token(data["token"], data["license"]["license_key"])
        except LicenseServerError as e:
            return False, str(e), {}
        self._save(pending_order_id="")
        return True, "Payment successful! Your plan is now active.", self.get_license_status()

    def check_pending_order(self) -> Optional[Dict[str, Any]]:
        """If a payment finished while the app was closed, pick up the license created by the webhook."""
        oid = self._row().get("pending_order_id") or ""
        if not oid:
            return None
        try:
            data = self._call("order_status", {"order_id": oid})
        except LicenseServerError as e:
            if e.code == "NOT_FOUND":
                self._save(pending_order_id="")
            return None
        if data.get("paid"):
            self._accept_token(data["token"], data["license"]["license_key"])
            self._save(pending_order_id="")
            return self.get_license_status()
        return None


_shared_service: Optional[LicenseService] = None
_shared_lock = threading.Lock()


def get_license_service() -> LicenseService:
    """One shared instance (the machine fingerprint is computed once)."""
    global _shared_service
    with _shared_lock:
        if _shared_service is None:
            _shared_service = LicenseService()
        return _shared_service
