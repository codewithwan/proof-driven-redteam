# Reporting: Findings, Reports, Disclosure (proof only)

One rule above all: the report contains only proven findings. The hypothesis queue stays in FINDINGS.md. The report is a professional deliverable: a client should be able to reproduce every claim in under two minutes and act on every remediation item without a clarification call.

## FINDINGS.md (per-round log, append only)

```md
## Round N - <title> (date, authorization note)
### [ID-xx] <verdict> - short title
raw command + raw response (curl, nc transcript, JSON)
interpretation + honesty boundary (what is NOT proven)
CVSS vector when final
Hypothesis queue update
```

Verdicts: VERIFIED / NEGATIVE / UNCONFIRMED (hypothesis queue) / RETRACTED.

Writes with the configured artifact prefix (config.json, default SECTEST_) are pre-registered here BEFORE execution, in the artifact registry, with cleanup evidence appended after.

## REPORT.md (executive structure)

1. Executive Summary: one systemic failure or the main chain, an impact table (evidence + status), aggregate severity, one-paragraph business risk statement in client language.
2. Attack Chain: reproduction under 2 minutes (curl blocks) + PoC script path.
3. Architecture and blast radius: host map, service map, cloud split, lateral movement map (which services accepted the credential).
4. Findings index: ID, finding, status, severity. PROVEN findings only.
5. Positive controls: honest negatives (validated social auth, locked databases, parameterized SQL). Raises the credibility of every severity claim.
6. Data handling: what was read, sample sizes, recency evidence, disposal notes. Clients audit this.
7. Open items: client-side log checks, staging, coordination.
8. Remediation P0 ordered: rotate secrets, ownership checks, scope enforcement, rate limits. Per finding: root cause, fix, verification step.

Banned words in REPORT.md (config.json): potential, candidate, likely, possibly, theoretical, could. If the word is needed, the finding is not ready.

## Full finding write-up skeleton (per finding, in section 4)

```md
### [KF-01] Title: imperative impact statement, not a class name
- Severity: CVSS vector + score (via the cvss MCP tool) + qualitative + program-class framing when applicable
- Status: VERIFIED (+ retest evidence)
- Summary: 2-3 sentences, business impact first, technical second
- Affected: exact components (host, endpoint, app version, build)
- Description: the vulnerability, plain language, one screen max
- Steps to reproduce: numbered, copy-pasteable, under 2 minutes total
- Evidence: file references into evidence/raw/ (tool-generated raw transcripts ONLY — hand-written or AI-summarized files are banned as proof; see workflow.md evidence rules)
- Impact quantification: the MEASURED numbers (record count, PII field population %, newest/oldest timestamps, scale across parameter values) — this block is mandatory for data findings and is what the severity stands on
- Impact: demonstrated (what we did) and bounded (what we deliberately did not do)
- Chain matrix row: what this finding enables elsewhere (finding-into-finding included), with evidence links
- Lateral map: which other surfaces accepted the same credential
- Root cause: the engineering reason (missing ownership check, static secret, etc)
- Remediation: ordered fixes + how to verify each fix closes it
```

Writing rules:
- Titles state impact ("Unauthenticated read of all medical prescriptions"), not class ("BOLA in API").
- Present tense, active voice. "An attacker retrieves" not "could potentially be retrieved by".
- One fact per sentence. Every claim maps to an evidence file.
- Quantify: record counts, dollar amounts, affected user classes, dates of newest data.

## Executive summary formula

1. One sentence: the systemic failure.
2. One sentence: the strongest demonstrated impact chain.
3. Impact table: rows are demonstrated impacts, columns are evidence and status.
4. One sentence: aggregate severity positioning (why the chain is Critical-equivalent even if per-finding scores are lower).
5. Remediation headline: the top 3 actions in order.

## Severity negotiation playbook

- Programs score per finding, isolated. Your position: chains. Present both (dual framing): per-finding CVSS as scored by the tool, plus the aggregate chain position with a one-paragraph justification.
- CVSS vectors are selected from MEASURED impact (config.testing.cvss_from_measured_impact): C:H requires quantified PII/location/credential disclosure (record counts, field populations, freshness); S:C requires the chain matrix proving cross-service impact; A:L/H requires demonstrated or credibly-argued availability effect. Never score from imagination — the vector must cite the impact-quantification block.
- When the measured data class elevates the finding beyond its vector (children's locations, identity numbers, PDP-law/GDPR classes, safety-of-persons), say so explicitly as program-class framing alongside — never by inflating the vector.
- When a reviewer downgrades with "requires an attacker to have X": show the acquisition path for X in your own evidence (the secret is public in the APK, the account registration is open, the enumeration yields targets). If the path is in your report, the precondition is satisfied.
- When a reviewer calls data stale: your recency evidence (newest-record dates, artifact write-read-back) answers before they ask.
- When told "not exploitable": you have the boundary proof section already, so the discussion stays factual.
- Never inflate. One retraction honestly handled beats ten inflated claims, and clients remember who retracted fast.

## Disclosure email pattern

- Subject: specific and verifiable.
- Answer their questions ONE BY ONE (yes/no plus evidence).
- Reproduction they can run themselves in under 2 minutes, two curl blocks.
- Attachments: self-verifying PoC (--mask default, --no-mask by request), seeded sampling CSV, ONE full record by request with disposal note.
- Offer a live demo or screen share, plus an encrypted channel for sensitive records.
- Root-cause remediation (rotate secret, ownership layer, gateway scope enforcement), not symptom patches.
- Give a rotation grace period before publishing anything.
- Cadence: initial notice > acknowledgment follow-up at 72h > status follow-up at 7d > resolution summary. Keep every message in FINDINGS as a communication log.

## Retest and validation handling

- Every verified finding is retested the configured number of times (default 2) with evidence captures per run, BEFORE the report ships.
- After the client deploys fixes: rerun the PoC suite verbatim, capture the new responses, mark each finding FIXED / PARTIALLY FIXED / UNFIXED with evidence. Never trust a fix description over a rerun.

## Negative results belong in the report too

Flat SQLi timings, CVE paths 404ing, parameterized logins, locked cloud buckets go under Positive Controls. Effect: honest positioning, no wasted re-testing, every remaining severity claim gets stronger.

## Final quality checklist (QA gate from workflow.md)

- Every finding has raw request, raw response, impact line, negative control, tool-scored CVSS, and retest evidence
- Every evidence citation points to a TOOL-GENERATED transcript in evidence/raw/ (request exactly as sent, response exactly as received, UTC timestamp); no finding cites analysis notes or hand-typed summaries; SHA256SUMS.txt covers every raw file
- Record minimum and recency evidence present for every data finding
- Capability matrices complete (can AND cannot)
- Lateral map present
- Coverage table closed
- Artifact cleanup evidenced
- Positive controls written
- Banned words absent
- Reproduction verified by a second operator or fresh session
