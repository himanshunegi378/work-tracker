#!/usr/bin/env bash
# Build a .deb from the PyInstaller bundle in dist/WorkTracker (run build_linux.sh first).
#   Installs to /opt/work-tracker, with `samta-tracker` and `work-tracker` on PATH via /usr/bin
#   and a desktop-menu entry. Upgrading is just installing a newer .deb over the old one.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE="$ROOT_DIR/dist/WorkTracker"
OUT_DIR="${1:-$ROOT_DIR/dist}"

[[ -x "$BUNDLE/WorkTracker" && -x "$BUNDLE/samta-tracker" ]] || {
  echo "Missing $BUNDLE: run scripts/build_linux.sh first." >&2; exit 1; }

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT_DIR/src/cli/__init__.py")"
ARCH="$(dpkg --print-architecture)"
PKG="work-tracker_${VERSION}_${ARCH}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ROOT="$STAGE/$PKG"

mkdir -p "$ROOT/opt" "$ROOT/usr/bin" "$ROOT/usr/share/applications" "$ROOT/DEBIAN"
cp -a "$BUNDLE" "$ROOT/opt/work-tracker"
ln -s /opt/work-tracker/samta-tracker "$ROOT/usr/bin/samta-tracker"
ln -s /opt/work-tracker/WorkTracker "$ROOT/usr/bin/work-tracker"

cat > "$ROOT/usr/share/applications/work-tracker.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Work Tracker
Comment=Log time to your timesheets
Exec=/opt/work-tracker/WorkTracker
Icon=appointment-soon
Terminal=false
Categories=Office;ProjectManagement;
DESKTOP

# The bundle is only self-contained up to glibc: it needs at least the glibc of the machine that built it
# (PyInstaller copies some system libraries such as GTK/GLib). Find the newest GLIBC_x.y symbol any
# bundled binary uses, and declare it so apt refuses a too-old system instead of failing at launch.
GLIBC_MIN="$(find "$ROOT/opt" -type f \( -name '*.so*' -o -name WorkTracker -o -name samta-tracker \) -print0 \
  | xargs -0 -n 50 objdump -T 2>/dev/null | grep -o 'GLIBC_[0-9][0-9.]*' | sed 's/GLIBC_//' | sort -V | tail -1)"
GLIBC_MIN="${GLIBC_MIN:-2.28}"
echo "Needs glibc >= $GLIBC_MIN"
if [[ -n "${MAX_GLIBC:-}" ]] && [[ "$(printf '%s\n%s\n' "$GLIBC_MIN" "$MAX_GLIBC" | sort -V | tail -1)" != "$MAX_GLIBC" ]]; then
  echo "ERROR: needs glibc $GLIBC_MIN but MAX_GLIBC=$MAX_GLIBC. Build on an older distribution." >&2; exit 1
fi

SIZE_KB="$(du -sk "$ROOT/opt" | cut -f1)"
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: work-tracker
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE_KB
Depends: libc6 (>= $GLIBC_MIN), libegl1, libgl1, libopengl0, libdbus-1-3, libxkbcommon-x11-0, libxcb-cursor0
Recommends: gnome-keyring | kwalletmanager
Maintainer: Work Tracker <noreply@users.noreply.github.com>
Homepage: https://github.com/himanshunegi378/work-tracker
Description: Work Tracker desktop app and samta-tracker command line
 Log time against projects on your Frappe/ERPNext server, from a desktop
 app or from the terminal with the samta-tracker command.
CONTROL

# Files in /opt are owned by root; folders 755, so any user can run the app.
find "$ROOT" -type d -exec chmod 755 {} +
chmod 644 "$ROOT/usr/share/applications/work-tracker.desktop"
mkdir -p "$OUT_DIR"
dpkg-deb --build --root-owner-group -Zxz "$ROOT" "$OUT_DIR/$PKG.deb" >/dev/null
echo "Built $OUT_DIR/$PKG.deb"
