"""
Copies backend/ into the Windows bundle (dist-backend-win/backend) as compiled Python 3.10 bytecode only.

    venv/bin/python scripts/build_win_backend.py

The Windows app runs an embedded Python 3.10, so every .py file is compiled with a Python 3.10 and stored
as a sourceless `name.pyc` next to where the .py would be (Python imports these directly). No readable source
code is shipped, so the licence checks cannot simply be edited in a text editor. Other files (templates,
models, data) are copied as they are. A standalone Python 3.10 is downloaded once into .tools/py310.
"""
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "backend")
DST = os.path.join(ROOT, "dist-backend-win", "backend")
TOOLS = os.path.join(ROOT, ".tools")
PY310 = os.path.join(TOOLS, "py310", "python", "bin", "python3.10")
PY310_URL = ("https://github.com/indygreg/python-build-standalone/releases/download/20240107/"
             "cpython-3.10.13+20240107-aarch64-apple-darwin-install_only.tar.gz")
SKIP_DIRS = {"__pycache__", ".photoflow_cache"}
SKIP_FILES = {"photoflow.db", ".DS_Store"}

COMPILER = """
import json, py_compile, sys
for src, dst, shown in json.load(sys.stdin):
    py_compile.compile(src, cfile=dst, dfile=shown, doraise=True)
"""


def ensure_py310() -> str:
    if not os.path.exists(PY310):
        os.makedirs(os.path.join(TOOLS, "py310"), exist_ok=True)
        archive = os.path.join(TOOLS, "py310.tar.gz")
        print("  downloading Python 3.10 (one time)...")
        urllib.request.urlretrieve(PY310_URL, archive)
        with tarfile.open(archive) as tf:
            tf.extractall(os.path.join(TOOLS, "py310"))
        os.remove(archive)
    return PY310


def main() -> None:
    py = ensure_py310()
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    jobs, copied = [], 0
    for folder, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(folder, SRC)
        out_dir = os.path.normpath(os.path.join(DST, rel))
        os.makedirs(out_dir, exist_ok=True)
        for name in files:
            if name in SKIP_FILES or name.endswith((".pyc", ".pyo")) or name.startswith("._"):
                continue
            src = os.path.join(folder, name)
            if name.endswith(".py"):
                shown = os.path.normpath(os.path.join("backend", rel, name)).replace(os.sep, "/")
                jobs.append([src, os.path.join(out_dir, name[:-3] + ".pyc"), shown])
            else:
                shutil.copy2(src, os.path.join(out_dir, name))
                copied += 1
    subprocess.run([py, "-I", "-c", COMPILER], input=json.dumps(jobs).encode(), check=True)
    left = [os.path.join(f, n) for f, _, ns in os.walk(DST) for n in ns if n.endswith(".py")]
    if left:
        sys.exit(f"Source files left in the Windows bundle: {left[:3]}")
    print(f"  Windows backend: {len(jobs)} modules compiled (no source), {copied} data files copied")


if __name__ == "__main__":
    main()
