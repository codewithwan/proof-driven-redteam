# apkpure-downloader

> this tool is purely for educational purposes — i got cloudflare-blocked while scraping the apkpure website T_T so i just reversed their android client instead and used their own api

CLI downloader for the **APKPure internal API** (`hyapi.pureapk.com/v3`) — reversed from the `APKPure 3.20.77` Android client.

It speaks the same v3 channel as the official app, which conveniently skips the Cloudflare wall that guards apkpure.com's web. Fetches the original file + verifies SHA256.

## Features

- **16 registered endpoints** (from `RequestConfigUrlType`/`j7/c.java`); tested: `get_app_detail`, `get_app_his_version`
- **Auto SHA256 verification** after download, skips if an identical file already exists
- **Versioned output paths** — `downloads/{package}/{version}/` — no cross-version collisions
- **Randomized device fingerprint** per request (X-Qimei, gaid, X-Country, UA pool)
- **TLS impersonation** via `curl_cffi` (okhttp4_android_* → chrome*_android → plain requests fallback)
- **Rate-limit + cache**: 2-5s jitter between calls, responses cached until the `asset.url` token expires
- **CLI/env overridable keys** — easy to refresh when APKPure rotates them
- **Auto re-extract keys**: `--extract-keys <apk|jadx-out>` after a client update

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Deps: `curl_cffi` (TLS impersonation), `requests` (fallback).

## Usage

```bash
# Metadata + download XAPK → downloads/com.termux/<version>/Termux.xapk
apkpure-dl com.termux

# Metadata only (no download)
apkpure-dl com.tesla.sw --json-only

# Version history
apkpure-dl com.whatsapp --command get_app_his_version

# No throttle / no TLS impersonation
apkpure-dl com.duolingo --fast
apkpure-dl com.duolingo --no-tls

# List all endpoints
apkpure-dl --list-commands
```

### Keys & env
Every default can be overridden via CLI or env:

| CLI | Env | Description |
|---|---|---|
| `--sign-key` | `APKPURE_SIGN_KEY` | Ual-Access signature MD5 key (`s4/l.java`) |
| `--auth-key` | `APKPURE_AUTH_KEY` | `X-Auth-Key` (`p.java`) |
| `--cv` | `APKPURE_CV` | Client version code |
| `--sv` | `APKPURE_SV` | Server version |
| `--host` | `APKPURE_HOST` | API base host |
| `--country` | `APKPURE_COUNTRY` | Fix X-Country |
| `--aid`, `--flavor` | `APKPURE_AID`, `APKPURE_FLAVOR` | App id / flavor |
| — | `APKPURE_CACHE_DIR` | Cache location (default `~/.cache/apkpure-dl`) |

## Architecture

```
apkpure_dl/
├── config.py        # all tunables + env override
├── crypto.py        # Ual-Access-Signature (MD5)
├── fingerprint.py   # randomized device fingerprint per request
├── transport.py     # TLS impersonation chain
├── throttle.py      # rate-limit jitter 2-5s
├── cache.py         # per-package cache, token-aware
├── commands.py      # v3 endpoint registry (16)
├── client.py        # generic API client + extract_asset
├── downloader.py    # download, sha256, versioned paths
├── extract_keys.py  # auto re-extract keys from APK/jadx
└── cli.py           # `apkpure-dl` entry point
```

Modular per feature — updating one doesn't touch the others.

## Artifacts

Reverse-engineering outputs live versioned in `artifacts/APKPure_3.20.77/`:
- `apkpure.apk` — the original client APK
- `jadx-out/` — decompiled sources
- `apktool/` — resource/smali decode
- `app_detail.json` — sample `get_app_detail` response

When APKPure ships a new client: drop the decode into `artifacts/APKPure_X.Y.Z/` and run `--extract-keys` for the fresh keys.

## Endpoints (from `j7/c.java` RequestConfigUrlType)

| Command | Params | Status |
|---|---|---|
| `get_app_detail` | `packageName`, `page` | ✅ tested |
| `get_app_his_version` | `packageName` | ✅ tested |
| `get_app_developer` | `developerId` | untested |
| `get_app_similar` | `packageName` | untested |
| `get_app_recommend` | `packageName` | untested |
| `get_app_list_about_tag` | `tagId` | untested |
| `search_query` | `q` | untested |
| `search_user` | `q` | untested |
| `get_top`, `get_top_developer_list` | — | untested |
| `get_market_category`, `get_market_rank` | — | untested |
| `get_topic_list`, `get_topics`, `get_topic_app_banner_list` | — | untested |
| `get_app_category` | — | untested |

## Disclaimer

For personal research/reverse-engineering only. Respect APKPure's ToS; don't bulk-scrape or mass-download. Rate-limits are on by default (2-5s jitter included).