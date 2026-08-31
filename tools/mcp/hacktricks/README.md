# mcphacktrick

Offline semantic search MCP server over the full [HackTricks](https://hacktricks.wiki/) knowledge base (902 pages EN). Dump → embed → query via MCP tools, no external API, no vector DB.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python dump.py     # crawl sitemap → data/pages/*.md (resumable)
.venv/bin/python index.py    # chunk + embed → data/hacktricks.db (resumable)
.venv/bin/python server.py   # MCP stdio server
```

MCP is already registered in `~/.config/opencode/opencode.json` as `hacktricks`.

## MCP tools

| Tool | Purpose |
|------|---------|
| `search_hacktricks(query, top_k=5, section=None)` | Semantic search across all pages, returns ranked chunks with title/URL/heading/snippet. `section` restricts to a URL-path prefix (e.g. `network-services-pentesting`, `pentesting-web`). |
| `get_page(path)` | Full markdown of one page (deep dive after a hit). |
| `list_pages(query=None, limit=100)` | Browse page titles, substring filter. |
| `db_stats()` | Page/chunk counts. |

Example search:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"cli","version":"1"}}}' | .venv/bin/python server.py
```

## Vigolium workflow

The MCP plugs into the agent (opencode), not into vigolium directly —
vigolium's agent mode has its own LLM pipeline and no MCP client. Flow:

```
vigolium scan -t <target> --fail-on high      # 1. find a bug
vigolium finding -j --min-severity high --compact --fields id,module_id,url
                                              # 2. read the finding
# 3. ask the agent: "search hacktricks for <module/title>" → MCP returns
#    the relevant exploitation knowledge (payloads, commands, references)
# 4. replay / confirm / escalate with that context
```

Example prompts after vigolium flags something:

- `search_hacktricks("oracle tns listener enumeration sqlnet.ora", section="network-services-pentesting")`
- `search_hacktricks("mssql xp_cmdshell command execution")`
- `get_page("network-services-pentesting/1521-1522-1529-pentesting-oracle-listener")`

## Rebuild after HackTricks updates

```bash
.venv/bin/python dump.py    # only new/changed pages (resumable by file)
.venv/bin/python index.py   # only unindexed pages (INSERT OR IGNORE)
```

## Layout

```
dump.py        crawl sitemap → markdown pages
index.py       chunk by headings + fastembed (bge-small-en-v1.5) → sqlite
server.py      MCP stdio server (fastmcp 3.x, JSONL framing)
data/pages/    raw markdown, mirrors URL paths
data/hacktricks.db   pages + chunks + embeddings
```
