# Vigolium: Web Lead Engine (hybrid integration)

Vigolium is a scanner plus evidence database plus its own LLM agent engine. It stays a
binary on PATH. This skill never vendors it (AGPL-3.0, 362MB) and never reimplements it;
it drives it through the CLI and imports its output as leads. The operator agent keeps
the judgment (proof gate, scope, chain matrix); vigolium provides machine speed.

## The rule

**Web scope means a vigolium run, every engagement.** No web engagement closes Gather
without a vigolium scan of the in-scope hosts (config.json `tools.vigolium.web_run_required`).
Pure mobile targets skip it. Mobile+API hybrids run it against the API hosts.

Every byte of vigolium output is a LEAD. Vigolium findings never enter REPORT.md and
never count as evidence. The path from lead to finding is: import to the hypothesis
queue, plan the probe, capture through evidence_capture.py, chain it. Vigolium's own
transcripts live in its database, not in evidence/raw/, and are never cited as proof.

## Dual-layer dispatch

Two execution layers, one judgment layer. Route per task:

| Task shape | Route | Why |
|---|---|---|
| Full-surface discovery (new web estate, dozens of hosts) | Delegate: `vigolium agent swarm -t <host> --discover` | surface-scale grinding wastes operator turns |
| Autonomous audit of a large area with triage | Delegate: `vigolium agent autopilot -t <host>` | long-running, budgeted, resumable |
| Single endpoint or parameter probe | Hand: `vigolium scan-url`, `fuzz`, `replay` via this agent | surgical beats autonomous |
| Precise manual confirmation | Hand: burpsuite MCP skill + evidence_capture | proof work is never delegated |
| Source audit of a web repo | Delegate: `vigolium agent audit --source <dir>` or hand per stack | either; diff-focused via `--diff` |
| Recon harvesting, JS unminify, JWT crack, secret scan | Hand: `vigolium kit harvest/js-beautify/jwt-crack/secret-scan` | deterministic utilities, no LLM needed |

Delegation is only allowed with budget flags (config.json `tools.vigolium.delegation_flags_required`):
`--token-budget`, `--max-iterations`, `--max-duration`, and `--fail-on` when running in CI.
An unbounded agent run violates the plan-gate discipline just as an unplanned probe does.

## Phase map

| Phase | Vigolium use | Output lands in |
|---|---|---|
| Gather | `vigolium scan -t <host> --strategy balanced` (mandatory for web), `kit harvest` for URL history | `scanning/vigolium-run/` (logs, exports) |
| Analyze | `kit secret-scan` over URL/JS corpus, `kit js-beautify` on minified bundles (endpoint extraction), `kit jwt-crack` on captured JWTs, `agent audit --source` on any web repo | recon notes + hypothesis queue via import |
| Plan | `vigolium finding -j` review: severity, confidence, record_kind rank the queue order | Dynamic Test Plan |
| Confirm | Hand probes only: evidence_capture (never a vigolium mode). `vigolium replay` may pre-check a request shape before it enters the plan | evidence/raw/ via capture tools only |
| Operate | `vigolium replay` bulk for retest captures material; OAST polling for dispatch proofs; `fuzz` for parameter sweeps when the plan covers them | FINDINGS retest blocks |
| Report | `finding -j` export is reference material, never report evidence | out-of-report appendix only |

## Leads import

```bash
vigolium finding -j | python3 bin/vigolium_leads.py <workspace>
```

The script appends hypothesis-queue rows (new H-IDs, deduped against previous imports by
vigolium finding id and by host/module/url tuple), with severity, confidence, CWE, and
record_kind preserved in the basis and detail lines. Queue entries start QUEUED; the
operator promotes them to TESTING only through the plan gate. Re-running the import is
safe: duplicates are skipped.

Severity floor: `--min-severity medium` (default imports everything; info/low noise stays
QUEUED and cheap to DEAD later).

## OAST lifecycle (dispatch proofs)

For blind SSRF, blind injection, and callback-reachability hypotheses:

1. `vigolium kit oast new` returns a payload URL; register it in the Dynamic Test Plan.
2. Deliver the payload through the planned surface (evidence_capture captures the request).
3. `vigolium kit oast poll` shows interactions; an interaction log is dispatch evidence
   (the callback happened), never impact evidence. Impact still needs the response-side
   proof captured through the normal gate.

## Vigolium agent LLM config (one-time)

Vigolium's agentic modes need their own LLM. Point it at the same backend the operator
agent uses, so there is one provider account and one bill:

```bash
vigolium config set agent.provider openai-compatible
vigolium config set agent.base_url <same endpoint as the operator agent>
vigolium config set agent.api_key <same key>
```

The operator agent and vigolium's agent are a hierarchy, not peers: this skill dispatches
vigolium with budgets, imports its triaged output as pre-ranked hypotheses, and keeps all
verdict authority. Never let vigolium's autopilot write to FINDINGS.md or evidence/.

## Hard lines

1. Vigolium output is leads. Its findings, confidence levels, and severities rank the
   queue; they never appear in REPORT.md.
2. Vigolium's database is not evidence/raw/. Its captured traffic is lead material for
   replay and retest planning; the transcript that proves a finding is the one written by
   evidence_capture.py in the same capture run as its negative control.
3. Delegated runs require budget flags and respect config.json http pacing: map
   delay_ms/max_parallel to `--rate-limit`/`--concurrency` on every scan and fuzz.
4. Web engagements must record the vigolium run (command, version, strategy) in the
   coverage table; a web surface never marked vigolium-scanned is a coverage gap.
5. Scope: vigolium scans only scope.txt hosts. Pass `--scope-file`/target lists derived
   from scope.txt; never a wildcard domain outside the contract.
