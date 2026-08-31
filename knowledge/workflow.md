# Workflow: The Proof-Driven Engagement Loop

One loop per target. Round-based, evidence-first, honest on failure. We are professional, authorized penetration testers: full coverage, no skipped phases, no half measures, no self-imposed effort limits.

```
G Gather   scaffold, acquire with provenance, full recon coverage
A Analyze  static decode, sweep secrets, map endpoints and business flows
P Plan     written dynamic test plan (gate: no plan, no dynamic testing)
C Confirm  minimal live probes, differential, convert hypotheses to PROOF
O Operate  capability matrices, lateral movement, artifact writes (pre-registered)
R Report   only proven findings, hypotheses stay queued
```

## Phase specifications (entry criteria, activities, exit criteria)

| Phase | Entry | Core activities | Exit criteria |
|---|---|---|---|
| Gather | scope.txt signed | scaffold, acquire app with provenance, subdomain/URL/JS/cloud recon, infra port map, estate screenshots | coverage inputs exist: hosts.txt, endpoints.txt, live-host list, recon notes complete |
| Analyze | gather outputs | decode, secret sweep, signature extraction, manifest triage, per-stack deep dive, business-flow map from app UI/API | secret leads classified, endpoint inventory, hypothesis queue H-001+ populated, coverage table initialized |
| Plan | hypothesis queue non-empty | dynamic test plan per objective: numbered requests, negative controls, artifact registrations, rollback | plan appended to FINDINGS, every request has a control and an expected result |
| Confirm | plan written | execute plan requests, capture evidence blocks, update hypotheses, escalate per ladder | every queued hypothesis is PROVEN, DEAD, or BLOCKED (with reason) |
| Operate | confirmed footholds | capability matrices, scale proofs, recency proofs, lateral replay across the whole estate, write-path chains with prefixed artifacts | ladder exhausted per finding, lateral map complete, cleanup done and evidenced |
| Report | operate exits | REPORT.md, evidence packaging, reproduction scripts, positive controls, disclosure draft | QA gate passed (below), client-ready |

## Hypothesis management system

Hypotheses are tracked with IDs in FINDINGS.md. A round without queue movement is a wasted round.

```md
### Hypothesis queue
| ID | Hypothesis | Basis | State | Outcome |
|----|-----------|-------|-------|---------|
| H-001 | static AES key signs the transport envelope | secret sweep + code path | TESTING | |
| H-002 | integer order IDs are enumerable | endpoints.txt + UI | QUEUED | |
| H-003 | staging token works on prod | config diff | DEAD | rejected signature (evidence/xxx) |
```

States: QUEUED, TESTING, PROVEN (linked to finding ID), DEAD (with evidence), BLOCKED (with reason and revisit condition).
Rules:
- Every round consumes or adds hypotheses. If the queue is empty, generate from the coverage table gaps before doing anything else.
- A DEAD hypothesis still gets an evidence line. Negative results feed Positive Controls in the report.
- A BLOCKED hypothesis gets a revisit condition (for example: blocked on second test account; revisit when tempmail registration completes).

## Engagement stop condition and budget (config.json: budget)

Token budget is UNLIMITED by policy and rounds have a minimum, not a maximum. Never conserve tokens, never summarize to save context, never stop because it "looks done enough". The loop does not end at the first High. An engagement ends only when one of:

1. A Critical-severity impact is PROVEN (chain demonstrated end to end with evidence) **AND its chain matrix is exhausted** — the critical itself has been chained into every other reachable surface, its data impact fully quantified, and every sibling of the vulnerable component probed (proving a Critical does NOT license skipping the ladder on it). Config token: `critical-proven-and-chained`, or
2. The attack surface is EXHAUSTED, with the exhaustion documented surface-by-surface in the coverage table (what was tested, what was negative, what remains blocked and why).

Defaults: rounds_min 8, stop_early false, intermediate states are never stops, parallel subagents encouraged.

## The escalation ladder (run it on every finding)

A finding is the start of escalation, not the finish line. Mandatory follow-ups before moving on:

