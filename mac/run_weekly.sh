#!/bin/bash
# Runs the crawler and (optionally) pushes the results to GitHub.
# macOS-safe: bash 3.2, BSD utilities only.
cd "$(dirname "$0")/.." || exit 1
PY=/usr/bin/python3
if [ "${JOBSEARCH_PROVIDER:-}" = "jobspy" ]; then
  # JobSpy needs Python 3.10+; macOS's built-in python3 is 3.9, so use a newer one (e.g. from Homebrew or python.org).
  for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY=$(command -v "$c"); break
    fi
  done
  "$PY" -m pip install --user -q python-jobspy >/dev/null 2>&1
fi
"$PY" crawler/crawl.py > data/last_run.log 2>&1
if [ -d .git ] && git remote get-url origin >/dev/null 2>&1; then
  git add data/ && git commit -q -m "Weekly job crawl $(date +%Y-%m-%d)" && git push -q
fi
