#!/bin/bash
# Build Funis.app, a .pkg installer and a .dmg disk image on macOS.
#
# Usage: packaging/build_macos.sh [path/to/python]
# The interpreter defaults to .venv/bin/python when it exists, otherwise python3.
# Output in dist/: Funis.app, Funis-<version>-macOS-<arch>.pkg and .dmg (arch: arm64 or x86_64).
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${1:-}"
if [ -z "$PY" ]; then
  if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
fi
echo "Using $($PY --version) at $PY"
"$PY" -m pip install --quiet --upgrade -r requirements.txt pyinstaller
VERSION=$("$PY" -c "import funis; print(funis.__version__)")

"$PY" packaging/make_icon.py
rm -rf build dist
"$PY" -m PyInstaller --noconfirm --clean --log-level WARN packaging/funis.spec

APP=dist/Funis.app
test -d "$APP"
# the one-folder collection is not needed next to the bundle
rm -rf dist/Funis

# the packaged program must start and solve every example
QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/Funis" --selftest build/selftest.png

if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  codesign --deep --force --options runtime --sign "$CODESIGN_IDENTITY" "$APP"
else
  codesign --deep --force --sign - "$APP"
fi

COMPONENT=dist/Funis-component.pkg
ARCH=$(uname -m)
PKG="dist/Funis-${VERSION}-macOS-${ARCH}.pkg"
pkgbuild --component "$APP" --install-location /Applications \
  --identifier org.funis.app --version "$VERSION" "$COMPONENT"
sed "s/@VERSION@/$VERSION/g" packaging/macos/distribution.xml > dist/distribution.xml
productbuild --distribution dist/distribution.xml --package-path dist \
  --resources packaging/macos "$PKG"
rm -f "$COMPONENT" dist/distribution.xml

DMG="dist/Funis-${VERSION}-macOS-${ARCH}.dmg"
STAGE=dist/dmg
rm -rf "$STAGE" && mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
# hdiutil now and then fails with "Resource busy" on build servers: try again
for attempt in 1 2 3 4 5; do
  if hdiutil create -volname "Funis" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null; then break; fi
  if [ "$attempt" -eq 5 ]; then echo "hdiutil could not create $DMG" >&2; exit 1; fi
  sleep 10
done
rm -rf "$STAGE"

echo
echo "Built:"
ls -la "$APP/Contents/MacOS/Funis" "$PKG" "$DMG"
