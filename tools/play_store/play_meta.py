#!/usr/bin/env python3
"""play_meta: exact Play Store metadata for a package - no account needed.

Primary source of truth for "what is the newest Play Store version" (mirrors lag).

Usage:
  python3 play_meta.py com.bpjstku
  python3 play_meta.py com.bpjstku com.jasamarga.jid   # multiple
  python3 play_meta.py <url>                            # play.google.com URLs accepted
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from google_play_scraper import app  # noqa: E402

PKG_FROM_URL = re.compile(r"play\.google\.com/store/apps/details\?id=([A-Za-z0-9._]+)")


def norm(target: str) -> str:
    m = PKG_FROM_URL.search(target)
    return m.group(1) if m else target


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for target in sys.argv[1:]:
        pkg = norm(target)
        try:
            d = app(pkg)
        except Exception as e:
            print(f"{pkg}: FETCH FAILED - {e}")
            continue
        print(f"{pkg}")
        print(f"  title    : {d.get('title')}")
        print(f"  version  : {d.get('version')} (Play Store, live)")
        print(f"  updated  : {d.get('updated') and __import__('datetime').datetime.fromtimestamp(d['updated']).date()}")
        print(f"  installs : {d.get('installs')}")
        print(f"  rating   : {d.get('score')} ({d.get('ratings')} ratings)")
        print(f"  developer: {d.get('developer')}")
        print(f"  genre    : {d.get('genre')}")
        print(f"  url      : https://play.google.com/store/apps/details?id={pkg}")
        if "--json" in sys.argv:
            Path(f"{pkg}.json").write_text(json.dumps(d, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
