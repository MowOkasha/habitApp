#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="/usr/local/bin/python3.13"
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import _tkinter
PY
then
  echo "Selected Python interpreter does not provide _tkinter: $PYTHON_BIN"
  echo "Set PYTHON_BIN to a tkinter-capable interpreter and rerun."
  exit 1
fi

echo "Generating app icon..."
"$PYTHON_BIN" scripts/generate_app_icon.py

echo "Checking py2app..."
if ! "$PYTHON_BIN" -m py2app --version >/dev/null 2>&1; then
  if "$PYTHON_BIN" -m pip help install | grep -q -- "--break-system-packages"; then
    "$PYTHON_BIN" -m pip install --user --break-system-packages py2app
  else
    "$PYTHON_BIN" -m pip install --user py2app
  fi
fi

echo "Building app bundle..."
rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist"
"$PYTHON_BIN" setup.py py2app

APP_SRC=""
if [ -d "$ROOT_DIR/dist/Habit Pulse.app" ]; then
  APP_SRC="$ROOT_DIR/dist/Habit Pulse.app"
elif [ -d "$ROOT_DIR/dist/main.app" ]; then
  APP_SRC="$ROOT_DIR/dist/main.app"
fi

if [ -z "$APP_SRC" ] || [ ! -d "$APP_SRC" ]; then
  echo "Build failed: app bundle not found."
  exit 1
fi

APP_DST="/Applications/Habit Pulse.app"
rm -rf "$APP_DST" || true

if cp -R "$APP_SRC" "$APP_DST"; then
  echo "Installed to $APP_DST"
else
  echo "Could not write to /Applications; installing to user Applications folder instead."
  USER_APP_DIR="$HOME/Applications"
  mkdir -p "$USER_APP_DIR"
  APP_DST="$USER_APP_DIR/Habit Pulse.app"
  rm -rf "$APP_DST" || true
  cp -R "$APP_SRC" "$APP_DST"
  echo "Installed to $APP_DST"
fi
