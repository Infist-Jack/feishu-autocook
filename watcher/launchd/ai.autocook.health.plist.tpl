<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>ai.autocook.health</string>
  <key>ProgramArguments</key>
  <array>
    <string>__PYTHON__</string>
    <string>__REPO__/watcher/watcher.py</string>
    <string>health</string>
  </array>
  <key>WorkingDirectory</key><string>__REPO__</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>__PATH__</string>
    <key>HOME</key><string>__HOME__</string>
    <key>LANG</key><string>en_US.UTF-8</string>
  </dict>
  <key>StartInterval</key><integer>900</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>__REPO__/state/launchd-health.log</string>
  <key>StandardErrorPath</key><string>__REPO__/state/launchd-health.log</string>
</dict>
</plist>