| After finding | Mandatory escalation |
|---|---|
| Any leaked key/token | Capability matrix, then replay against every discovered service (lateral) |
| Any read access to objects | Scale proof (record minimum), then recency proof, then hunt the write path |
| Any write access | Chain upward: write to privilege, privilege to cross-tenant or admin |
| Any user-level foothold | Vertical escalation attempt, then credential reuse across the estate |
| Any single-service impact | Map every sibling service sharing auth, tokens, or infrastructure |
| Any Medium | Ask: what does this enable? Chain it until the real impact is demonstrated or bounded honestly |

If the ladder dead-ends, the bound itself goes in the report (honest boundaries make the remaining claims stronger).

## The chain matrix (mandatory for every VERIFIED finding)

One finding is one row; every other discovered surface is a column. A finding is NOT report-ready
until its row is complete. This is the anti-pattern killer: finding one exposed endpoint and
stopping is the most common way engagements undersell impact. Maintain in FINDINGS.md:

```md
### Chain matrix
| Finding ↓ / enables → | chat API | tracking API | gateway REST | gRPC | web SPA | IdP | ... |
|---|---|---|---|---|---|---|---|
| [XX-01] leaked secret | token mint ✓ | n/a | 401 ✗ | n/a | n/a | password-grant ✓ | |
| [XX-02] unauth endpoint | n/a | data ✓ | ... | | | | |
```

Rules:
- Every cell is TESTED (✓ with evidence link), NOT-APPLICABLE (reason), or BLOCKED (reason) —
  never empty. An empty cell means the finding is not done.
- Include the credential/data of the finding as a foothold INTO other findings: can the unauth
  data reveal identifiers that feed another vuln (e.g. fleet data revealing valid member codes,
  pool UUIDs, order IDs)? Chain findings into findings, not just surfaces.
- Parameter-space chaining counts: if an endpoint ignores one parameter (sid/sub/loc), probing
  every value of that parameter is part of the row (bounded sweep, minimization respected).

### The deep-chain checklist (run BEFORE declaring any finding done)

A finding passes the chain gate only when ALL of these have a tested answer — this is the
minimum professional bar, not extra credit:

1. **Parameter semantics map**: for EVERY parameter of the vulnerable endpoint — is it validated,
   filtered, or ignored? Ignored parameters multiply impact by their cardinality (sub ignored →
   every subscription readable; sid = city → sweep every city; seq semantics → history vs cursor).
   Prove each with at least: valid value, garbage value, empty value (3-way differential).
2. **Scale proof**: how many distinct datasets does one request shape reach? (other tenants,
   cities, pools, environments — bounded sweep, record the count).
3. **Depth proof**: is the response a snapshot, an archive, or a stream? Cursor semantics matter
   for impact claims (an enumerable history archive outranks a live snapshot; do not claim either
   without the differential).
4. **Data-class inventory**: parse the captured bytes and enumerate WHAT data classes ride the
   response (personal names, device identifiers, school/child markers, financial hints) — each
   class is a potential finding-into-finding foothold AND a severity driver.
5. **Foothold export**: from the captured data, list every identifier that other vulnerable
   surfaces accept (vehicle numbers, member codes, pool names, order IDs, usernames) and attempt
   each against its consumer surface (bounded; blocked ones recorded as BLOCKED-on-input).
6. **Environment replication**: the same request shape against every environment discovered
   (dev/stg/prod hosts from bundle mining) — enforcement often exists on exactly one layer.
7. **Escalation attempt**: does the unauth READ surface have a sibling WRITE/subscribe/push
   surface reachable with the same (absent) credentials? (Look for POST/PUT/SSE on the same
   prefix.) If found: pre-register artifact rules before probing.

Findings that cannot answer all seven are UNCHAINED — they stay out of REPORT.md and stay in the
hypothesis queue with the missing chain-links named.

## Mode selection: static-first vs dynamic-first (conditional, per engagement)

The loop is not rigid about order. Choose the starting mode deliberately, log the choice and the
reason in FINDINGS.md Round 1, and re-decide when the evidence says so:

**Default: static-first** (mobile APK / thick client / web bundle available):
- Decode, sweep secrets, map every route/RPC/bridge FIRST — the static map decides which dynamic
  probes are worth firing. A dynamic probe without a static basis is guessing.
