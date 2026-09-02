#!/usr/bin/env python3
"""
server.py -- APKPure + Play Store target intelligence MCP server (stdio transport).

Wraps the vendored apkpure_dl toolkit and adds:
  apkpure_detail  - app metadata + asset info from the APKPure mirror
  apkpure_pull    - download the app package (XAPK/APK) with SHA-256 verification
  play_verify     - live Play Store version/update/rating check (no account)
  target_score    - engagement-fit scoring: version freshness, install scale,
                    update cadence, mirror-vs-Play drift, activeness verdict

Protocol: newline-delimited JSON-RPC 2.0 over stdio (MCP stdio transport).
Deps: requests (apkpure_dl lib is vendored in ./apkpure_dl).
"""

import contextlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "apkpure_dl"))

from apkpure_dl.config import Config  # noqa: E402
from apkpure_dl.client import app_detail as _app_detail, extract_asset  # noqa: E402
from apkpure_dl.downloader import download_from_detail  # noqa: E402
from apkpure_dl.throttle import throttle  # noqa: E402

try:
    from google_play_scraper import app as play_app
except ImportError:
    play_app = None

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "apkpure-mcp", "version": "1.0.0"}

# apkpure_dl prints "[cache]" and download logs to stdout, which corrupts the
# JSON-RPC stream. Silence its stdout during tool calls.
_devnull = io.StringIO()


@contextlib.contextmanager
def _quiet():
    old = sys.stdout
    sys.stdout = _devnull
    try:
        yield
    finally:
        sys.stdout = old


FRESH_DAYS = {7: 1.0, 14: 0.9, 30: 0.7, 90: 0.4, 180: 0.15, 10**9: 0.0}
INSTALL_BONUS = [
    (1_000_000, 15), (500_000, 13), (100_000, 11), (50_000, 8),
    (10_000, 5), (1_000, 2), (0, 0),
]
MIN_FRESH = 0.3


