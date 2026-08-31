#!/usr/bin/env python3
"""hunt_recall: search the skill knowledge base for prior art by technique.

Portable by default (searches knowledge/ inside this skill). Optionally also
searches your local workspace FINDINGS files with --workspaces <dir>.

Usage: python3 hunt_recall.py <keyword> [keyword ...] [--workspaces dir]
       python3 hunt_recall.py idor jwt otp
       python3 hunt_recall.py "capability matrix" --workspaces ~/bughunting
"""
import argparse
import sys
from pathlib import Path

KNOW = Path(__file__).resolve().parent.parent / "knowledge"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("--workspaces", help="also search FINDINGS/report files under this dir")
    args = ap.parse_args()
    terms = [q.lower() for q in args.query]

    def hit(line: str) -> bool:
        low = line.lower()
        return all(t in low for t in terms)

    def scan(path: Path, label: str, max_hits: int = 4):
        out, count, ctx = [], 0, 0
        for line in path.read_text(errors="ignore").splitlines():
            if count >= max_hits:
                break
            if hit(line):
                count += 1
                ctx = 2
                out.append(f"  {path.name}: {line.strip()[:160]}")
            elif ctx and line.strip():
                out.append(f"     {line.strip()[:140]}")
                ctx -= 1
        return [(label, o) for o in out]

    results = []
    for f in sorted(KNOW.glob("*.md")):
        results += scan(f, "[knowledge]")
    if args.workspaces:
        wroot = Path(args.workspaces).expanduser()
        for d in sorted(wroot.iterdir()) if wroot.is_dir() else []:
            for f in sorted(d.glob("*.md")):
                results += scan(f, f"[{d.name}]", max_hits=3)

    if not results:
        print("no matches:", " ".join(terms))
        print("try playbook terms: bola, idor, jwt, otp, pbkdf2, firebase, s3, minio, keycloak, lmtp, takeover, signature, capability matrix, lateral, honeypot")
        return 1

    current = None
    for tag, line in results[:40]:
        if tag != current:
            print(f"\n{tag}")
            current = tag
        print(line)
    print(f"\n{len(results)} hits. knowledge: {KNOW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