- Switch trigger to dynamic: when a hardcoded credential, unauth contract, or parameter
  semantics question can only be answered by the server (differential), or when bundle mining
  reveals an endpoint whose enforcement state is unknown (the FLEET-01 pattern: static bundle
  mining found the endpoint, ONLY the dynamic differential proved it unauthenticated).

**Dynamic-first** (no client artifact: pure API, IoT, or already have credentials):
- Start from live surface mapping (OPTIONS, auth matrices, error differentials), and grow the
  static side from traffic (har capture → endpoint inventory → targeted parameter sweeps).
- Switch trigger to static: when traffic reveals a client artifact (JS bundle, APK download) —
  then mine it; the bundle usually knows more endpoints than the traffic shows.

**Mixed reality (most real engagements):** static maps the surface, dynamic proves the gates,
and every dynamic result feeds back into the static map (new hosts, new params, new chains).
Log mode transitions explicitly: "R4: switching to dynamic — reason: unauth contract question on
fleet API". Never let mode boundaries become an excuse to skip the proof gate: whichever mode
found the lead, only raw captured evidence makes it a finding.

## Data-driven impact quantification (mandatory before CVSS for every data finding)

CVSS is scored from MEASURED impact, never from imagination. After capturing raw evidence of a
data-returning finding, parse the captured bytes (binary included — port the client's parser if
needed; the SPA/SDK shipped in the app/web build usually contains it) and record in FINDINGS.md:

```md
### Impact quantification [XX-01]
- Record count: N (per parameter value; note if parameter ignored → multiply by cardinality)
- Freshness: newest record timestamp vs capture time (anti-honeypot), oldest record timestamp
- PII field population: which fields carry PII, on how many of N records (count + %)
- Scale: cities/tenants/parameter values returning distinct datasets (bounded sweep only)
- Data classes present: personal names, device identifiers, children/school identifiers,
  location history depth, financial hints — each with the count that proves it
- Moving/live elements: e.g. vehicles with speed>0 at capture time
```

These measured numbers select the CVSS vector (C:H only when the measured PII/locations justify
it; scope S:C only when the chain matrix proves cross-service impact), and they select the
report's program-class framing (child-safety / PDP-law / financial classes). A finding whose
impact was quantified from data outranks a bigger theoretical finding — because it survived
reviewer questions about scale, recency, and sensitivity without speculation.

## The PLAN gate (dynamic analysis)

No dynamic testing without a written plan. The plan is appended to FINDINGS.md before the first live request:

```md
### Dynamic Test Plan (Round N)
- Objective: what impact we are trying to demonstrate
- Surface: exact hosts/endpoints, from recon outputs
- Requests: numbered list, each with method, params, expected result, control (garbage-token negative)
- Preconditions: credentials/accounts owned, scope check against scope.txt
- Artifact registrations: every write/edit/delete with the configured prefix, target object, cleanup step
- Rate: delay/parallelism from config.json http settings
- Stop/rollback: when to abort, how to restore state
- Success criteria: what response proves the objective
```

Why: plans make evidence blocks reproducible, keep authorization clean, and stop drift into unplanned destructive actions.

## The Proof Gate (non-negotiable)

1. No proof, no report. Every finding is a real request, a real response, and demonstrated impact.
2. "Potential / candidate / likely / possible" is banned in REPORT.md. Those words mark a HYPOTHESIS in FINDINGS.md. Hypotheses get tested or they die. They never ship.
3. IDOR/BOLA: the configured record minimum (default 20) of distinct records, masked, plus recency proof. Stale data is honeypot-suspect, not impact.
4. Keys and secrets: full capability matrix, proven by real calls per capability (can-do AND cannot-do).
5. Lateral movement is mandatory from every foothold. Single-endpoint impact understates the finding almost every time.
6. Writes, edits, deletes: artifacts labeled with the configured prefix (default SECTEST_), dummy IDs or terminal-state objects, pre-registered in FINDINGS BEFORE execution, cleaned up after, cleanup evidence in the report.
7. Retest verified findings the configured number of times (default 2) before they enter the report.

## Round rules

