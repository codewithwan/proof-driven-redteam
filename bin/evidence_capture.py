#!/usr/bin/env python3
"""evidence_capture: the single front door for capturing proof in an engagement.

Every dynamic probe MUST go through this tool so evidence is always a tool-generated
raw transcript (config.json: evidence.transcripts_tool_generated_only). Hand-written
evidence files are banned as proof; this tool makes them unnecessary.

Usage:
  python3 bin/evidence_capture.py <workspace> <finding-id> <method> <url> \
      [--header 'K: V']... [--data '...'] [--tag slug] [--note '...'] [--pacing 0.6]

Writes:
  <workspace>/evidence/raw/<finding-id>_<tag>.txt   full raw transcript
  <workspace>/evidence/raw/<finding-id>_<tag>.bin   byte-exact body (binary responses)
  regenerates <workspace>/evidence/raw/SHA256SUMS.txt

Exit codes: 0 captured; 2 usage error; 3 network/HTTP error recorded in transcript.
"""
import argparse
import hashlib
import http.client
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
from datetime import datetime, timezone

CTX = ssl.create_default_context()


def parse_header(s):
    if ":" not in s:
        raise argparse.ArgumentTypeError(f"header must be 'K: V', got: {s}")
    k, v = s.split(":", 1)
    return k.strip(), v.strip()


def capture(host, port, method, path, headers, body, timeout):
    """Perform one request, return (request_render, status, reason, resp_headers, resp_body)."""
    conn = http.client.HTTPSConnection(host, port, context=CTX, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return None, resp.status, resp.reason, resp.getheaders(), resp.read()
    except Exception as e:
        return None, "ERR", f"{type(e).__name__}: {e}"[:200], [], b""
    finally:
        conn.close()


def render_transcript(tag, note, ts_req, method, scheme, host, path, headers, body_bytes,
                      ts_resp, status, reason, resp_headers, resp_body, bin_relpath):
    lines = [
        f"CAPTURE TIME (UTC): {ts_req}",
        f"TOOL: evidence_capture.py (raw transcript; no manual edits)",
        f"NOTE: {note}" if note else "",
        "=== REQUEST (exactly as sent) ===",
        f"{method} {scheme}://{host}{path} HTTP/1.1",
        f"Host: {host}",
    ]
    lines += [f"{k}: {v}" for k, v in headers.items()]
    if body_bytes:
        lines += ["", "[request body] " + body_bytes.decode("utf-8", "replace")]
    lines += ["", f"=== RESPONSE (exactly as received, {ts_resp}) ===",
              f"HTTP/1.1 {status} {reason}"]
    lines += [f"{k}: {v}" for k, v in resp_headers]
    lines += [""]
    is_binary = any(b > 0x7e or (b < 0x20 and b not in (0x09, 0x0a, 0x0d)) for b in resp_body[:512])
    if is_binary and resp_body:
        lines += [
            f"[response body: BINARY, {len(resp_body)} bytes, saved byte-exact to {bin_relpath}]",
            f"[sha256 of body: {hashlib.sha256(resp_body).hexdigest()}]",
            "[first 256 bytes as hex dump]",
        ]
        hexhead = resp_body[:256].hex(" ")
        lines += ["  " + hexhead[i:i + 96] for i in range(0, len(hexhead), 96)]
    else:
        lines += ["[response body, verbatim]", resp_body.decode("utf-8", "replace")]
    lines += ["", f"[body sha256: {hashlib.sha256(resp_body).hexdigest()}]"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Raw evidence capture front door")
    ap.add_argument("workspace")
    ap.add_argument("finding_id")
    ap.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
    ap.add_argument("url")
    ap.add_argument("--header", type=parse_header, action="append", default=[])
    ap.add_argument("--data", default=None, help="request body (string)")
    ap.add_argument("--tag", default="probe", help="slug for the filename")
    ap.add_argument("--note", default="")
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--pacing", type=float, default=0.0, help="sleep after capture (seconds)")
    a = ap.parse_args()

    u = urllib.parse.urlsplit(a.url)
    if u.scheme != "https":
        print("refusing non-https URL (engagement policy: TLS only)", file=sys.stderr)
        return 2
    host, port = u.hostname, u.port or 443
    path = u.path + (("?" + u.query) if u.query else "")

    headers = dict(a.header)
    body = a.data.encode() if a.data is not None else None
    if body is not None and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    if body is not None and "Content-Length" not in headers:
        headers["Content-Length"] = str(len(body))

    raw_dir = os.path.join(a.workspace, "evidence", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    fname = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{a.finding_id}_{a.tag}")
    txt_path = os.path.join(raw_dir, fname + ".txt")
    bin_path = os.path.join(raw_dir, fname + ".bin")

    ts_req = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    _, status, reason, resp_headers, resp_body = capture(host, port, a.method, path, headers, body, a.timeout)
    ts_resp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    is_binary = any(b > 0x7e or (b < 0x20 and b not in (0x09, 0x0a, 0x0d)) for b in resp_body[:512])
    bin_rel = fname + ".bin"
    if is_binary and resp_body:
        with open(bin_path, "wb") as f:
            f.write(resp_body)
    transcript = render_transcript(fname, a.note, ts_req, a.method, "https", host, path,
                                   headers, body or b"", ts_resp, status, reason, resp_headers,
                                   resp_body, bin_rel)
    with open(txt_path, "w") as f:
        f.write(transcript)

    sums = os.path.join(raw_dir, "SHA256SUMS.txt")
    subprocess_hashes = []
    for fn in sorted(os.listdir(raw_dir)):
        if fn in ("SHA256SUMS.txt",) or fn.startswith("."):
            continue
        with open(os.path.join(raw_dir, fn), "rb") as f:
            subprocess_hashes.append(f"{hashlib.sha256(f.read()).hexdigest()}  {fn}")
    with open(sums, "w") as f:
        f.write("\n".join(subprocess_hashes) + "\n")

    print(f"[{fname}] HTTP {status} {len(resp_body)}B -> {fname}.txt{' + ' + bin_rel if is_binary and resp_body else ''}")
    if a.pacing:
        time.sleep(a.pacing)
    return 0 if status != "ERR" else 3


if __name__ == "__main__":
    sys.exit(main())
