# play_store tools

Direct Google Play access without mirrors. Two tools, one folder:

## play_meta.py - live Play Store metadata (no account)

The authoritative answer to "what is the newest Play version" - mirrors like
APKPure lag behind Play by days or weeks.

```bash
python3 play_meta.py com.bpjstku
python3 play_meta.py "https://play.google.com/store/apps/details?id=com.bpjstku"
```

Deps: requests only (google_play_scraper vendored in lib/).

## play_pull.py - download APKs straight from Play (burner account)

Wraps the unofficial Play API (gpapi vendored in lib/). First login needs a
burner Google account; tokens persist afterwards.

```bash
pip install protobuf cryptography requests
cp play_account.json.example play_account.json   # fill burner email/password
python3 play_pull.py com.bpjstku --out play_downloads
```

Notes:
- Use a burner account. Automated Play downloads violate Google ToS and the
  account may be flagged - same risk profile as mirror tooling, but on your
  own account. Never use a personal/primary account.
- Output is base.apk + config splits (same shape as device pulls), ready for
  the standard apk_recon pipeline.
- If login fails with 2FA errors: the account must not require interactive
  2FA for this flow; try an account with an app password or reduced security.

## Layout

```
play_store/
  play_meta.py              no-account metadata checker
  play_pull.py              account-gated direct downloader
  play_account.json.example credentials template (copy, never commit)
  lib/google_play_scraper/  vendored (MIT)
  lib/gpapi/                vendored (MIT)
```

## Alternatives when an account is not available

- Device pull (tools/device_pull) if the app is already installed: always
  exact-build, zero account risk.
- Aurora Store on the test device downloads from Play anonymously; then pull
  via adb. Useful for apps not on any mirror (e.g. region-locked listings).
