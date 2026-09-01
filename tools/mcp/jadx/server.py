#!/usr/bin/env python3
"""JADX MCP server (stdlib only, drives the jadx CLI).

Interactive APK source access for the analyze phase: single-class decompile,
full-project code search, class listing, and the decoded manifest. Pure
Python stdlib, no dependencies, no jadx GUI required.

The jadx binary is found on PATH; JADX_BIN overrides it. A full decompile is
cached under the system temp dir keyed by APK path, size and mtime, so search
and list calls are fast after the first warm-up.

Tools:
    jadx_decompile(apk)              warm the cache, report stats
    jadx_get_class(apk, class)       decompile one class (fast, no cache)
    jadx_search_code(apk, pattern)   substring search across decompiled code
    jadx_list_classes(apk, filter)   list class paths under sources/
    jadx_get_manifest(apk)           decoded AndroidManifest.xml

Registration (opencode example, adapt <repo>):

{
  "mcp": {
    "jadx": { "type": "local",
              "command": ["python3", "<repo>/tools/mcp/jadx/server.py"],
              "enabled": true }
  }
}

Methodology fit: static-first mode lives here. Secrets and endpoints found
via jadx are LEADS until a dynamic proof converts them (evidence_capture
policy still applies to every live probe).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

JADX_BIN = os.environ.get("JADX_BIN", "jadx")
CACHE_ROOT = Path(tempfile.gettempdir()) / "jadx-mcp-cache"

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "jadx-cli", "version": "1.0.0"}
SEARCH_DEFAULT_MAX = 50
LIST_DEFAULT_LIMIT = 100
MAX_TEXT = 400_000  # cap per returned file so one huge class cannot flood the context

TOOLS = [
    {
        "name": "jadx_decompile",
        "description": (
            "Decompile an APK with jadx into a cache dir (first call is slow "
            "on big apps, later calls are instant). Returns class and resource "
            "counts. Call this before jadx_search_code or jadx_list_classes."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "apk": {"type": "string", "description": "Path to the .apk file"},
                "force": {"type": "boolean", "description": "Re-decompile even if cached (default false)"},
            },
            "required": ["apk"],
        },
    },
    {
        "name": "jadx_get_class",
        "description": (
            "Decompile one class to Java source (fast, does not need the "
            "cache). Class name is fully qualified, e.g. com.example.app.MainActivity."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "apk": {"type": "string", "description": "Path to the .apk file"},
                "class": {"type": "string", "description": "Fully qualified class name"},
            },
            "required": ["apk", "class"],
        },
    },
    {
        "name": "jadx_search_code",
        "description": (
            "Substring search across decompiled Java sources (case-sensitive). "
            "Returns file, line number and line text for each hit. Warms the "
            "cache automatically on first use."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "apk": {"type": "string", "description": "Path to the .apk file"},
                "pattern": {"type": "string", "description": "Substring to find"},
                "max_hits": {"type": "integer", "description": f"Max hits (default {SEARCH_DEFAULT_MAX})"},
            },
            "required": ["apk", "pattern"],
        },
    },
    {
        "name": "jadx_list_classes",
        "description": (
            "List decompiled class paths under sources/, optional substring "
            "filter. Warms the cache automatically on first use."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "apk": {"type": "string", "description": "Path to the .apk file"},
                "filter": {"type": "string", "description": "Substring filter on the class path"},
                "limit": {"type": "integer", "description": f"Max rows (default {LIST_DEFAULT_LIMIT})"},
            },
            "required": ["apk"],
        },
    },
    {
        "name": "jadx_get_manifest",
        "description": (
            "Decoded AndroidManifest.xml (permissions, exported components, "
            "deeplinks). Warms the cache automatically on first use."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "apk": {"type": "string", "description": "Path to the .apk file"},
            },
            "required": ["apk"],
        },
    },
]


def cache_dir(apk: str) -> Path:
    key = hashlib.sha256(
        f"{os.path.abspath(apk)}:{os.path.getsize(apk)}:{os.path.getmtime(apk)}".encode()
    ).hexdigest()[:16]
    return CACHE_ROOT / key


def run_jadx(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([JADX_BIN, *args], capture_output=True, text=True, timeout=3600)


def ensure_cache(apk: str, force: bool = False) -> tuple[Path, dict]:
    """Full decompile into the cache dir; returns (dir, stats)."""
    out = cache_dir(apk)
    done_marker = out / ".jadx-mcp-done"
    if force and out.exists():
        for child in out.iterdir():
            child.is_file() and child.unlink()
    if not done_marker.exists():
        out.mkdir(parents=True, exist_ok=True)
        proc = run_jadx(["-d", str(out), "--no-debug-info", apk])
        # jadx exit codes are not stable (partial decompile errors are normal
        # on obfuscated apps); trust the output, not the exit code.
        sources = out / "sources"
        has_sources = sources.is_dir() and any(sources.rglob("*.java"))
        if not has_sources:
            log = (proc.stderr or proc.stdout).strip().splitlines()
            return out, {"error": f"jadx produced no sources (code {proc.returncode})",
                         "log_tail": log[-5:]}
        done_marker.write_text("ok")
    sources = out / "sources"
    classes = sum(1 for _ in sources.rglob("*.java")) if sources.is_dir() else 0
    resources = sum(1 for _ in (out / "resources").rglob("*") if _.is_file()) if (out / "resources").is_dir() else 0
    return out, {"cache_dir": str(out), "classes": classes, "resources": resources}


def require_file(path: str) -> dict | None:
    if not os.path.isfile(path):
        return {"error": f"file not found: {path}"}
    return None


def tool_decompile(args):
    apk = (args.get("apk") or "").strip()
    miss = require_file(apk)
    if miss:
        return miss
    out, stats = ensure_cache(apk, bool(args.get("force")))
    stats["apk"] = os.path.abspath(apk)
    return stats


def tool_get_class(args):
    apk = (args.get("apk") or "").strip()
    cls = (args.get("class") or "").strip()
    miss = require_file(apk)
    if miss:
        return miss
    if not cls:
        return {"error": "class is required"}
    tmp = Path(tempfile.mkdtemp(prefix="jadx-single-"))
    try:
        proc = run_jadx(["--single-class", cls, "--single-class-output", str(tmp), apk])
        files = sorted(tmp.rglob("*.java"))
        if not files:
            log = (proc.stderr or proc.stdout).strip().splitlines()
            return {"error": f"no source for class {cls}", "log_tail": log[-5:]}
        src = files[0].read_text(encoding="utf-8", errors="replace")
        return {"class": cls, "source": src[:MAX_TEXT], "truncated": len(src) > MAX_TEXT}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def tool_search_code(args):
    apk = (args.get("apk") or "").strip()
    pattern = args.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return {"error": "pattern is required"}
    miss = require_file(apk)
    if miss:
        return miss
    max_hits = int(args.get("max_hits") or SEARCH_DEFAULT_MAX)
    out, stats = ensure_cache(apk)
    if "error" in stats:
        return stats
    sources = out / "sources"
    hits: list[dict] = []
    for path in sorted(sources.rglob("*.java")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for no, line in enumerate(lines, 1):
            if pattern in line:
                hits.append({"file": path.relative_to(sources).as_posix(),
                             "line": no, "text": line.strip()[:200]})
                if len(hits) >= max_hits:
                    return {"pattern": pattern, "hits": hits, "truncated": True}
    return {"pattern": pattern, "hits": hits, "truncated": False}


def tool_list_classes(args):
    apk = (args.get("apk") or "").strip()
    miss = require_file(apk)
    if miss:
        return miss
    flt = (args.get("filter") or "").lower()
    limit = int(args.get("limit") or LIST_DEFAULT_LIMIT)
    out, stats = ensure_cache(apk)
    if "error" in stats:
        return stats
    sources = out / "sources"
    out_paths: list[str] = []
    for path in sorted(sources.rglob("*.java")):
        rel = path.relative_to(sources).as_posix()[:-5]
        if flt and flt not in rel.lower():
            continue
        out_paths.append(rel)
        if len(out_paths) >= limit:
            break
    return {"classes": out_paths, "shown": len(out_paths)}


def tool_get_manifest(args):
    apk = (args.get("apk") or "").strip()
    miss = require_file(apk)
    if miss:
        return miss
    out, stats = ensure_cache(apk)
    if "error" in stats:
        return stats
    manifest = out / "resources" / "AndroidManifest.xml"
    if not manifest.is_file():
        return {"error": "AndroidManifest.xml not in decompiled resources"}
    text = manifest.read_text(encoding="utf-8", errors="replace")
    return {"manifest": text[:MAX_TEXT], "truncated": len(text) > MAX_TEXT}


HANDLERS = {
    "jadx_decompile": tool_decompile,
    "jadx_get_class": tool_get_class,
    "jadx_search_code": tool_search_code,
    "jadx_list_classes": tool_list_classes,
    "jadx_get_manifest": tool_get_manifest,
}


def dispatch(call_id, method, params):
    if method == "initialize":
        return {"protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if not handler:
            return {"error": {"code": -32601, "message": f"unknown tool '{name}'"}}
        try:
            payload = json.dumps(handler(arguments), indent=1)
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
            return {"error": {"code": -32000, "message": f"invalid input: {exc}"}}
        return {"content": [{"type": "text", "text": payload}]}
    if method.startswith("notifications/"):
        return None
    return {"error": {"code": -32601, "message": "method not found"}}


def main():
    if subprocess.run(["sh", "-c", f"command -v {JADX_BIN}"], capture_output=True).returncode != 0:
        sys.stderr.write(f"[jadx-mcp] jadx binary not found ({JADX_BIN}); set JADX_BIN\n")
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        call_id = message.get("id")
        method = message.get("method", "")
        if call_id is None:
            continue
        response = {"jsonrpc": "2.0", "id": call_id}
        result = dispatch(call_id, method, message.get("params") or {})
        if isinstance(result, dict) and "error" in result and "content" not in result:
            response.update(result)
        else:
            response["result"] = result
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
