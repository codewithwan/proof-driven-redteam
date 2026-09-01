# MCP Toolbox: What to Call, When (proof-oriented usage)

Base tools of this skill live in `tools/` inside this repo, so the skill is self-contained and portable to any machine. MCP servers can be registered with any MCP-capable agent (opencode, Claude Code, Codex CLI). Nothing here assumes a specific machine layout.

## Vendored tools (in this repo)

Each tool is a self-contained folder. Every MCP server follows the same convention: one folder, one `server.py`.

| Tool | Path | What it does |
|---|---|---|
| APK mirror downloader | `tools/apkpure/` | Acquire target APKs with provenance (versioned + SHA256), bypasses CDN bot walls via TLS impersonation. Run: `python3 tools/apkpure/apkpure_dl/cli.py <package>` |
| Play Store metadata | `tools/play_store/` | `play_meta.py <pkg>` - live Play Store version/update date, no account, no mirror lag. The authoritative "newest Play version" check. `play_pull.py` downloads directly from Play but needs a burner Google account (see its README) |
| Device APK puller | `tools/device_pull/` | ADB split-APK pull with SHA256, when you have a physical device |
| CVSS MCP | `tools/mcp/cvss/` | cvss31 score/explain/batch, honest severity for reports |
| Tempmail MCP | `tools/mcp/tempmail/` | 7-provider disposable email: account registration + OTP arrival proofs |
| Shodan MCP | `tools/mcp/shodan/` | host/search intel (needs SHODAN_API_KEY) |
| HackTricks MCP | `tools/mcp/hacktricks/` | technique lookup before touching unfamiliar surface |
| JADX MCP | `tools/mcp/jadx/` | APK decompile over the jadx CLI: single class, code search, class list, manifest (needs jadx on PATH, JADX_BIN overrides) |
| Burp MCP bridge | `tools/mcp/burp/` | transparent stdio proxy to Burp's native MCP server: raw HTTP requests, Repeater/Intruder, Collaborator, scanner issues, proxy history (needs Burp running, BURP_MCP_URL overrides) |

Python deps for the vendored tools: requests, androguard, curl_cffi, pycryptodome (all listed by `bin/bounty_doctor.py`).

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
    "jadx":     { "type": "local", "command": ["python3", "<repo>/tools/mcp/jadx/server.py"], "enabled": true },
    "burp":     { "type": "local", "command": ["python3", "<repo>/tools/mcp/burp/server.py"], "enabled": true },
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
- Raw request/response transcripts through the same engine used by hand: burp send_http1_request / send_http2_request. The returned transcript IS the evidence block, captured from Burp, satisfying the raw-pairs rule without leaving the agent.
- Out-of-band proof (SSRF, blind injection, callback reachability): burp generate_collaborator_payload, then poll get_collaborator_interactions. An interaction log entry is dispatch evidence, nothing more.
- Hand a raw request to the human for a verdict: burp create_repeater_tab (HTTP/2 variant for modern targets), send_to_intruder for parameter sweeps.

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

### Static analysis (APK, agent-driven)
- Decode one suspicious class fast, no full decompile first: jadx get_class with the fully qualified name.
- Secret and endpoint sweep over decompiled sources: jadx search_code (substring, warms the cache on first call; big apps take a while, later calls are instant).
- Manifest review (permissions, exported components, deeplinks): jadx get_manifest.
- Class inventory for the coverage table: jadx list_classes with a filter, feeds all_endpoints_probed and all_keys_capability_matrixed bookkeeping.
- What jadx finds is a LEAD: hardcoded keys, endpoints, weak crypto. Capability matrices and lateral replay still convert leads into findings.

### Burp-centric triage
- Scanner issues (burp get_scanner_issues): LEADS, never findings. Manually confirm before any report line.
- Proxy history mining (get_proxy_http_history_regex): reconstruct session flow, find auth tokens and untested endpoints from real traffic.

## Division of labor (memorize)

- Scanners (nuclei, vigolium, semgrep, Burp scanner) produce LEADS. They never produce reportable findings.
- MCP tools VALIDATE: cve-mcp turns versions into verified-or-discarded CVEs, tempmail proves dispatch, cvss makes severity defensible, jadx serves the static corpus, burp issues and replays the real requests.
- Manual requests (curl, Burp, Frida, python) are THE PROOF. The evidence block in every report is a real request you made and a real response you received. That is what gets paid.
