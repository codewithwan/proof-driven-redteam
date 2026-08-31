# <target> - Security Assessment Report

**Target:** <app/domain + version + build>
**Reporter:** <company> (authorized security assessment / coordinated disclosure)
**Period:** <dates> (N rounds: R1-Rk static, Rm-Rn authorized dynamic)
**Classification:** CONFIDENTIAL - contains sensitive data samples until rotation

## 1. Executive Summary

One systemic failure or the main chain, plus the impact table:

| # | Impact | Evidence | Status |
|---|--------|----------|--------|
| 1 | | | VERIFIED |

Severity: per-finding CVSS plus aggregate chain position.

Remediation P0 (ordered):
1.
2.

## 2. Attack Chain (reproduction under 2 minutes)

```bash
# step 1
# step 2
```

PoC: `poc/<script>` (self-verifying, `--no-mask` for verifiers).

## 3. Architecture and blast radius

- Host map, service map, cloud split
- Lateral movement map: which services/endpoints accepted the leaked credential

## 4. Findings index (PROVEN findings only)

| ID | Finding | Status | Severity |
|----|---------|--------|----------|

## 5. Positive controls (honest negatives)

## 6. Data handling (for client audit)

Records read (count + masking + recency evidence: newest record timestamps), disposal notes.

## 7. Open items

1.

Methodology: static analysis then authorized dynamic verification, non-destructive by design (SECTEST_-labeled writes only, cleaned up). Every claim is backed by raw request/response evidence.
