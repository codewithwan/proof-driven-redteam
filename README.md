# Proof-Driven Red Team Methodology

An engagement operating system for offensive security work: a proof gate, a chain-first
finding discipline, and impact quantification from measured data — enforced by policy as
code, not by memory.

## Core principles

1. **No proof, no report.** Every finding ships with a raw request, a raw response, and a
   demonstrated impact. Evidence is tool-generated transcripts only — hand-written summaries
   are banned as proof and treated as tampering.
2. **Chains beat points.** A finding is the start of escalation, never the finish line. Every
   verified finding must pass the deep-chain checklist (parameter semantics, scale, depth,
   data classes, foothold export, environment replication, write siblings) before it is
   reportable. One unchained finding is unfinished work.
3. **Severity from measurement.** CVSS vectors cite quantified impact — parsed record counts,
   PII field populations, freshness windows, parameter cardinality — never imagination.
4. **Honesty is leverage.** Explicit retractions, honest boundaries, and negative results are
   recorded with the same rigor as findings. They are why clients grant more access.
5. **Mode is conditional.** Static-first when a client artifact exists, dynamic-first when it
   does not; mixed mode is normal. The mode choice and every transition is logged. Whichever
   mode finds the lead, only captured evidence makes it a finding.

## What is inside

| Path | Purpose |
|---|---|
| `config.json` | Engagement policy engine: budget, stop conditions, proof gates, evidence rules, chain requirements — agents treat it as law |
| `knowledge/workflow.md` | The engagement loop: phases, hypothesis management, plan gate, proof gate, chain matrix, deep-chain checklist, mode selection, QA gate |
| `knowledge/playbook.md` | Vulnerability classes ranked by real hit-rate, each with proof bars and escalation trees, plus anti-patterns |
| `knowledge/mobile.md` | APK acquisition-to-proof pipeline: decode, sweep, instrumentation, IPC |
| `knowledge/web.md` | Web estate methodology |
| `knowledge/reporting.md` | Report structure, severity negotiation, dual framing |
| `bin/` | Scaffolding + recon + **enforcement tooling**: `evidence_capture.py` (the only front door for dynamic probes — raw transcripts guaranteed), `differential.py` (3-way parameter-semantics prober), `impact_parser.py` (impact quantification from captured bodies), `chain_gate.py` (QA gate as code — a report ships only when it exits 0) |
| `tools/` | Vendored utilities (one folder per concern, pure where possible) |
| `templates/` | Report and finding templates |

## Quick start

```bash
python3 bin/bounty_doctor.py          # environment checklist
python3 bin/target_init.py <slug>     # scaffold an engagement workspace
```

## The loop

```
G Gather   scaffold, acquire with provenance, recon coverage
A Analyze  decode, sweep secrets, map endpoints and flows
P Plan     written dynamic test plan (no plan, no dynamic testing)
C Confirm  minimal live probes, differentials, hypotheses to proof
O Operate  capability matrices, lateral movement, artifact discipline
R Report   only proven findings; hypotheses stay queued
```

## License / use

Internal methodology distilled from authorized engagements. Use only against systems you are
explicitly authorized to test. The policy engine (`config.json`) is the contract — edit it,
never soften it silently.
