# Playbook: Proven Vuln Classes (ranked by real hit-rate across 30+ authorized engagements)

Every class has the same structure: Signal, Detection workflow, PROOF BAR, False-positive traps, Escalation tree, Case pattern. Read the Proof Gate first: it governs everything below.

Core doctrine: a vulnerability class is a search strategy, not a finding. Findings are born only when a real request meets a real response and impact is demonstrated.

## THE PROOF GATE

1. No proof, no report. Real request, real response, demonstrated impact. Nothing else ships.
2. IDOR/BOLA needs the configured record minimum (config.json, default 20 distinct records), masked, PLUS recency proof. If the dataset is smaller than the minimum, document the real total honestly.
3. Every leaked key or secret gets a capability matrix: what it CAN do (each capability proven by a real call) and what it CANNOT (the 403s are evidence too). "Key is valid" is not a finding. "Key lists 12 partner credentials" is.
4. Every foothold triggers lateral movement: the credential gets replayed against EVERY discovered endpoint and service. One credential accepted by many services is the real story.
5. Anti-honeypot recency proof. Data impact claims require proof the data is CURRENT:
   - Field level: created_at / updated_at / status of the newest records you saw. Record the actual date in evidence.
   - Behavior level (gold standard): create a prefixed artifact through the official app flow, then read it back through the vulnerability. Proves the current write path, live data, and not-honeypot in one move.
   - App level: the feature is live in the current app-store build, or the service returns today's config.
   - Stale data beyond the configured recency window (default 180 days) with no way to prove current: mark HONEYPOT-SUSPECT/LEGACY. Do not claim data impact. Pivot to current infrastructure.
6. All write/edit/delete tests use artifacts labeled with the configured prefix (default SECTEST_), pre-registered in FINDINGS before execution, cleaned up after, cleanup evidence in the report.
7. Scanner output is a lead, never a finding. Manual proof converts a lead into a finding.
8. The escalation ladder (workflow.md) runs on every finding without exception.

---

## 1. Hardcoded Secrets in Mobile Binaries (hit-rate: 8 of 12 APKs)

Signal: BuildConfig fields, @Headers("Authorization: Basic ..."), base64 blobs, long int-arrays in Dart source, AIza/AKIA/BEGIN PRIVATE markers, client_secret, keys in JS bundles, .env-style assets.

Detection workflow:
1. Decode (mobile.md pipeline): jadx + apktool + per-stack dumper (blutter for Flutter, hbc-decompiler for Hermes).
2. Regex sweep over string dumps: cloud keys (AIza, AKIA, ASIA, GOOG), JWTs (eyJ...), basic auth blobs, private key PEM blocks, generic secret naming (secret, apiKey, signing, salt, iv).
3. Decode base64 candidates immediately. A basic auth blob is a client:secret pair.
4. Localize precisely: file:line for the report. BuildConfig.AUTH_TOKEN, Retrofit @Headers annotations, Dart object pool indices, assets/app.config.
5. Classify the secret: OAuth client pair, symmetric key, cloud service account, API key, signing secret. The class determines the capability matrix.

PROOF BAR:
- USE the secret against production: mint the token, call the API, list the bucket. Capture the real response.
- Capability matrix per secret class: authentication as what, read scope, write scope, which services accept it, cost abuse potential, expiry.
- Lateral replay: gateway, every sibling microservice, cloud APIs in the same project, admin consoles.

False-positive traps:
- Public API keys that are client-identifier-only by design (Maps keys with proper package+SHA-1 restrictions, Firebase web configs). Still test them: restrictions fail more often than they hold.
- Test/staging keys left in prod builds. Check which environment actually accepts them before claiming prod impact.
- Sample/documentation keys. Verify against the real service, never assume.

Escalation tree: secret > token mint > read one sensitive object > scale (records minimum) > write path > privilege chain > cross-service lateral > aggregate chain severity.

