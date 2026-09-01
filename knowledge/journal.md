# Journal: dated learn-back log

Append-only, one entry per learned technique. This file exists so hunt_recall finds dated
prior art that does not yet belong in a playbook class. When an entry hardens into a class
(battle-tested, proof bar validated), promote it into playbook.md and leave a stub line here
pointing at the class number.

Entry format (keep every field, one screen max):

```md
## YYYY-MM-DD - <technique in one imperative line>
- Engagement type: mobile / web / infra / mixed (anonymized, no client names)
- Signal: what made us look
- Technique: the exact commands or code shape that worked
- Proof bar: what evidence converted it (or why it stayed a lead)
- Status: LEAD / PROVEN / RETRACTED / PROMOTED to playbook class N
```

Rules:
- No target names, no client names, no raw secrets. Techniques and shapes only.
- A RETRACTED entry is as valuable as a PROVEN one: it kills a repeat detour.
- After every engagement (workflow.md: after the report ships), append what was new.
- Techniques that repeat across two engagements get promoted into playbook.md.

## 2026-09-01 - Vendor an MCP server by writing a stdlib stdio JSON-RPC loop

- Engagement type: tooling (skill development, first external contributions)
- Signal: two community PRs (merged as #1, #2) arrived following an undocumented but repeatable format
- Technique: the repeatable contribution shape is: one folder tools/mcp/<name>/server.py (pure Python stdlib, hand-rolled initialize/tools/list/tools/call dispatch, newline-delimited JSON-RPC on stdin/stdout) + a doctor row in bounty_doctor.py + a table row and registration snippet in knowledge/mcp-tools.md + a SKILL.md routing line. No mcp SDK dependency, no machine paths, config via env var override.
- Proof bar: py_compile plus a live stdio handshake test (printf initialize + tools/list into the server, parse the JSON out). That is enough to trust the server before registering it.
- Status: PROVEN (both PRs merged, jadx handshake verified live: 5 tools listed)

## 2026-09-01 - Ghidra on macOS via brew needs JAVA_HOME pointed at the keg-only JDK

- Engagement type: tooling (environment setup for native RE)
- Signal: brew formula ghidra installed but analyzeHeadless failed with "Unable to locate a Java Runtime" even though openjdk@21 was present as a dependency
- Technique: brew installs openjdk@21 keg-only (not linked, java stub cannot see it). Fix: export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home in the shell profile. Ghidra 12.x requires JDK 21+.
- Proof bar: analyzeHeadless prints the JDK banner and usage text with JAVA_HOME set; it errors without.
- Status: PROVEN

## 2026-09-01 - semgrep-mcp wrapper hard-fails without a Semgrep account; CLI suffices

- Engagement type: tooling (MCP wiring)
- Signal: uvx semgrep-mcp died in server lifespan even with the semgrep CLI installed
- Technique: semgrep-mcp v0.9.0 runs `semgrep --pro --version` at startup, which requires semgrep-core-proprietary (login or SEMGREP_APP_TOKEN). Same doctrine as nuclei: scanner = leads only, so the CLI (brew install semgrep, 1.175.0) is sufficient; keep the MCP entry disabled.
- Proof bar: reproduce with a stdio initialize handshake; the traceback names ensure_semgrep_available and the --pro check.
- Status: PROVEN (decision: CLI-only, same reasoning as nuclei-MCP skip)

## 2026-09-01 - MCP servers that proxy a host GUI app only live with the host running

- Engagement type: tooling (architecture pattern)
- Signal: burp bridge and ghidra-mcp bridge both fail fast when their host app is down
- Technique: treat GUI-backed MCP bridges as on-demand: the bridge exits when the host is unreachable, and the agent restarts it next session. Before an engagement round needing Burp or Ghidra, start the host app first (Burp with MCP enabled on 9876; Ghidra GUI with the GhidraMCP plugin server started on 8080). Cache jshookmcp's large npx deps before an engagement, first download is slow.
- Proof bar: handshake tests with and without the host running.
- Status: PROVEN