1. FINDINGS.md is append-only. Round = date, signal, raw commands and responses, verdict (VERIFIED / NEGATIVE / UNCONFIRMED / RETRACTED), hypothesis-queue update. Never tidy it up, it is the reproducibility log.
2. Static rounds first (1 to 3 rounds): file:line proofs, everything verifiable offline. Live rounds after the plan gate.
3. Differential controls in every live probe: valid credential vs garbage vs none, in the same evidence block. A response difference is proof. A lone 200 is an anecdote.
4. Retract explicitly when evidence does not support the claim. Retraction is what makes clients escalate trust and grant more access.
5. Vendor says honeypot, legacy, deprecated? Do not argue. (a) Build the anti-honeypot dossier: newest-record timestamps, artifact write-read-back, feature live in today's app-store build. (b) Simultaneously pivot to current infrastructure: corporate web estate, mail servers, internal apps. The pivot has repeatedly landed Criticals on current infra after stale-data discounts.
6. Full coverage is enforced (config.json full_coverage_enforced): every discovered endpoint probed, every key capability-matrixed, every host infra-scanned, every autoVerify host assetlinks-checked.

### Coverage table format (maintained in FINDINGS.md, closed before engagement end)

```md
### Coverage table
| Surface | Tested | Verdict | Notes |
|---------|--------|---------|-------|
| endpoints.txt (247) | 247/247 probed | 3 findings, 244 negative | evidence links |
| hosts.txt live (31) | 31/31 port-scanned | 2 findings | |
| keys found (6) | 6/6 matrixed | 2 findings | 4 decoy/public-by-design |
| autoVerify hosts (4) | 4/4 assetlinks | 1 finding | |
```

## Anti-honeypot recency checklist (before ANY data-impact claim)

- Newest record created_at/updated_at inside the configured recency window? Record the actual date in evidence.
- Active-status records present, not only terminal or canceled ones?
- Prefixed artifact created through the official app flow, then read back through the vulnerability? (gold standard)
- Feature live in the current app-store version? Service returns current config?
- If all fail: mark HONEYPOT-SUSPECT/LEGACY, do NOT claim data impact, pivot to current infra.

## Evidence file naming convention

EVIDENCE MUST BE RAW TOOL OUTPUT. Hand-typed or AI-summarized "evidence" files are BANNED: a
rewritten summary presented as evidence is indistinguishable from fabricated proof and will be
treated as evidence tampering. Files in evidence/raw/ are produced by a capture tool (curl with
verbose logging, mitmproxy export, or the workspace capture script) — never authored by hand.

```
evidence/raw/<finding-id>_<short-slug>.txt     tool-generated RAW transcript: UTC timestamp, exact request (method/URL/headers/body as sent), exact response (status/headers/body verbatim)
evidence/raw/<finding-id>_<short-slug>.bin     byte-exact binary response body (when body is not text); sha256 of the body recorded inside the .txt transcript
evidence/raw/<finding-id>_control.txt          negative control capture (garbage credential / no credential), captured in the SAME capture run
evidence/raw/<finding-id>_retest1.txt          retest captures (retest count from config.json)
evidence/raw/SHA256SUMS.txt                    sha256 checksum chain over every file in evidence/raw/
evidence/sectest_registry.md                   artifact pre-registrations + cleanup evidence
evidence/analysis_notes/                       hand-written interpretation and summaries — INTERNAL ONLY, never cited as proof in FINDINGS.md or REPORT.md
poc/poc_<finding-id>.py                        self-verifying, --mask default
```

Tools that enforce this mechanically (use them; they are the front doors):
  - `bin/evidence_capture.py` — every dynamic probe runs through it; it writes the transcript,
    the byte-exact .bin, and regenerates SHA256SUMS.txt itself. No other path produces evidence.
  - `bin/differential.py` — fires the 3-way parameter-semantics probe (valid/garbage/empty)
    and captures all three runs as raw evidence.
  - `bin/impact_parser.py` — parses captured bodies (JSON or length-prefixed binary, schema
    given as field specs) and emits the measured impact-quantification block.
  - `bin/chain_gate.py` — the QA gate as code: raw evidence present, controls, retests, chain
    matrix completeness, impact quantification, SHA coverage. A report ships only when it
    exits 0.

