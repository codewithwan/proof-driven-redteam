# Web Hunting: Recon to Full Coverage to Proof

Order: OSINT, subdomains, URLs/JS, secrets, cloud, surface check, then manual hunting inside business flows, then lateral movement. Scanner output is leads. This file is the complete web methodology.

## 1. Recon (timeboxed, then hunt)

- Subdomains, always 2+ sources (crt.sh 502s regularly; certspotter and hackertarget as fallback), then httpx for live hosts. Screenshot the estate (gowitness/aquatone style) for a visual index.
- URL history: waybackurls, gau, katana. Merge, dedupe, filter to scope.txt. Full coverage, not sampling. Check for .js, .map (source maps leak original source), .json, .bak, .old, /api, /admin, /test paths in history.
- JS harvest: download all JS from the URL corpus, plus source maps. Grep for AKIA, AIza, sk_live, client_secret, api_key, Bearer eyJ, internal hostnames, GraphQL endpoints, WebSocket URLs.
- DNS anomalies worth a round every time: subdomains resolving to 127.0.0.1 (internal misconfig leak), CNAMEs to load balancers (alive means no takeover, dangling means takeover path), NXDOMAIN hosts still referenced by app manifests or assetlinks.
- Technology fingerprint per live host: headers, cookies, generator tags, favicon hashes. Feeds the CVE triage later.

## 2. SPA and API surface, check ALL of these every time

