#!/usr/bin/env python3
"""信号脚本，不用 LLM。由 launchd 定时执行。

  watcher.py tick     每 60 秒：写心跳；拉新消息写批次；有批次且无锁且不在冷却期就触发 paseo schedule run-once
  watcher.py health   每 15 分钟：心跳过期、鉴权失败、paseo 不可达时用 bot 告警 Jack
"""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import INBOX, POLICY, STATE, append_jsonl, iso, load_json, log, now, parse_iso, save_json  # noqa: E402

HEARTBEAT = STATE / "watcher_heartbeat.json"
WLOG = STATE / "watcher.jsonl"
PY = sys.executable


def sh(cmd, timeout=120):
    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def notify_alert(key, text):
    code, out, err = sh([PY, str(ROOT / "scripts" / "notify.py"), "--alert", key, "--text", text])
    append_jsonl(WLOG, {"ts": iso(now()), "event": "alert", "key": key, "ok": code == 0, "out": out[:200]})


def lock_held():
    code, out, _ = sh([PY, str(ROOT / "scripts" / "state.py"), "lock", "status"])
    try:
        return bool(json.loads(out).get("held"))
    except ValueError:
        return False


def trigger_run():
    cfg = load_json(ROOT / "config" / "paseo.local.json", {})
    sid = cfg.get("scheduleId")
    if not sid or sid.startswith("sch_xxx"):
        append_jsonl(WLOG, {"ts": iso(now()), "event": "no_schedule_id"})
        return False
    hb = load_json(HEARTBEAT, {})
    last = hb.get("last_trigger")
    cool = int(POLICY.get("watcher_trigger_cooldown_seconds", 180))
    if last and (now() - parse_iso(last)).total_seconds() < cool:
        return False
    code, out, err = sh(["paseo", "schedule", "run-once", sid, "--json"], timeout=60)
    hb["last_trigger"] = iso(now())
    hb["last_trigger_ok"] = code == 0
    save_json(HEARTBEAT, hb)
    append_jsonl(WLOG, {"ts": iso(now()), "event": "trigger", "ok": code == 0, "out": (out or err)[:300]})
    if code != 0:
        notify_alert("paseo", "paseo schedule run-once 失败：%s" % (err or out)[:200])
    return code == 0


def tick():
    hb = load_json(HEARTBEAT, {})
    hb["last_tick"] = iso(now())
    save_json(HEARTBEAT, hb)
    code, out, err = sh([PY, str(ROOT / "scripts" / "fetch_since.py"), "--write-batch"], timeout=170)
    hb = load_json(HEARTBEAT, {})
    hb["last_fetch_exit"] = code
    hb["last_fetch_note"] = (err.splitlines() or [""])[-1][:200]
    save_json(HEARTBEAT, hb)
    if code == 3:
        notify_alert("auth", "lark 用户 token 失效，需要在这台机器上执行 lark-cli auth login")
        return 3
    if code not in (0,):
        append_jsonl(WLOG, {"ts": iso(now()), "event": "fetch_error", "exit": code, "err": err[:300]})
    if code == 0 and out.startswith("{"):
        append_jsonl(WLOG, {"ts": iso(now()), "event": "batch", "detail": out[:200]})
    if any(INBOX.glob("*.json")) and not lock_held():
        trigger_run()
    return 0


def health():
    hb = load_json(HEARTBEAT, {})
    stale = int(POLICY.get("watcher_stale_seconds", 900))
    last = hb.get("last_tick")
    if not last or (now() - parse_iso(last)).total_seconds() > stale:
        notify_alert("watcher", "watcher 已 %s 没有心跳，请检查 launchd 任务 ai.autocook.watcher" % ("超过 %d 分钟" % (stale // 60)))
    code, out, err = sh(["paseo", "status", "--json"], timeout=30)
    if code != 0:
        notify_alert("paseo", "paseo daemon 不可达：%s" % (err or out)[:200])
    lock = load_json(STATE / "lock.json", {})
    if lock and (now() - parse_iso(lock["acquired_at"])).total_seconds() > int(POLICY.get("lock_stale_seconds", 1500)) * 2:
        notify_alert("lock", "autocook 锁已过期很久仍未释放，上一次 run 可能异常退出")
    print(json.dumps({"ok": True, "heartbeat": hb}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tick"
    sys.exit({"tick": tick, "health": health}.get(cmd, lambda: 2)())
