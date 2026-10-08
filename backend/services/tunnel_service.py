"""
Tunnel Service for Ai PhotoFlow
Provides instant public HTTPS URLs (via Custom Domains, Cloudflare Named Tunnels, or Quick Tunnels) and LAN IP detection
so mobile phones anywhere in the world (or on local Wi-Fi) can open client photo selection galleries.
"""
import os
import sys
import re
import socket
import shutil
import subprocess
import threading
import time
from typing import Optional, Dict, Any

class TunnelManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TunnelManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.tunnel_process: Optional[subprocess.Popen] = None
        self.active_url: Optional[str] = None
        self.status: str = "OFFLINE" # "OFFLINE", "STARTING", "ONLINE", "ERROR"
        self.error_message: Optional[str] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._should_stay_alive: bool = False

    def get_local_ip(self) -> str:
        """Finds computer's primary LAN IP address (e.g. 192.168.1.15)."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 1))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
        finally:
            s.close()

    def get_domain_settings(self) -> Dict[str, str]:
        """Fetches custom domain and Cloudflare token configured by user."""
        try:
            from backend.db.database import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM app_settings WHERE key IN ('custom_domain_url', 'cloudflare_tunnel_token')")
            rows = cursor.fetchall()
            conn.close()
            return {r["key"]: (r["value"] or "").strip() for r in rows}
        except Exception:
            return {}

    def find_cloudflared_binary(self) -> Optional[str]:
        """Finds bundled or system cloudflared executable."""
        which_cf = shutil.which("cloudflared")
        if which_cf:
            return which_cf

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        exe_name = "cloudflared.exe" if sys.platform == "win32" else "cloudflared"

        candidates = [
            os.path.join(base_dir, exe_name),
            os.path.join(base_dir, "dist-backend-win", "cloudflared.exe"),
            os.path.join(sys.prefix, "..", exe_name),
            os.path.join(sys.prefix, exe_name),
            os.path.join(base_dir, "build", "cloudflared-darwin-arm64"),
            os.path.join(base_dir, "photoflow-backend", "cloudflared"),
            os.path.join(getattr(sys, "_MEIPASS", ""), "cloudflared"),
            "/tmp/cloudflared",
        ]

        for c in candidates:
            if c and os.path.isfile(c) and os.access(c, os.X_OK if sys.platform != "win32" else os.R_OK):
                return c

        return None

    def _is_process_running(self) -> bool:
        return self.tunnel_process is not None and self.tunnel_process.poll() is None

    def start_tunnel(self, port: int = int(os.environ.get("PORT", 8000)), timeout: int = 25) -> Dict[str, Any]:
        """
        Starts public tunnel or connects to Custom Domain / Cloudflare Named Tunnel.
        Prevents Error 1033 with keep-alive watchdog and dead URL invalidation.
        """
        domain_cfg = self.get_domain_settings()
        custom_domain = domain_cfg.get("custom_domain_url", "")
        cf_token = domain_cfg.get("cloudflare_tunnel_token", "")

        # 1. Custom Domain with Cloudflare Tunnel Token (Permanent & Enterprise Speed)
        if custom_domain and cf_token:
            if not custom_domain.startswith("http://") and not custom_domain.startswith("https://"):
                custom_domain = f"https://{custom_domain}"
            custom_domain = custom_domain.rstrip("/")

            bin_path = self.find_cloudflared_binary()
            if bin_path:
                self.stop_tunnel()
                self.status = "STARTING"
                cmd = [bin_path, "tunnel", "run", "--token", cf_token]
                try:
                    self.tunnel_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    self.active_url = custom_domain
                    self.status = "ONLINE"
                    self._should_stay_alive = True
                    self._start_watchdog(port)
                    return {
                        "success": True,
                        "url": self.active_url,
                        "status": "ONLINE",
                        "is_custom_domain": True,
                        "local_ip": self.get_local_ip()
                    }
                except Exception as e:
                    self.error_message = str(e)

        # 2. Custom Domain without token (e.g. Reverse Proxy / VPS / cPanel Port Forward)
        if custom_domain:
            if not custom_domain.startswith("http://") and not custom_domain.startswith("https://"):
                custom_domain = f"https://{custom_domain}"
            custom_domain = custom_domain.rstrip("/")
            self.active_url = custom_domain
            self.status = "ONLINE"
            return {
                "success": True,
                "url": self.active_url,
                "status": "ONLINE",
                "is_custom_domain": True,
                "local_ip": self.get_local_ip()
            }

        # 3. Cloudflare Quick Tunnel (with Auto-Watchdog against Error 1033)
        if self._is_process_running() and self.active_url and self.status == "ONLINE":
            return {
                "success": True,
                "url": self.active_url,
                "status": self.status,
                "is_custom_domain": False,
                "local_ip": self.get_local_ip()
            }

        self.stop_tunnel()
        bin_path = self.find_cloudflared_binary()
        if not bin_path:
            return self._start_localtunnel_fallback(port, timeout)

        self.status = "STARTING"
        self.error_message = None
        cmd = [bin_path, "tunnel", "--url", f"http://127.0.0.1:{port}"]

        try:
            self.tunnel_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except Exception as e:
            self.status = "ERROR"
            self.error_message = str(e)
            return {"success": False, "error": str(e), "local_ip": self.get_local_ip()}

        url_found = threading.Event()

        def _reader():
            pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
            while self.tunnel_process and self.tunnel_process.poll() is None:
                line = self.tunnel_process.stdout.readline()
                if not line:
                    break
                match = pattern.search(line)
                if match:
                    self.active_url = match.group(0)
                    self.status = "ONLINE"
                    url_found.set()

            # If loop exited because process died
            if not self._is_process_running() and not self.get_domain_settings().get("custom_domain_url"):
                self.status = "OFFLINE"
                self.active_url = None

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

        if url_found.wait(timeout=timeout):
            self._should_stay_alive = True
            self._start_watchdog(port)
            return {
                "success": True,
                "url": self.active_url,
                "status": "ONLINE",
                "is_custom_domain": False,
                "local_ip": self.get_local_ip()
            }
        else:
            self.status = "ERROR"
            self.error_message = "Tunnel connection timed out. Please check your internet or retry."
            return {
                "success": False,
                "error": self.error_message,
                "local_ip": self.get_local_ip()
            }

    def _start_watchdog(self, port: int):
        """Monitors tunnel health and auto-reconnects if disconnected."""
        def _watch():
            while self._should_stay_alive:
                time.sleep(5)
                if self._should_stay_alive and not self._is_process_running():
                    domain_cfg = self.get_domain_settings()
                    if not domain_cfg.get("custom_domain_url"):
                        # Reconnect quick tunnel
                        self.start_tunnel(port)

        if not self._watchdog_thread or not self._watchdog_thread.is_alive():
            self._watchdog_thread = threading.Thread(target=_watch, daemon=True)
            self._watchdog_thread.start()

    def _start_localtunnel_fallback(self, port: int, timeout: int) -> Dict[str, Any]:
        """Fallback to npx localtunnel if cloudflared binary is missing."""
        npx_bin = shutil.which("npx")
        if not npx_bin:
            self.status = "ERROR"
            self.error_message = "No tunnel binary available."
            return {"success": False, "error": self.error_message, "local_ip": self.get_local_ip()}

        self.status = "STARTING"
        cmd = [npx_bin, "--yes", "localtunnel", "--port", str(port)]
        try:
            self.tunnel_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except Exception as e:
            self.status = "ERROR"
            return {"success": False, "error": str(e), "local_ip": self.get_local_ip()}

        url_found = threading.Event()
        def _lt_reader():
            pattern = re.compile(r"https://[a-zA-Z0-9-]+\.loca\.lt")
            while self.tunnel_process and self.tunnel_process.poll() is None:
                line = self.tunnel_process.stdout.readline()
                if not line:
                    break
                match = pattern.search(line)
                if match:
                    self.active_url = match.group(0)
                    self.status = "ONLINE"
                    url_found.set()

            if not self._is_process_running():
                self.status = "OFFLINE"
                self.active_url = None

        t = threading.Thread(target=_lt_reader, daemon=True)
        t.start()

        if url_found.wait(timeout=timeout):
            return {"success": True, "url": self.active_url, "status": "ONLINE", "local_ip": self.get_local_ip()}
        else:
            self.status = "ERROR"
            return {"success": False, "error": "Localtunnel timeout", "local_ip": self.get_local_ip()}

    def stop_tunnel(self):
        """Stops active tunnel and watchdog."""
        self._should_stay_alive = False
        if self.tunnel_process:
            try:
                self.tunnel_process.terminate()
                self.tunnel_process.kill()
            except Exception:
                pass
            self.tunnel_process = None
        self.active_url = None
        self.status = "OFFLINE"

    def get_info(self) -> Dict[str, Any]:
        """Returns verified real-time tunnel state."""
        domain_cfg = self.get_domain_settings()
        custom_domain = domain_cfg.get("custom_domain_url", "")
        cf_token = domain_cfg.get("cloudflare_tunnel_token", "")

        # Check if process died
        if not custom_domain and self.tunnel_process and not self._is_process_running():
            self.status = "OFFLINE"
            self.active_url = None

        effective_url = self.active_url
        if custom_domain and not effective_url:
            effective_url = custom_domain

        return {
            "status": self.status if (self._is_process_running() or custom_domain) else "OFFLINE",
            "url": effective_url,
            "local_ip": self.get_local_ip(),
            "port": int(os.environ.get("PORT", 8000)),
            "custom_domain_url": custom_domain,
            "has_cloudflare_token": bool(cf_token),
            "is_custom_domain": bool(custom_domain),
            "error": self.error_message
        }

tunnel_service = TunnelManager()
