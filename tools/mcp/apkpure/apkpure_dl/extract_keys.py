"""Auto re-extract sign/auth keys from an updated APK or a jadx-out dir.

Keys rotate when APKPure ships a new client → re-run and pass the new values
via --sign-key / --auth-key (or APKPURE_SIGN_KEY / APKPURE_AUTH_KEY).
"""

import re
import zipfile
from pathlib import Path

from .config import Config

_SIG_RE = re.compile(r"^[0-9a-f]{32}$")
_AUTH_RE = re.compile(r"^[A-Za-z0-9]{28,40}$")
_HEX32_INLINE = re.compile(r'"([0-9a-f]{32})"')
_AUTH_TARGET = re.compile(
    r'(?:setAuthKey\s*\(\s*|"X-Auth-Key"\s*,\s*|\bAuthKey\s*=\s*)["\']([^"\']{24,40})["\']'
)
_SIGN_TARGET = re.compile(
    r'(?i)(?:md5|messageDigest|getInstance\s*\(\s*"MD5"|digestBytes|signkey|sign_key)[^\n]{0,80}?"?\b([0-9a-f]{32})\b'
)


def _dex_string_runs(data: bytes):
    for m in re.finditer(rb"[\x20-\x7e]{12,}", data):
        yield m.group().decode("ascii", "ignore")


def _is_clean_token(s: str) -> bool:
    if any(c in s for c in "/. ()"):
        return False
    if s[0].isupper():
        return False  # class names start uppercase; APKPure keys start lowercase
    return not s.startswith(("android", "com/", "androidx", "java/", "kotlin", "okhttp"))


def extract_keys(target: str) -> None:
    p = Path(target)
    results = {"sign_keys": set(), "auth_keys": set()}

    if p.is_dir():
        for f in p.rglob("*.java"):
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in _AUTH_TARGET.finditer(txt):
                v = m.group(1)
                if _AUTH_RE.match(v) and v != "0" * 32:
                    results["auth_keys"].add(v)
            for m in _SIGN_TARGET.finditer(txt):
                v = m.group(1)
                if _SIG_RE.match(v):
                    results["sign_keys"].add(v)
            for m in _HEX32_INLINE.finditer(txt):
                v = m.group(1)
                if _SIG_RE.match(v) and _is_clean_token(v):
                    results["sign_keys"].add(v)
    else:
        if not zipfile.is_zipfile(p):
            raise SystemExit(f"not a zip/apk: {p}")
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if name.startswith("classes") and name.endswith(".dex"):
                    for run in _dex_string_runs(z.read(name)):
                        for tok in re.findall(r"[0-9a-f]{32}", run):
                            if _is_clean_token(tok):
                                results["sign_keys"].add(tok)
                        for tok in re.findall(r"[A-Za-z0-9]{28,40}", run):
                            if len(tok) <= 36 and tok != "0" * 32 and _is_clean_token(tok):
                                results["auth_keys"].add(tok)

    print(f"=== key extraction from: {p}")
    sigs = sorted(results["sign_keys"])
    auths = sorted(results["auth_keys"])
    if sigs:
        print("\n[+] SIGN keys (32-hex) → --sign-key:")
        for k in sigs:
            mark = "  <-- current default" if k == Config.DEFAULT_SIGN_KEY else ""
            print(f"    {k}{mark}")
    else:
        print("\n[!] no sign keys found (release dex may obfuscate — try the jadx-out dir).")
    if auths:
        print("\n[+] AUTH keys → --auth-key:")
        for k in auths:
            mark = "  <-- current default" if k == Config.DEFAULT_AUTH_KEY else ""
            print(f"    {k}{mark}")
    else:
        print("\n[!] no auth keys found (release dex may obfuscate — try the jadx-out dir).")
    print("\n[tip] sign key = MD5 key (s4/l.java), auth key = X-Auth-Key (p.java / s4/j.java).")