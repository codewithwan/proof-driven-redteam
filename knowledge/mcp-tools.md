# MCP Toolbox: What to Call, When (proof-oriented usage)

Base tools of this skill live in `tools/` inside this repo, so the skill is self-contained and portable to any machine. MCP servers can be registered with any MCP-capable agent (opencode, Claude Code, Codex CLI). Nothing here assumes a specific machine layout.

## Vendored tools (in this repo)

Each tool is a self-contained folder. Every MCP server follows the same convention: one folder, one `server.py`.

| Tool | Path | What it does |
|---|---|---|
| APK mirror downloader | `tools/apkpure/` | Acquire target APKs with provenance (versioned + SHA256), bypasses CDN bot walls. Run: `python3 tools/apkpure/apkpure_dl/cli.py <package>` |
| Device APK puller | `tools/device_pull/` | ADB split-APK pull with SHA256, when you have a physical device |
| CVSS MCP | `tools/mcp/cvss/` | cvss31 score/explain/batch, honest severity for reports |
| Tempmail MCP | `tools/mcp/tempmail/` | 7-provider disposable email: account registration + OTP arrival proofs |
| Shodan MCP | `tools/mcp/shodan/` | host/search intel (needs SHODAN_API_KEY) |
| HackTricks MCP | `tools/mcp/hacktricks/` | technique lookup before touching unfamiliar surface |

Python deps for the vendored tools: requests, androguard, curl_cffi, pycryptodome (all listed by `bin/bounty_doctor.py`).

Vigolium (external binary on PATH, not vendored, AGPL) is the web lead engine: dispatch
routing, leads import, OAST lifecycle, and agent LLM setup live in `knowledge/vigolium.md`.

## Registering the MCP servers (any machine, any agent)

Example for an opencode config (`~/.config/opencode/opencode.json`), adapt `<repo>` to your clone path:

```json
{
  "mcp": {
    "cvss":      { "type": "local", "command": ["python3", "<repo>/tools/mcp/cvss/server.py"], "enabled": true },
    "tempmail":  { "type": "local", "command": ["python3", "<repo>/tools/mcp/tempmail/server.py"], "enabled": true },
    "shodan":    { "type": "local", "command": ["python3", "<repo>/tools/mcp/shodan/server.py"], "enabled": true,
                   "environment": { "SHODAN_API_KEY": "<key>" } },
    "hacktricks":{ "type": "local", "command": ["python3", "<repo>/tools/mcp/hacktricks/server.py"], "enabled": true },
    "cve-mcp":   { "type": "local", "command": ["npx", "-y", "cve-mcp"], "enabled": true }
  }
}
```

For Claude Code or Codex, the same servers register with their respective MCP config formats, same commands.

## When to call what

### Acquisition and evidence chain
- Need the target APK (kickoff, version diffing, exact prod build): apkpure_dl. The versioned download + SHA256 answers the report question "how did you obtain the app".
- Second account for an A-to-B IDOR proof: tempmail create, register, tempmail wait with from/subject filters.
- OTP arrival proof: tempmail wait. The received message IS the evidence. Try skipping email verification entirely first, some backends never check it.

### Validation and severity
- Exposed version fingerprint (mail servers, storage, K8s, frameworks): cve-mcp cve_by_product / nvd_search.
- Which CVEs are weaponized: cve_enrich (EPSS + KEV + PoC availability), cve_prioritize.
- PoC / metasploit / nuclei template for a candidate: exploit_search, msf_check, nuclei_check.
- CWE classification and ATT&CK impact framing: cwe_get, cvss_to_attack.
- Severity: cvss31_score + cvss31_explain, full vector in evidence, never invent scores.

Rule: a CVE from version matching is a HYPOTHESIS. Proof is the vulnerable path actually responding (404 means patched, 501 means wrong service). Report verified impact, list the unverified as surface notes.

### Recon and intel
- Unknown product or port before touching it: hacktricks search, then get_page.
- Map an IP estate, ports, banners, CPEs: shodan host. Feeds lateral movement targets.

## Division of labor (memorize)

- Scanners (nuclei, vigolium, semgrep) produce LEADS. They never produce reportable findings.
- MCP tools VALIDATE: cve-mcp turns versions into verified-or-discarded CVEs, tempmail proves dispatch, cvss makes severity defensible.
- Manual requests (curl, Burp, Frida, python) are THE PROOF. The evidence block in every report is a real request you made and a real response you received. That is what gets paid.
