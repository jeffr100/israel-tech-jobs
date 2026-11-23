#!/bin/bash
# Opens the job site on this computer at http://localhost:8000
# macOS: double-click this file (or run: bash start_site.command). Linux: bash start_site.command
# Stop the site with Control-C, or by closing this window.
cd "$(dirname "$0")" || exit 1

PORT=8000
# Use the next free port if 8000 is taken (macOS-safe: no GNU-only tools).
while lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; do
  PORT=$((PORT + 1))
done

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python 3 is needed. On a Mac, run: xcode-select --install"
  exit 1
fi

if [ ! -f data/site.json ]; then
  echo "data/site.json is missing. Run: $PY crawler/crawl.py"
  exit 1
fi

URL="http://localhost:$PORT/"
echo "Job site running at $URL  (press Control-C to stop)"
( sleep 1
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1
  fi ) &
exec "$PY" -m http.server "$PORT" --bind 127.0.0.1
