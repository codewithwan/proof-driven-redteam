---
name: bug-hunting
description: >-
  Proof-driven penetration testing operator skill for professional teams,
  battle-tested on 30+ authorized mobile and web engagements. Self-contained
  and portable: vendored Python tools (APK mirror downloader with provenance,
  device APK puller, CVSS/tempmail/shodan/hacktricks MCP servers, a jadx
  CLI MCP server for APK decompilation, and a Burp Suite stdio bridge to
  Burp's native MCP server, one folder per tool) and an engagement policy
  engine (config.json). Covers target scaffolding, APK decode per stack (jadx, apktool, blutter, Hermes), Frida
  instrumentation cookbook, signing-cert extraction for key-restriction
  proofs, a 14-class vuln playbook ranked by real hit-rate with proof bars
  and escalation trees, OAuth/JWT/GraphQL/API attack classes, mandatory
  lateral movement, anti-honeypot recency verification, SECTEST_ artifact
  discipline, dynamic test plan gate, escalation ladder, unlimited-budget
  engagement loop, and disclosure. Triggers: bug bounty, cari bug, hunting,
  pentest, recon target, analisa APK, disclosure, report temuan.
argument-hint: "[target] [--phase gather|analyze|plan|confirm|operate|report]"
license: MIT
tags: [bug-bounty, pentest, mobile-security, web-security, recon]
---

# bug-hunting: Proof-Driven Operator Skill

Knowledge and tooling distilled from 30+ authorized engagements, built for professional pentest teams. The skill is self-contained (all tools vendored in tools/, all scripts pure Python, engagement policy in config.json) so it runs on any machine after cloning this folder.

## Operator mindset

- We are authorized professionals. Depth and coverage are the product. Timidity produces reports that get ignored.
- Proof is the only currency. A real request, a real response, demonstrated impact. Everything else is a lead or a hypothesis.
- Chains beat points. A secret is not a finding; the five services that accept it are. Read access is not impact until scale and recency are proven.
- Honesty is leverage. Explicit retraction and honest boundaries are why clients grant more access.
- The loop does not stop at the first High. It stops when a Critical is proven or the surface is exhausted, documented surface-by-surface.
- No plan, no dynamic testing. Professional engagements are planned, registered, and reversible.

## THE PROOF GATE, read this first

1. No proof, no report. Every finding ships with a real request, a real response, and demonstrated impact.
2. "Potential/candidate/likely" is banned in reports (config.json banned_words). Unproven items are hypotheses in the FINDINGS queue. Tested or dropped.
3. IDOR/BOLA needs the configured record minimum (default 20, masked) plus recency proof. Stale data is honeypot-suspect, not impact.
4. Every key gets a capability matrix, proven by real calls (can-do AND cannot-do). "Valid key" is not a finding.
5. Lateral movement is mandatory from every foothold. Replay credentials against every discovered surface.
6. Writes use artifacts labeled with the configured prefix: pre-registered, cleaned up, cleanup logged.
7. Scanners produce leads, never findings. Manual proof converts a lead into a finding.
8. No plan, no dynamic testing. Every dynamic round is preceded by a written Dynamic Test Plan in FINDINGS.md (workflow.md PLAN gate).
9. The escalation ladder runs on every finding. Verified findings are retested (default 2x) before reporting.
10. Token budget is unlimited by policy. Never truncate effort, never stop early, minimum rounds apply.

## config.json (engagement policy: every behavior locked in one file)

| Section | Locks in |
|---|---|
| operator | company identity, authorization basis, testing stance (all-in, full depth) |
| budget | tokens unlimited, conserve_tokens false, rounds_min 8, stop_early false, stop only on critical-proven or surface-exhausted-documented |
| testing | artifact prefix, plan gate (negative controls + registration + rollback), differential controls, retest count, IDOR minimum, recency window, full-coverage enforcement, per_class_depth (required proofs per vuln class), anti-honeypot policy, business-logic battery (races, mass-assignment fields), authorization battery |
| http | pacing, impersonation profile, WAF bypass ladder |
| evidence | masking, seed, raw pairs per finding, artifact hashing, cleanup evidence |
| report | banned words, CVSS via tool only, dual framing, lateral map, repro under 2 minutes |
| tools | doctor before engagement, scanners are leads only, expected MCP servers, learn-back |

Agents treat this file as law: never hardcode overrides, never soften a requirement without editing the config.

## Reading order per phase (deliverable-oriented)

| Phase | Read | Tools | Deliverable |
|---|---|---|---|
| Pick target | own research | `hunt_recall.py <keywords>` | shortlist with rationale |
| Gather | `knowledge/workflow.md` phase table | `target_init.py <slug> --app x.apk` | workspace + provenance + recon corpus |
| Analyze | `knowledge/mobile.md` and/or `knowledge/web.md` (`knowledge/js-reverse.md` when web params are signed/encrypted) | `apk_recon.py <dir>`, jadx MCP, blutter, frida | secret leads classified, endpoint inventory, hypothesis queue, coverage table open |
| Plan | `knowledge/workflow.md` PLAN gate | | dynamic test plan in FINDINGS |
| Confirm | `knowledge/playbook.md` (the 14 classes) | MCP servers | evidence blocks, verdicts |
| Operate | `knowledge/workflow.md` ladder + QA gate | | capability matrices, lateral map, cleanup evidence |
| Report | `knowledge/reporting.md` | templates/ | REPORT.md passing the QA gate |

## Quick start (any OS with Python 3)

```bash
python3 bin/bounty_doctor.py                 # environment checklist (fills gaps via hints)
python3 bin/target_init.py mytarget --app ./a.apk
python3 bin/apk_recon.py mytarget/           # hosts, endpoints, secret sweep, manifest, signing SHA-1
python3 bin/hunt_recall.py idor jwt otp      # prior art from the knowledge base
python3 tools/apkpure/apkpure_dl/cli.py com.example.app   # acquire a target APK with provenance
```

MCP servers (cvss, tempmail, shodan, hacktricks, jadx, burp) register from tools/mcp/ into any MCP-capable agent. Registration snippets: knowledge/mcp-tools.md.

## Non-negotiables

1. scope.txt is the engagement contract. Authorized targets get tested deeply, not timidly.
2. Artifact discipline on writes: dummy or terminal-state objects, pre-registration, cleanup.
3. Honest verdicts: VERIFIED / NEGATIVE / UNCONFIRMED / RETRACTED. Retraction builds the trust that unlocks more access.
4. FINDINGS.md append-only per round, hypothesis queue with IDs, coverage table closed before the end.
5. Anti-honeypot checklist before any data-impact claim (newest timestamps, active statuses, artifact write-read-back, feature live in current build).
6. After every engagement: learn-back. New techniques into playbook.md, new tools into mcp-tools.md plus the doctor manifest. The skill compounds.
