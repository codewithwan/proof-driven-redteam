"""CLI entry point: `apkpure-dl`."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .client import app_detail, app_his_version, extract_asset, call
from .commands import COMMANDS, command_names
from .config import Config
from .downloader import download_from_detail
from .extract_keys import extract_keys as _extract_keys
from .throttle import throttle

DEFAULT_DELAY = (2.0, 5.0)


def _parse_delay(s: str):
    if "-" in s:
        a, b = s.split("-", 1)
        return (float(a), float(b))
    v = float(s)
    return (v, v)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="apkpure-dl",
        description=f"APKPure internal API downloader (v{__version__}) — reversed from APKPure 3.20.77")
    ap.add_argument("package", nargs="?", help="packageName, e.g. com.termux")
    ap.add_argument("--command", "-c", default="get_app_detail", choices=command_names(),
                    help="endpoint command (default: get_app_detail)")
    ap.add_argument("--json-only", action="store_true", help="fetch metadata only")
    ap.add_argument("--out", "-o", default="downloads", help="output dir (default: ./downloads)")
    ap.add_argument("--dump", help="dump raw JSON response to file")
    ap.add_argument("--no-cache", action="store_true", help="ignore cached response")
    ap.add_argument("--fast", action="store_true", help="disable 2-5s jitter throttle")
    ap.add_argument("--delay", default=None, help="throttle range, e.g. '2-5' or '0'")
    ap.add_argument("--no-tls", action="store_true", help="skip TLS impersonation")
    ap.add_argument("--verbose", action="store_true", help="print generated headers")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # key / device overrides
    ap.add_argument("--sign-key", help="Ual-Access signature MD5 key (s4/l.java)")
    ap.add_argument("--auth-key", help="X-Auth-Key value (p.java)")
    ap.add_argument("--cv", help="X-Cv client version code")
    ap.add_argument("--sv", help="X-Sv server version")
    ap.add_argument("--host", help="API base host")
    ap.add_argument("--country", help="X-Country (default: random from pool)")
    ap.add_argument("--aid", help="X-Aid app id")
    ap.add_argument("--flavor", help="X-Flavor")
    ap.add_argument("--extract-keys", metavar="PATH",
                    help="auto-extract sign/auth keys from an APK or jadx-out dir, then exit")
    ap.add_argument("--list-commands", action="store_true", help="print all endpoint commands")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_commands:
        print("APKPure v3 commands (from RequestConfigUrlType / j7/c.java):")
        for name in command_names():
            desc = COMMANDS[name]["desc"]
            params = ", ".join(COMMANDS[name]["params"]) or "—"
            tested = " [tested]" if name in {"get_app_detail", "get_app_his_version"} else ""
            print(f"  {name:<28} params: {params:<40} {desc}{tested}")
        return 0

    if args.extract_keys:
        _extract_keys(args.extract_keys)
        return 0

    if not args.package:
        print("[!] package required (or use --extract-keys / --list-commands)", file=sys.stderr)
        return 2

    rng = _parse_delay(args.delay) if args.delay is not None else (DEFAULT_DELAY if not args.fast else (0, 0))

    cfg = Config(sign_key=args.sign_key, auth_key=args.auth_key, cv=args.cv, sv=args.sv,
                 host=args.host, country=args.country, aid=args.aid, flavor=args.flavor,
                 no_tls=args.no_tls, verbose=args.verbose)

    if args.command == "get_app_detail":
        throttle(enabled=rng[1] > 0, rng=rng)
        resp = app_detail(cfg, args.package, use_cache=not args.no_cache)
        info = extract_asset(resp)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        if args.dump:
            Path(args.dump).write_text(json.dumps(resp, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[+] dumped → {args.dump}")
        if not args.json_only:
            download_from_detail(resp, Path(args.out))
    else:
        params = {}
        if "packageName" in COMMANDS[args.command]["params"]:
            params["packageName"] = args.package
        elif "q" in COMMANDS[args.command]["params"]:
            params["q"] = args.package
        elif "developerId" in COMMANDS[args.command]["params"]:
            params["developerId"] = args.package
        throttle(enabled=rng[1] > 0, rng=rng)
        resp = call(cfg, args.command, params if params else None, use_cache=not args.no_cache)
        print(json.dumps(resp, indent=2, ensure_ascii=False)[:4000])
        if args.dump:
            Path(args.dump).write_text(json.dumps(resp, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[+] dumped → {args.dump}")
    return 0


if __name__ == "__main__":
    sys.exit(main())