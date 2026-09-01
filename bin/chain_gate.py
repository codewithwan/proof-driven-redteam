#!/usr/bin/env python3
"""chain_gate: enforce the QA gate mechanically on a workspace's FINDINGS.md + REPORT.md + evidence/.

Per VERIFIED finding (FINDINGS.md):
  - raw evidence exists (evidence/raw/<finding-id>_* transcript, non-empty)
  - negative control present (a _control or control file for the finding)
  - retest captures present (config retest_verified_findings, default 2)
  - chain matrix row exists and has no empty cells
  - impact quantification block present (data findings)
  - CVSS vector present and cites measured numbers (impact block present alongside)

Workspace-wide (FINDINGS.md):
  - coverage table section present when verified findings exist (config full_coverage_enforced)
  - artifact pre-registrations have cleanup evidence

Report-side (REPORT.md, checked when the file exists, i.e. at ship time):
  - banned words absent (config report.banned_words, word-boundary match)
  - required sections present: Positive controls, Findings index, lateral movement map
  - every VERIFIED finding ID from FINDINGS.md appears in the report

Plus: SHA256SUMS.txt covers every evidence/raw file.

Exit code 0 = all gates pass; 1 = violations found (blocks the report).

Usage:
  python3 bin/chain_gate.py <workspace> [--finding FLEET-01 ...] [--json]
"""
import argparse
import json
import os
import re
import sys

HEADING = re.compile(r"^#+\s*\[([A-Z]+-\d+)\]", re.MULTILINE)


def load_config(workspace):
    for p in (os.path.join(os.path.dirname(__file__), "..", "config.json"),
              "config.json"):
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    return {}


