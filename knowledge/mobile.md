# Mobile Hunting: APK Acquisition to Proof Pipeline (per stack)

The proven loop across 12+ APK engagements: acquire with provenance, decode, extract, sweep, signature, dynamic instrumentation, minimal live proof, lateral movement. This file is the complete mobile methodology.

## 1. Acquisition WITH PROVENANCE EVIDENCE

A report must answer "how did you obtain the app?". Record it every time.

| Method | Tool | Evidence produced |
|---|---|---|
| App-store mirror | `python3 tools/apkpure/apkpure_dl/cli.py <package>` (vendored) | versioned downloads/{pkg}/{ver}/ plus SHA256; handles CDN bot walls via TLS impersonation |
| From a device | `python3 tools/device_pull/get_app_from_device.py` (vendored) | apk-dumps/{pkg}/base.apk plus splits, SHA256 per file |
| Client-provided file | copy into app/, hash immediately | app/SHA256SUMS.txt plus app/PROVENANCE.txt |

Rules:
- app/ is the untouched source of truth. Decode elsewhere.
- XAPK is a zip: extract, use the non-config apk as base, keep splits (signatures and native libs differ per split).
- Version diffing is a first-class technique: acquire two versions and diff string dumps and pools. Secrets get added between versions, and diffing surfaces exactly what changed.
- Record the app-store metadata (version code) alongside the hash: builds are identified by versionCode, not versionName.

## 2. Decode (all stacks)

`python3 bin/apk_recon.py <target-dir>` automates the core. Manual depth beyond it:

- jadx: full Java/Kotlin source. Use `jadx --deobf` for obfuscated builds; keep both raw and deobf outputs.
- apktool: manifest, res/, assets/, lib/. The smali is the fallback when jadx chokes.
- strings: apk_recon.py implements a stdlib printable-run extractor so no binary dependency exists. For huge .so files prefer targeted extraction after the first pass.
- hosts.txt and endpoints.txt come from URL and path regexes. Also extract: base64-looking blobs, JSON assets, embedded .env files, protobuf descriptors.

Manifest triage, 2 minutes, pays off every time:
- allowBackup, usesCleartextTraffic, missing networkSecurityConfig
- exported activities/services/receivers/providers (payment activities are a classic)
- autoVerify hosts: fetch https://<host>/.well-known/assetlinks.json for each immediately
- URL schemes and intent-filter actions
- BASE_URLs pointing at dev domains in prod builds: hygiene finding plus dangling-host risk
- debuggable, testOnly flags

## 3. Signing signature, REQUIRED for key-restriction proofs

The app's signing cert SHA-1 unlocks X-Android-Cert proofs (Maps restriction bypass) and proves which build you tested.

Modern APKs are v2/v3-only signed and `keytool -printcert -jarfile` FAILS on them ("Not a signed jar file"). Use androguard, which handles v1+v2+v3 (apk_recon.py does this automatically):

```python
from androguard.core.apk import APK
import hashlib
a = APK("base.apk")
certs = a.get_certificates_der_v3() or a.get_certificates_der_v2() or [a.get_certificate_der()]
print(hashlib.sha1(certs[0]).hexdigest())  # raw lowercase hex, no colons
```

Use the raw hex in X-Android-Cert and the package name in X-Android-Package. Cross-check: the SHA-1 must be consistent across splits. This step is mandatory, not optional.

## 4. Per-stack deep dive

### Flutter (Dart AOT), libapp.so
- blutter (github.com/worawit/blutter) dumps the Dart class pool into pp.txt, asm, and a frida hook template. Point BLUTTER_HOME at your clone; the doctor checks it.
- blutter needs the Dart SDK matching the snapshot version. Version-mismatch errors name the version needed; fetch that SDK and retry.
- The object pool is the secret magnet: service-account keys as int-arrays, OAuth creds at fixed pool indices. Static-only extraction is preferred over runtime hooks when possible.
- Strings from libapp.so miss pool data that blutter recovers. Run both.

### React Native / Hermes (HBC bytecode)
- hbc-decompiler or hbctool disasm. Output is large JS: grep for secrets and endpoints directly. AES keys hide at exact line numbers in the decompiled bundle.
- Bundle version matters: match the Hermes bytecode version to the tool build.

### Expo
- assets/app.config, app.json, embedded manifest: credentials frequently ship in plaintext there. Always cat the assets directory listing.