Case patterns (anonymized, all real):
- OAuth basic pair (client:123456-grade) baked into a production APK. The minted client_credentials token was accepted by 5+ microservices with no scope checks. Mass disclosure of medical records followed. The chain, not the string, was the Critical.
- GCP service account private key stored as a 4658-element int array inside Dart source. Proven with a live oauth2 token mint plus secretmanager list. Score 10.0.
- Partner-hub clientSecret in a Flutter pool: an all:read token unlocked a vault of 12 partner bank and telco credentials plus CRUD, proven with a 201 create followed by delete.
- AES key + IV + admin password in an Expo app config: minted a channel JWT. Every mutation returned an auth error, so the finding was honestly bounded to read-only High. Boundary proof is proof discipline.
- SECRET-AGE PROOF VIA VERSION BISECTION (2026-08, static-only engagement): with live testing off the table, acquire 2-3 historical builds from the mirror website (see mobile.md acquisition rules) and diff secret markers across them. Byte-identical secret values across versions = a MEASURED no-rotation window ("public and unrotated since >= 2026-03"), which converts rotation urgency from assumption to evidence; the introduction window (first version carrying the secret) dates the exposure; and a clean OLD build doubles as a positive control — it proves the client's pipeline CAN ship without the secret, killing the "it's unavoidable in Flutter apps" remediation objection before it is raised.

## 2. BOLA / IDOR on Sequential and Weak Identifiers (hit-rate: 7 of 30)

Signal: integer /{id}, user_public_id, trxID, reservation_id, barcode or tracking number, UUID v1 (timestamp-leaking), predictable base64 identifiers, incrementing order numbers visible in email links.