def _parse_dl_count(raw):
    if raw is None:
        return None
    s = str(raw).strip().lower()
    try:
        if s.endswith("+"):
            return int(s[:-1])
        if s.endswith("k"):
            return int(float(s[:-1]) * 1_000)
        if s.endswith("m"):
            return int(float(s[:-1]) * 1_000_000)
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _days_since(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except (ValueError, TypeError):
        return None


def _freshness(days):
    if days is None:
        return 0.2, "unknown-date"
    for limit, score in FRESH_DAYS.items():
        if days <= limit:
            label = ("updated-today" if days == 0 else
                     f"updated-{days}d-ago" if days <= 30 else
                     f"updated-{days // 30}mo-ago")
            return score, label
    return 0.0, "ancient"


def _ver_gt(a, b):
    def key(v):
        return [int(x) for x in "".join(ch if ch.isdigit() else "." for ch in v).split(".") if x]
    try:
        return key(a) > key(b)
    except ValueError:
        return False


def tool_apkpure_detail(package, no_cache=False):
    cfg = Config()
    throttle(enabled=True, rng=(1.0, 2.5))
    with _quiet():
        resp = _app_detail(cfg, package, use_cache=not no_cache)
        info = extract_asset(resp)
    a = resp.get("app_detail", {})
    dl = _parse_dl_count(a.get("download_count_v2") or a.get("download_count"))
    upd = (a.get("update_date") or "")[:19]
    dev = a.get("developer")
    dev = dev.get("name") if isinstance(dev, dict) else dev
    return {
        "package": package,
        "title": a.get("title"),
        "developer": dev,
        "version_name": a.get("version_name"),
        "version_code": a.get("version_code"),
        "update_date": upd or None,
        "days_since_update": _days_since(upd),
        "on_store_since": (a.get("create_date") or "")[:10] or None,
        "downloads_mirror_window": dl,
        "asset_type": info.get("asset_type"),
        "file_size_bytes": info.get("file_size"),
        "file_sha256": info.get("file_sha256"),
        "url": f"https://apkpure.com/{package}",
    }


def tool_apkpure_pull(package, out_dir):
    cfg = Config()
    throttle(enabled=True, rng=(1.0, 2.5))
    with _quiet():
        resp = _app_detail(cfg, package, use_cache=True)
        info = extract_asset(resp)
        out = Path(out_dir).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        download_from_detail(resp, out)
        a = resp.get("app_detail", {})
    return {
        "package": package,
        "downloaded_to": str(out),
        "file_sha256": info.get("file_sha256"),
        "version_name": a.get("version_name"),
        "version_code": a.get("version_code"),
    }


def tool_play_verify(package):
    if play_app is None:
        return {"error": "google_play_scraper not importable"}
    try:
        d = play_app(package)
    except Exception as e:
        return {"package": package, "found": False, "error": f"{e}"[:200]}
    return {
        "package": package,
        "found": True,
        "title": d.get("title"),
        "version": d.get("version"),
        "updated": (datetime.fromtimestamp(d["updated"], tz=timezone.utc).date().isoformat()
                    if d.get("updated") else None),
        "installs": d.get("installs"),
        "installs_parsed": _parse_dl_count(d.get("installs")),
        "rating": d.get("score"),
        "ratings_count": d.get("ratings"),
        "developer": d.get("developer"),
        "url": f"https://play.google.com/store/apps/details?id={package}",
    }


def tool_target_score(package, max_score=30):
    detail = tool_apkpure_detail(package, no_cache=True)
    if not detail.get("update_date") and not detail.get("file_sha256"):
        return {"package": package, "error": "not on APKPure mirror", "play": tool_play_verify(package)}

    days = detail.get("days_since_update")
    fresh, fresh_label = _freshness(days)
    dlm = detail.get("downloads_mirror_window")

    play = tool_play_verify(package)
    play_ver = (play or {}).get("version")
    mirror_ver = detail.get("version_name")
    drift = None
    if play_ver and mirror_ver and str(play_ver) != "Varies with device":
        if str(mirror_ver) == str(play_ver):
            drift = "match"
        elif _ver_gt(str(mirror_ver), str(play_ver)):
            drift = "mirror-ahead"
        else:
            drift = "play-ahead"

    installs = (play or {}).get("installs_parsed") or dlm or 0
    installs_bonus = 0
    for limit, pts in INSTALL_BONUS:
        if installs >= limit:
            installs_bonus = pts
            break

    score = round(fresh * 15 + installs_bonus, 1)
    verdict = "ACTIVE" if fresh >= 0.7 else "ALIVE" if fresh >= MIN_FRESH else "STALE"
    if drift == "mirror-ahead":
        verdict = "ACTIVE (dev iterates fast: mirror ahead of Play)"

    return {
        "package": package,
        "score": f"{score}/{max_score}",
        "verdict": verdict,
        "version": {"mirror": mirror_ver, "play": play_ver, "drift": drift},
        "update": {"date": detail.get("update_date"), "days": days, "freshness": fresh_label},
        "scale": {"installs_play": (play or {}).get("installs"),
                  "mirror_window_downloads": dlm},
        "developer": detail.get("developer") or (play or {}).get("developer"),
        "title": detail.get("title") or (play or {}).get("title"),
    }


TOOLS = {
    "apkpure_detail": {
        "description": "APKPure mirror metadata for an Android package: version, "
                       "update date, downloads, asset type, SHA-256.",
        "input": {"package": str, "no_cache": bool},
        "fn": lambda package, no_cache=False: tool_apkpure_detail(package, no_cache),
    },
    "apkpure_pull": {
        "description": "Download the app package from APKPure with SHA-256 verification. "
                       "Returns the output directory and file hash.",
        "input": {"package": str, "out_dir": str},
        "fn": lambda package, out_dir="./downloads": tool_apkpure_pull(package, out_dir),
    },
    "play_verify": {
        "description": "Live Play Store check (no account): current version, update date, "
                       "installs, rating. The authoritative 'newest Play version' source.",
        "input": {"package": str},
        "fn": lambda package: tool_play_verify(package),
    },
    "target_score": {
        "description": "Engagement-fit score for a hunting target (0-30): update freshness, "
                       "install scale, mirror-vs-Play version drift, verdict ACTIVE/ALIVE/STALE.",
        "input": {"package": str},
        "fn": lambda package: tool_target_score(package),
    },
}


def handle(req):
    method = req.get("method", "")
    rid = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [
            {"name": n, "description": t["description"],
             "inputSchema": {"type": "object", "properties": {
                 k: {"type": v.__name__.replace("bool", "boolean").replace("str", "string").replace("int", "integer")}
                 for k, v in t["input"].items()},
                 "required": [k for k in t["input"] if k != "no_cache"]}}
            for n, t in TOOLS.items()]}}
    if method == "tools/call":
        name = req.get("params", {}).get("name", "")
        args = req.get("params", {}).get("arguments", {}) or {}
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"unknown tool {name}"}}
        try:
            result = TOOLS[name]["fn"](**args)
        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"[:300]}
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False, default=str)}],
            "isError": bool(result.get("error"))}}
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"unknown method {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
