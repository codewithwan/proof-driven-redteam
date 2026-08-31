"""Asset downloader: versioned paths + sha256 verification + skip-if-identical."""

import hashlib
from pathlib import Path

from . import transport
from .client import extract_asset


def target_path(out_dir: Path, pkg: str, version_name: str, filename: str) -> Path:
    """downloads/{package}/{version}/file — versions never collide."""
    safe_pkg = pkg.replace("/", "_")
    safe_ver = (version_name or "unknown").replace("/", "_")
    return out_dir / safe_pkg / safe_ver / filename


def pick_filename(asset_type: str, package: str, version: str, url: str) -> str:
    import urllib.parse as up
    if "filename=" in url:
        fn = up.parse_qs(up.urlparse(url).query).get("filename", [None])[0]
        if fn:
            return up.unquote(fn)
    ext = ".xapk" if asset_type == "XAPK" else ".apk"
    return f"{package}_{version}{ext}"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url: str, out: Path, expected_sha256: str = "", chunk: int = 8192) -> str:
    if out.exists() and out.stat().st_size > 0:
        print(f"[-] exists {out} ({out.stat().st_size} bytes)")
        if expected_sha256:
            got = sha256_of(out)
            if got == expected_sha256:
                print(f"[+] already downloaded, sha256 OK (skip)")
                return got
            print(f"[!] hash mismatch, re-downloading…")
    out.parent.mkdir(parents=True, exist_ok=True)
    resp = transport.get(url)
    try:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        with open(out, "wb") as f:
            for c in resp.iter_content(chunk_size=chunk):
                if c:
                    f.write(c)
                    done += len(c)
                    if total:
                        print(f"\r  {done}/{total} ({done * 100 // total}%)", end="", flush=True)
    finally:
        resp.close()
    print()
    got = sha256_of(out)
    if expected_sha256:
        if got == expected_sha256:
            print(f"[+] sha256 OK: {got}")
        else:
            print(f"[!] sha256 MISMATCH\n    expected {expected_sha256}\n    got      {got}")
    return got


def download_from_detail(resp: dict, out_dir: Path) -> Path:
    info = extract_asset(resp)
    url = info["asset_url"]
    if not url:
        raise SystemExit("[!] no asset.url in response — nothing to download")
    fname = pick_filename(info["asset_type"], info["package_name"], info["version_name"], url)
    out = target_path(out_dir, info["package_name"], info["version_name"], fname)
    print(f"[+] download → {out}")
    download(url, out, expected_sha256=info["file_sha256"])
    return out