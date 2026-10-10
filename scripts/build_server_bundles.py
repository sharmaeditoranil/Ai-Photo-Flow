"""
Builds every server upload for license.aiphotoflow.in in one go.

    venv/bin/python scripts/build_server_bundles.py

Creates in dist-server/ (git-ignored, contains the PRIVATE signing key except the album zip):
  AiPhotoFlow_License_Server.zip              license server only           (has private key)
  LICENSE_AND_ALBUM_license.aiphotoflow.in.zip  license server + album/ folder (has private key) - fresh install
  ALBUM_ONLY_license.aiphotoflow.in.zip       album/ folder only            (no secrets)     - album updates

Upload: extract in the license.aiphotoflow.in folder (overwrite). The data folder apf_license_data lives
outside public_html, so re-uploading never touches licenses, payments or the admin account.
"""
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist-server")
ALBUM_FILES = [("master_hosting/index.php", "album/index.php"), ("master_hosting/.htaccess", "album/.htaccess")]


def main() -> None:
    # 1. License server zip (config.php is generated from ~/AiPhotoFlow_Private/license_keys.json)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_license_server.py")], check=True)
    lic_zip = os.path.join(DIST, "AiPhotoFlow_License_Server.zip")

    # 2. License + album (fresh install of the subdomain)
    combined = os.path.join(DIST, "LICENSE_AND_ALBUM_license.aiphotoflow.in.zip")
    with zipfile.ZipFile(lic_zip) as zi, zipfile.ZipFile(combined, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            zo.writestr(item, zi.read(item.filename))
        for src, dst in ALBUM_FILES:
            zo.write(os.path.join(ROOT, src), dst)

    # 3. Album only (safe to share with a helper: no keys inside)
    album_only = os.path.join(DIST, "ALBUM_ONLY_license.aiphotoflow.in.zip")
    with zipfile.ZipFile(album_only, "w", zipfile.ZIP_DEFLATED) as zo:
        for src, dst in ALBUM_FILES:
            zo.write(os.path.join(ROOT, src), dst)

    # 4. Legacy single-file album zip kept in the repo (index.php + .htaccess)
    legacy = os.path.join(ROOT, "master_hosting", "AiPhotoFlow_Master_Hosting.zip")
    with zipfile.ZipFile(legacy, "w", zipfile.ZIP_DEFLATED) as zo:
        for src, _ in ALBUM_FILES:
            zo.write(os.path.join(ROOT, src), os.path.basename(src))

    for path in (lic_zip, combined, album_only, legacy):
        print(f"  {os.path.relpath(path, ROOT):60s} {os.path.getsize(path) // 1024:>6} KB")


if __name__ == "__main__":
    main()
