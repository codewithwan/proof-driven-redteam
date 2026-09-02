# apkpure MCP server

APKPure + Play Store target intelligence as MCP tools. Wraps the vendored
apkpure_dl toolkit plus live Play Store checks and engagement-fit scoring.

## Tools (all tested live)

| Tool | What it does |
|---|---|
| `apkpure_detail` | Mirror metadata: version, versionCode, update date, downloads, SHA-256, asset type |
| `apkpure_pull` | Download the package (XAPK) with tool-side SHA-256 verification |
| `play_verify` | Live Play Store check (no account): current version, update date, installs, rating |
| `target_score` | Engagement-fit score 0-30 + verdict: freshness (weighted 15pts) + install scale (15pts) + mirror-vs-Play version drift. ACTIVE / ALIVE / STALE |

`target_score` encodes the operator's hunting criteria: an app updated within
30 days with 100k+ installs scores well; stale apps (6mo+) are flagged STALE
regardless of size; "mirror-ahead" drift upgrades the verdict (dev iterates
faster than Play listing shows).

## Registration (any MCP-capable agent)

```json
{
  "mcp": {
    "apkpure": { "type": "local",
      "command": ["python3", "<repo>/tools/mcp/apkpure/server.py"],
      "enabled": true }
  }
}
```

Deps: `requests` (apkpure_dl vendored in ./apkpure_dl; google_play_scraper
optional - falls back to mirror-only detail if absent).

## Usage flow (the standard target-verification ritual)

1. `target_score <package>` - one call answers: worth hunting? verdict + why
2. `apkpure_detail` + `play_verify` - exact versions both sources (drift check)
3. `apkpure_pull` - acquire with provenance (SHA-256 returned, store in evidence)

Discipline: every target suggestion includes this verification before naming
the target (operator rule, 2026-08-31).
