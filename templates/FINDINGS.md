# FINDINGS.md - <target>

Append-only round log. Verdicts: VERIFIED / NEGATIVE / UNCONFIRMED (hypothesis queue) / RETRACTED.
Artifact prefix comes from the skill config.json (default SECTEST_). All writes/edits/deletes are pre-registered here BEFORE execution, with cleanup evidence appended after.
Dynamic rounds require a written Dynamic Test Plan first (see workflow.md, the PLAN gate).

## Round 1 - Initial static (date, authorization note)

- Signal: what triggered this round
- Command + raw output:
```bash
```
- Interpretation + honesty boundary (what is NOT proven):
- Next hypotheses: the queue

<!-- Verified-finding template:
### [XX-01] VERIFIED - title
raw request + raw response (curl / nc transcript / JSON)
- Impact demonstrated: one concrete line
- Evidence: evidence/xx01.json (masked)
- CVSS: AV:.../... -> score (via the cvss MCP tool)
- Lateral: which other surfaces accepted this credential, or "none, bounded"
- Escalation ladder: which follow-ups were run (capability matrix / scale / recency / chain)
-->

<!-- Dynamic Test Plan template (REQUIRED before dynamic rounds):
### Dynamic Test Plan (Round N)
- Objective: what impact we are demonstrating
- Surface: exact hosts/endpoints from recon outputs
- Requests: numbered, each with method, params, expected result, negative control
- Preconditions: owned accounts, scope.txt check
- Artifact registrations: every write/edit/delete with the configured prefix, target object, cleanup step
- Rate: delay/parallelism from config.json
- Stop/rollback: when to abort, how to restore state
- Success criteria: what response proves the objective
-->

<!-- Artifact pre-registration template:
### <PREFIX>_pre-registration (Round N)
- Action: create object named <PREFIX>POC_XX01_YYYYMMDD via the official flow, then read via the vulnerability
- Cleanup: delete/cancel + evidence appended below
-->