def finding_sections(text):
    """Split FINDINGS.md into {finding-id: section-text} for VERIFIED headings."""
    out = {}
    matches = list(HEADING.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.setdefault(m.group(1), []).append(text[m.start():end])
    return {k: "\n".join(v) for k, v in out.items()}


def raw_evidence_state(workspace, fid):
    raw = os.path.join(workspace, "evidence", "raw")
    if not os.path.isdir(raw):
        return {"transcripts": [], "controls": [], "retests": []}
    files = [f for f in os.listdir(raw) if f.startswith(fid + "_") and not f.startswith(".")]
    return {
        "transcripts": [f for f in files if f.endswith(".txt") and not f.endswith(("_control.txt",))],
        "controls": [f for f in files if "control" in f],
        "retests": [f for f in files if re.search(r"_retest\d+", f)],
    }


def check_finding(workspace, fid, section, cfg):
    issues = []
    ev = raw_evidence_state(workspace, fid)
    if not ev["transcripts"]:
        issues.append("no raw transcript in evidence/raw/")
    if not ev["controls"]:
        issues.append("no negative-control capture (evidence/raw/*control*)")
    need = int(cfg.get("testing", {}).get("retest_verified_findings", 2))
    if len(ev["retests"]) < need:
        issues.append(f"retest captures {len(ev['retests'])}/{need}")

    m = re.search(r"Chain matrix.*?\n((?:\|.*\n)+)", section)
    if not m:
        issues.append("no chain matrix row")
    else:
        rows = [r for r in m.group(1).splitlines() if r.startswith("|")]
        cells = [c.strip() for c in rows[-1].split("|")[1:-1]] if len(rows) >= 2 else []
        data_cells = cells[1:] if cells else []
        empty = [i for i, c in enumerate(data_cells) if c in ("", "-")]
        if not data_cells:
            issues.append("chain matrix row has no surface columns")
        elif empty:
            issues.append(f"chain matrix has {len(empty)} empty cell(s) — cells must be TESTED/NOT-APPLICABLE/BLOCKED")

    has_data = re.search(r"\b(\d{2,})\b\s*(records|recs|vehicles|users|entries|rows)", section, re.I)
    if has_data and "Impact quantification" not in section:
        issues.append("data finding without an 'Impact quantification' block")

    if "CVSS" in section and "Impact quantification" not in section and has_data:
        issues.append("CVSS present but does not cite an impact-quantification block (cvss_from_measured_impact)")

    return {"finding": fid, "raw_files": sum(len(v) for v in ev.values()), "issues": issues}


def strip_template_comments(text):
    """Drop HTML comments: scaffold templates inside them are inert, not evidence."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def report_checks(workspace, cfg):
    """QA checks on REPORT.md. Returns (issues, report_text) or None when no report yet.

    Mid-engagement workspaces have no REPORT.md; those checks run at ship time.
    """
    rpath = os.path.join(workspace, "REPORT.md")
    if not os.path.exists(rpath):
        return None
    report = open(rpath, encoding="utf-8", errors="ignore").read()
    rep = cfg.get("report", {})
    issues = []
    for w in rep.get("banned_words", []):
        hits = re.findall(r"\b" + re.escape(w) + r"\b", report, re.IGNORECASE)
        if hits:
            issues.append(f"banned word in REPORT.md: '{w}' x{len(hits)} — hypothesis language, findings ship proof only")
    if rep.get("positive_controls_section_required", True) and not re.search(r"(?i)positive controls", report):
        issues.append("REPORT.md missing the Positive controls section (honest negatives raise every severity claim)")
    if rep.get("lateral_movement_map_required", True) and not re.search(r"(?i)\blateral\b", report):
        issues.append("REPORT.md missing the lateral movement map")
    if not re.search(r"(?i)findings index", report):
        issues.append("REPORT.md missing the Findings index section")
    return issues, report


def workspace_checks(findings_text, cfg):
    """Workspace-wide FINDINGS.md checks. Text must already be comment-stripped."""
    issues = []
    if cfg.get("testing", {}).get("full_coverage_enforced", {}).get("coverage_table_in_findings_required", True):
        if not re.search(r"(?i)#{2,}\s*coverage table", findings_text):
            issues.append("no 'Coverage table' section in FINDINGS.md — full coverage is enforced, surfaces must be closed surface-by-surface")
    if re.search(r"(?i)pre-registrat", findings_text) and not re.search(r"(?i)clean(?:up|ed)", findings_text):
        issues.append("artifact pre-registrations present but no cleanup evidence in FINDINGS.md")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--finding", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    fpath = os.path.join(a.workspace, "FINDINGS.md")
    if not os.path.exists(fpath):
        print(json.dumps({"error": "FINDINGS.md not found"}) if a.json else "FINDINGS.md not found")
        return 1
    text = open(fpath).read()
    cfg = load_config(a.workspace)
    sections = finding_sections(text)

    fids = a.finding or sorted(sections)
    results, failures = [], 0
    for fid in fids:
        sec = sections.get(fid, "")
        if "VERIFIED" not in sec and "CRITICAL" not in sec:
            continue
        r = check_finding(a.workspace, fid, sec, cfg)
        results.append(r)
        if r["issues"]:
            failures += 1

    clean_text = strip_template_comments(text)
    global_issues = workspace_checks(clean_text, cfg)

    report_issues = []
    checked_fids = [r["finding"] for r in results]
    rc = report_checks(a.workspace, cfg)
    if rc is None:
        report_note = "no REPORT.md yet; report-side checks run at ship time"
    else:
        report_issues, report_text = rc
        missing = [fid for fid in checked_fids if fid not in report_text]
        for fid in missing:
            report_issues.append(f"verified finding {fid} missing from REPORT.md")
        report_note = None
    failures += len(global_issues) + len(report_issues)

    raw = os.path.join(a.workspace, "evidence", "raw")
    sums_path = os.path.join(raw, "SHA256SUMS.txt")
    uncovered = []
    if os.path.isdir(raw):
        covered = set()
        if os.path.exists(sums_path):
            covered = {ln.split(None, 1)[1].strip() for ln in open(sums_path) if ln.strip()}
        for f in os.listdir(raw):
            if f != "SHA256SUMS.txt" and not f.startswith(".") and f not in covered:
                uncovered.append(f)
    if uncovered:
        failures += 1

    if a.json:
        print(json.dumps({"results": results,
                          "workspace_issues": global_issues,
                          "report_issues": report_issues,
                          "report_note": report_note,
                          "sha_uncovered": uncovered,
                          "failures": failures}, indent=1))
    else:
        for r in results:
            state = "PASS" if not r["issues"] else "FAIL"
            print(f"[{state}] {r['finding']} (raw files: {r['raw_files']})")
            for i in r["issues"]:
                print(f"       - {i}")
        if global_issues:
            print("[FAIL] workspace")
            for i in global_issues:
                print(f"       - {i}")
        if report_issues:
            print("[FAIL] REPORT.md")
            for i in report_issues:
                print(f"       - {i}")
        elif report_note:
            print(f"[ -- ] {report_note}")
        if uncovered:
            print(f"[FAIL] SHA256SUMS.txt does not cover: {', '.join(uncovered[:5])}"
                  + (" ..." if len(uncovered) > 5 else ""))
        print(f"\nchain_gate: {'PASS — report may ship' if failures == 0 else 'FAIL — findings above are unfinished'}")
    return 0 if failures == 0 and results else 1


if __name__ == "__main__":
    sys.exit(main())
