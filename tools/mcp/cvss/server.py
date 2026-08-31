#!/usr/bin/env python3
"""
server.py -- Offline CVSS v3.1 scoring MCP server (stdio transport).

Zero-dependency. Implements the FIRST CVSS v3.1 specification:
base + temporal-free environmental metrics, Scope Changed math,
and the specification rounding rule (roundup to 1 decimal).

MCP tools:
  cvss31_score(vector | metrics) -> score, severity, breakdown
  cvss31_batch([vector, ...])    -> table of results
  cvss31_explain(vector)         -> human-readable metric explanations

Protocol: newline-delimited JSON-RPC 2.0 over stdio (MCP stdio transport).
Tested against Claude Code / OpenCode / any MCP stdio client.
"""

import json
import math
import sys

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "cvss-offline", "version": "1.0.0"}

AV_W = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
AC_W = {"L": 0.77, "H": 0.44}
PR_W_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
PR_W_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.50}
UI_W = {"N": 0.85, "R": 0.62}
CIA_W = {"H": 0.56, "L": 0.22, "N": 0.00}
AR_W = {"H": 1.0, "M": 1.0, "L": 0.5}          # CR/IR/AR requirement weights
ENV_PREFIX = ("E", "RL", "RC")

BASE_KEYS = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
ENV_KEYS = ["CR", "IR", "AR",
            "MAV", "MAC", "MPR", "MUI", "MS", "MC", "MI", "MA"]

METRIC_NAMES = {
    "AV": "Attack Vector", "AC": "Attack Complexity",
    "PR": "Privileges Required", "UI": "User Interaction",
    "S": "Scope", "C": "Confidentiality", "I": "Integrity",
    "A": "Availability", "CR": "Confidentiality Requirement",
    "IR": "Integrity Requirement", "AR": "Availability Requirement",
}


def roundup1(x):
    """CVSS specification rounding: smallest 1-decimal >= value."""
    return math.ceil(round(x * 10, 6)) / 10.0


def parse_vector(vector):
    raw = vector.strip()
    if raw.upper().startswith("CVSS:"):
        parts = raw.split("/")[1:]
    else:
        parts = raw.split("/")
    out = {}
    for p in parts:
        if ":" not in p:
            raise ValueError(f"malformed metric '{p}'")
        k, v = p.split(":", 1)
        k, v = k.strip().upper(), v.strip().upper()
        if not k or not v:
            raise ValueError(f"malformed metric '{p}'")
        out[k] = v
    return out


def _w(group, value):
    try:
        return group[value]
    except KeyError:
        raise ValueError(f"invalid metric value '{value}'")


def score_cvss31(metrics):
    """Full CVSS v3.1 base (+environmental when present) computation."""
    m = dict(metrics)

    missing_base = [k for k in BASE_KEYS if k not in m or not m[k]]
    if missing_base:
        raise ValueError(f"missing required base metrics: {', '.join(missing_base)}")

    scope_changed = m["S"] == "C"

    def eff(key, base_group):
        """Effective weight for a metric honoring its Modified override."""
        mod = m.get("M" + key)
        if mod:
            return mod, True
        return m[key], False

    av, _ = eff("AV", AV_W)
    ac, _ = eff("AC", AC_W)
    pr_v, _ = eff("PR", {})
    ui, _ = eff("UI", UI_W)
    ms = m.get("MS", m["S"])
    changed_scope = ms == "C"

    c, _ = eff("C", CIA_W)
    i, _ = eff("I", CIA_W)
    a, _ = eff("A", CIA_W)

    exploitability = (8.22 * _w(AV_W, av) * _w(AC_W, ac)
                      * _w(PR_W_CHANGED if changed_scope else PR_W_UNCHANGED, pr_v)
                      * _w(UI_W, ui))

    isc = min(1 - (1 - _w(CIA_W, c)) * (1 - _w(CIA_W, i)) * (1 - _w(CIA_W, a)), 0.915)

    cr = AR_W.get(m.get("CR", "H"), 1.0)
    ir = AR_W.get(m.get("IR", "H"), 1.0)
    ar = AR_W.get(m.get("AR", "H"), 1.0)

    if changed_scope:
        isc_p = min(1 - (1 - isc * cr) * (1 - isc * ir) * (1 - isc * ar), 0.915)
        impact = min(7.52 * (isc_p - 0.029) - 3.25 * ((isc_p - 0.02) ** 15), 10)
    else:
        impact = 6.42 * min(
            1 - (1 - _w(CIA_W, c) * cr) * (1 - _w(CIA_W, i) * ir) * (1 - _w(CIA_W, a) * ar),
            0.915)

    if impact <= 0:
        return {"score": 0.0, "severity": "None", "impact": 0.0,
                "exploitability": 0.0}

    base_score = roundup1(min(impact + exploitability, 10))
    if base_score < 4:
        severity = "Low"
    elif base_score < 7:
        severity = "Medium"
    elif base_score < 9:
        severity = "High"
    else:
        severity = "Critical"

    return {
        "score": base_score,
        "severity": severity,
        "impact": round(impact, 3),
        "exploitability": round(exploitability, 3),
        "scope_effective": ms,
    }


