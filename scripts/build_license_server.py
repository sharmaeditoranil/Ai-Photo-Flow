"""
Builds dist-server/AiPhotoFlow_License_Server.zip for upload to public_html/license/.
The Ed25519 private key and setup code are read from ~/AiPhotoFlow_Private/license_keys.json
and written only into the zip's config.php (never into the git repository).
"""
import json
import os
import shutil
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "license_server")
OUT_DIR = os.path.join(ROOT, "dist-server")
KEYS = os.path.expanduser("~/AiPhotoFlow_Private/license_keys.json")


def main():
    keys = json.load(open(KEYS))
    stage = os.path.join(OUT_DIR, "license")
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(SRC, stage, ignore=shutil.ignore_patterns("config.php", "config.sample.php", ".DS_Store", "SETUP_GUIDE.md"))
    cfg = open(os.path.join(SRC, "config.sample.php")).read()
    cfg = (cfg.replace("__PUBLIC_KEY__", keys["public_key"])
              .replace("__SECRET_KEY__", keys["secret_key"])
              .replace("__SETUP_CODE__", keys["setup_code"]))
    with open(os.path.join(stage, "config.php"), "w") as f:
        f.write(cfg)
    zpath = os.path.join(OUT_DIR, "AiPhotoFlow_License_Server.zip")
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(stage):
            for fn in files:
                full = os.path.join(base, fn)
                z.write(full, os.path.relpath(full, stage))
    print(zpath)


if __name__ == "__main__":
    main()
