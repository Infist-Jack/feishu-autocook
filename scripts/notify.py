#!/usr/bin/env python3
"""bot 身份私聊 Jack：汇报或告警。告警按 key 冷却（默认一小时一次）。

用法：
  notify.py --text "..."                 普通通知
  notify.py --markdown-file state/report.md
  notify.py --alert auth --text "..."    告警（冷却）
"""
import argparse
import json
import sys

from common import POLICY, STATE, append_jsonl, iso, jack_open_id, lark, load_json, now, parse_iso, save_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--markdown-file")
    ap.add_argument("--alert", help="告警 key；同 key 在冷却期内不重复发")
    a = ap.parse_args()
    if not (a.text or a.markdown_file):
        sys.exit("需要 --text 或 --markdown-file")

    if a.alert:
        alerts = load_json(STATE / "alerts.json", {})
        last = alerts.get(a.alert)
        cool = int(POLICY.get("alert_cooldown_seconds", 3600))
        if last and (now() - parse_iso(last)).total_seconds() < cool:
            print(json.dumps({"ok": True, "suppressed": True, "alert": a.alert}))
            return
        alerts[a.alert] = iso(now())
        save_json(STATE / "alerts.json", alerts)

    me = jack_open_id()
    if a.markdown_file:
        args = ["im", "+messages-send", "--user-id", me, "--markdown", "@" + a.markdown_file]
    else:
        text = ("[autocook 告警 %s] " % a.alert if a.alert else "") + a.text
        args = ["im", "+messages-send", "--user-id", me, "--text", text]
    res = lark(args, as_="bot")
    append_jsonl(STATE / "notify.jsonl", {"ts": iso(now()), "alert": a.alert, "ok": bool(res.get("ok")),
                                          "message_id": ((res.get("data") or {}).get("message_id")), "error": res.get("error")})
    print(json.dumps({"ok": bool(res.get("ok")), "message_id": ((res.get("data") or {}).get("message_id")), "error": res.get("error")}, ensure_ascii=False))
    if not res.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
