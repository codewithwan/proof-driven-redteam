#!/usr/bin/env python3
"""MCP server: semantic search over dumped HackTricks knowledge base.

Run with stdio transport (default for local MCP):
    .venv/bin/python server.py

Tools:
    search_hacktricks(query, top_k=5, section=None)
        Semantic search across all pages. Returns ranked chunks with
        page title, URL, heading, and a content snippet.
    get_page(path) / get_page_by_url(url)
        Return the full markdown of one page (deep dive after a hit).
    list_pages(query=None, limit=100)
        Browse page titles; substring filter on title/path.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from fastmcp import FastMCP

DATA = Path(__file__).parent / "data"
DB = DATA / "hacktricks.db"

mcp = FastMCP("hacktricks")

_model: TextEmbedding | None = None
_db: sqlite3.Connection | None = None
_embeddings: np.ndarray | None = None
_chunk_ids: np.ndarray | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _model


def get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _db = sqlite3.connect(DB)
        _db.row_factory = sqlite3.Row
    return _db


def load_embeddings() -> None:
    global _embeddings, _chunk_ids
    if _embeddings is not None:
        return
    rows = get_db().execute(
        "SELECT id, embedding FROM chunks ORDER BY id"
    ).fetchall()
    _chunk_ids = np.array([r["id"] for r in rows], dtype=np.int64)
    _embeddings = np.stack(
        [np.frombuffer(r["embedding"], dtype="<f4") for r in rows]
    )


def cosine_top_k(query_vec: np.ndarray, k: int) -> list[tuple[int, float]]:
    scores = _embeddings @ query_vec
    top = np.argsort(scores)[::-1][:k]
    return [(int(_chunk_ids[i]), float(scores[i])) for i in top]


@mcp.tool()
def search_hacktricks(query: str, top_k: int = 5, section: str | None = None) -> list[dict]:
    """Semantic search over the HackTricks knowledge base.

    Args:
        query: What you're looking for (e.g. "oracle tns listener enumeration",
               "sqli bypass waf", "dump lsass memory").
        top_k: How many results to return (default 5).
        section: Optional URL-path prefix to restrict the search to, e.g.
                 "network-services-pentesting" or "pentesting-web". None = all.
    """
    load_embeddings()
    model = get_model()
    vec = np.array(list(model.embed([query]))[0], dtype="<f4")
    hits = cosine_top_k(vec, top_k * 3)
    db = get_db()
    results = []
    for chunk_id, score in hits:
        row = db.execute(
            """SELECT c.id, c.heading, c.content, p.path, p.title, p.url
               FROM chunks c JOIN pages p ON p.id = c.page_id
               WHERE c.id = ?""",
            (chunk_id,),
        ).fetchone()
        if row is None:
            continue
        if section and not row["path"].startswith(section):
            continue
        results.append(
            {
                "score": round(score, 4),
                "title": row["title"],
                "path": row["path"],
                "url": row["url"],
                "heading": row["heading"],
                "snippet": row["content"][:1200],
            }
        )
        if len(results) >= top_k:
            break
    return results


@mcp.tool()
def get_page(path: str) -> dict:
    """Return the full markdown of one page by its URL path.

    Args:
        path: The path part of the URL, e.g. "network-services-pentesting/
              1521-1522-1529-pentesting-oracle-listener" (with or without
              .html suffix). Find paths via search_hacktricks / list_pages.
    """
    p = path.removesuffix(".html").strip("/")
    row = get_db().execute(
        "SELECT * FROM pages WHERE path = ?", (p,)
    ).fetchone()
    if row is None:
        like = f"%{p}%"
        row = get_db().execute(
            "SELECT * FROM pages WHERE path LIKE ? LIMIT 1", (like,)
        ).fetchone()
    if row is None:
        return {"error": f"page not found: {path}"}
    return {"title": row["title"], "url": row["url"], "path": row["path"], "markdown": row["markdown"]}


@mcp.tool()
def list_pages(query: str | None = None, limit: int = 100) -> list[dict]:
    """List pages in the knowledge base, optionally filtered by substring.

    Args:
        query: Substring to match against title or path (case-insensitive).
        limit: Max rows (default 100).
    """
    sql = "SELECT path, title, url FROM pages"
    params: list[str] = []
    if query:
        sql += " WHERE title LIKE ? OR path LIKE ?"
        params = [f"%{query}%", f"%{query}%"]
    sql += " ORDER BY path LIMIT ?"
    params.append(str(limit))
    rows = get_db().execute(sql, params).fetchall()
    return [{"path": r["path"], "title": r["title"], "url": r["url"]} for r in rows]


@mcp.tool()
def db_stats() -> dict:
    """Return counts of pages and chunks in the index."""
    db = get_db()
    return {
        "pages": db.execute("SELECT COUNT(*) FROM pages").fetchone()[0],
        "chunks": db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
