#!/usr/bin/env python3
"""状态操作：锁、决策日志、开环、批次提交、无关摘要。

  state.py lock acquire|release|status
  state.py decision '<json>'
  state.py thread open '<json>' | close <id> | list [chat_id]
  state.py batch commit <inbox 文件>
  state.py digest add '<json>' | due | mark
"""
import json
import os
import shutil
import sys
import uuid

from common import DONE, POLICY, STATE, append_jsonl, iso, load_json, now, parse_iso, parse_create_time, save_json, read_jsonl

LOCK = STATE / "lock.json"


def lock(cmd):
    cur = load_json(LOCK, {})
    stale = int(POLICY.get("lock_stale_seconds", 1500))
    if cmd == "status":
        held = bool(cur) and (now() - parse_iso(cur["acquired_at"])).total_seconds() < stale
        print(json.dumps({"held": held, "lock": cur}))
        return 0
    if cmd == "acquire":
        if cur and (now() - parse_iso(cur["acquired_at"])).total_seconds() < stale:
            print(json.dumps({"ok": False, "reason": "locked", "lock": cur}))
            return 1
        save_json(LOCK, {"pid": os.getpid(), "acquired_at": iso(now()), "token": uuid.uuid4().hex[:8]})
        print(json.dumps({"ok": True}))
        return 0
    if cmd == "release":
        if LOCK.exists():
            LOCK.unlink()
        print(json.dumps({"ok": True}))
        return 0
    return 2


def decision(raw):
    d = json.loads(raw)
    d["ts"] = iso(now())
    append_jsonl(STATE / "decisions.jsonl", d)
    print(json.dumps({"ok": True}))
    return 0


def thread(cmd, arg=None):
    path = STATE / "threads.json"
    db = load_json(path, {"items": []})
    if cmd == "open":
        t = json.loads(arg)
        t.setdefault("id", "th_" + uuid.uuid4().hex[:8])
        t["status"] = "open"
        t["opened_at"] = iso(now())
        t.setdefault("followups", 1)
        db["items"].append(t)
        save_json(path, db)
        print(json.dumps({"ok": True, "id": t["id"]}))
        return 0
    if cmd == "close":
        for t in db["items"]:
            if t.get("id") == arg:
                t["status"] = "closed"
                t["closed_at"] = iso(now())
        save_json(path, db)
        print(json.dumps({"ok": True}))
        return 0
    if cmd == "list":
        items = [t for t in db["items"] if t.get("status") == "open" and (not arg or t.get("chat_id") == arg)]
        print(json.dumps(items, ensure_ascii=False, indent=1))
        return 0
    return 2


def batch_commit(path):
    b = load_json(path, {})
    handled = load_json(STATE / "handled.json", {})
    ts = iso(now())
    for m in b.get("messages", []):
        handled[m["message_id"]] = ts
    save_json(STATE / "handled.json", handled)
    cursor = load_json(STATE / "cursor.json", {})
    until = b.get("until")
    if until and (not cursor.get("since") or parse_iso(until) > parse_iso(cursor["since"])):
        save_json(STATE / "cursor.json", {"since": until})
    shutil.move(path, DONE / os.path.basename(path))
    print(json.dumps({"ok": True, "handled": len(b.get("messages", [])), "cursor": until}))
    return 0


def digest(cmd, arg=None):
    sent = load_json(STATE / "digest_sent.json", {})
    t = now()
    slot = None
    for h in POLICY.get("digest_hours", [9, 18]):
        if t.hour == int(h):
            slot = "%s-%02d" % (t.strftime("%Y%m%d"), int(h))
    if cmd == "add":
        d = json.loads(arg)
        d["ts"] = iso(t)
        append_jsonl(STATE / "digest.jsonl", d)
        print(json.dumps({"ok": True}))
        return 0
    if cmd == "due":
        pending = read_jsonl(STATE / "digest.jsonl")
        due = bool(slot) and slot not in sent and bool(pending)
        print(json.dumps({"due": due, "slot": slot, "pending": len(pending), "items": pending if due else []}, ensure_ascii=False))
        return 0
    if cmd == "mark":
        if slot:
            sent[slot] = iso(t)
            save_json(STATE / "digest_sent.json", sent)
        p = STATE / "digest.jsonl"
        if p.exists():
            shutil.move(p, DONE / ("digest-%s.jsonl" % t.strftime("%Y%m%d-%H%M")))
        print(json.dumps({"ok": True, "slot": slot}))
        return 0
    return 2


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    c = argv[0]
    if c == "lock":
        return lock(argv[1])
    if c == "decision":
        return decision(argv[1])
    if c == "thread":
        return thread(argv[1], argv[2] if len(argv) > 2 else None)
    if c == "batch" and argv[1] == "commit":
        return batch_commit(argv[2])
    if c == "digest":
        return digest(argv[1], argv[2] if len(argv) > 2 else None)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
