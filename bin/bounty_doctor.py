#!/usr/bin/env python3
"""bounty_doctor: environment checklist for the bug-hunting skill.

Detect-only. Works on macOS, Linux, and Windows (pure Python, stdlib only).
Usage: python3 bounty_doctor.py [--json]
"""
import json
import os
import shutil
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(SKILL_DIR, "tools")

rows = []


def add(name, ok, hint="", optional=False):
    status = "READY" if ok else ("OPTIONAL" if optional else "MISSING")
    rows.append((name, status, hint))


def which(cmd):
    return shutil.which(cmd) is not None


# --- enforcement tools (must exist inside the skill) ---
for tool in ("evidence_capture", "differential", "impact_parser", "chain_gate"):
    p = os.path.join(SKILL_DIR, "bin", tool + ".py")
    add(tool + ".py", os.path.exists(p),
        "part of this skill; reinstall/repair the skill copy" if not os.path.exists(p) else "")

# --- core CLI tools ---
for cmd, hint in [
    ("jadx", "Java decompiler: brew install jadx / scoop install jadx"),
    ("apktool", "Resource+manifest decoder: brew install apktool"),
    ("nuclei", "Template scanner (leads only): projectdiscovery releases"),
    ("adb", "Android platform-tools"),
    ("java", "Needed by jadx/apktool/keytool"),
    ("nc", "netcat for infra port proofs (Windows: use Test-NetConnection)"),
    ("curl", "HTTP client"),
]:
    add(cmd, which(cmd), hint, optional=cmd in ("nuclei", "nc"))
for cmd, hint, opt in [
    ("subfinder", "go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest", True),
    ("waybackurls", "go install github.com/tomnomnom/waybackurls@latest", True),
    ("gau", "go install github.com/lc/gau/v2/cmd/gau@latest", True),
    ("katana", "go install github.com/projectdiscovery/katana/cmd/katana@latest", True),
    ("trufflehog", "secrets scanner", True),
    ("semgrep", "SAST", True),
    ("hbc-decompiler", "npm i -g hbc-decompiler (Hermes/RN bundles)", True),
    ("frida", "pip install frida-tools (dynamic hooks)", True),
    ("ideviceinstaller", "brew install libimobiledevice (iOS app pull, jailbroken device)", True),
    ("class-dump", "ObjC header dumper for iOS binaries (brew install class-dump)", True),
    ("node", "Node for js-reverse.md deobfuscation sandboxes (Babel/AST work)", True),
    ("js-beautify", "npm i -g js-beautify (pretty-print, js-reverse.md)", True),
]:
    add(cmd, which(cmd), hint, optional=opt)

# --- vigolium (web lead engine, knowledge/vigolium.md; versioned) ---
if which("vigolium"):
    try:
        out = subprocess.run(["vigolium", "version", "-j"], capture_output=True,
                             text=True, timeout=15)
        ver = json.loads(out.stdout).get("version", "").lstrip("v")
        add("vigolium", True, f"v{ver} web lead engine (see knowledge/vigolium.md)")
    except (json.JSONDecodeError, ValueError, subprocess.SubprocessError, OSError):
        add("vigolium", True, "version unreadable; see knowledge/vigolium.md")
else:
    add("vigolium", False, "web lead engine: curl -fsSL https://vigolium.com/install.sh | bash", optional=True)

# --- blutter (Flutter Dart AOT dumper): env override, then common paths ---
blutter = os.environ.get("BLUTTER_HOME") or ""
if not blutter:
    for cand in ("~/Tools/blutter", "~/tools/blutter", "~/blutter"):
        p = os.path.expanduser(cand)
        if os.path.exists(os.path.join(p, "blutter.py")):
            blutter = p
            break
if not blutter:
    blutter = "blutter.py" if which("blutter") else ""
add("blutter", bool(blutter), blutter or "BLUTTER_HOME=<clone of worawit/blutter>; needs dart+flutter+cmake+ninja", optional=True)
add("dart", which("dart"), "flutter SDK (blutter dependency)", optional=True)
add("flutter", which("flutter"), "flutter SDK (blutter dependency)", optional=True)

# --- python libs ---
for mod, hint, opt in [
    ("requests", "pip install requests", False),
    ("androguard", "pip install androguard (v1+v2+v3 signing cert SHA-1)", False),
    ("curl_cffi", "pip install curl_cffi (WAF/CDN bypass)", True),
    ("Crypto", "pip install pycryptodome (AES/DES replicas)", True),
]:
    try:
        __import__(mod)
        add("py:" + mod, True)
    except ImportError:
        add("py:" + mod, False, hint, optional=opt)

# --- vendored tools (ship with this skill, always present) ---
add("tools/apkpure", os.path.isfile(os.path.join(TOOLS_DIR, "apkpure", "apkpure_dl", "cli.py")))
add("tools/play_store", os.path.isfile(os.path.join(TOOLS_DIR, "play_store", "play_meta.py")))
add("tools/device_pull", os.path.isfile(os.path.join(TOOLS_DIR, "device_pull", "get_app_from_device.py")))
add("tools/mcp/cvss", os.path.isfile(os.path.join(TOOLS_DIR, "mcp", "cvss", "server.py")))
add("tools/mcp/tempmail", os.path.isfile(os.path.join(TOOLS_DIR, "mcp", "tempmail", "server.py")))
add("tools/mcp/shodan", os.path.isfile(os.path.join(TOOLS_DIR, "mcp", "shodan", "server.py")))
add("tools/mcp/hacktricks", os.path.isfile(os.path.join(TOOLS_DIR, "mcp", "hacktricks", "server.py")))
add("tools/mcp/jadx", os.path.isfile(os.path.join(TOOLS_DIR, "mcp", "jadx", "server.py")))
add("tools/mcp/burp", os.path.isfile(os.path.join(TOOLS_DIR, "mcp", "burp", "server.py")))

# --- MCP registration (agent config, machine specific, informational only) ---
cfg = os.path.expanduser("~/.config/opencode/opencode.json")
if os.path.isfile(cfg):
    try:
        mcp = (json.load(open(cfg)).get("mcp") or {})
        for m in ("cve-mcp", "cvss", "tempmail", "hacktricks", "shodan", "jadx", "burp"):
            add("mcp:" + m, bool(mcp.get(m, {}).get("enabled")), "register via knowledge/mcp-tools.md", optional=True)
    except Exception:
        pass
else:
    rows.append(("mcp:registration", "SKIPPED", "no opencode config on this machine; see knowledge/mcp-tools.md",))

json_out = "--json" in sys.argv
if json_out:
    print(json.dumps({n: s for n, s, _ in rows}, indent=2))
    sys.exit(0)

print(f"{'TOOL':24}{'STATUS':10}HINT")
print("-" * 78)
for n, s, h in rows:
    print(f"{n:24}{s:10}{h}")
ready = sum(1 for _, s, _ in rows if s == "READY")
print("-" * 78)
print(f"{ready}/{len(rows)} ready. Doctrine: PROOF OR NOTHING. Scanner output is a lead;")
print("findings need a real request, a real response, and demonstrated impact.")
print(f"Skill root: {SKILL_DIR}")
