"""
Master Hosting sync for client proofing galleries.

The photographer uploads master_hosting/index.php to their own cPanel / web hosting and saves that
URL (e.g. https://yourdomain.com/album) in the app. This service then:
  * checks that the URL really runs the Ai PhotoFlow Master Hosting script (?action=ping),
  * pushes gallery metadata (?action=sync) and every watermarked preview (?action=upload_preview),
  * verifies the gallery page opens on the domain,
  * pulls the client's selections back (?action=get_selections) into the local database.
The public link for a synced gallery is  <master_url>/?id=<gallery_uuid>[&pin=<pin>].
"""
import io
import json
import re
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid as uuid_mod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from PIL import Image

from backend.db.database import get_connection

# Some shared hosts (mod_security) reject requests without a browser-like User-Agent
_USER_AGENT = "Mozilla/5.0 (compatible; AiPhotoFlow/1.0; +master-hosting-sync)"
_TIMEOUT = 30
# Ai PhotoFlow's own album server; used when the owner has not set a different Master Hosting URL
DEFAULT_MASTER_URL = "https://aiphotoflow.in/files/public_html"


def _auth_headers() -> Dict[str, str]:
    """The album server only accepts uploads from apps holding a server-signed license / trial token."""
    from backend.services.license_service import get_license_service
    token = get_license_service().current_token()
    if not token:
        raise RuntimeError("An active Ai PhotoFlow license or trial is needed to upload client albums.")
    return {"X-APF-License": token}


def normalize_master_url(url: Optional[str]) -> str:
    """'yourdomain.com/album/index.php?x' -> 'https://yourdomain.com/album'."""
    u = (url or "").strip()
    if not u:
        return ""
    if not u.lower().startswith(("http://", "https://")):
        u = "https://" + u
    u = u.split("#", 1)[0].split("?", 1)[0]
    scheme, _, rest = u.partition("://")
    u = scheme + "://" + re.sub(r"/{2,}", "/", rest)
    if u.lower().endswith("/index.php"):
        u = u[: -len("/index.php")]
    return u.rstrip("/")


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


def _request(url: str, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None,
             timeout: int = _TIMEOUT) -> tuple:
    """Returns (status_code, body_bytes). Raises RuntimeError with a readable message on network errors."""
    h = {"User-Agent": _USER_AGENT, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return e.code, body
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ssl.SSLError):
            raise RuntimeError(f"SSL certificate error on hosting ({reason}). Enable free SSL (AutoSSL) in cPanel.")
        raise RuntimeError(f"Hosting not reachable: {reason}")
    except Exception as e:
        raise RuntimeError(f"Hosting request failed: {e}")


def _api(base: str, action: str, extra: Optional[Dict[str, str]] = None) -> str:
    # Always call index.php directly: '/album?action=..' gets a 301 to '/album/' and POST bodies are lost
    q = {"action": action}
    q.update(extra or {})
    return f"{base}/index.php?{urllib.parse.urlencode(q)}"


def _json(body: bytes) -> Dict[str, Any]:
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return {}


def gallery_public_url(base: str, gallery_uuid: str, pin: str = "") -> str:
    url = f"{base}/?id={urllib.parse.quote(gallery_uuid)}"
    if pin:
        url += f"&pin={urllib.parse.quote(pin)}"
    return url


