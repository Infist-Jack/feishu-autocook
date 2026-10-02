#!/usr/bin/env python3
"""给一条消息拼上下文：消息本体、会话信息、最近消息、线程、开环、历史决策、关键词命中。输出 JSON。"""
import argparse
import json

from common import STATE, chat_names, jack_open_id, lark, log, read_jsonl, topic_hits, load_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("message_id")
    ap.add_argument("--recent", type=int, default=15)
    a = ap.parse_args()
    me = jack_open_id()

    res = lark(["im", "+messages-mget", "--message-ids", a.message_id])
    msgs = ((res.get("data") or {}).get("messages") or []) if res.get("ok") else []
    if not msgs:
        raise SystemExit(json.dumps({"error": "消息不存在或不可见", "detail": res.get("error")}, ensure_ascii=False))
    msg = msgs[0]
    chat_id = msg.get("chat_id")

    info = chat_names().get(chat_id, {})
    recent = []
    r2 = lark(["im", "+chat-messages-list", "--chat-id", chat_id, "--page-size", str(a.recent), "--no-reactions"])
    if r2.get("ok"):
        for m in reversed(((r2.get("data") or {}).get("messages") or [])):
            s = m.get("sender") or {}
            recent.append({
                "message_id": m.get("message_id"), "create_time": m.get("create_time"), "msg_type": m.get("msg_type"),
                "from": "Jack" if s.get("id") == me else (s.get("name") or s.get("id")),
                "is_app": s.get("sender_type") == "app",
                "content": m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"), ensure_ascii=False),
            })
    else:
        log("chat-messages-list 失败：", json.dumps(r2.get("error"), ensure_ascii=False)[:200])

    threads = [t for t in load_json(STATE / "threads.json", {}).get("items", []) if t.get("chat_id") == chat_id and t.get("status") == "open"]
    decisions = [d for d in read_jsonl(STATE / "decisions.jsonl") if d.get("chat_id") == chat_id][-10:]
    content = msg.get("content") if isinstance(msg.get("content"), str) else json.dumps(msg.get("content"), ensure_ascii=False)

    out = {
        "message": msg,
        "chat": {"chat_id": chat_id, "name": info.get("name") or ("单聊" if (msg.get("chat_type") or info.get("chat_mode")) == "p2p" else ""),
                 "mode": info.get("chat_mode") or msg.get("chat_type"), "external": info.get("external", False)},
        "mentions_me": any((x or {}).get("id") == me for x in (msg.get("mentions") or [])),
        "topic_hits": topic_hits(content),
        "recent": recent,
        "open_threads": threads,
        "prior_decisions": decisions,
        "already_decided": any(d.get("message_id") == a.message_id for d in decisions),
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
