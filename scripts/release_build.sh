#!/bin/bash
# Full release build on the Mac: tests -> Mac DMG -> Windows installer -> server zips.
#   bash scripts/release_build.sh
# Outputs: dist-dmg/Ai PhotoFlow-<version>-arm64.dmg, dist-dmg/Ai PhotoFlow Setup <version>.exe, dist-server/*.zip
set -e
cd "$(dirname "$0")/.."

echo "== 1/6 Unit tests"
for t in tests/test_*.py; do venv/bin/python -m unittest "$t"; done

echo "== 2/6 TypeScript check"
(cd frontend && npx tsc -p tsconfig.app.json --noEmit)

echo "== 3/6 Mac build (frontend + PyInstaller backend + DMG)"
npm run build:dmg

echo "== 4/6 Windows build (same backend code into the embedded-Python bundle, then NSIS installer)"
rsync -a --delete --exclude "__pycache__" --exclude "*.pyc" --exclude "photoflow.db" --exclude ".photoflow_cache" \
      backend/ dist-backend-win/backend/
npx electron-builder --win nsis --x64

echo "== 5/6 Verify"
hdiutil verify dist-dmg/*.dmg | tail -1
diff -rq --exclude=__pycache__ --exclude="*.pyc" --exclude=photoflow.db --exclude=.photoflow_cache \
     backend dist-dmg/win-unpacked/resources/photoflow-backend-win/backend && echo "Windows backend == source"

echo "== 6/6 Server zips"
venv/bin/python scripts/build_server_bundles.py

ls -la dist-dmg/*.dmg dist-dmg/*.exe