class HostingSyncService:
    def __init__(self):
        self._ping_cache: Dict[str, tuple] = {}  # url -> (timestamp, result)
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ---------------- settings / detection ----------------
    def get_master_url(self) -> str:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT value FROM app_settings WHERE key = 'custom_domain_url'")
            row = cur.fetchone()
            conn.close()
            return normalize_master_url(row["value"] if row and row["value"] else DEFAULT_MASTER_URL)
        except Exception:
            return DEFAULT_MASTER_URL

    def uses_master_hosting(self) -> str:
        """Master URL if new galleries should be uploaded to it, else ''.
        A custom domain together with a Cloudflare tunnel token is a tunnel to this PC, not the PHP host."""
        base = self.get_master_url()
        if not base:
            return ""
        if self.check(base)["is_master"]:
            return base
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT value FROM app_settings WHERE key = 'cloudflare_tunnel_token'")
            row = cur.fetchone()
            conn.close()
            has_token = bool(row and (row["value"] or "").strip())
        except Exception:
            has_token = False
        # Without a tunnel token the domain can only be the Master Hosting; keep it so the error is shown
        return "" if has_token else base

    def check(self, url: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
        """Pings <url>/index.php?action=ping. is_master=True only for the Ai PhotoFlow Master Hosting script."""
        base = normalize_master_url(url if url is not None else self.get_master_url())
        if not base:
            return {"configured": False, "is_master": False, "url": "", "error": None}
        cached = self._ping_cache.get(base)
        if use_cache and cached and time.time() - cached[0] < (300 if cached[1]["is_master"] else 20):
            return cached[1]
        res: Dict[str, Any] = {"configured": True, "is_master": False, "url": base, "error": None}
        try:
            status, body = _request(_api(base, "ping"), timeout=12)
            data = _json(body)
            if status == 200 and "Master Hosting" in str(data.get("server", "")):
                res["is_master"] = True
                res["version"] = data.get("version")
            elif status == 404:
                res["error"] = f"index.php not found at {base}/ (HTTP 404). Check the folder name in the URL."
            else:
                res["error"] = f"{base}/index.php did not answer as Ai PhotoFlow Master Hosting (HTTP {status})."
        except RuntimeError as e:
            res["error"] = str(e)
        self._ping_cache[base] = (time.time(), res)
        return res

    # ---------------- DB helpers ----------------
    @staticmethod
    def _set_status(gallery_uuid: str, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"UPDATE client_galleries SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE gallery_uuid = ?",
                    list(fields.values()) + [gallery_uuid])
        conn.commit()
        conn.close()

    def _lock_for(self, gallery_uuid: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(gallery_uuid, threading.Lock())

    def mark_pending(self, gallery_uuid: str, base: str):
        self._set_status(gallery_uuid, hosting_url=base, hosting_status="PENDING", hosting_error="",
                         hosting_uploaded=0)

    # ---------------- push ----------------
    def sync_gallery(self, gallery_uuid: str, base: Optional[str] = None,
                     progress: Optional[Callable[[int, int, str], None]] = None) -> Dict[str, Any]:
        """Uploads gallery metadata + all previews to the Master Hosting. Safe to call again (re-sync / retry)."""
        from backend.services.proofing_service import proofing_service, PROOFING_CACHE_DIR

        base = normalize_master_url(base or self.get_master_url())
        lock = self._lock_for(gallery_uuid)
        if not lock.acquire(blocking=False):
            return {"success": False, "error": "Upload already running for this gallery"}
        try:
            if not base:
                raise RuntimeError("Master Hosting URL is not set.")
            chk = self.check(base, use_cache=False)
            if not chk["is_master"]:
                raise RuntimeError(chk.get("error") or "Master Hosting not reachable.")

            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM client_galleries WHERE gallery_uuid = ?", (gallery_uuid,))
            g = cur.fetchone()
            if not g:
                conn.close()
                raise RuntimeError("Gallery not found.")
            g = dict(g)
            cur.execute("""
                SELECT p.id, p.filename FROM client_gallery_photos gp JOIN photos p ON p.id = gp.photo_id
                WHERE gp.gallery_uuid = ? ORDER BY gp.photo_id ASC
            """, (gallery_uuid,))
            photos = [dict(r) for r in cur.fetchall()]
            conn.close()

            total = len(photos)
            self._set_status(gallery_uuid, hosting_url=base, hosting_status="UPLOADING", hosting_error="",
                             hosting_uploaded=0)

            payload = {
                "gallery_uuid": gallery_uuid,
                "title": g.get("title") or "Photo Selection",
                "client_name": g.get("client_name") or "",
                "client_pin": (g.get("client_pin") or "").strip(),
                # Watermark is already burnt into every preview; avoid a second CSS overlay on the host
                "watermark_enabled": False,
                "watermark_text": g.get("watermark_text") or "",
                "created_at": str(g.get("created_at") or ""),
                "photos": [{"id": p["id"], "filename": p["filename"]} for p in photos],
            }
            status, body = _request(_api(base, "sync"), json.dumps(payload).encode("utf-8"),
                                    {"Content-Type": "application/json", **_auth_headers()})
            if status == 401:
                raise RuntimeError("Album server needs an active Ai PhotoFlow license (or trial) on this computer.")
            if status != 200 or not _json(body).get("success"):
                raise RuntimeError(f"Gallery sync rejected by hosting (HTTP {status}): {body[:200]!r}")

            gallery_dir = os.path.join(PROOFING_CACHE_DIR, gallery_uuid)
            done = [0]
            failed: List[str] = []
            done_lock = threading.Lock()

            def upload_one(p):
                err = None
                try:
                    prev = os.path.join(gallery_dir, f"{p['id']}.webp")
                    if not os.path.exists(prev):
                        prev = proofing_service.ensure_single_preview(gallery_uuid, p["id"])
                    jpeg = self._to_jpeg(prev)
                    for attempt in range(3):
                        try:
                            ok = self._upload_preview(base, gallery_uuid, p["id"], jpeg)
                            if ok:
                                err = None
                                break
                            err = "rejected"
                        except RuntimeError as e:
                            err = str(e)
                        time.sleep(1.0 + attempt)
                except Exception as e:
                    err = str(e)
                with done_lock:
                    done[0] += 1
                    if err:
                        failed.append(f"{p['filename']}: {err}")
                    n = done[0]
                if n % 5 == 0 or n == total:
                    self._set_status(gallery_uuid, hosting_uploaded=n - len(failed))
                if progress:
                    progress(n, total, p["filename"])

            with ThreadPoolExecutor(max_workers=4) as ex:
                list(ex.map(upload_one, photos))

            if failed:
                raise RuntimeError(f"{len(failed)} of {total} photos failed to upload. First error: {failed[0]}")

            # Verify the public page really opens on the domain
            status, body = _request(gallery_public_url(base, gallery_uuid, payload["client_pin"]), timeout=20)
            if status != 200 or b"Gallery Not Found" in body:
                raise RuntimeError(f"Uploaded, but the gallery page does not open on the domain (HTTP {status}). "
                                   "Check that the hosting folder is writable (data/ folder).")

            self._set_status(gallery_uuid, hosting_status="ONLINE", hosting_error="", hosting_uploaded=total)
            return {"success": True, "url": gallery_public_url(base, gallery_uuid), "uploaded": total}
        except Exception as e:
            self._set_status(gallery_uuid, hosting_url=base, hosting_status="FAILED", hosting_error=str(e)[:500])
            return {"success": False, "error": str(e)}
        finally:
            lock.release()

    def sync_gallery_async(self, gallery_uuid: str) -> None:
        threading.Thread(target=self.sync_gallery, args=(gallery_uuid,), daemon=True).start()

    @staticmethod
    def _to_jpeg(path: Optional[str]) -> bytes:
        # The PHP host stores previews as <id>.jpg, so send real JPEG data
        if not path or not os.path.exists(path):
            raise RuntimeError("preview missing")
        with Image.open(path) as im:
            im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=84, optimize=True, progressive=True)
            return buf.getvalue()

    @staticmethod
    def _upload_preview(base: str, gallery_uuid: str, photo_id: int, jpeg: bytes) -> bool:
        boundary = "----AiPhotoFlow" + uuid_mod.uuid4().hex
        parts = []
        for name, value in (("gallery_uuid", gallery_uuid), ("photo_id", str(photo_id))):
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"preview\"; filename=\"{photo_id}.jpg\"\r\n"
            f"Content-Type: image/jpeg\r\n\r\n".encode() + jpeg + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        status, body = _request(_api(base, "upload_preview"), b"".join(parts),
                                {"Content-Type": f"multipart/form-data; boundary={boundary}", **_auth_headers()}, timeout=60)
        if status == 413:
            raise RuntimeError("hosting upload size limit too small (HTTP 413)")
        return status == 200 and bool(_json(body).get("success"))

    # ---------------- pull selections ----------------
    def pull_selections(self, gallery_uuid: str) -> Dict[str, Any]:
        """Copies the client's selections from the hosting into the local DB (used by app + export)."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT hosting_url, hosting_status FROM client_galleries WHERE gallery_uuid = ?", (gallery_uuid,))
        row = cur.fetchone()
        conn.close()
        if not row or not row["hosting_url"] or row["hosting_status"] not in ("ONLINE", "EXPIRED"):
            return {"pulled": False}
        base = row["hosting_url"]
        try:
            status, body = _request(_api(base, "get_selections", {"id": gallery_uuid}), headers=_auth_headers(), timeout=8)
        except RuntimeError as e:
            return {"pulled": False, "error": str(e)}
        data = _json(body)
        if status != 200 or not isinstance(data, dict):
            return {"pulled": False, "error": f"HTTP {status}"}

        items = data.get("items") or {}
        if not isinstance(items, dict):
            items = {}
        conn = get_connection()
        cur = conn.cursor()
        for pid, it in items.items():
            try:
                photo_id = int(pid)
            except (TypeError, ValueError):
                continue
            sel = str((it or {}).get("status", "UNRATED")).upper()
            if sel not in ("SELECTED", "REJECTED", "UNRATED"):
                sel = "UNRATED"
            note = str((it or {}).get("note", "") or "")
            cur.execute("""UPDATE client_gallery_photos SET client_selection = ?, client_note = ?
                           WHERE gallery_uuid = ? AND photo_id = ?""", (sel, note, gallery_uuid, photo_id))
            if cur.rowcount:
                cur.execute("UPDATE photos SET client_selection = ?, client_note = ? WHERE id = ?",
                            (sel, note, photo_id))
        cur.execute("""SELECT COUNT(*) AS n FROM client_gallery_photos
                       WHERE gallery_uuid = ? AND client_selection = 'SELECTED'""", (gallery_uuid,))
        n = cur.fetchone()["n"]
        if data.get("expired"):
            # Hosting auto-cleaned the photos (7 days after submit); the selection itself is kept
            cur.execute("UPDATE client_galleries SET hosting_status = 'EXPIRED' WHERE gallery_uuid = ?", (gallery_uuid,))
        if str(data.get("status", "")).upper() == "SUBMITTED":
            cur.execute("""UPDATE client_galleries SET selected_count = ?, status = 'SUBMITTED',
                           submitted_at = COALESCE(submitted_at, CURRENT_TIMESTAMP) WHERE gallery_uuid = ?""",
                        (n, gallery_uuid))
        else:
            cur.execute("UPDATE client_galleries SET selected_count = ? WHERE gallery_uuid = ?", (n, gallery_uuid))
        conn.commit()
        conn.close()
        return {"pulled": True, "selected_count": n}


hosting_sync_service = HostingSyncService()
