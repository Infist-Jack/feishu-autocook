#!/bin/sh
# 渲染 launchd 模板并加载。用法：watcher/install.sh [--uninstall]
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
PYTHON=$(command -v python3)
PASEO_BIN=$(dirname "$(command -v paseo)")
LARK_BIN=$(dirname "$(command -v lark-cli)")
PATH_VAL="$PASEO_BIN:$LARK_BIN:/usr/local/bin:/usr/bin:/bin"
UID_NUM=$(id -u)
mkdir -p "$REPO/state" "$HOME/Library/LaunchAgents"

for name in ai.autocook.watcher ai.autocook.health; do
  tpl="$REPO/watcher/launchd/$name.plist.tpl"
  out="$REPO/watcher/launchd/$name.rendered.plist"
  dst="$HOME/Library/LaunchAgents/$name.plist"
  launchctl bootout "gui/$UID_NUM/$name" 2>/dev/null || true
  if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$dst" "$out"; echo "removed $name"; continue
  fi
  sed -e "s|__PYTHON__|$PYTHON|g" -e "s|__REPO__|$REPO|g" -e "s|__PATH__|$PATH_VAL|g" -e "s|__HOME__|$HOME|g" "$tpl" > "$out"
  cp "$out" "$dst"
  launchctl bootstrap "gui/$UID_NUM" "$dst"
  echo "loaded $name"
done
[ "${1:-}" = "--uninstall" ] || launchctl print "gui/$UID_NUM/ai.autocook.watcher" | grep -E "state|last exit" | head -3
