#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

cd "$ROOT_DIR"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install -r requirements.txt pyinstaller
"$VENV_DIR/bin/python" -m PyInstaller --noconfirm --clean work_tracker.spec

echo "macOS app bundle ready in: $ROOT_DIR/dist/WorkTracker.app"