def build_vector(metrics):
    keys = BASE_KEYS + ENV_KEYS
    return "/".join(f"{k}:{metrics[k]}" for k in keys if k in metrics and metrics[k])


def normalize(metrics):
    cleaned = {}
    for k, v in metrics.items():
        k = str(k).strip().upper().lstrip("/")
        v = str(v).strip().upper()
        if k in BASE_KEYS + ENV_KEYS and v:
            cleaned[k] = v
    return cleaned


def tool_score(args):
    if args.get("vector"):
        metrics = parse_vector(args["vector"])
    else:
        metrics = normalize(args.get("metrics") or args)
    result = score_cvss31(metrics)
    result["vector"] = build_vector(metrics)
    result["qualitative_severity"] = result.pop("severity")
    return result


def tool_batch(args):
    vectors = args.get("vectors") or []
    rows = []
    for v in vectors:
        try:
            r = score_cvss31(parse_vector(v))
            rows.append({"vector": build_vector(parse_vector(v)),
                         "score": r["score"], "severity": r["severity"]})
        except ValueError as exc:
            rows.append({"vector": v, "error": str(exc)})
    rows.sort(key=lambda r: -r.get("score", 0))
    return {"count": len(rows), "results": rows}


def tool_explain(args):
    vector = args.get("vector")
    if not vector:
        raise ValueError("'vector' is required")
    metrics = parse_vector(vector)
    lines = ["CVSS v3.1 metric breakdown:", ""]
    for k in BASE_KEYS + [k for k in ENV_KEYS if k in metrics]:
        if k not in metrics:
            continue
        name = METRIC_NAMES.get(k, k)
        lines.append(f"  {k}:{metrics[k]}  {name}")
        if k == "S":
            lines[-1] += " (Changed = impact may propagate to other authorities)"
        elif k == "AV":
            lines[-1] += {"N": " (network-reachable)", "A": " (adjacent network)",
                          "L": " (local access)", "P": " (physical)"}.get(metrics[k], "")
    result = score_cvss31(metrics)
    lines += ["", f"Base score : {result['score']} ({result['severity']})",
              f"Impact sub-score       : {result['impact']}",
              f"Exploitability sub-score: {result['exploitability']}"]
    bands = "None <0.1 | Low 0.1-3.9 | Medium 4.0-6.9 | High 7.0-8.9 | Critical 9.0-10"
    lines.append(f"Severity bands: {bands}")
    return "\n".join(lines)


TOOLS = [
    {
        "name": "cvss31_score",
        "description": (
            "Calculate a CVSS v3.1 score (FIRST specification) from a vector "
            "string or from individual metrics. Supports Scope Changed math "
            "and Environmental metrics (CR/IR/AR + MAV/MAC/MPR/MUI/MS/MC/MI/MA). "
            "Returns the score, qualitative severity and sub-scores."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vector": {"type": "string",
                           "description": "CVSS v3.1 vector, e.g. AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:L"},
                "metrics": {"type": "object",
                            "description": "Alternative: metric map e.g. {\"AV\":\"N\",\"AC\":\"L\",...,\"MC\":\"L\"}"},
            },
        },
    },
    {
        "name": "cvss31_batch",
        "description": "Score many CVSS v3.1 vectors at once, sorted highest first.",
        "inputSchema": {
            "type": "object",
            "properties": {"vectors": {"type": "array", "items": {"type": "string"}}},
            "required": ["vectors"],
        },
    },
    {
        "name": "cvss31_explain",
        "description": "Explain every metric of a CVSS v3.1 vector in plain language.",
        "inputSchema": {
            "type": "object",
            "properties": {"vector": {"type": "string"}},
            "required": ["vector"],
        },
    },
]

HANDLERS = {
    "cvss31_score": tool_score,
    "cvss31_batch": tool_batch,
    "cvss31_explain": tool_explain,
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
            return {"error": {"code": -32601,
                              "message": f"unknown tool '{name}'"}}
        try:
            payload = json.dumps(handler(arguments), indent=1)
        except (ValueError, KeyError) as exc:
            return {"error": {"code": -32000,
                              "message": f"invalid input: {exc}"}}
        return {"content": [{"type": "text", "text": payload}]}
    if method.startswith("notifications/"):
        return None
    return {"error": {"code": -32601, "message": "method not found"}}


def main():
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