Detection workflow:
1. Inventory every object reference in the API surface: path params, query params, body fields, headers (X-User-Id patterns).
2. Range probe: 1, 100, 500, 1000, 10000, 99999999. Classify each response: 200-full, 200-empty, 404, 403, redirect. Build the response-signature table.
3. Differential test with two owned accounts (A reads B's object) for the horizontal proof.
4. Random sample to the configured record minimum with a fixed seed (config.json sampling_seed). Mask PII in evidence.
5. Scale estimate via status-code-only sweep, bodies discarded.
6. Recency: newest record timestamps, active statuses, gold-standard artifact write-read-back.

PROOF BAR:
- The full response-signature table, the masked record set at the configured minimum, newest-record dates, and the negative control (unauthenticated or garbage token gets 401/403 on the same endpoint in the same block).
- Architectural oracle: a NotFoundException AFTER auth passed means authorization is missing. A domain error like "currentUser.id must not be null" proves the request passed every gate and died in business logic. That is architectural evidence of a missing authorization layer, stronger than any single record.

False-positive traps:
- Records returning 200 but all empty shells (soft-deleted rows). Check content, not status.
- Shared/public-by-design objects (public catalog items). Confirm the object class is actually user-scoped.
- Stale datasets (see anti-honeypot). A 2019-last-write table is not impact, it is archaeology.

Escalation tree: read one > read many (minimum records) > recency proof > write path (update/delete as owner-confused) > privilege objects (admin records) > cross-tenant > chain into aggregate.

Case patterns: prescription detail by integer ID, 100/100 random IDs returned full records, zero 401/403, current-year data, around 19k live medical records accepted by the client CSIRT. Hotel/flight booking walk: 135 bookings with real values plus 101 employee profiles, sequential IDs. Tracking by public barcode plus postal code: recipient PII plus a signed JWT with no account at all.

## 3. Auth Bypass / Token Forgery (hit-rate: 6 of 30)

Signal: HS256 JWT with the key in the binary, guest tokens with id=0, staging secrets identical to prod, deterministic signature schemes, missing audience/issuer checks, expired-token acceptance.

Detection workflow:
1. Collect every token the client can obtain: login, guest, refresh, deep links, cached.
2. Decode headers and claims (alg, exp, iat, iss, aud, scope, roles). Map expiry and scope anomalies first: they are cheap proofs.
3. Identify the signing material: static key in the binary, key derivation from a public value, HMAC over a predictable body.
4. Forge minimally: change one claim at a time (sub, role, exp). Record which forgeries the server accepts.
5. Probe the staging/prod boundary: staging-signed tokens against prod endpoints and the reverse.
6. Negative control: garbage signature must fail. If garbage passes, that is an even bigger finding (signature not verified at all).
7. FINGERPRINT LADDER (added 2026-08, PNM Digi case): when a gateway nginx-401s EVERY unauthenticated request regardless of headers, do not conclude "gated". Replay the app client's exact fingerprint: User-Agent okhttp/4.x + Accept-Encoding: gzip + Connection: Keep-Alive + Content-Type with charset. WAF client-fingerprint rules (browser blocked, app-UA allowed) are used as the ONLY gate in some stacks - and the app UA is a public constant in the APK. Test at least: browser-UA, okhttp-UA, curl-UA against the same endpoint in one matrix.

PROOF BAR:
- The forged or guest token performs an action or reads data that requires a real user, captured 200.
- Negative control in the same evidence block.
- Staging/prod crossover captured explicitly when present.

Escalation tree: token accepted > which claims are trusted > role escalation > admin surface > every service sharing the validation logic (lateral) > account takeover chains (password reset flows) > aggregate.

Case patterns: unauthenticated getToken endpoint plus four static AES keys in a native library, forged HS256 JWT, full BOLA chain, 9.8. Staging JWT secret identical to production. Signature scheme that was plain sha256(md5(ts:key:method:path:body:secret)), fully deterministic and forgeable offline. Guest JWT valid 24h with id=0 and an empty device_id accepted by user endpoints.

Case pattern (2026-08, PNM-style): open token mint with MARKER BINDING. The mint endpoint accepted garbage credentials but the issued token only unlocked the flow named in the request's `url` marker field. Technique: grep the decompiled corpus for `new ReqAccessToken\w+\([^)]*"/..."` to extract every marker string (each is a scoped capability), then matrix mint-marker x endpoint. Login-flow markers ("/login/v3") let garbage tokens reach member-lookup business logic, which doubled as a username-existence oracle (see class 14). Related: ERR_SID_CHANGED-style errors are PASSWORD-VALIDITY PROOFS - a device-binding rejection after the credential check proves the recovered credential is correct without completing the takeover.

## 4. OTP Abuse (hit-rate: 5 of 30, nearly every consumer app)

Audit SEND and VERIFY as two separate surfaces, always.

Detection workflow (SEND):
1. Trigger OTP to YOUR OWN number or tempmail inbox. Arrival is the only dispatch proof.
2. Repeat to the configured attempt count. Record inter-request timing and any counters in responses.
3. Probe per-target vs per-account vs per-IP limit dimensions: limits often bind the wrong key.

Detection workflow (VERIFY):
1. Submit wrong codes, at least the configured minimum attempts (default 10), uniform payloads.
2. Watch for: lockout, attempt counters, code invalidation on failure, rate limiting, response differentials.
3. If a valid code is obtainable (own inbox), complete a successful verify to map the full flow.

PROOF BAR:
- SEND: arrivals on our own inbox/number, repeated, with no effective throttle. result:true alone is a known false positive on invalid targets (retracted-claim case in real history: the per-target daily limit actually worked).
- VERIFY: uniform failures across the minimum wrong attempts with no lockout or counter change.
- Feasibility math is mandatory: attempts per second x validity window x keyspace = probability per window. This converts "no lockout" into "account takeover in N days" or kills the claim.

False-positive traps: client-side-only counters (check server behavior, not the app UI), honeypot OTP buckets, silent dispatch failures dressed as success.

Escalation tree: no-lockout verify > password reset chain > ATO feasibility > pair with enumeration (class 14) for targeting > aggregate with any leaked credential class.

Case patterns: 16 uniform verify failures with no lockout feeding a password-reset ATO chain with math included. OTP bombing to arbitrary numbers via a forged JWT plus a deterministic md5 signature, messages actually received. request_otp to any number with only a 45-second cooldown.

## 5. Client-Side "Encryption" (hit-rate: 4 of 12 APKs)

Signal: hardcoded AES key/IV, low PBKDF2 iterations, RSA-as-auth, salt:::iv:::b64 wire formats, encrypted bodies with static material, "signing" that is base64(hash(static + body)).

Detection workflow:
1. Recover the material: keys, IVs, salts, iteration counts, ordering. Localize file:line.
2. Replicate offline: a small decrypter for a captured payload (evidence artifact).
3. Replicate the encrypt path: craft a valid encrypted request.
4. Submit the forged ciphertext. Server acceptance is the proof.
5. Differential: replace the encrypted field with garbage padding. If both are accepted, the "encryption" is not authentication.

PROOF BAR:
- Offline-decrypted REAL payload (the replica script goes in evidence) AND a server-accepted forged request.

False-positive traps: hardware-backed keys (KeyStore/StrongBox) that never leave the device, these bound the finding honestly. Server-side HMAC with per-session secrets: the static material you found may be decoy or legacy.

Escalation tree: decrypt > forge > which endpoints accept forgeries > auth bypass (class 3) > write operations > aggregate.

Case patterns: PBKDF2-HMAC-SHA512 with iteration count 999, cracked offline, the same derived key used for AES-CBC transport and JWT HS256 signing. AES-CBC with the IV prepended to the ciphertext, ten-line replica. Deterministic signing keys reused across endpoints.

Case pattern (2026-08, PNM-style): the SERVER returns password blobs encrypted with the app's static key. The API's member-record response carried an AES-128-ECB base64 `password` field (same static key the app uses at login, AESCrypt-style). Chain: open token mint (class 3) > BOLA record dump (class 2) > offline decrypt with the APK key > single login attempt. The decrypt is stage-3 proof; the login differential (ERR_SID_CHANGED = password accepted, device-binding refused) is stage-4 validity proof without completing takeover. Signal to grep for: the app's crypto utility class (AESCrypt/SecurePrefs) used BOTH in login request-building AND appearing verbatim in API response models.

## 6. Public Cloud Storage and Object Exposure (hit-rate: 5 of 30)

Signal: bucket names in strings or JS, SDK configs, presigned URL patterns, storage hosts in recon, MinIO consoles, R2/B2 endpoints.

Detection workflow:
1. Enumerate: anonymous list (GET /?list-type=2 for S3/GCS/MinIO families), web console probing, error-message leakage.
2. Assess contents: object dates (recency!), object classes (exports, backups, uploads, logs).
3. Existence proof: exactly ONE small or non-sensitive object downloaded, or HEAD plus Content-Length.
4. Sensitivity proof without theft: a filter query that would match sensitive entries, run with a match-zero or single-benign result, plus counts from listing metadata.

PROOF BAR:
- Listing showing real, recent objects. One sample (or HEAD+size). Object dates. The filter-based sensitivity proof.

False-positive traps: abandoned buckets (old-only dates, no write path) are exposure notes, not impact. Public-by-design asset CDN buckets. Always check the recency window.

Escalation tree: list > read one > upload path (poisoning: RAG knowledge bases, code, CI artifacts) > write to overwrite path > credential files in bucket > aggregate.

Case patterns: S3 bulk-export buckets with voucher archives. MinIO anonymous listing with an open console. Unauthenticated upload into a RAG pipeline bucket enabling knowledge poisoning (a documented, weaponizable integrity impact).

## 7. Infrastructure Exposure (hit-rate: 6 of 30 via corporate web pivot)

Signal: non-standard ports open to the internet (7025/7071 mail stacks, 9000/9001 object storage, 8084 MQTT, 8243 API gateways, 1025 SMTP), admin consoles, K8s API servers, database ports, PHP panels on shared IPs, out-of-date management planes.

Detection workflow:
1. Port sweep the in-scope IP estate (config pacing). Banner-grab.
2. Fingerprint versions from public assets (versioned JS URLs, ETag patterns, error pages, default pages).
3. Protocol-level interaction proofs: SMTP/LMTP dialogues, storage listing, MQTT anonymous subscribe (subscribe-only to a harmless topic first), admin console HTML.
4. CVE triage via the cve MCP tools, then per-path verification of every candidate: 404 means patched, 501 means wrong service. Unverified CVEs are surface notes, never findings.

PROOF BAR:
- Protocol transcript (the raw 250/550 dialogue, the console HTML, the version fingerprint).
- Delivery proofs only to your own test accounts.
- Per-path CVE verification results.

Escalation tree: exposure > unauthenticated interaction > data path (mail delivery, object read) > integrity path (mail injection is post-filter delivery: bypasses SPF/DMARC/AV entirely, the perfect BEC vector) > takeover attempts on weak management planes > aggregate.

Case patterns: unauthenticated LMTP mail injection on an internet-open port plus 550-vs-250 user enumeration with zero emails sent (QUIT before DATA). A CodePush-style PHP update panel public on a shared IP (OTA RCE chain surface). Keycloak with open registration plus a public admin console, verified with two prefixed test accounts.

## 8. Tenant Takeover / Mass Assignment (hit-rate: 3 of 30, B2B gold)

Signal: invitation flows, tenant-scoped object refs without tenant checks, role fields in writable payloads, self-service user management, UUID exposure in URLs.

Detection workflow:
1. Two owned tenants/accounts minimum (tempmail for registration).
2. Inventory writable fields per endpoint; attempt the configured mass-assignment field list (role, isAdmin, is_paid, approved, balance, amount, status) plus app-specific variants.
3. Invitation abuse test: invite to a tenant you do not control, register via the invitation, observe the role granted.
4. Cross-tenant object refs: tenant A references tenant B objects by raw ID.
5. 403 vs 422 differential mapping as a per-field permission oracle.

PROOF BAR:
- The full chain executed against a tenant you control (prefixed artifacts) or with explicit authorization. The role-change response captured. Victim-count claims only when the chain is demonstrably reproducible pre-auth.

Escalation tree: member > admin of own tenant > admin of arbitrary tenant > platform-level roles > data exfiltration across tenants > aggregate (usually Critical).

Case patterns: register, POST invitations to an arbitrary company with no check, fetch invitations, register with the invitation UUID, become admin of any tenant, proven on three controlled tenants. PUT member with a global ID for cross-tenant role escalation. Unauthenticated role-types endpoint dumping the entire RBAC model.

## 9. WebView / Deeplink Chains (hit-rate: 4 of 12 APKs)

Signal: autoVerify hosts, OneLink/app.link attribution domains, shouldInterceptRequest overrides, addJavascriptInterface, JS bridges (window.X objects), exported activities, custom URL schemes, file access in WebViews.

Detection workflow:
1. Manifest triage: exported components, autoVerify host lists, scheme handlers.
2. Fetch .well-known/assetlinks.json for every autoVerify host. Default pages or broken JSON are reportable as-is (HTTP response alone proves the misconfiguration).
3. Static chain construction: redirect entry > WebView load > bridge exposure > native handlers (file access, camera, payments).
4. On-device execution: fire the intent chain via adb, capture logcat, screenshots, or an HTTP callback you host. Static chains are HYPOTHESES until executed.
5. Fuzz the parameters of deeplink handlers (a small intent fuzzer script per target).
6. CF-CHALLENGED WEBVIEW CONSUMERS (added 2026-08): app-session URLs (minted webview tokens) load behind Cloudflare "Just a moment" interstitials that TLS-impersonation requests never clear - the raw response is just the challenge page, indistinguishable from rejection. Verify every minted-session URL in a REAL browser (Playwright/Chromium): navigate, wait 8-10s for the challenge to clear, then read the final URL + body. First-party Rails consumers redirect to layout_error_login with distinct codes per failure reason - the post-challenge page is the actual validation verdict.

PROOF BAR:
- On-device execution evidence of the full chain, or the assetlinks/misconfig HTTP proof for the configuration finding.

Escalation tree: open redirect > WebView with bridge > file read > token theft from JS context > payment activity abuse > aggregate.

Case patterns: an attribution link with an open redirect feeding an InAppWebView with a JS bridge and a file-access handler. An exported payment activity registered to a dead App Link host (hanging registration). Account deletion links carrying tokens in the URL (token leakage via history/referrer).

## 10. API Key Abuse: Maps / Firebase / LLM / Payment (hit-rate: 6 of 30)

Signal: AIza keys in strings or bundles, Firebase configs, unauthenticated /api/config endpoints, payment SDK public keys, push tokens.

Detection workflow:
1. Classify the key type from its prefix and usage context.
2. Maps restriction check: call the API with X-Android-Package and X-Android-Cert (the app signing SHA-1, raw lowercase hex, from the signature extraction step). A 200 with the headers while naked calls fail means the restriction is spoofable with public information (the package name and SHA-1 are IN the APK). That is the finding.
3. Firebase: Remote Config fetch with the app id and a zeroed instance id; RTDB/.json read; Storage rules probe.
4. LLM keys: model catalog list, then sibling APIs in the same project, then one tiny generation if authorized (cost proof, one token).
5. Fill the matrix: one real call per capability, one 403 per restriction.

PROOF BAR:
- The completed capability matrix with raw responses. Billable abuse quantified (per-call cost x scale).

Escalation tree: valid key > which APIs > restrictions bypassable > cost abuse > data APIs in the same project (lateral) > admin surfaces > aggregate.

Case patterns: Maps key fully usable with spoofed package+SHA-1 headers (confirmed geocode+static map). Remote Config fetch leaking PRIVATE_KEY-grade material. A live LLM key readable from an unauthenticated manufacturing-app config endpoint, model catalog returned, Translate disabled (403), the matrix itself was the High.

## 11. Race Conditions and Concurrency (hit-rate: 3 of 30, rising)

Signal: balances, counters, coupons, referral credits, booking hold/release, withdrawal flows, anything with check-then-act patterns visible in responses.

Detection workflow:
1. Identify state-changing endpoints with a read-modify-write shape.
2. Baseline single-request behavior first (the sequential truth).
3. Parallel burst at the configured concurrency (20 to start, up to 100) with synchronized starts (barrier release or last-byte sync).
4. Compare outcome counts vs sequential truth. N successes where 1 is correct is the finding.
5. Check idempotency keys: absent, client-controlled, or reusable?

PROOF BAR:
- Sequential control (1 success) vs concurrent run (N successes) with raw responses and final state verification (balance delta, coupon count). Use your own accounts and prefixed artifacts.

Escalation tree: single double-spend > repeatable > cross-account (gift/transfer races) > monetary cap estimate > aggregate.

Case patterns: referral credit granted N times per burst. Coupon redemption races. Double booking of a single slot.

## 12. SSRF and Request Forgery (hit-rate: 4 of 30 on web estates)

Signal: url/image/webhook/callback params, PDF generators, importers, proxy endpoints, internal hostnames in client configs.

Detection workflow:
1. Point the parameter at a callback host you control. Interactivity is the first proof.
2. Cloud metadata targets (169.254.169.254 family, per-provider variants) via GET only, read minimal fields, never exfiltrate credentials you do not need (note the path works, capture only a harmless field).
3. Internal network mapping via response differentials (open/closed/refused) and error text.
4. Scheme and redirect abuse: redirects to internal, gopher/file schemes where the fetcher allows.

PROOF BAR:
- Callback capture (the request arrived at your host) or a metadata response field (harmless one, like a timestamp or instance-id prefix). Response-differential maps for internal ranges.

Escalation tree: external callback > internal reachability > cloud metadata (role name disclosure) > credential access path documented and NOT executed beyond the harmless proof > RCE-adjacent services (internal admins, Redis, metadata IMDSv1) > aggregate.

## 13. Injection: SQL, NoSQL, Template, Command (hit-rate: moderate, always tested)

Signal: string-concatenated queries visible in decompiled code, sort/filter params, template rendering of user input, export/report generators, legacy PHP surfaces.

Detection workflow:
1. Time-based first (SLEEP/pg_sleep equivalents), boolean second, error-based third. Content-based only with clear controls.
2. NoSQL: operator injection ($gt, $ne, $regex) in JSON bodies, Mongo filter patterns.
3. Template: SSTI probes (math expressions) in fields that look rendered.
4. Bound every test with a control payload (same request minus payload syntax) in the same block.

PROOF BAR:
- A time differential vs control (for example 5.0s payload vs 0.16s control, repeated), an error-based leak, or a boolean differential on real data. Flat responses are honest NEGATIVE results: record them (they are Positive Controls in the report).

Escalation tree: detection > data read path (with client authorization for content extraction) > write path (UPDATE/INSERT via stacked queries, only with explicit authorization) > OS-level (only with authorization) > aggregate.

## 14. Enumeration and Information Oracles (hit-rate: high, force multiplier for everything else)

Signal: login/forgot/register differentials, tracking endpoints, user lookup by phone/email, mail-server RCPT behavior, error-message specificity.

Detection workflow:
1. Pair every probe: known-valid vs known-invalid identifiers. Any consistent differential (status, timing, body shape, error text) is an oracle.
2. Mail servers: the 550-vs-250 RCPT dialogue (QUIT before DATA, zero emails).
3. Phone/email lookup endpoints: response shape and timing pairs.
4. Quantify: oracle + OTP no-lockout + password reset = targeting pipeline for ATO.

PROOF BAR:
- The differential pair captured in one evidence block. For mail servers, the protocol transcript.

Escalation tree: oracle > bulk enumeration feasibility (rate math) > chain into ATO classes (3, 4) > aggregate.

---

## 15. Frontend Bundle Mining for Hidden Attack Surface (hit-rate: 1 Critical in 1 engagement, technique generalizes everywhere)

Proven on a 2026 private engagement (target anonymized): the engagement's Critical was NOT in the
APK — it was in the production web SPA the app talks to. Every modern SPA/Next.js/Nuxt build ships a complete map
of its own attack surface. Mine it before touching endpoints:

- Build manifest: fetch /_next/static/<buildId>/_buildManifest.js — it lists EVERY route,
  including internal tooling (/automation, /library-version, /admin) the client never links to.
- Lazy chunk resolution: page chunks reference webpack ids (r.e(247)); the webpack runtime chunk
  contains the id→filename map (r.u=e=>"static/chunks/"+...). Follow EVERY lazy chunk — the
  real API code lives there, not in the page shell.
- API host inventory: grep lazy chunks for https:// hosts and path templates — SPAs routinely
  embed staging AND production API bases (dev/stg/prod split leaks environment topology).
- TEST/DEBUG COMPONENTS ARE GOLD: leftover components (StreamingTest, PlaygroundDemo, *Debug*)
  contain hardcoded working request examples — pool UUIDs, token formats, endpoint paths the
  UI never uses. That engagement's Critical (unauth fleet telemetry) came from a leftover test component
  component leaking the non-student resource path format.
- Parameter semantics: compare how the SPA constructs URLs (trailing slash, seq cursor, param
  order) — replicating the client's EXACT construction is often the difference between 400 and 200.
- Binary parsers ship in the bundle: when an API returns application/octet-stream, the SPA's
  own decoder (DataView/getUint8 loops) is the schema — port it verbatim to parse captured
  evidence. Impact quantification (record counts, PII fields, timestamps) then becomes
  mechanical instead of guessed.
- Version-diff environments: dev/prod hosts serving the same app with DIFFERENT chunk hashes =
  different builds = different API bases. Diffing the two reveals environment topology and
  staging credentials (test JWTs, pool UUIDs) routinely.
- Chain the finds: fleet telemetry that ignores its `sub=` parameter means every UUID works —
  parameter-space chaining (config.testing.parameter_space_chaining). Data from one finding
  (pool names, member codes, school names) feeds the chain matrix of every other finding.

## Anti-patterns (career-limiting)

- Reporting scanner output. Leads only become findings through manual proof.
- Reporting stale or deprecated data as impact. That is how honeypots eat you. Prove recency or pivot.
- Stopping at "key is valid". Enumerate what the key DOES.
- One-endpoint proof when the credential is accepted by ten services. Lateral movement is the report.
- Stopping at the FIRST data hit. Parse the captured bytes: the same endpoint may carry school
  buses inside the charter fleet, names inside telemetry, children's data inside a generic feed.
  Impact quantification is where severity actually comes from (config.testing.impact_quantification_required).
- Treating one environment's fix as the story. Test the same chain on EVERY environment the
  bundle reveals (dev/stg/prod) — enforcement often exists on exactly one layer.
- Bulk-downloading PII or vouchers. The configured record minimum, masked, plus scale-by-sampling beats a dump every time, and keeps you employable.
- Skipping the negative control. A lone 200 is an anecdote; the differential is the proof.
- Skipping retests. Verified findings get retested (config.json retest_verified_findings) before reporting.
- Skipping the chain matrix. A VERIFIED finding with an incomplete chain matrix row is unfinished
  work, not a reportable finding.