- Public configs: /config.json, /api/config, __NEXT_DATA__ blocks, /v3/api-docs and Swagger UI (a real engagement found 74 endpoints with zero auth behind a public swagger), /graphql, /actuator/*, /.well-known/*.
- _buildManifest.js and route maps: admin routes leaking into public builds.
- Feature flags in client state (EnableMFA:false), dev endpoints (localhost refs) inside production bundles.
- Infra quick check per live host: ports 7025, 7071, 9000, 9001, 8084, 8243, 1025, plus database ports where scope allows.
- API versioning discovery: /v1../v9, /api/v1, mobile-specific gateways (/m/, /mobile/), partner APIs. Old versions often lack the controls of current ones.

## 3. Authentication surface audit (always, in this order)

1. JWT audit: alg confusion (HS256 with a public RSA key as the secret), missing exp/aud/iss validation, None-alg acceptance, weak HMAC secrets (crackable), kid injection into file paths or SQL.
2. OAuth2/OIDC audit: redirect_uri validation (open redirects on the callback), state parameter presence, code reuse, implicit-flow token leakage in URLs, PKCE absence where clients are public.
3. SAML (where present): signature wrapping (XSW), Comment injection in NameID, audience/receiver checks.
4. Session management: logout actually invalidating server-side, session fixation, token rotation on privilege change, cookie flags (HttpOnly, Secure, SameSite).
5. Password flows: reset token entropy and expiry, reset token in URL (leaks via history/referrer/logs), reset poisoning via Host/X-Forwarded-Host, enumeration differentials.
6. Registration: email verification actually enforced, disposable email handling, role fields accepted at registration.

## 4. Business logic, where the money is

Hunt stateful features, not pages:

```
create > approve > publish > delete > refund > transfer
apply  > review > accept/reject > issue > verify > close
draft  > submit > pay > confirm > fulfill > ship > delivered
```

Test every transition: skip a step (pay without checkout), repeat a step (refund or claim twice), rollback or negative values (amount, balance, stock, counters), server-side vs client-only validation, race conditions on transitions (playbook class 11), per-step vs first-step-only permissions.

| Domain | Classics |
|---|---|
| E-commerce/POS | client-side prices, stackable discounts, coupon reuse, negative stock, checkout races |
| Finance/payment | double refunds, negative amounts, fee bypass, settlement IDOR, currency confusion |
| Ticketing/booking | seat price tamper, double booking, ticket transfer |
| Logistics | tracking IDOR, shipping fee manipulation, status skip |
| Subscriptions | trial forever, downgrade-keep-features, invoice manipulation |

## 5. Authorization battery, always two accounts (A and B, both yours)

1. Horizontal: A reads or edits B's object (swap ID, referrer, neighbor UUID).
2. Vertical: user hits admin endpoint. Middleware, or just hidden UI?
3. Mass assignment: the configured field list (role, isAdmin, is_paid, approved, balance, amount, status) plus app-specific variants.
4. Method confusion: GET vs POST vs PUT, users/me into users/1.
5. Integer IDs mean IDOR somewhere, almost guaranteed.
6. Multi-tenant: cross-tenant object refs, invitation flows without checks.
7. 403 vs 422 differential is a per-field permission oracle.

IDOR proof bar: the configured record minimum of distinct fresh records, masked, with recency evidence (playbook class 2).

## 6. Modern API surfaces

- GraphQL: introspection (is it open?), query depth/complexity abuse, field-level authorization gaps (resolver-level checks), mutations without ownership checks, batching attacks against rate limits.
- WebSockets: authentication on connect vs per-message (per-message is often missing), origin validation, subscription authorization (can you subscribe to other users' channels?).
- gRPC/protobuf: reflection endpoints, proto files in JS bundles, method-level authn.
- Serverless/function URLs: unauthenticated invoke paths, verbose error leakage.

## 7. Classic web classes that still pay

- SSRF (playbook class 12): url/webhook/callback params, PDF generators, importers.
- File upload: extension/content-type validation gaps, path traversal in stored names, SVG XSS, upload-to-executable-path chains, zip slip in extractors.
- CORS: reflected Origin with credentials true is the finding; check subdomain wildcards and null origin handling.
- Host header injection: password reset links, cache keys, absolute URLs generated from Host.
- Cache poisoning/deception: unkeyed headers reflected into cache, web cache deception on authorization-gated paths (/js style tricks serving authenticated content to a shared cache).
- Request smuggling: only safe detection (timing differentials) unless explicitly authorized for depth.
- Open redirect: login/callback/logout redirect params; chainable into OAuth redirect_uri weaknesses.

## 8. Rate limiting and abuse resistance

- Map which dimensions limits bind (per-IP, per-account, per-token, global). Limits that bind the wrong dimension are bypassable: rotate the unbound dimension.
- Bypass ladder: header spoofing (X-Forwarded-For family), case/path normalization tricks, HTTP/2 multiplexing, distributed vantage, batch endpoints, GraphQL batching.
- OTP endpoints get the full playbook class 4 treatment. Enumeration endpoints get class 14.

## 9. Lateral movement (mandatory from every foothold)

- One token or key accepted by multiple services: map ALL of them. That is the real impact story.
- Leaked cloud key: probe sibling resources in the same project (error messages leak names), IAM reads, other APIs in the project. One real call per capability, one 403 per restriction.
- Corporate pivot: a foothold on one app extends to everything sharing the credential, IP range, or SSO: mail servers, internal manufacturing apps, admin clusters, CI/CD.
- Old versions live: staging, mobile-API v1, partner endpoints frequently share prod data with fewer controls.

## 10. Infra surface proof patterns

- Mail servers (Zimbra pattern): LMTP on 7025, LHLO, then MAIL FROM with an arbitrary sender (250 means spoof accepted), then RCPT TO (550 vs 250 is a user enumeration oracle), then QUIT before DATA (zero emails sent). Delivery proof only to your own test account. Fingerprint the build via versioned asset URLs. CVE candidates verified per path: 404 means patched, 501 means wrong service.
- Object storage: anonymous listing via ?list-type=2, console on :9001.
- Identity providers (Keycloak pattern): open registration on the realm, public admin console. Prove with prefixed test accounts.
- Old app servers: unauth reset, enumeration, weak password policies. Prove takeover with a prefixed test account. Never lock real users out.
- Kubernetes: API server exposure (version-banner first, self-subject rules review only if authenticated and authorized).

## 11. Internal app cluster inventory (after a corporate pivot)

Typical estate: HRIS, procurement, travel, document management, fleet, LMS, plant dashboards. Quick-win paths: /api/config, /config, /.env, /.git, PHP login pairs. Time-based SQLi checks with SLEEP: a flat response is an honest negative (parameterized). Keep an inventory table with status codes (401, 302, login). Report the exposure, deep-test where credentials are authorized.