Hard rules (enforced by the QA gate):
- A transcript is written by the capture tool, and contains the request EXACTLY as sent and the
  response EXACTLY as received. If a finding has no evidence/raw/ transcript, it has no evidence.
- The negative control and retest captures must be captured in the same capture run as the
  positive probe (same tool, same session), not reconstructed afterwards.
- REPORT.md and FINDINGS.md may cite ONLY evidence/raw/ files. analysis_notes/ exist to organize
  thinking, never to prove a claim.
- SHA256SUMS.txt is regenerated after every capture run; verifiers re-hash the .bin files against it.

## Ethics and discipline

Targets are engagement-authorized: test fully and deeply, timidity produces the stale "potential" reports that never pay. Keep the discipline anyway, because it makes reports unanswerable:

- GET and HEAD first. Writes are pre-registered artifacts, cleaned up.
- OTP proofs on your OWN numbers and inboxes. Zero third-party bombing.
- Data minimization: the record minimum, masked, beats any bulk dump. Scale via status-code-only sampling with the configured seed.
- scope.txt is the engagement contract. Vendor infrastructure reached through a client app gets coordinated via the client.
- Never move real money. A 400 VALIDATION or a state differential is full proof.
- Cleanup and disclosure: test accounts deleted, evidence masked by default, sensitive full records only on client request with disposal notes.

## QA gate (before any report ships)

- [ ] Every finding: raw request + raw response + impact line + negative control + CVSS via tool + retest evidence
- [ ] Every evidence citation points to a tool-generated transcript in evidence/raw/ (request exactly as sent, response exactly as received, UTC timestamp; binary bodies byte-exact .bin with sha256); ZERO findings cite hand-written or AI-summarized files; SHA256SUMS.txt covers every raw file
- [ ] Chain matrix present and complete for EVERY verified finding (no empty cells; each cell TESTED/NOT-APPLICABLE/BLOCKED); the proven critical's matrix exhausted before engagement stop
- [ ] Deep-chain checklist answered for every verified finding (parameter semantics 3-way, scale, depth, data classes, foothold export, environment replication, write-sibling check) — findings with unanswered links are UNCHAINED and excluded from REPORT.md
- [ ] Mode selection logged in Round 1 and every mode transition recorded with its trigger
- [ ] Impact quantification block present for every data finding (record count, PII population, freshness, scale) and the CVSS vector cites it (cvss_from_measured_impact)
- [ ] Record minimum and recency evidence present for every data finding
- [ ] Capability matrices complete for every key (can AND cannot)
- [ ] Lateral map present (which services accepted each credential)
- [ ] Coverage table closed (every surface tested or blocked-with-reason)
- [ ] Artifact cleanup evidenced
- [ ] Positive controls section written
- [ ] Banned words absent from REPORT.md
- [ ] Reproduction under 2 minutes verified by a second operator or a fresh agent session

## Common stalls and proven unblocks

| Stalled on | Unblock |
|---|---|
| WAF/CDN blocks | curl_cffi impersonation (configured profile), targeted low-concurrency scans, rotate vantage, skip full spidering |
| Need a platform account (SSO, invite-only) | log as BLOCKED hypothesis, pivot to unauthenticated surfaces meanwhile |
| Geofence or timeout claims | resolve via public DNS first, often just dead DNS |
| Runtime-only signing | hook the signer on-device (frida), captured signature + accepted replay is proof |
| Certificate transparency API down | second and third sources (certspotter, hackertarget) |
| Critical turns out read-only | prove the boundary honestly (all mutations rejected), downgrade, keep the read impact, continue the ladder elsewhere |
| Frida/root detection walls | gadget mode, spawn-time hooks, static pool extraction as the fallback |

## After the report ships

1. Track each finding status (accepted, duplicate, need-more-info) in FINDINGS.
2. Learn-back, the skill compounds: new technique into playbook.md, new tool into mcp-tools.md plus the doctor manifest, reusable code into your own snippets.
3. Credentials we exposed are our disclosure responsibility: state it in the email, give a grace period.
