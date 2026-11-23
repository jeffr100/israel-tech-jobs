#!/bin/bash
# Installs a launchd job that runs the crawler every Monday at 6:17 am (local time).
# Usage: bash mac/install_weekly_job.sh      Remove: launchctl unload ~/Library/LaunchAgents/com.israeltechjobs.crawl.plist
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.israeltechjobs.crawl.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.israeltechjobs.crawl</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$REPO/mac/run_weekly.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>17</integer></dict>
  <key>StandardErrorPath</key><string>$REPO/data/launchd.err</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST" && echo "Installed. The crawler will run every Monday at 6:17 am. Run it now with: bash $REPO/mac/run_weekly.sh"
