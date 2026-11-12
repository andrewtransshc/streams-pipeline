#!/bin/bash
# One-time setup for the Streams pipeline on macOS (Apple Silicon or Intel).
# Run from the Streams folder:   bash setup-mac.sh            (core: transcription + editing)
#                                bash setup-mac.sh --extras   (also speaker detection + thumbnail cutouts)
set -e
cd "$(dirname "$0")"

echo "== Streams setup (macOS) =="

if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Installing Homebrew (it will ask for your Mac password)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done
fi

if ! command -v ffmpeg >/dev/null 2>&1 && [ ! -x bin/ffmpeg ]; then
  echo "Installing ffmpeg..."
  brew install ffmpeg
fi

PY="$(command -v python3.11 || true)"
if [ -z "$PY" ]; then
  echo "Installing Python 3.11..."
  brew install python@3.11
  PY="$(brew --prefix)/bin/python3.11"
fi

if [ ! -e .venv ]; then
  echo "Creating .venv..."
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt

if [ "$1" = "--extras" ]; then
  [ -e .venv-voice ] || "$PY" -m venv .venv-voice
  .venv-voice/bin/python -m pip install --upgrade pip -q
  .venv-voice/bin/python -m pip install -r requirements-extras.txt
fi

mkdir -p Raw Ouput work
echo
.venv/bin/python check_setup.py
