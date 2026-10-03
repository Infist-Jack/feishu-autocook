"""feishu-autocook 公共工具：路径、配置、时间、lark-cli 调用、状态文件。只用标准库。"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
STATE = ROOT / "state"
INBOX = STATE / "inbox"
DONE = STATE / "done"
for _d in (STATE, INBOX, DONE):
    _d.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    path = pathlib.Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def append_jsonl(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


POLICY = load_json(CONFIG / "policy.json", {})
TOPICS = load_json(CONFIG / "topics.local.json", load_json(CONFIG / "topics.example.json", {}))


def _tz():
    name = POLICY.get("timezone", "Asia/Singapore")
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return dt.timezone(dt.timedelta(hours=8))


TZ = _tz()


def now():
    return dt.datetime.now(TZ)


def iso(d):
    return d.isoformat(timespec="seconds")


def parse_iso(s):
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
    return d.astimezone(TZ)


def parse_create_time(s):
    """lark-cli 返回的 create_time 可能是 'YYYY-MM-DD HH:MM'、ISO 或毫秒时间戳字符串。"""
    s = str(s).strip()
    if s.isdigit():
        return dt.datetime.fromtimestamp(int(s) / 1000, TZ)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s, fmt).replace(tzinfo=TZ)
        except ValueError:
            pass
    return parse_iso(s)


def log(*parts):
    print(*parts, file=sys.stderr, flush=True)


def lark(args, as_="user", timeout=90):
    """调用 lark-cli，返回 dict。stdin 接 /dev/null，输出强制 JSON。"""
    cmd = ["lark-cli", *args, "--as", as_, "--json"]
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": {"type": "timeout", "message": "lark-cli timeout: %s" % " ".join(args[:2])}}
    except FileNotFoundError:
        return {"ok": False, "error": {"type": "cli", "message": "lark-cli not found in PATH"}}
    raw = p.stdout.strip() or p.stderr.strip()
    try:
        res = json.loads(raw)
    except ValueError:
        return {"ok": False, "error": {"type": "cli", "message": (p.stderr or p.stdout)[:500], "exit": p.returncode}}
    if isinstance(res, dict) and "ok" not in res:
        res = {"ok": p.returncode == 0, "data": res}
    return res


def is_auth_error(res):
    err = (res or {}).get("error") or {}
    t = str(err.get("type", "")).lower()
    msg = str(err.get("message", "")).lower()
    return t in ("auth", "missing_scope", "unauthorized") or "token" in msg and ("expired" in msg or "invalid" in msg)


def _identity():
    """Jack 的 open_id 与本 CLI 应用的 app_id，缓存 6 小时。"""
    cache = STATE / "identity.json"
    ident = load_json(cache, {})
    if ident.get("open_id") and ident.get("fetched_at"):
        age = (now() - parse_iso(ident["fetched_at"])).total_seconds()
        if age < 6 * 3600:
            return ident
    try:
        p = subprocess.run(["lark-cli", "auth", "status"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        d = json.loads(p.stdout)
        oid = (((d.get("identities") or {}).get("user") or {}).get("openId")) or d.get("openId")
        app = d.get("appId")
    except Exception:
        oid, app = None, None
    if oid:
        ident = {"open_id": oid, "app_id": app, "fetched_at": iso(now())}
        save_json(cache, ident)
        return ident
    if ident.get("open_id"):
        return ident
    raise SystemExit("无法确定 Jack 的 open_id：lark-cli auth status 失败")


def jack_open_id():
    return _identity()["open_id"]


def own_app_id():
    """autocook 自己的 bot 应用 id；它发给 Jack 的汇报不能再被当成待处理消息。"""
    return _identity().get("app_id")


def chat_names(refresh=False):
    """chat_id -> {name, chat_mode, external}，缓存 6 小时。"""
    cache = STATE / "chats.json"
    c = load_json(cache, {})
    fresh = c.get("fetched_at") and (now() - parse_iso(c["fetched_at"])).total_seconds() < 6 * 3600
    if fresh and not refresh:
        return c.get("chats", {})
    res = lark(["im", "+chat-list", "--types", "p2p,group", "--sort", "active_time", "--page-size", "100", "--page-all", "--page-limit", "10"])
    if not res.get("ok"):
        return c.get("chats", {})
    chats = {}
    for ch in ((res.get("data") or {}).get("chats") or []):
        chats[ch["chat_id"]] = {"name": ch.get("name") or "", "chat_mode": ch.get("chat_mode"), "external": bool(ch.get("external"))}
    save_json(cache, {"fetched_at": iso(now()), "chats": chats})
    return chats


def topic_hits(text):
    text = (text or "").lower()
    hits = []
    for proj in TOPICS.get("projects", []):
        for kw in proj.get("keywords", []):
            if kw.lower() in text:
                hits.append({"project": proj.get("name"), "keyword": kw, "context": proj.get("context")})
                break
    for kw in TOPICS.get("general_keywords", []):
        if kw.lower() in text:
            hits.append({"project": None, "keyword": kw})
    return hits
