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

echo "== 4/6 Windows build (same backend code, compiled to Python 3.10 bytecode without source, then NSIS installer)"
venv/bin/python scripts/build_win_backend.py
npx electron-builder --win nsis --x64

echo "== 5/6 Verify"
hdiutil verify dist-dmg/*.dmg | tail -1
WINB=dist-dmg/win-unpacked/resources/photoflow-backend-win/backend
[ -z "$(find "$WINB" -name '*.py')" ] || { echo "Windows backend contains source files"; exit 1; }
diff <(cd backend && find . -name '*.py' ! -path '*/.photoflow_cache/*' | sed 's/\.py$//' | sort) \
     <(cd "$WINB" && find . -name '*.pyc' | sed 's/\.pyc$//' | sort) && echo "Windows backend == source (compiled, no source)"

echo "== 6/6 Server zips"
venv/bin/python scripts/build_server_bundles.py

ls -la dist-dmg/*.dmg dist-dmg/*.exe