### Native Kotlin/Java
- Custom .so config libraries: run the strings extractor over every lib/*/lib*.so, not just libapp.so.
- Check assets/ and res/raw/ for embedded JSON configs, certs, and databases.

### WebView hybrids
- Grep for loadUrl, addJavascriptInterface, shouldInterceptRequest, @JavascriptInterface methods. Map every bridge method and its native capability.

## 5. Secret sweep (before ANY live request)

Regex classes: AIza..., AKIA/ASIA..., BEGIN PRIVATE, eyJ... (JWT), Authorization: Basic, client_secret, BuildConfig.AUTH, aesKey/ivB64/hmac/salt/signing, sk_live/pk_live, ghp_/gho_ (GitHub), xox (Slack), webhook URLs.

Post-sweep discipline: classify each hit (secret class per playbook class 1), then plan the capability matrix. All hits are LEADS until proven.

## 6. Network capture stack (dynamic)

1. Device or emulator with developer options. Check `getprop ro.product.cpu.abi` BEFORE pushing anything (mismatched arch wastes sessions).
2. Proxy: Burp or mitmproxy at a known IP:port on your host.
3. CA certificate: Android 7+ blocks user CAs for app traffic by default. Options in order: (a) app targets API < 24 or has a permissive networkSecurityConfig (check the manifest first, several prod apps still do), (b) system CA via rooted device or AVB-disabled emulator, (c) Frida unpinning plus SSLUnpinning hooks, (d) repair the client's TLS stack at the Frida layer if needed.
4. Proxy-detection bypass: apps that check system_proxy_properties or test connectivity directly. Frida hooks neutralize the checks.
5. Capture the full first-run flow: install > register (tempmail) > login > browse every main feature. Save har/flows files into traffic/.

## 7. Dynamic instrumentation cookbook (Frida)

Standard hooks that pay off across targets (each is a small script; keep a per-target harness folder):

| Hook target | What it gives you |
|---|---|
| Signature/header builders (sign, X-Signature, wToken, nonce methods) | The exact signing inputs and key material at runtime |
| Cipher.init / Cipher.doFinal (javax.crypto) | Keys and IVs as used, for the crypto class |
| okhttp Interceptor chain | Every request with headers, before pinning |
| WebView.loadUrl + shouldInterceptRequest | Deeplink chain execution tracing |
| SharedPreferences reads/writes | Token storage locations and formats |
| root/attestation checks | Bypasses for protected apps |

Method: locate the method statically (jadx/blutter), hook it, exercise the app, capture inputs/outputs. A captured real signature plus a replayed accepted request is proof. The blutter frida template and the hook above both live in the harness folder per target.

Anti-analysis you will meet and their standard bypasses:
- Root detection (su, magisk, busybox paths): hook the detection methods, not the filesystem.
- Frida detection (port 27042, frida-server name, thread names): rename frida-server, use gadget mode, or spawn-time hooks.
- Integrity/integrity-play checks (Play Integrity, SafetyNet remnants): usually out of scope to attack, note and continue.
- Certificate pinning: standard unpinning scripts first, custom pins via okhttp/SSLContext hooks second.
- LIAPP and commercial packers: static extraction still works on string pools; runtime hooks may need anti-anti-frida work. Budget time for it.

## 8. IPC and exported surface testing

For every exported component from manifest triage:
- Activities: start via adb am start with crafted extras. Watch for crashes and unauthorized UI access (exported payment activities are a classic).
- Receivers: broadcast crafted intents (protected broadcasts will refuse; note which are protected).
- Providers: query via content:// URIs, check grantUriPermissions, path traversal in openFile implementations.
- Deeplinks: fire the full intent chain (playbook class 9), fuzz handler parameters.

Backup analysis (allowBackup=true): adb backup > ABE unpack > grep for tokens and PII in the extracted data. This is a standalone finding (local data theft via adb backup on a lost or shared device).

## 9. Live proof: minimal, differential, lateral

- One real request with the recovered credential against the most sensitive READ endpoint, saved as evidence JSON. Negative control (garbage token gets 401/403) in the same block.
- Lateral movement is mandatory: replay the credential against EVERY host in hosts.txt and EVERY endpoint in endpoints.txt. "One public client secret accepted by five microservices" was a real Critical report.
- WAF or CDN blocking: curl_cffi impersonation with the configured profile.
- NXDOMAIN vs geofence: resolve via public DNS before claiming unreachable. Several "geo-fenced" hosts turned out to be dead DNS.
- Writes: prefixed artifacts, dummy IDs or terminal-state objects, pre-registered in FINDINGS, cleaned up, cleanup logged.
- OTP dispatch proof: your OWN number or inbox. Arrival, not result:true.

## 10. Required outputs per target

```
app/SHA256SUMS.txt + PROVENANCE.txt
extracted/{allstrings, flutter_strings, hosts, endpoints, secret_sweep, manifest_triage, signature}.txt
decoded/{jadx-out, apktool, blutter_out or hbc-out}
traffic/first-run.har or .flows
recon/harness/ (frida scripts per target)
poc/poc_<id>.py            self-verifying, --mask default, prints PASS/FAIL
evidence/*.json            real request+response pairs, masked
```
