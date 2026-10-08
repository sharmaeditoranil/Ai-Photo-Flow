"""
Tunnel Service for Ai PhotoFlow
Provides instant public HTTPS URLs (via Cloudflare Quick Tunnel) and LAN IP detection
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
            os.path.join(base_dir, "build", "cloudflared-darwin-arm64"),
            os.path.join(base_dir, "photoflow-backend", "cloudflared"),
            os.path.join(getattr(sys, "_MEIPASS", ""), "cloudflared"),
            "/tmp/cloudflared",
        ]

        for c in candidates:
            if c and os.path.isfile(c) and os.access(c, os.X_OK if sys.platform != "win32" else os.R_OK):
                return c

        return None

    def start_tunnel(self, port: int = 8000, timeout: int = 25) -> Dict[str, Any]:
        """Starts cloudflared quick tunnel and captures public HTTPS URL."""
        if self.status == "ONLINE" and self.active_url:
            return {
                "success": True,
                "url": self.active_url,
                "status": self.status,
                "local_ip": self.get_local_ip()
            }

        bin_path = self.find_cloudflared_binary()
        if not bin_path:
            # Fallback check for npx localtunnel
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

        # Read output in thread until trycloudflare.com URL is found
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

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

        if url_found.wait(timeout=timeout):
            return {
                "success": True,
                "url": self.active_url,
                "status": "ONLINE",
                "local_ip": self.get_local_ip()
            }
        else:
            self.status = "ERROR"
            self.error_message = "Tunnel initialization timed out. Please check your internet connection."
            return {
                "success": False,
                "error": self.error_message,
                "local_ip": self.get_local_ip()
            }

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

        t = threading.Thread(target=_lt_reader, daemon=True)
        t.start()

        if url_found.wait(timeout=timeout):
            return {"success": True, "url": self.active_url, "status": "ONLINE", "local_ip": self.get_local_ip()}
        else:
            self.status = "ERROR"
            return {"success": False, "error": "Localtunnel timeout", "local_ip": self.get_local_ip()}

    def stop_tunnel(self):
        """Stops active tunnel."""
        if self.tunnel_process:
            try:
                self.tunnel_process.terminate()
            except Exception:
                pass
            self.tunnel_process = None
        self.active_url = None
        self.status = "OFFLINE"

    def get_info(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "url": self.active_url,
            "local_ip": self.get_local_ip(),
            "port": 8000,
            "error": self.error_message
        }

tunnel_service = TunnelManager()
