"""
Standalone executable entrypoint for Ai PhotoFlow Backend.
Supports macOS compiled binary and Windows standalone runtime with OpenCV, NumPy, and FastAPI.
"""
import os
import sys
import multiprocessing

base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# Ensure Windows standalone python finds Lib/site-packages and all DLLs
if sys.platform == "win32":
    site_packages = os.path.join(base_dir, "python", "Lib", "site-packages")
    if os.path.isdir(site_packages) and site_packages not in sys.path:
        sys.path.insert(0, site_packages)

    numpy_libs = os.path.join(site_packages, "numpy.libs")
    py_dir = os.path.join(base_dir, "python")
    cv2_dir = os.path.join(site_packages, "cv2")
    rawpy_dir = os.path.join(site_packages, "rawpy")

    for d in [numpy_libs, py_dir, site_packages, cv2_dir, rawpy_dir]:
        if d and os.path.isdir(d):
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")

# Persistent logging in case of startup error
def log_startup_error(err_str: str):
    try:
        user_home = os.environ.get("USERPROFILE") or os.path.expanduser("~") or "."
        log_dir = os.path.join(user_home, ".photoflow")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "backend_crash.log"), "a", encoding="utf-8") as f:
            f.write(f"\n[Crash] {err_str}\n")
    except Exception:
        pass

try:
    import uvicorn
    from backend.main import app
except Exception as e:
    import traceback
    err_msg = traceback.format_exc()
    log_startup_error(err_msg)
    print(f"CRITICAL ERROR STARTING BACKEND:\n{err_msg}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    port = int(os.environ.get("PORT", 8000))
    print(f"Ai PhotoFlow Backend running on 0.0.0.0:{port}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        log_startup_error(err_msg)
        print(f"Error during uvicorn run: {err_msg}", file=sys.stderr)
        sys.exit(1)
