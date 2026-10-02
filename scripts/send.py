#!/usr/bin/env python3
"""唯一的对外发消息入口：以 Jack 身份回复或发送。自动加签名、幂等键；shadow 模式只记录不发送；每次 run 有上限。

用法：
  send.py reply --message-id om_xxx (--text "..." | --markdown "...") [--in-thread]
  send.py send  --chat-id oc_xxx   (--text "..." | --markdown "...")
"""
import argparse
import json
import sys

from common import POLICY, STATE, append_jsonl, iso, is_auth_error, lark, load_json, now, parse_iso, read_jsonl


def with_signature(text):
    sig = POLICY.get("signature") or ""
    text = text.rstrip()
    if sig and not text.endswith(sig):
        text = text + ("\n" if "\n" in text or len(text) > 30 else " ") + sig
    return text


def outbound_count_this_run():
    lock = load_json(STATE / "lock.json", {})
    since = lock.get("acquired_at")
    if not since:
        return 0
    s = parse_iso(since)
    return sum(1 for r in read_jsonl(STATE / "outbound.jsonl") if parse_iso(r["ts"]) >= s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["reply", "send"])
    ap.add_argument("--message-id")
    ap.add_argument("--chat-id")
    ap.add_argument("--text")
    ap.add_argument("--markdown")
    ap.add_argument("--in-thread", action="store_true")
    a = ap.parse_args()
    if a.action == "reply" and not a.message_id:
        sys.exit("reply 需要 --message-id")
    if a.action == "send" and not a.chat_id:
        sys.exit("send 需要 --chat-id")
    if not (a.text or a.markdown):
        sys.exit("需要 --text 或 --markdown")

    body = with_signature(a.text or a.markdown)
    mode = POLICY.get("mode", "shadow")
    key = ("ac-" + a.message_id) if a.action == "reply" else ("ac-" + a.chat_id[-12:] + "-" + now().strftime("%m%d%H%M"))
    record = {"ts": iso(now()), "mode": mode, "action": a.action, "message_id": a.message_id, "chat_id": a.chat_id,
              "format": "markdown" if a.markdown else "text", "body": body, "idempotency_key": key[:50]}

    if mode != "live":
        record["shadow"] = True
        append_jsonl(STATE / "outbound_shadow.jsonl", record)
        print(json.dumps({"ok": True, "shadow": True, "would_send": body}, ensure_ascii=False))
        return

    cap = int(POLICY.get("max_outbound_per_run", 15))
    if outbound_count_this_run() >= cap:
        print(json.dumps({"ok": False, "error": {"type": "cap", "message": "本次 run 对外消息已达上限 %d" % cap}}, ensure_ascii=False))
        sys.exit(2)

    fmt_flag = "--markdown" if a.markdown else "--text"
    if a.action == "reply":
        args = ["im", "+messages-reply", "--message-id", a.message_id, fmt_flag, body, "--idempotency-key", key[:50]]
        if a.in_thread:
            args.append("--reply-in-thread")
    else:
        args = ["im", "+messages-send", "--chat-id", a.chat_id, fmt_flag, body, "--idempotency-key", key[:50]]
    res = lark(args)
    record["ok"] = bool(res.get("ok"))
    record["result_message_id"] = ((res.get("data") or {}).get("message_id")) if res.get("ok") else None
    record["error"] = None if res.get("ok") else res.get("error")
    append_jsonl(STATE / "outbound.jsonl", record)
    print(json.dumps({"ok": record["ok"], "message_id": record["result_message_id"], "error": record["error"],
                      "auth_error": is_auth_error(res)}, ensure_ascii=False))
    if not record["ok"]:
        sys.exit(3 if is_auth_error(res) else 1)


if __name__ == "__main__":
    main()
