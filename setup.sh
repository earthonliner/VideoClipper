#!/usr/bin/env bash
# One-shot setup for macOS (Apple Silicon recommended). Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

if [[ "$(uname)" == "Darwin" ]]; then
  if ! command -v brew >/dev/null; then
    echo "Homebrew not found. Install it first: https://brew.sh" >&2
    exit 1
  fi
  brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
  brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
  PY="$(brew --prefix python@3.12)/bin/python3.12"
else
  PY="${PY:-python3}"
fi

[[ -d .venv ]] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
if [[ "$(uname -m)" == "arm64" && "$(uname)" == "Darwin" ]]; then
  .venv/bin/pip install -q -e ".[mac]"
else
  .venv/bin/pip install -q -e .
fi

mkdir -p projects data .secrets music
chmod 700 .secrets
[[ -f .env ]] || cp .env.example .env
[[ -f music/library.json ]] || echo "[]" > music/library.json

if [[ "$(uname)" == "Darwin" ]]; then
  PLIST=~/Library/LaunchAgents/com.videostudio.analytics.plist
  sed "s#__ROOT__#${ROOT}#g" launchd/com.videostudio.analytics.plist > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "Daily analytics sync scheduled (09:00) via launchd."
fi

echo
.venv/bin/studio doctor
cat <<'EOF'

Next steps:
  1. Fill PEXELS_API_KEY / PIXABAY_API_KEY in .env
  2. Put your Google OAuth desktop client JSON at .secrets/client_secret.json, then run:
       .venv/bin/studio auth
  3. Drop some royalty-free music into music/
  4. Open this folder in Cursor -> Settings -> MCP: enable "video-studio"
EOF
