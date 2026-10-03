#!/usr/bin/env python3
"""拉取游标之后、与 Jack 有可能相关的新消息，过滤出"未读且超过 N 秒"的，输出 JSON；--write-batch 时写入 state/inbox/。

退出码：0 正常（可能 0 条）；3 鉴权失败；4 其他 lark 错误。
"""
import argparse
import json
import sys

from common import (DONE, INBOX, POLICY, STATE, iso, is_auth_error, jack_open_id, own_app_id, lark, load_json, log, now,
                    parse_create_time, parse_iso, save_json, chat_names, topic_hits)
import datetime as dt

HUMAN_TYPES = {"text", "post", "image", "file", "audio", "media", "sticker", "interactive", "share_chat", "share_user"}


def pending_ids():
    ids = set()
    for f in INBOX.glob("*.json"):
        b = load_json(f, {})
        for m in b.get("messages", []):
            ids.add(m["message_id"])
    return ids


def handled_ids():
    h = load_json(STATE / "handled.json", {})
    cutoff = now() - dt.timedelta(days=7)
    kept = {k: v for k, v in h.items() if parse_iso(v) >= cutoff}
    if len(kept) != len(h):
        save_json(STATE / "handled.json", kept)
    return set(kept)


def read_status(ids):
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        res = lark(["im", "+messages-read-status", "--message-ids", ",".join(chunk)])
        if not res.get("ok"):
            if is_auth_error(res):
                raise SystemExit(3)
            log("read-status 失败，按未读处理：", json.dumps(res.get("error"), ensure_ascii=False)[:200])
            for m in chunk:
                out[m] = False
            continue
        for it in ((res.get("data") or {}).get("items") or []):
            out[it["message_id"]] = bool(it.get("is_read"))
        for bad in ((res.get("data") or {}).get("invalid_message_ids") or []):
            out[bad] = True  # 查不到的当作不需要处理
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-age", type=int, default=POLICY.get("min_unread_seconds", 600))
    ap.add_argument("--all", action="store_true", help="不按已读过滤")
    ap.add_argument("--since", help="覆盖游标（ISO）")
    ap.add_argument("--pages", type=int, default=10)
    ap.add_argument("--write-batch", action="store_true")
    a = ap.parse_args()

    me = jack_open_id()
    own_app = own_app_id()
    include_app = bool(POLICY.get("include_app_senders", True))
    cursor = load_json(STATE / "cursor.json", {})
    if a.since:
        since = parse_iso(a.since)
    elif cursor.get("since"):
        since = parse_iso(cursor["since"])
    else:
        since = now() - dt.timedelta(seconds=POLICY.get("initial_lookback_seconds", 7200))
        save_json(STATE / "cursor.json", {"since": iso(since)})
    start = since - dt.timedelta(seconds=POLICY.get("search_overlap_seconds", 900))

    res = lark(["im", "+messages-search", "--start", iso(start), "--page-size", "50", "--page-all",
                "--page-limit", str(a.pages), "--no-reactions"])
    if not res.get("ok"):
        log("messages-search 失败：", json.dumps(res.get("error"), ensure_ascii=False)[:300])
        sys.exit(3 if is_auth_error(res) else 4)
    msgs = (res.get("data") or {}).get("messages") or []

    skip = pending_ids() | handled_ids()
    never = set(((load_json(STATE.parent / "config" / "topics.local.json", {})).get("never_handle_chat_ids") or []))
    t_now = now()
    cands = []
    for m in msgs:
        if m.get("deleted"):
            continue
        s = m.get("sender") or {}
        if s.get("id") == me:
            continue
        is_app = s.get("sender_type") not in (None, "", "user")
        if is_app and (not include_app or (own_app and s.get("id") == own_app)):
            continue
        if m.get("msg_type") not in HUMAN_TYPES:
            continue
        if m["message_id"] in skip or m.get("chat_id") in never:
            continue
        ct = parse_create_time(m.get("create_time"))
        age = (t_now - ct).total_seconds()
        if age < a.min_age:
            continue
        m["_age_seconds"] = int(age)
        m["_create_iso"] = iso(ct)
        cands.append(m)

    if cands and not a.all:
        rs = read_status([m["message_id"] for m in cands])
        cands = [m for m in cands if not rs.get(m["message_id"], False)]

    names = chat_names() if cands else {}
    for m in cands:
        info = names.get(m.get("chat_id"), {})
        m["_chat_name"] = info.get("name") or ("单聊" if m.get("chat_type") == "p2p" else "")
        m["_external"] = info.get("external", False)
        m["_mentions_me"] = any((x or {}).get("id") == me for x in (m.get("mentions") or []))
        m["_from_app"] = (m.get("sender") or {}).get("sender_type") not in (None, "", "user")
        content = m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"), ensure_ascii=False)
        m["_topic_hits"] = topic_hits(content)
    cands.sort(key=lambda x: x["_create_iso"])

    log("搜索 %d 条，候选 %d 条（since %s）" % (len(msgs), len(cands), iso(since)))
    if a.write_batch and cands:
        until = max(m["_create_iso"] for m in cands)
        path = INBOX / ("%s.json" % t_now.strftime("%Y%m%d-%H%M%S"))
        save_json(path, {"created": iso(t_now), "since": iso(since), "until": until, "messages": cands})
        log("批次已写入", str(path))
        print(json.dumps({"batch": str(path), "count": len(cands)}, ensure_ascii=False))
    else:
        print(json.dumps(cands, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
