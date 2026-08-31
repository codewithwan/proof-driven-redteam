#!/usr/bin/env python3
"""Chunk + embed dumped HackTricks pages into sqlite.

Reads data/pages/*.md, chunks by heading, embeds with fastembed
(bge-small-en-v1.5), stores in data/hacktricks.db.

Schema:
    pages(id INTEGER PK, path TEXT UNIQUE, title TEXT, url TEXT, markdown TEXT)
    chunks(id INTEGER PK, page_id INTEGER FK, seq INTEGER, heading TEXT,
           content TEXT, embedding BLOB)

Run from project root. Resumable: re-running skips pages already indexed
(when their chunk count matches), or rebuilds incrementally.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastembed import TextEmbedding

DATA = Path(__file__).parent / "data"
PAGES = DATA / "pages"
DB = DATA / "hacktricks.db"
BATCH = 64

SECTION_RE = (
    "## ",
    "### ",
    "#### ",
)


def iter_pages() -> list[Path]:
    return sorted(PAGES.rglob("*.md"))


def split_headings(md: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, content) sections at heading boundaries."""
    sections: list[tuple[str, str]] = []
    cur_heading = ""
    cur_lines: list[str] = []
    for line in md.split("\n"):
        stripped = line.strip()
        if stripped.startswith(SECTION_RE) and len(stripped) < 200:
            if cur_lines:
                sections.append((cur_heading, "\n".join(cur_lines).strip()))
            cur_heading = stripped.lstrip("#").strip()
            cur_lines = [line]
        else:
            cur_lines.append(line)
    if cur_lines:
        sections.append((cur_heading, "\n".join(cur_lines).strip()))
    return [(h, c) for h, c in sections if len(c) > 80]


def chunk_section(heading: str, content: str, max_len: int = 1500, overlap: int = 120) -> list[str]:
    """Split a section into overlapping chunks at paragraph boundaries."""
    if len(content) <= max_len:
        return [content]
    paras = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        if cur and len(cur) + len(p) > max_len:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            cur = (tail + "\n\n" if tail else "") + p
        else:
            cur = (cur + "\n\n" + p) if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def build_db() -> None:
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            title TEXT,
            url TEXT,
            markdown TEXT
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            page_id INTEGER NOT NULL REFERENCES pages(id),
            seq INTEGER NOT NULL,
            heading TEXT,
            content TEXT,
            embedding BLOB
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_page ON chunks(page_id);
        """
    )
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    print("model ready", flush=True)

    pages = iter_pages()
    total = len(pages)
    known = {r[0] for r in db.execute("SELECT path FROM pages")}
    new_pages = [p for p in pages if str(p.relative_to(PAGES)) not in known]

    print(f"pages: {total}, new: {len(new_pages)}", flush=True)

    for idx, p in enumerate(new_pages, 1):
        rel = str(p.relative_to(PAGES)).removesuffix(".md")
        title = p.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
        title = title.lstrip("#").strip() or rel
        url = f"https://hacktricks.wiki/en/{rel}.html"
        md = p.read_text(encoding="utf-8", errors="replace")
        cur = db.execute(
            "INSERT OR IGNORE INTO pages(path, title, url, markdown) VALUES(?,?,?,?)",
            (rel, title, url, md),
        )
        if cur.rowcount == 0:
            continue
        page_id = cur.lastrowid

        chunks: list[tuple[str, str]] = []
        for heading, content in split_headings(md):
            for c in chunk_section(heading, content):
                chunks.append((heading, c))

        texts = [c for _, c in chunks]
        for start in range(0, len(texts), BATCH):
            batch = texts[start:start + BATCH]
            embeds = list(model.embed(batch))
            for j, (heading, content) in enumerate(chunks[start:start + BATCH]):
                blob = embeds[j].astype("<f4").tobytes()
                db.execute(
                    "INSERT INTO chunks(page_id, seq, heading, content, embedding) VALUES(?,?,?,?,?)",
                    (page_id, start + j, heading, content, blob),
                )
        db.commit()
        if idx % 25 == 0 or idx == len(new_pages):
            print(f"  indexed {idx}/{len(new_pages)} (page_id={page_id})", flush=True)

    db.commit()
    n_pages = db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    n_chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"DONE pages={n_pages} chunks={n_chunks}", flush=True)
    db.close()


if __name__ == "__main__":
    sys.exit(build_db())
