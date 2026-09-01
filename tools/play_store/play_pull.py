#!/usr/bin/env python3
"""play_pull: download an app directly from Google Play (no mirrors).

Uses the unofficial Play API (gpapi). Requires a Google account for the first
login (use a burner account); gsfId + authSubToken are persisted afterwards so
credentials are only needed once.

Setup:
  1. pip install protobuf cryptography requests   (gpapi deps)
  2. cp play_account.json.example play_account.json  and fill email/password
  3. python3 play_pull.py com.bpjstku [--out DIR]

The account file is local-only; never commit it.
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")  # gpapi pb2 shim
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

HERE = Path(__file__).resolve().parent
ACCOUNT = HERE / "play_account.json"
TOKENS = HERE / "play_tokens.json"


def get_api():
    from gpapi.googleplay import GooglePlayAPI

    if TOKENS.is_file():
        t = json.loads(TOKENS.read_text())
        api = GooglePlayAPI(locale="en_US", timezone="Asia/Jakarta", device_codename=t.get("device", "px_7a"))
        api.setAuthSubToken(t["authSubToken"])
        api.gsfId = t["gsfId"]
        return api

    if not ACCOUNT.is_file():
        print("no tokens and no play_account.json - copy play_account.json.example,")
        print("fill a burner Google email/password, and rerun.")
        sys.exit(2)
    acc = json.loads(ACCOUNT.read_text())
    api = GooglePlayAPI(locale="en_US", timezone="Asia/Jakarta", device_codename=acc.get("device", "px_7a"))
    api.login(email=acc["email"], password=acc["password"])
    TOKENS.write_text(json.dumps({"gsfId": api.gsfId, "authSubToken": api.authSubToken, "device": acc.get("device", "px_7a")}))
    print(f"[+] login ok, tokens saved to {TOKENS.name} (delete it to force re-login)")
    return api


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--out", default="play_downloads")
    args = ap.parse_args()

    api = get_api()
    det = api.details(args.package)
    details = det.get("details", {}).get("appDetails", {})
    print(f"{args.package}: {det.get('title')} | version {details.get('versionString')} ({details.get('versionCode')})")

    out = Path(args.out) / args.package / (details.get("versionString") or "unknown")
    out.mkdir(parents=True, exist_ok=True)

    dl = api.download(args.package)
    files = dl.get("splits", {})
    base = dl.get("file")
    if base is not None:
        (out / "base.apk").write_bytes(base.read())
        print(f"[+] base.apk")
    for name, fh in files.items():
        (out / f"{name}.apk").write_bytes(fh.read())
        print(f"[+] {name}.apk")
    print(f"done -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
