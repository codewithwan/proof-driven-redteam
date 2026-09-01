#!/usr/bin/env python3
"""vigolium_leads: import vigolium findings into a workspace hypothesis queue.

Scanner output is LEADS, never evidence. Reads `vigolium finding -j` JSON (stdin or
--input file), appends deduped hypothesis-queue rows to <workspace>/FINDINGS.md with
new H-IDs continuing the existing numbering, and preserves severity, confidence,
CWE, and record_kind in the basis/detail lines for triage.

Usage:
    vigolium finding -j | python3 bin/vigolium_leads.py <workspace>
    python3 bin/vigolium_leads.py <workspace> --input findings.json
    python3 bin/vigolium_leads.py <workspace> --min-severity medium
    python3 bin/vigolium_leads.py --check     # self-test on synthetic data
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
FINDINGS_FILE = "FINDINGS.md"
MAX_SUMMARY = 160


def severity_rank(sev: str) -> int:
    sev = (sev or "").lower()
    return SEVERITY_ORDER.index(sev) if sev in SEVERITY_ORDER else len(SEVERITY_ORDER)


def load_findings(data) -> list[dict]:
    """Accept {"findings":[...]}, a bare list, or {"data":[...]} for forward compat."""
    if isinstance(data, list):
        return [f for f in data if isinstance(f, dict)]
    if isinstance(data, dict):
        for key in ("findings", "data", "results"):
            items = data.get(key)
            if isinstance(items, list):
                return [f for f in items if isinstance(f, dict)]
    return []


def clean(text, limit=0) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).replace("|", "/").strip()
    return text[:limit] if limit else text


def dedup_key(f: dict) -> str:
    raw = "|".join(clean(f.get(k)) for k in ("hostname", "module_id", "url"))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def next_h_id(content: str) -> int:
    ids = [int(m) for m in re.findall(r"\bH-(\d+)\b", content)]
    return (max(ids) + 1) if ids else 1


def vigolium_id(f: dict) -> str:
    # module_id is NOT per-finding unique; fall back to the tuple key, not module_id
    return clean(f.get("id")) if f.get("id") else ""


def build_rows(findings: list[dict], existing: str, min_rank: int):
    """Split into (new, skipped_dup, skipped_sev) with dedup markers appended."""
    seen_ids = set(re.findall(r"\[VG:([^\]]+)\]", existing))
    seen_keys = set(re.findall(r"vigolium-dedup:([a-f0-9]+)", existing))
    new, dup, sev = [], 0, 0
    for f in findings:
        key = dedup_key(f)
        vid = vigolium_id(f) or key
        if vid in seen_ids or key in seen_keys:
            dup += 1
            continue
        if severity_rank(f.get("severity")) > min_rank:
            sev += 1
            continue
        new.append((f, vid, key))
    return new, dup, sev


def import_lines(new: list, existing: str, workspace: Path, dup: int, sev: int) -> tuple[list, int]:
    """Render the appended section; returns (lines, next H id cursor)."""
    round_no = len(re.findall(r"^## Round\b", existing, flags=re.M)) + 1
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    h = next_h_id(existing)
    rows, details, markers = [], [], []
    for f, vid, key in new:
        basis = " ".join(x for x in [
            "vigolium",
            clean(f.get("module_name") or f.get("module_id")),
            f"{clean(f.get('severity')) or '?'}/{clean(f.get('confidence')) or '?'}",
            f"on {clean(f.get('hostname')) or clean(f.get('url')) or '?'}",
        ] if x and x != "vigolium")
        rows.append(f"| H-{h:03d} | [VG:{vid}] {clean(f.get('short') or 'untitled', 120)} "
                    f"| {basis} | QUEUED | |")
        details.append(
            f"- H-{h:03d} [VG:{vid}]: url={clean(f.get('url')) or '-'} "
            f"cwe={clean(f.get('cwe_id')) or '-'} kind={clean(f.get('record_kind')) or '-'} "
            f"grade={clean(f.get('evidence_grade')) or '-'} "
            f"found={clean(f.get('found_at')) or '-'}")
        desc = clean(f.get("description"), MAX_SUMMARY)
        if desc:
            details.append(f"  summary: {desc}")
        markers.append(f"<!-- vigolium-dedup:{key} -->")
        h += 1

    lines = [
        f"## Round {round_no} - vigolium lead import ({date})",
        "",
        "- Signal: vigolium output imported as hypothesis-queue leads (scanner output is never evidence)",
        f"- Import: {len(new)} imported, {dup} duplicate(s) skipped, {sev} below severity floor",
        "- Queue entries start QUEUED; promote to TESTING only through the PLAN gate (workflow.md)",
        "",
        *markers,
        "",
        "### Hypothesis queue (vigolium import)",
        "| ID | Hypothesis | Basis | State | Outcome |",
        "|----|-----------|-------|-------|---------|",
        *rows,
        "",
        "Details:",
        *details,
        "",
    ]
    return lines, h


def run_import(workspace: Path, findings: list[dict], min_rank: int) -> dict:
    target = workspace / FINDINGS_FILE
    if not target.is_file():
        raise SystemExit(f"not a workspace (missing {FINDINGS_FILE}): {workspace}")
    existing = target.read_text(encoding="utf-8")
    new, dup, sev = build_rows(findings, existing, min_rank)
    lines, _ = import_lines(new, existing, workspace, dup, sev)
    with target.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"imported": len(new), "duplicates": dup, "below_floor": sev}


def read_input(path: str) -> list[dict]:
    if path in ("-", ""):
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    if not raw.strip():
        return []
    return load_findings(json.loads(raw))


def check() -> int:
    """Self-test: synthetic workspace, import twice, assert dedup and H-id growth."""
    import tempfile

    synthetic = [
        {"id": "f-001", "severity": "high", "confidence": "firm",
         "short": "Reflected XSS in search", "module_name": "xss-reflected",
         "module_id": "xss-reflected", "hostname": "app.example.com",
         "url": "https://app.example.com/search", "cwe_id": "CWE-79",
         "record_kind": "finding", "evidence_grade": "captured",
         "found_at": "2026-01-01T00:00:00Z", "description": "payload reflected"},
        {"id": "f-002", "severity": "critical", "confidence": "certain",
         "short": "SQLi in login", "module_name": "sqli-error", "module_id": "sqli-error",
         "hostname": "app.example.com", "url": "https://app.example.com/login",
         "cwe_id": "CWE-89", "record_kind": "finding", "evidence_grade": "captured",
         "found_at": "2026-01-01T00:00:00Z", "description": "error-based sqli"},
    ]
    with tempfile.TemporaryDirectory(prefix="vigolium-leads-check-") as tmp:
        ws = Path(tmp)
        (ws / FINDINGS_FILE).write_text(
            "# FINDINGS.md - test\n\n## Round 1 - initial\n\n"
            "| H-001 | existing hypothesis | static | DEAD | |\n", encoding="utf-8")
        first = run_import(ws, synthetic, severity_rank("info"))
        second = run_import(ws, synthetic, severity_rank("info"))
        content = (ws / FINDINGS_FILE).read_text(encoding="utf-8")
        assert first["imported"] == 2, first
        assert second == {"imported": 0, "duplicates": 2, "below_floor": 0}, second
        assert "H-002" in content and "H-003" in content and "[VG:f-001]" in content
        assert content.count("| H-002 |") == 1, "H-002 must appear exactly once"
        low = run_import(ws, [{**synthetic[0], "id": "f-003", "severity": "info",
                               "url": "https://app.example.com/legacy",
                               "module_id": "info-leak", "module_name": "info-leak"}],
                         severity_rank("medium"))
        assert low == {"imported": 0, "duplicates": 0, "below_floor": 1}, low
    print("self-check PASS: import, dedup by id, severity floor, H-id continuation")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="import vigolium findings as hypothesis-queue leads")
    ap.add_argument("workspace", nargs="?", help="engagement workspace dir (contains FINDINGS.md)")
    ap.add_argument("--input", default="-", help="JSON file path or - for stdin (default)")
    ap.add_argument("--min-severity", default="info",
                    choices=SEVERITY_ORDER, help="severity floor (default: import all)")
    ap.add_argument("--check", action="store_true", help="run the self-test and exit")
    args = ap.parse_args()

    if args.check:
        return check()
    if not args.workspace:
        ap.error("workspace is required (or pass --check)")

    findings = read_input(args.input)
    if not findings:
        print("no findings in input; nothing to do")
        return 0
    summary = run_import(Path(args.workspace), findings, severity_rank(args.min_severity))
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
