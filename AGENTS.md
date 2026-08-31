# AGENTS.md - bug-hunting skill

Cross-agent instructions (opencode, Codex, Claude Code, Cursor all get the same brain). This folder is the pushable unit: everything the skill needs travels inside it.

## If USING this skill (engagement running)

1. Read SKILL.md first: the PROOF GATE and phase routing (Gather, Analyze, Confirm, Operate, Report).
2. knowledge/playbook.md is what to look for, with the proof bar per vuln class.
3. Scripts (pure Python, any OS): bin/bounty_doctor.py (environment), bin/target_init.py (scaffold), bin/apk_recon.py (decode pipeline incl. signing SHA-1), bin/hunt_recall.py (prior art).
4. Vendored tools in tools/, one folder per tool (tools/apkpure, tools/device_pull, tools/mcp/<name>/server.py for each MCP server). Registration snippets in knowledge/mcp-tools.md.
5. Hard rules:
   - PROOF OR NOTHING. No "potential/candidate/likely" in reports. Real request, real response, demonstrated impact only.
   - NO PLAN, NO DYNAMIC TESTING. Every dynamic round is preceded by a written Dynamic Test Plan in FINDINGS.md.
   - DO NOT STOP AT THE FIRST HIGH. Run the escalation ladder on every finding. The engagement ends when a Critical is proven or the surface is exhausted, documented surface-by-surface.
   - IDOR/BOLA: the configured record minimum (config.json, default 20), masked, plus recency proof. Stale data is honeypot-suspect: pivot, do not report.
   - Every key: capability matrix proven by real calls.
   - Every foothold: lateral movement against all discovered surfaces.
   - Writes: artifacts labeled with the configured prefix from config.json (default SECTEST_), dummy/terminal-state targets, pre-registered in FINDINGS, cleaned up, cleanup logged.
   - scope.txt is the engagement contract. Authorized targets get tested deeply.
   - FINDINGS.md append-only per round plus a hypothesis queue.
   - Honest verdicts including explicit retraction when evidence fails.
   - Never write target or client names into this skill. Techniques, not platforms.
6. Engagement policy lives in config.json (operator, budget, testing, http, evidence, report, tools). Read it at engagement start and obey it like law. Budget is UNLIMITED by policy: never truncate effort to conserve tokens, never stop early, minimum rounds apply, and the only stop conditions are critical-proven or surface-exhausted-documented. Do not hardcode overrides in scripts; change behavior by changing the config.

## If DEVELOPING this skill

- Keep it self-contained and portable: pure Python (stdlib where possible), no machine-specific absolute paths, every tool vendored in its own folder under tools/ (MCP servers follow tools/mcp/<name>/server.py).
- knowledge/ is the source of truth. bin/ is thin automation on top.
- After each engagement, learn back into knowledge/ and tools/. Never let lessons die inside a target workspace.
- English only. Minimal emoji and em-dashes.
- Never commit real secrets, target names, or client names into this repo. Sanitize case studies to technique patterns.
