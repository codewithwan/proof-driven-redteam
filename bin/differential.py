#!/usr/bin/env python3
"""differential: run the deep-chain gate #1 (parameter semantics, 3-way) via evidence_capture.

For each URL template parameter you mark, fires three requests — valid value, garbage
value, empty value — captures all three as raw evidence through evidence_capture.py,
and prints the differential verdict:

  IDENTICAL  → parameter ignored by the server (impact multiplier — sweep its cardinality)
  FILTERED   → response differs by value (the parameter does something; chain via values)
  MIXED      → empty/garbage rejected, valid accepted (parameter validated)

Usage:
  python3 bin/differential.py <workspace> <finding-id> <url-with-{param}> \
      --valid <value> [--header 'K: V']... [--data '...'] [--tag slug]

Example:
  python3 bin/differential.py <workspace> <finding-id> \
      'https://api.example/v1/things/?sid=CITY&sub={sub}&seq=1' --valid <valid-sub-value>
The {param} placeholder is replaced per probe; all three runs land in evidence/raw/.
"""
import argparse
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CAPTURE = os.path.join(HERE, "evidence_capture.py")


def size_of(workspace, finding, tag):
    raw = os.path.join(workspace, "evidence", "raw")
    for ext in (".bin", ".txt"):
        p = os.path.join(raw, f"{finding}_{tag}{ext}")
        if os.path.exists(p):
            return os.path.getsize(p)
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("finding_id")
    ap.add_argument("url")
    ap.add_argument("--valid", required=True, help="valid value for the {param}")
    ap.add_argument("--header", action="append", default=[])
    ap.add_argument("--data", default=None)
    ap.add_argument("--tag", default="param")
    ap.add_argument("--param", default="sub")
    a = ap.parse_args()

    if "{%s}" % a.param not in a.url:
        print(f"url must contain {{{a.param}}} placeholder", file=sys.stderr)
        return 2

    variants = [
        ("valid", a.valid),
        ("garbage", "GARBAGECONTROL"),
        ("empty", ""),
    ]
    results = {}
    for name, value in variants:
        url = a.url.replace("{%s}" % a.param, value)
        tag = f"{a.tag}_{name}"
        cmd = [sys.executable, CAPTURE, a.workspace, a.finding_id, "GET", url,
               "--tag", tag, "--note", f"[differential {a.param}={name}]"]
        for h in a.header:
            cmd += ["--header", h]
        if a.data:
            cmd += ["--data", a.data]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr or r.stdout)
            return 3
        results[name] = size_of(a.workspace, a.finding_id, tag)
        print(r.stdout.strip())

    sizes = {k: v for k, v in results.items()}
    if sizes["valid"] == sizes["garbage"] == sizes["empty"] and sizes["valid"] > 0:
        verdict = "IDENTICAL — parameter IGNORED by server: impact multiplies by its cardinality (sweep values, bounded)"
    elif sizes["garbage"] == sizes["empty"] and sizes["valid"] != sizes["garbage"]:
        verdict = "VALIDATED — empty/garbage treated alike, valid differs: parameter enforced"
    else:
        verdict = "MIXED — response differs across variants: parameter FILTERS (chain via its values)"
    print(f"\ndifferential[{a.param}]: sizes {sizes}")
    print(f"verdict: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
