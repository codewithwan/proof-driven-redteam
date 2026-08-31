#!/usr/bin/env python3
"""Dump hacktricks.wiki EN site (from sitemap) to markdown files.

Structure mirrors URL paths:
    https://hacktricks.wiki/en/<path>.html  ->  data/pages/<path>.md

Resumable: already-fetched files are skipped. Run from project root.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import httpx
import trafilatura

SITEMAP = "https://hacktricks.wiki/en/sitemap.xml"
OUT_DIR = Path(__file__).parent / "data" / "pages"
CONCURRENCY = 12
TIMEOUT = 30.0
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) mcphacktrick-dump/1.0"


async def fetch_sitemap_urls(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(SITEMAP, timeout=TIMEOUT)
    r.raise_for_status()
    urls = re.findall(r"<loc>(.*?)</loc>", r.text)
    return [u for u in urls if "/en/" in u]


def clean_markdown(md: str) -> str:
    """Strip HackTricks promo boilerplate from extracted markdown.

    Known noise, in order:
      1. leading "Tip / Learn & practice AWS/GCP/Azure Hacking" ad block
      2. "## Support HackTricks" block that sometimes repeats mid-page
      3. trailing footer (last "## Support HackTricks" block)
    """
    if not md:
        return ""
    lines = md.split("\n")

    keep = []
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln == "## Support HackTricks":
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        if ln == "Tip" and i + 2 < len(lines) and "Learn & practice" in lines[i + 2]:
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        keep.append(lines[i])
        i += 1

    md = "\n".join(keep)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


def extract_page(html: str, url: str) -> str:
    start = html.find("<h1")
    if start < 0:
        return ""
    main = html[start:]
    md = trafilatura.extract(
        main,
        include_comments=False,
        include_tables=True,
        output_format="markdown",
        url=url,
    )
    return clean_markdown(md or "")


def url_to_path(url: str) -> tuple[Path, str]:
    """Map URL to (file_path, title)."""
    rel = url.replace("https://hacktricks.wiki/en/", "").removesuffix(".html")
    if not rel:
        rel = "index"
    # strip trailing slash variants
    rel = rel.rstrip("/") or "index"
    file_path = OUT_DIR / f"{rel}.md"
    title = rel.replace("-", " ").replace("/", " » ").title()
    return file_path, title


async def worker(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str, stats: dict) -> None:
    file_path, _ = url_to_path(url)
    if file_path.exists():
        stats["skipped"] += 1
        return
    async with sem:
        try:
            r = await client.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            md = extract_page(r.text, url)
            if len(md) < 200:
                stats["empty"] += 1
                (OUT_DIR / ".." / ".." / "data" / "empty.txt").parent.mkdir(parents=True, exist_ok=True)
                with open(OUT_DIR.parent / "empty.txt", "a") as f:
                    f.write(url + "\n")
                return
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(md, encoding="utf-8")
            stats["ok"] += 1
        except Exception as e:  # noqa: BLE001 - network resilience
            stats["failed"] += 1
            with open(OUT_DIR.parent / "failed.txt", "a") as f:
                f.write(f"{url}\t{type(e).__name__}: {e}\n")


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=CONCURRENCY)
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        limits=limits,
        follow_redirects=True,
    ) as client:
        urls = await fetch_sitemap_urls(client)
        print(f"sitemap: {len(urls)} pages", flush=True)
        stats = {"ok": 0, "skipped": 0, "failed": 0, "empty": 0}
        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = [asyncio.create_task(worker(client, sem, u, stats)) for u in urls]
        # progress reporter
        done = 0
        total = len(tasks)
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{total}  ok={stats['ok']} skip={stats['skipped']} fail={stats['failed']} empty={stats['empty']}", flush=True)
        print(f"DONE ok={stats['ok']} skipped={stats['skipped']} failed={stats['failed']} empty={stats['empty']}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
