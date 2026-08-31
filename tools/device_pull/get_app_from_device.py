#!/usr/bin/env python3
import os
import re
import subprocess
from pathlib import Path

OUT = Path.cwd() / "apk-dumps"

def run(cmd):
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def adb(*args):
    return run(["adb", *args])

def check_device():
    r = adb("devices")
    lines = [x for x in r.stdout.splitlines()[1:] if x.strip()]
    devices = [(x.split()[0], x.split()[1]) for x in lines if len(x.split()) >= 2]
    ready = [d for d in devices if d[1] == "device"]
    if not ready:
        print("\n[!] No ADB device in 'device' state.")
        print(r.stdout.strip() or r.stderr.strip())
        print("\nFix Wireless Debugging / USB debugging, then run this again.")
        return False
    print(f"[+] Connected: {ready[0][0]}")
    return True

def get_packages():
    r = adb("shell", "pm", "list", "packages")
    if r.returncode != 0:
        print(r.stderr)
        return []
    return sorted(x.replace("package:", "").strip()
                  for x in r.stdout.splitlines() if x.startswith("package:"))

def get_paths(pkg):
    r = adb("shell", "pm", "path", pkg)
    paths = []
    for line in r.stdout.splitlines():
        if line.startswith("package:"):
            paths.append(line.replace("package:", "", 1).strip())
    return paths

def get_version(pkg):
    r = adb("shell", "dumpsys", "package", pkg)
    vc = re.search(r"versionCode=(\d+)", r.stdout)
    vn = re.search(r"versionName=([^\s]+)", r.stdout)
    return (vn.group(1) if vn else "?"), (vc.group(1) if vc else "?")

def safe_name(remote):
    return Path(remote).name or "app.apk"

def main():
    print("=" * 58)
    print(" ADB APK DUMPER — interactive split APK extractor")
    print("=" * 58)

    if not check_device():
        return

    packages = get_packages()
    if not packages:
        print("[!] No packages found.")
        return

    query = input("\nSearch package [Enter = show all]: ").strip().lower()
    matches = [p for p in packages if query in p.lower()] if query else packages

    if not matches:
        print("[!] No matching package.")
        return

    # Keep menu manageable while allowing exact package selection.
    for i, p in enumerate(matches, 1):
        print(f"{i:4}. {p}")

    choice = input("\nSelect number or type package name: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(matches):
        pkg = matches[int(choice) - 1]
    else:
        pkg = choice
        if pkg not in packages:
            print("[!] Package not found.")
            return

    version, code = get_version(pkg)
    paths = get_paths(pkg)

    if not paths:
        print(f"[!] Could not get APK paths for {pkg}.")
        return

    out = OUT / pkg
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n[+] Package     : {pkg}")
    print(f"[+] Version     : {version} (code {code})")
    print(f"[+] APK splits  : {len(paths)}")
    print(f"[+] Output      : {out}")

    for remote in paths:
        name = safe_name(remote)
        dest = out / name
        print(f"\n[*] Pulling {name} ...")
        r = adb("pull", remote, str(dest))
        if r.returncode == 0:
            print(f"[+] OK: {dest}")
        else:
            print(f"[!] Failed: {r.stderr.strip()}")

    print("\n[+] SHA-256:")
    for f in sorted(out.glob("*.apk")):
        r = run(["shasum", "-a", "256", str(f)])
        print(r.stdout.strip() if r.returncode == 0 else f"[!] {f.name}: hash failed")

    print("\nDone.")

if __name__ == "__main__":
    main()

