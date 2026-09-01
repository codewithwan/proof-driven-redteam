#!/usr/bin/env python3
"""Burp Suite MCP bridge (stdio client to Burp's built-in MCP server).

Burp Suite Professional ships a native MCP server using the SSE transport
(GET stream for server messages, POST for client messages). Many agents only
speak stdio MCP, so this script is a transparent proxy: JSON-RPC lines on
stdin are POSTed to Burp's session endpoint, and SSE messages from Burp are
written back to stdout. No Burp tool knowledge is hardcoded: whatever Burp
exposes flows through (raw HTTP sender, Repeater and Intruder tabs,
Collaborator payloads and interactions, scanner issues, proxy history,
encoders, options).

Burp side: enable the MCP server in Burp, default http://127.0.0.1:9876.
Point any stdio MCP client at this script, e.g. for opencode:

{
  "mcp": {
    "burp": { "type": "local",
              "command": ["python3", "<repo>/tools/mcp/burp/server.py"],
              "enabled": true }
  }
}

BURP_MCP_URL environment variable overrides the default URL.

Methodology fit (proof gate):
- send_http1_request / send_http2_request: the raw request and raw response
  transcript IS the evidence block, captured from the same Burp engine used
  by hand, so dynamic probes through Burp satisfy the raw-pairs rule.
- generate_collaborator_payload + get_collaborator_interactions: out-of-band
  proof (SSRF, blind injection, callback reachability).
- get_scanner_issues: scanner output is a LEAD, never a finding.
- create_repeater_tab: hand the raw request to the human for manual verdicts.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from urllib.parse import urljoin

DEFAULT_URL = "http://127.0.0.1:9876"
BURP_URL = os.environ.get("BURP_MCP_URL", DEFAULT_URL).rstrip("/")

endpoint_holder: dict[str, str] = {}
endpoint_ready = threading.Event()


def sse_loop() -> None:
    """Read Burp's SSE stream forever, forward JSON messages to stdout."""
    req = urllib.request.Request(BURP_URL + "/", headers={"Accept": "text/event-stream"})
    try:
        stream = urllib.request.urlopen(req)  # no timeout: stream stays open
    except (urllib.error.URLError, OSError) as exc:
        sys.stderr.write(f"[burp-mcp] cannot reach Burp at {BURP_URL}: {exc}\n")
        sys.exit(1)

    event_name = ""
    for raw in stream:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = line.split(":", 1)[1].strip()
            if event_name == "endpoint":
                # First event: Burp hands out the POST endpoint (sessionId).
                endpoint_holder["url"] = urljoin(BURP_URL + "/", data)
                endpoint_ready.set()
            elif data.startswith("{"):
                sys.stdout.write(data + "\n")
                sys.stdout.flush()
        elif line == "":
            event_name = ""
    # ponytail: no SSE reconnect; if Burp closes the stream the bridge exits
    # and the MCP client restarts it (a fresh session is created on restart).
    sys.stderr.write("[burp-mcp] SSE stream closed\n")
    os._exit(1)


def post_line(line: str) -> None:
    """POST one JSON-RPC line to Burp, forward the result as JSON-RPC error."""
    url = endpoint_holder["url"]
    req = urllib.request.Request(
        url,
        data=line.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()  # Burp answers 202 Accepted; real reply comes via SSE
            if resp.status >= 400:
                raise OSError(f"HTTP {resp.status}")
            return
    except (urllib.error.URLError, OSError) as exc:
        sys.stderr.write(f"[burp-mcp] POST failed: {exc}\n")
        try:
            msg = json.loads(line)
            if msg.get("id") is not None:
                err = {"jsonrpc": "2.0", "id": msg["id"],
                       "error": {"code": -32000, "message": f"burp bridge: {exc}"}}
                sys.stdout.write(json.dumps(err) + "\n")
                sys.stdout.flush()
        except (ValueError, KeyError):
            pass


def stdin_loop() -> None:
    """Forward stdin JSON-RPC lines to Burp once the endpoint is known."""
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        if not endpoint_ready.wait(timeout=60):
            sys.stderr.write("[burp-mcp] no endpoint from Burp within 60s\n")
            os._exit(1)
        post_line(line)


def main() -> None:
    threading.Thread(target=stdin_loop, daemon=True).start()
    sse_loop()  # runs on the main thread until the stream ends


if __name__ == "__main__":
    main()
