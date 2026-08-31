#!/usr/bin/env python3
"""impact_parser: quantify impact from captured raw evidence (data-driven severity input).

Parses a captured evidence body (JSON or a delimited binary blob) and emits the
impact-quantification block mandated by workflow.md: record count, field population,
freshness (newest/oldest timestamps), distinct-value scale for identifier fields.

Binary mode: supply a record schema as field specs (see --field). Length-prefixed
strings are the common shape in compact wire formats; fixed types supported:
  s:<name>            u8 length-prefixed utf-8 string
  u32:<name> i32:<name> u8:<name> u16:<name>   little-endian integers
  f32:<name> f64:<name>                          little-endian floats

Usage:
  python3 bin/impact_parser.py <evidence.bin|evidence.json> [--field s:vehicle_no ...] \
      [--timestamp-field date_epoch] [--pii customer_name customer_code] [--json]

Output: human-readable quantification block (or JSON with --json) ready to paste into
FINDINGS.md. Numbers only — severity framing stays with the operator.
"""
import argparse
import json
import struct
import sys
from datetime import datetime, timezone

INT_TYPES = {"u8": (1, "<B"), "u16": (2, "<H"), "u32": (4, "<I"), "i32": (4, "<i"),
             "f32": (4, "<f"), "f64": (8, "<d")}


def parse_schema(specs):
    out = []
    for s in specs:
        t, _, name = s.partition(":")
        if not name or (t not in INT_TYPES and t != "s"):
            raise SystemExit(f"bad field spec: {s} (use s:name | " + " | ".join(INT_TYPES) + ")")
        out.append((t, name))
    return out


def parse_binary(buf, schema):
    recs, n = [], 0
    while n < len(buf):
        try:
            rec, m = {}, n
            for t, name in schema:
                if t == "s":
                    ln = buf[m]; m += 1
                    rec[name] = buf[m:m + ln].decode("utf-8", "replace"); m += ln
                else:
                    size, fmt = INT_TYPES[t]
                    rec[name] = struct.unpack_from(fmt, buf, m)[0]; m += size
            recs.append(rec); n = m
        except Exception:
            break
    return recs


def quantify(recs, ts_field, pii_fields):
    q = {"record_count": len(recs)}
    if not recs:
        return q
    fields = sorted(set().union(*(r.keys() for r in recs)))
    pop = {}
    for f in fields:
        c = sum(1 for r in recs if r.get(f) not in (None, "", 0))
        pop[f] = {"populated": c, "percent": round(100.0 * c / len(recs), 1)}
    q["field_population"] = pop
    if ts_field and ts_field in recs[0]:
        eps = sorted(r[ts_field] for r in recs if isinstance(r.get(ts_field), (int, float)))
        if eps:
            q["freshness"] = {
                "newest": datetime.fromtimestamp(max(eps), tz=timezone.utc).isoformat(),
                "oldest": datetime.fromtimestamp(min(eps), tz=timezone.utc).isoformat(),
            }
    for f in pii_fields:
        if f in pop:
            pop[f]["pii"] = True
    idscale = {}
    for f in fields:
        vals = {json.dumps(r.get(f), default=str) for r in recs}
        if len(vals) > 1 and len(vals) >= len(recs) * 0.5:
            idscale[f] = len(vals)
    if idscale:
        q["distinct_value_scale"] = idscale
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="evidence body file (.json or binary)")
    ap.add_argument("--field", action="append", default=[])
    ap.add_argument("--timestamp-field", dest="timestamp_field", default=None)
    ap.add_argument("--pii", default=[], help="comma-separated PII field names")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    a.pii = [p for p in a.pii.split(",") if p] if isinstance(a.pii, str) else a.pii

    raw = open(a.path, "rb").read()
    if a.path.endswith(".json"):
        try:
            data = json.loads(raw)
            recs = data if isinstance(data, list) else data.get("data", data.get("rows", [data]))
            if isinstance(recs, dict):
                recs = [recs]
        except Exception:
            recs = []
    elif a.field:
        recs = parse_binary(raw, parse_schema(a.field))
    else:
        print("binary body needs --field schema (s:name, u32:name, f32:name, ...)", file=sys.stderr)
        return 2
    q = quantify(recs, a.timestamp_field, a.pii)

    if a.json:
        print(json.dumps(q, indent=1))
    else:
        print(f"### Impact quantification (impact_parser, source: {a.path})")
        print(f"- Record count: {q['record_count']}")
        for f, st in sorted(q.get("field_population", {}).items()):
            tag = " [PII]" if st.get("pii") else ""
            print(f"- {f}{tag}: {st['populated']}/{q['record_count']} populated ({st['percent']}%)")
        if "freshness" in q:
            print(f"- Freshness: newest {q['freshness']['newest']}, oldest {q['freshness']['oldest']}")
        for f, c in sorted(q.get("distinct_value_scale", {}).items(), key=lambda x: -x[1]):
            print(f"- Distinct values [{f}]: {c} (identifier-grade scale)")
        print("- Severity input: cite these measured numbers in the CVSS justification "
              "(config cvss_from_measured_impact); framing stays with the operator.")
    return 0 if q["record_count"] else 1


if __name__ == "__main__":
    sys.exit(main())
