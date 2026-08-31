#!/usr/bin/env python3
"""
server.py -- Offline-friendly Shodan REST MCP server (stdio transport).

Zero-dependency. Wraps api.shodan.io endpoints with graceful handling of
membership-gated responses (free 'oss' plan returns an error for most
data endpoints; this surfaces that as a clean tool result instead of a crash).

MCP tools:
  shodan_api_info   -> account/plan/credits (works on every plan)
  shodan_host       -> host lookup by IP          [membership required]
  shodan_search     -> host search by query       [membership required]
  shodan_count      -> result count for a query   [membership required]
  shodan_dns_domain -> subdomains for a domain    [membership required]
"""

import json
import sys
import urllib.request
import urllib.parse
import urllib.error

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "shodan-lite", "version": "1.0.0"}
BASE = "https://api.shodan.io"
API_KEY = None


def _get(path, params=None):
    params = dict(params or {})
    params["key"] = API_KEY
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "mcp-shodan-lite"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {"error": f"HTTP {exc.code}"}
    except Exception as exc:
        return -1, {"error": str(exc)[:150]}


def _fmt_host(data):
    lines = [
        f"IP        : {data.get('ip_str')} ({data.get('org','?')}, "
        f"{data.get('country_name','?')})",
        f"Hostnames : {', '.join((data.get('hostnames') or [])[:10])}",
        f"Ports     : {data.get('ports')}",
        f"Last seen : {data.get('last_update')}",
    ]
    for banner in (data.get("data") or [])[:8]:
        product = banner.get("product") or banner.get("_shodan", {}).get("module", "?")
        version = banner.get("version", "")
        cpe = ",".join(banner.get("cpe", [])[:3])
        vulns = list((banner.get("vulns") or {}).keys())[:6]
        lines.append(f"  [{banner.get('port')}] {product} {version}"
                     + (f" | CPE: {cpe}" if cpe else "")
                     + (f" | vulns: {', '.join(vulns)}" if vulns else ""))
    return "\n".join(lines)


def t_api_info(_args):
    st, data = _get("/api-info")
    if isinstance(data, dict) and "plan" in data:
        return (f"plan={data.get('plan')} query_credits={data.get('query_credits')} "
                f"scan_credits={data.get('scan_credits')} monitored_ips="
                f"{data.get('monitored_ips')}\nNOTE: search/host/dns endpoints "
                "require a paid membership on Shodan; the free 'oss' plan only "
                "exposes this endpoint.")
    return json.dumps(data, indent=1)


def t_host(args):
    ip = args.get("ip")
    if not ip:
        raise ValueError("'ip' is required")
    st, data = _get(f"/shodan/host/{ip}", {"minify": "true"})
    if isinstance(data, dict) and "error" in data:
        return f"Shodan API error ({st}): {data['error']}\nTip: host lookups need a paid membership."
    return _fmt_host(data)


def t_search(args):
    q = args.get("query")
    if not q:
        raise ValueError("'query' is required")
    st, data = _get("/shodan/host/search", {"query": q, **{
        k: str(v) for k, v in args.items() if k in ("facets", "page")}})
    if isinstance(data, dict) and "error" in data:
        return f"Shodan API error ({st}): {data['error']}"
    out = [f"total matches: {data.get('total')}"]
    for m in (data.get("matches") or [])[:10]:
        out.append(f"  {m.get('ip_str')}:{m.get('port')} {m.get('product','?')} "
                   f"{m.get('version','')} | {m.get('hostnames',[])[:3]} | "
                   f"{m.get('location',{}).get('country_name','?')}")
    return "\n".join(out)


def t_count(args):
    q = args.get("query")
    if not q:
        raise ValueError("'query' is required")
    st, data = _get("/shodan/host/count", {"query": q})
    if isinstance(data, dict) and "error" in data:
        return f"Shodan API error ({st}): {data['error']}"
    return f"total matches: {data.get('total')}"


def t_dns_domain(args):
    domain = args.get("domain")
    if not domain:
        raise ValueError("'domain' is required")
    st, data = _get(f"/dns/domain/{domain}")
    if isinstance(data, dict) and "error" in data:
        return f"Shodan API error ({st}): {data['error']}"
    subs = []
    for name, entries in sorted((data.get("subdomains") and {
            s: [] for s in data["subdomains"]}).items())[:100]:
        subs.append(f"{name}.{domain}")
    return "\n".join(subs) or "(empty)"


TOOLS = [
    {"name": "shodan_api_info",
     "description": "Account info: plan, query/scan credits. Works on every plan.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "shodan_host",
     "description": "Lookup everything Shodan knows about one IP: ports, banners, products, vulns. Requires paid membership.",
     "inputSchema": {"type": "object",
                     "properties": {"ip": {"type": "string"}},
                     "required": ["ip"]}},
    {"name": "shodan_search",
     "description": "Search Shodan index by query string (e.g. 'ssl.cert.subject.CN:example.com'). Requires paid membership.",
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string"},
                                    "page": {"type": "string"}},
                     "required": ["query"]}},
    {"name": "shodan_count",
     "description": "Count results for a query without fetching banners. Requires paid membership.",
     "inputSchema": {"type": "object",
                     "properties": {"query": {"type": "string"}},
                     "required": ["query"]}},
    {"name": "shodan_dns_domain",
     "description": "Enumerate known subdomains for a domain. Requires paid membership.",
     "inputSchema": {"type": "object",
                     "properties": {"domain": {"type": "string"}},
                     "required": ["domain"]}},
]

HANDLERS = {
    "shodan_api_info": t_api_info,
    "shodan_host": t_host,
    "shodan_search": t_search,
    "shodan_count": t_count,
    "shodan_dns_domain": t_dns_domain,
}


def dispatch(method, params):
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
        handler = HANDLERS.get(name)
        if not handler:
            return {"error": {"code": -32601,
                              "message": f"unknown tool '{name}'"}}
        global API_KEY
        API_KEY = (params.get("arguments") or {}).pop("_key", None) or API_KEY
        try:
            text = handler(params.get("arguments") or {})
        except ValueError as exc:
            return {"error": {"code": -32000, "message": f"invalid input: {exc}"}}
        return {"content": [{"type": "text", "text": str(text)}]}
    if method.startswith("notifications/"):
        return None
    return {"error": {"code": -32601, "message": "method not found"}}


def main():
    global API_KEY
    import os
    API_KEY = os.environ.get("SHODAN_API_KEY")
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        call_id = message.get("id")
        if call_id is None:
            continue
        response = {"jsonrpc": "2.0", "id": call_id}
        result = dispatch(message.get("method", ""), message.get("params") or {})
        if isinstance(result, dict) and "error" in result and "content" not in result:
            response.update(result)
        else:
            response["result"] = result
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
