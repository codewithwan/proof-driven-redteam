#!/usr/bin/env python3
"""target_init: scaffold a bug-hunting target workspace (canonical layout).

Reads config.json at the skill root so team settings (artifact prefix, record
minimums, HTTP profile) propagate into every workspace automatically.

Pure Python, stdlib only, runs on any OS.
Usage: python3 target_init.py <slug> [--app path] [--url url] [--scope file] [--root dir]
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"
LAYOUT = [
    "app", "decoded", "extracted",
    "recon/subdomains", "recon/urls", "recon/js", "recon/cloud", "recon/notes.md",
    "traffic",
    "scanning/nuclei", "scanning/vigolium-run", "scanning/trufflehog",
    "poc", "evidence",
    "out-of-scope.txt", "FINDINGS.md",
]


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def findings_header(prefix: str, min_records: int, plan_required: bool) -> str:
    return (
        f"# FINDINGS.md - <target>\n\n"
        f"Append-only round log. Verdicts: VERIFIED / NEGATIVE / UNCONFIRMED (hypothesis queue) / RETRACTED.\n"
        f"Team config: artifact prefix `{prefix}` | IDOR minimum {min_records} distinct records + recency proof"
        f" | dynamic test plan {'REQUIRED before any live request' if plan_required else 'recommended'}.\n"
        f"All writes/edits/deletes are pre-registered here BEFORE execution, with cleanup evidence appended after.\n\n"
        "## Round 1 - Initial static (date, authorization note)\n\n"
        "- Signal: what triggered this round\n"
        "- Command + raw output:\n```bash\n```\n"
        "- Interpretation + honesty boundary (what is NOT proven):\n"
        "- Next hypotheses: the queue\n\n"
        f"<!-- Verified-finding template:\n"
        f"### [XX-01] VERIFIED - title\n"
        f"raw request + raw response\n"
        f"- Impact demonstrated: one concrete line\n"
        f"- Evidence: evidence/raw/xx01_<slug>.txt (+ .bin if binary) — TOOL-GENERATED raw transcript only; hand-written summaries are banned as proof (config.json evidence section)\n"
        f"- CVSS: via the cvss MCP tool, full vector\n"
        f"- Lateral: which other surfaces accepted this credential, or 'none, bounded'\n"
        f"-->\n\n"
        f"<!-- Dynamic test plan template (required before dynamic rounds):\n"
        f"### Dynamic Test Plan (Round N)\n"
        f"- Objective / Surface / numbered Requests (method, params, expected, negative control)\n"
        f"- Preconditions (owned accounts, scope.txt check)\n"
        f"- Artifact registrations: every write with `{prefix}` prefix, target object, cleanup step\n"
        f"- Rate (from config.json) / Stop and rollback / Success criteria\n"
        f"-->\n\n"
        f"<!-- Artifact pre-registration template:\n"
        f"### {prefix}pre-registration (Round N)\n"
        f"- Action: create object named {prefix}POC_XX01_YYYYMMDD via the official flow, then read via the vulnerability\n"
        f"- Cleanup: delete/cancel + evidence appended below\n"
        f"-->\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="scaffold a bug-hunting workspace")
    ap.add_argument("slug")
    ap.add_argument("--app")
    ap.add_argument("--url")
    ap.add_argument("--scope")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    cfg = load_config()
    testing = cfg.get("testing", {})
    prefix = testing.get("artifact_prefix", "SECTEST_")
    min_records = testing.get("idor_min_records", 20)
    plan_required = bool(testing.get("require_dynamic_test_plan", True))
    company = (cfg.get("operator", {}) or {}).get("company_name") or "<company>"
    budget = cfg.get("budget", {})
    rounds_min = budget.get("rounds_min", "n/a")
    stop_conditions = " or ".join(budget.get("stop_conditions", ["critical-proven", "surface-exhausted-documented"]))

    dest = Path(args.root).expanduser() / args.slug
    if dest.exists():
        print(f"already exists: {dest}")
        return 1

    for item in LAYOUT:
        p = dest / item
        if "." in os.path.basename(item):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        else:
            p.mkdir(parents=True, exist_ok=True)

    scope_lines = []
    if args.scope and Path(args.scope).is_file():
        scope_lines = Path(args.scope).read_text().splitlines()
    elif args.url:
        host = args.url.split("//", 1)[-1].split("/", 1)[0]
        scope_lines = [f"*.{host}", args.url]
    (dest / "scope.txt").write_text("\n".join(scope_lines) + "\n")

    (dest / "FINDINGS.md").write_text(findings_header(prefix, min_records, plan_required))
    tpl = SKILL_DIR / "templates" / "REPORT.md"
    (dest / "REPORT.md").write_text(tpl.read_text() if tpl.exists() else "")

    (dest / "README.md").write_text(
        f"# {args.slug} security assessment workspace\n\n"
        f"- Operator: {company} (authorized security assessment)\n"
        "- Scope: scope.txt (the engagement contract)\n"
        f"- Started: {datetime.date.today()}\n"
        f"- Artifact prefix: {prefix} (all test writes, from config.json)\n"
        "- Loop: knowledge/workflow.md (proof gate, plan gate, escalation ladder)\n"
        f"- Engagement policy: minimum {rounds_min} rounds | stop ONLY on: {stop_conditions}\n"
        f"- Budget: tokens unlimited, no early stop, escalation ladder mandatory per finding\n"
    )

    (dest / "app" / "PROVENANCE.txt").write_text("manual copy\n")

    if args.app:
        src = Path(args.app).expanduser()
        if not src.is_file():
            print(f"app not found: {src}")
            return 1
        shutil.copy2(src, dest / "app" / src.name)
        digest = sha256(dest / "app" / src.name)
        (dest / "app" / "SHA256SUMS.txt").write_text(f"{digest}  {src.name}\n")
        (dest / "app" / "PROVENANCE.txt").write_text(f"file {src.name} sha256 {digest}\n")

    print(f"OK {dest}")
    print(f"config: prefix={prefix} idor_min={min_records} plan_gate={'on' if plan_required else 'off'}")
    print("Fill scope.txt first, then run apk_recon.py if you have an app package.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
