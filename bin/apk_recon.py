#!/usr/bin/env python3
"""apk_recon: decode an APK/XAPK into hosts, endpoints, secrets, manifest triage,
and the signing cert SHA-1 needed for key-restriction proofs.

Pure Python where possible (stdlib strings replacement, zipfile for XAPK, androguard
for signatures), so it runs on macOS, Linux, and Windows. jadx/apktool are used when
available and skipped gracefully when not.

Usage: python3 apk_recon.py <target-dir>
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

URL_RE = re.compile(rb"https?://[^\x00-\x20\"'<>\\)]+")
EP_RE = re.compile(r"/(?:api|v[0-9]+|user|auth|payment|otp|voucher|order|reservation|tracking)[A-Za-z0-9_/.{}\-]{3,}")
SECRET_RE = re.compile(
    r"(AIza[0-9A-Za-z_\-]{35}|AKIA[0-9A-Z]{16}|BEGIN (?:RSA |EC )?PRIVATE|eyJ[A-Za-z0-9_\-]{25,}"
    r"|Authorization: Basic [A-Za-z0-9+/=]{10,}|client_secret|aesKey|ivB64|hmac|signing.?key)",
    re.IGNORECASE,
)


def py_strings(path: Path) -> bytes:
    """stdlib replacement for the strings binary: extract printable runs."""
    data = path.read_bytes()
    return b"\n".join(m.group() for m in re.finditer(rb"[\x20-\x7e]{6,}", data))


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except FileNotFoundError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", help="target workspace directory (contains app/)")
    args = ap.parse_args()
    root = Path(args.dir).expanduser()
    appdir = root / "app"
    if not appdir.is_dir():
        print("no app/ directory in", root)
        return 1
    (root / "decoded").mkdir(exist_ok=True)
    (root / "extracted").mkdir(exist_ok=True)

    apk = next((p for p in sorted(appdir.glob("*.apk"))), None)
    if apk is None:
        xapk = next((p for p in sorted(appdir.glob("*.xapk"))), None)
        if not xapk:
            print("no apk/xapk in app/")
            return 1
        out = appdir / "unzipped"
        with zipfile.ZipFile(xapk) as z:
            z.extractall(out)
        apk = next((p for p in sorted(out.glob("*.apk")) if "config" not in p.name), None) or next(iter(out.glob("*.apk")))
    print(f"[1/6] apk: {apk.name}")

    if not (root / "decoded" / "jadx-out").exists() and shutil.which("jadx"):
        run(["jadx", "-d", str(root / "decoded" / "jadx-out"), str(apk)])
    if not (root / "decoded" / "apktool").exists() and shutil.which("apktool"):
        run(["apktool", "d", "-q", str(apk), "-o", str(root / "decoded" / "apktool")])
    print("[2/6] decode done (jadx/apktool skipped if missing)")

    allstrings = py_strings(apk)
    (root / "extracted" / "allstrings.txt").write_bytes(allstrings)
    flutter = b""
    for so in (root / "decoded" / "apktool" / "lib").glob("*/libapp.so"):
        flutter += py_strings(so) + b"\n"
    if flutter:
        (root / "extracted" / "flutter_strings.txt").write_bytes(flutter)
    blob = (allstrings + b"\n" + flutter).decode("utf-8", "ignore")
    hosts = sorted(set(m.group(0).decode("utf-8", "ignore").split('"')[0].split(",")[0] for m in URL_RE.finditer((allstrings + flutter))))
    (root / "extracted" / "hosts.txt").write_text("\n".join(h for h in hosts if h[:4] == "http"))
    eps = sorted(set(EP_RE.findall(blob)))
    (root / "extracted" / "endpoints.txt").write_text("\n".join(eps))
    print(f"[3/6] hosts: {len(hosts)}  endpoints: {len(eps)}")

    lines = ["=== secret sweep (LEADS ONLY, prove manually) ==="]
    for ln in blob.splitlines():
        if SECRET_RE.search(ln):
            lines.append(ln.strip()[:200])
            if len(lines) > 80:
                break
    (root / "extracted" / "secret_sweep.txt").write_text("\n".join(lines))
    print(f"[4/6] secret_sweep.txt: {len(lines) - 1} hits, triage manually")

    man = root / "decoded" / "apktool" / "AndroidManifest.xml"
    triage = ["=== manifest ===", "(decode apktool for full manifest)"]
    if man.exists():
        mtext = man.read_text(errors="ignore")
        triage = [
            "=== manifest flags ===",
            "\n".join(sorted(set(re.findall(r'android:(?:allowBackup|usesCleartextTraffic)="[a-z]+"', mtext)))) or "(defaults)",
            "=== exported components ===",
            "\n".join(re.findall(r'android:name="([^"]+)"', "\n".join(l for l in mtext.splitlines() if 'android:exported="true"' in l))[:10]) or "(none)",
            "=== autoVerify hosts ===",
            "\n".join(sorted(set(re.findall(r'android:host="([^"]+)"', mtext)))[:15]) or "(none)",
        ]
    libdir = root / "decoded" / "apktool" / "lib"
    stack = []
    if any(libdir.glob("*/libapp.so")):
        stack.append("FLUTTER: run blutter on decoded/apktool/lib/<abi> (secrets live in the Dart object pool)")
    if (root / "decoded" / "apktool" / "assets" / "index.android.bundle").exists():
        stack.append("REACT NATIVE: hbc-decompiler on the bundle")
    if (root / "decoded" / "apktool" / "assets" / "app.config").exists():
        stack.append("EXPO: read assets/app.config (plaintext creds are common there)")
    triage += ["=== stack ===", "\n".join(stack) or "native/other"]
    (root / "extracted" / "manifest_triage.txt").write_text("\n".join(triage))
    print("\n".join(triage))

    sig = ["=== signing cert SHA-1 (for X-Android-Cert proofs) ==="]
    try:
        from androguard.core.apk import APK  # type: ignore
        a = APK(str(apk))
        certs = a.get_certificates_der_v3() or a.get_certificates_der_v2() or [a.get_certificate_der()]
        rawhex = hashlib.sha1(certs[0]).hexdigest()
        sig += [f"rawhex: {rawhex}", f"package: {a.get_package()}", "use rawhex in X-Android-Cert and package in X-Android-Package"]
    except Exception as e:
        sig += [f"signature extraction failed: {e}", "pip install androguard"]
    (root / "extracted" / "signature.txt").write_text("\n".join(sig))
    print("\n".join(sig))
    print("[5/6] outputs written")
    print("[6/6] next: triage secret_sweep + manifest_triage, capability-matrix every key,")
    print("      lateral movement against all discovered surfaces, minimal live proof.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
