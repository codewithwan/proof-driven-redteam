# tempmail-mcp

MCP server disposable-email multi-provider untuk opencode. Dibangun untuk bug bounty / security testing (registrasi flow, OTP, verifikasi email) — terbukti dipakai di engagement PELNI (guerrillamail menerima email verifikasi `pajak.noreply@pelni.co.id`).

## Provider

| Provider | Status (30 Aug 2026) | Metode | Catatan |
|---|---|---|---|
| `guerrilla` | ✅ OK | REST `api.guerrillamail.com` | paling andal, default pertama utk `auto` |
| `mailtm` | ✅ OK | REST `api.mail.tm` | JWT, delete akun didukung |
| `mailgw` | ✅ OK | REST `api.mail.gw` | kembar mail.tm, rate-limit lebih longgar |
| `tempmail_io` | ✅ OK | `api.internal.temp-mail.io` v3 | token per address |
| `mailnesia` | ✅ OK | HTML scrape | mailbox publik, tanpa state |
| `inboxkitten` | ✅ OK | JSON API `inboxkitten.com` | mailbox publik |
| `dropmail` | ⛔ disabled | GraphQL | upstream mematikan legacy token (`legacy_token_disabled`) |
| `maildrop` | ⛔ disabled | v2 API | route dihapus upstream |
| `tempmail_lol` | ⛔ disabled | v1 API | sekarang wajib API key |

`create(provider="auto")` mencoba provider urut keandalan; provider gagal otomatis dilompati.

## Tools (7)

| Tool | Fungsi |
|---|---|
| `tempmail_providers` | daftar provider enabled + disabled (dengan alasan) |
| `tempmail_health` | health check live semua provider |
| `tempmail_create` | bikin inbox → `{session, address, provider}` |
| `tempmail_list` | pesan di inbox (id, from, subject, preview) |
| `tempmail_read` | baca pesan: body + **links[] ter-ekstrak** + **codes[] (kandidat OTP)** |
| `tempmail_wait` | poll sampai pesan match filter `from_contains`/`subject_contains` (default 90 dtk) — buat nunggu email verifikasi |
| `tempmail_delete` | cleanup session |

## Binding opencode

Sudah terpasang di `~/.config/opencode/opencode.json`:

```json
"mcp": {
  "tempmail": {
    "type": "local",
    "command": ["python3", "<absolute-path-to-this-skill>/tools/mcp/tempmail/server.py"],
    "enabled": true
  }
}
```

Restart opencode setelah mengubah config. Tools muncul sebagai `tempmail_*`.

## Uji mandiri

```bash
python3 server.py --health   # tabel health provider
python3 server.py --smoke    # handshake MCP penuh (initialize→tools→create→list→delete)
```

## Implementasi

- Zero dependency (pakai `requests` bila ada, fallback `urllib`). MCP stdio: JSON-RPC newline-delimited.
- Tambah provider: subclass `BaseProvider` (health/create/list/read/delete) → daftarkan di `PROVIDERS` + `AUTO_ORDER`.
- Provider disabled tetap di kode (kelas lengkap) — cukup pindahkan namanya ke `AUTO_ORDER` bila upstream-nya hidup lagi.
