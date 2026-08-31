#!/usr/bin/env python3
"""
tempmail-mcp — Multi-provider disposable email MCP server for opencode.

Zero required dependencies (uses `requests` if importable, else urllib).
MCP stdio transport: newline-delimited JSON-RPC 2.0.

Providers: guerrilla, dropmail, mail.tm, mail.gw, temp-mail.io,
           maildrop, mailnesia, inboxkitten, tempmail.lol

Tools:
  tempmail_providers  — list known providers + notes
  tempmail_health     — live health check of every provider
  tempmail_create     — create inbox (auto-fallback across providers)
  tempmail_list       — list messages in a session inbox
  tempmail_read       — read a message (body + extracted links + OTP codes)
  tempmail_wait       — poll until a message matches sender/subject filter
  tempmail_delete     — cleanup session (best effort)

CLI:
  python3 server.py            # run MCP server (stdio)
  python3 server.py --health   # print provider health table and exit
  python3 server.py --smoke    # self-test MCP handshake (subprocess) and exit
"""
import json
import random
import re
import secrets
import string
import sys
import time
import urllib.parse
import urllib.request

# ---------------------------------------------------------------- http helper
try:
    import requests as _rq  # type: ignore
    HAVE_REQUESTS = True
except Exception:  # pragma: no cover
    HAVE_REQUESTS = False

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


class HttpError(Exception):
    def __init__(self, status, body=""):
        super().__init__(f"HTTP {status}: {body[:160]}")
        self.status = status
        self.body = body


def http(method, url, *, headers=None, json_body=None, data=None, timeout=15):
    """Return (status, text). Raises HttpError only on transport errors."""
    hdrs = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    if headers:
        hdrs.update(headers)
    payload = None
    if json_body is not None:
        payload = json.dumps(json_body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    elif data is not None:
        payload = data.encode() if isinstance(data, str) else data
    if HAVE_REQUESTS:
        r = _rq.request(method, url, headers=hdrs, data=payload, timeout=timeout,
                        allow_redirects=True)
        return r.status_code, r.text
    req = urllib.request.Request(url, data=payload, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def jhttp(method, url, **kw):
    status, text = http(method, url, **kw)
    try:
        return status, json.loads(text)
    except Exception:
        return status, text


def rand_local(prefix="tmp", n=8):
    return f"{prefix}{''.join(random.choices(string.ascii_lowercase + string.digits, k=n))}"


class ProviderError(Exception):
    pass


# ---------------------------------------------------------------- providers
class BaseProvider:
    name = "base"
    note = ""

    def health(self):
        raise NotImplementedError

    def create(self, prefix="tmp"):
        raise NotImplementedError

    def list(self, sess):
        raise NotImplementedError

    def read(self, sess, mid):
        raise NotImplementedError

    def delete(self, sess):
        return "noop (provider cleans up automatically)"


class MailTmLike(BaseProvider):
    """mail.tm and mail.gw share the same API shape."""

    def __init__(self, name, api):
        self.name = name
        self.api = api
        self.note = "REST API + JWT; delete supported"

    def _domains(self):
        st, j = jhttp("GET", f"{self.api}/domains", timeout=12)
        if st != 200:
            raise ProviderError(f"domains HTTP {st}")
        if isinstance(j, list):
            doms = j
        else:
            doms = j.get("hydra:member", j.get("member", [])) if isinstance(j, dict) else []
        active = [d["domain"] for d in doms if d.get("isActive", True)]
        if not active:
            raise ProviderError("no active domains")
        return active[0]

    def health(self):
        self._domains()
        return True

    def create(self, prefix="tmp"):
        dom = self._domains()
        addr = f"{rand_local(prefix)}@{dom}"
        pw = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        st, j = jhttp("POST", f"{self.api}/accounts", json_body={"address": addr, "password": pw})
        if st not in (200, 201):
            raise ProviderError(f"account create HTTP {st} ({str(j)[:120]})")
        st, j = jhttp("POST", f"{self.api}/token", json_body={"address": addr, "password": pw})
        if st != 200 or not isinstance(j, dict) or not j.get("token"):
            raise ProviderError(f"token HTTP {st} ({str(j)[:120]})")
        return {
            "provider": self.name,
            "address": addr,
            "password": pw,
            "token": j["token"],
            "account_id": (j.get("id") or ""),
        }

    def _auth(self, sess):
        return {"Authorization": f"Bearer {sess['token']}"}

    def list(self, sess):
        st, j = jhttp("GET", f"{self.api}/messages", headers=self._auth(sess))
        if st != 200:
            raise ProviderError(f"list HTTP {st}")
        items = j.get("hydra:member", j.get("member", [])) if isinstance(j, dict) else j
        out = []
        for m in items:
            frm = m.get("from", {})
            out.append({
                "id": m.get("id", ""),
                "from": (frm.get("address") if isinstance(frm, dict) else str(frm)) or "",
                "subject": m.get("subject", ""),
                "preview": (m.get("intro") or "")[:140],
            })
        return out

    def read(self, sess, mid):
        st, j = jhttp("GET", f"{self.api}/messages/{mid}", headers=self._auth(sess))
        if st != 200:
            raise ProviderError(f"read HTTP {st}")
        frm = j.get("from", {})
        html = j.get("html", [])
        html = "".join(html) if isinstance(html, list) else str(html or "")
        return {
            "id": mid,
            "from": (frm.get("address") if isinstance(frm, dict) else str(frm)) or "",
            "subject": j.get("subject", ""),
            "text": j.get("text") or strip_html(html),
            "html": html[:8000],
        }

    def delete(self, sess):
        try:
            st, me = jhttp("GET", f"{self.api}/me", headers=self._auth(sess))
            if st == 200 and isinstance(me, dict) and me.get("id"):
                st2, _ = jhttp("DELETE", f"{self.api}/accounts/{me['id']}", headers=self._auth(sess))
                return f"account deleted (HTTP {st2})"
        except Exception as e:
            return f"delete best-effort failed: {e}"
        return "delete skipped (no account id)"


class Guerrilla(BaseProvider):
    name = "guerrilla"
    note = "sid_token session API; proven reliable; default for auto"

    def health(self):
        st, j = jhttp("GET", "https://api.guerrillamail.com/ajax.php?f=get_email_address", timeout=12)
        if st != 200 or not (isinstance(j, dict) and j.get("email_addr")):
            raise ProviderError(f"health HTTP {st}")
        return True

    def create(self, prefix="tmp"):
        st, j = jhttp("GET", "https://api.guerrillamail.com/ajax.php?f=get_email_address")
        if st != 200 or not (isinstance(j, dict) and j.get("email_addr")):
            raise ProviderError(f"create HTTP {st}")
        return {
            "provider": self.name,
            "address": j["email_addr"],
            "sid": j.get("sid_token", ""),
            "ts": j.get("email_timestamp", 0),
        }

    def _call(self, sess, **params):
        q = {"sid_token": sess.get("sid", "")}
        q.update(params)
        st, j = jhttp("GET", "https://api.guerrillamail.com/ajax.php?" + urllib.parse.urlencode(q), timeout=15)
        if st != 200:
            raise ProviderError(f"HTTP {st}")
        return j

    def list(self, sess):
        j = self._call(sess, f="get_email_list", offset=0)
        out = []
        for m in (j.get("list") or []):
            if str(m.get("mail_id", "0")) == "1" and "guerrilla" in (m.get("mail_from") or ""):
                continue  # welcome mail
            out.append({
                "id": str(m.get("mail_id", "")),
                "from": m.get("mail_from", ""),
                "subject": m.get("mail_subject", ""),
                "preview": (m.get("mail_excerpt") or "")[:140],
            })
        return out

    def read(self, sess, mid):
        j = self._call(sess, f="fetch_email", email_id=mid)
        return {
            "id": mid,
            "from": j.get("mail_from", ""),
            "subject": j.get("mail_subject", ""),
            "text": j.get("mail_body") or "",
            "html": (j.get("mail_body") or "")[:8000],
        }

    def delete(self, sess):
        try:
            self._call(sess, f="del_email", **{"email_ids[]": "all"})
            return "mailbox cleared"
        except Exception as e:
            return f"delete best-effort failed: {e}"


class Dropmail(BaseProvider):
    name = "dropmail"
    note = "public GraphQL API; session id; no signup"

    def _gql(self, query, variables=None):
        url = f"https://dropmail.me/api/graphql/{secrets.token_hex(8)}"
        st, j = jhttp("POST", url, json_body={"query": query, "variables": variables or {}}, timeout=15)
        if st != 200 or not isinstance(j, dict):
            raise ProviderError(f"gql HTTP {st}")
        if j.get("errors"):
            raise ProviderError(str(j["errors"])[:160])
        return j.get("data", {})

    def health(self):
        d = self._gql("mutation { introduceSession { id expiresAt addresses { address } } }")
        if not d.get("introduceSession", {}).get("id"):
            raise ProviderError("no session id")
        return True

    def create(self, prefix="tmp"):
        d = self._gql("mutation { introduceSession { id expiresAt addresses { address } } }")
        s = d.get("introduceSession", {})
        addrs = s.get("addresses") or []
        if not s.get("id") or not addrs:
            raise ProviderError("session incomplete")
        return {"provider": self.name, "sid": s["id"], "address": addrs[0]["address"],
                "expires": s.get("expiresAt", "")}

    def list(self, sess):
        d = self._gql(
            'query($id: ID!){ session(id:$id){ mails { rawSize fromAddr headerSubject text } } }',
            {"id": sess["sid"]})
        mails = (d.get("session") or {}).get("mails") or []
        out = []
        for i, m in enumerate(mails):
            out.append({
                "id": str(i),
                "from": m.get("fromAddr", ""),
                "subject": m.get("headerSubject", ""),
                "preview": (m.get("text") or "")[:140],
            })
        return out

    def read(self, sess, mid):
        mails = self.list(sess)
        idx = int(mid)
        if idx < 0 or idx >= len(mails):
            raise ProviderError("id out of range")
        # re-fetch full text
        d = self._gql(
            'query($id: ID!){ session(id:$id){ mails { fromAddr headerSubject text html } } }',
            {"id": sess["sid"]})
        m = (d.get("session") or {}).get("mails", [])[idx]
        return {"id": mid, "from": m.get("fromAddr", ""), "subject": m.get("headerSubject", ""),
                "text": m.get("text") or "", "html": (m.get("html") or "")[:8000]}


class TempMailIo(BaseProvider):
    name = "tempmail_io"
    note = "internal API v3; token issued per address"

    def health(self):
        st, j = jhttp("POST", "https://api.internal.temp-mail.io/api/v3/email/new",
                      json_body={"min_name_length": 10, "max_name_length": 10}, timeout=12)
        if st not in (200, 201) or not (isinstance(j, dict) and j.get("email")):
            raise ProviderError(f"health HTTP {st}")
        return True

    def create(self, prefix="tmp"):
        st, j = jhttp("POST", "https://api.internal.temp-mail.io/api/v3/email/new",
                      json_body={"min_name_length": 10, "max_name_length": 10})
        if st not in (200, 201) or not (isinstance(j, dict) and j.get("email")):
            raise ProviderError(f"create HTTP {st}")
        return {"provider": self.name, "address": j["email"], "token": j.get("token", "")}

    def _msgs(self, sess):
        st, j = jhttp("GET", f"https://api.internal.temp-mail.io/api/v3/email/{sess['address']}/messages",
                      timeout=15)
        if st != 200 or not isinstance(j, list):
            raise ProviderError(f"list HTTP {st}")
        return j

    def list(self, sess):
        return [{"id": str(m.get("id", i)), "from": m.get("from", ""),
                 "subject": m.get("subject", ""),
                 "preview": (m.get("body_text") or "")[:140]}
                for i, m in enumerate(self._msgs(sess))]

    def read(self, sess, mid):
        for m in self._msgs(sess):
            if str(m.get("id")) == str(mid):
                return {"id": mid, "from": m.get("from", ""), "subject": m.get("subject", ""),
                        "text": m.get("body_text") or "",
                        "html": (m.get("body_html") or "")[:8000]}
        raise ProviderError("message not found")


class Maildrop(BaseProvider):
    name = "maildrop"
    note = "classic v2 JSON API; no signup; public mailbox (anyone may read)"

    def health(self):
        st, j = jhttp("GET", "https://api.maildrop.cc/v2/mailbox/healthchecktmp", timeout=12)
        if st != 200:
            raise ProviderError(f"health HTTP {st}")
        return True

    def create(self, prefix="tmp"):
        addr = f"{rand_local(prefix)}@maildrop.cc"
        return {"provider": self.name, "address": addr}

    def list(self, sess):
        local = sess["address"].split("@")[0]
        st, j = jhttp("GET", f"https://api.maildrop.cc/v2/mailbox/{local}")
        if st != 200 or not isinstance(j, dict):
            raise ProviderError(f"list HTTP {st}")
        out = []
        for m in (j.get("messages") or []):
            out.append({"id": str(m.get("id", "")), "from": m.get("from", ""),
                        "subject": m.get("subject", ""), "preview": ""})
        return out

    def read(self, sess, mid):
        local = sess["address"].split("@")[0]
        st, j = jhttp("GET", f"https://api.maildrop.cc/v2/mailbox/{local}/{mid}")
        if st != 200:
            raise ProviderError(f"read HTTP {st}")
        return {"id": mid, "from": j.get("from", ""), "subject": j.get("subject", ""),
                "text": j.get("body") or "", "html": (j.get("html") or "")[:8000]}


class Mailnesia(BaseProvider):
    name = "mailnesia"
    note = "public mailbox page, HTML scraping; no API"

    def _get(self, path):
        st, text = http("GET", "https://mailnesia.com" + path, timeout=15,
                        headers={"Accept": "text/html"})
        if st != 200:
            raise ProviderError(f"HTTP {st}")
        return text

    def health(self):
        self._get("/mailbox/healthchecktmp")
        return True

    def create(self, prefix="tmp"):
        local = rand_local(prefix)
        return {"provider": self.name, "address": f"{local}@mailnesia.com", "local": local}

    def list(self, sess):
        html_ = self._get(f"/mailbox/{sess['local']}")
        rows = re.findall(
            r'href="/mailbox/' + sess["local"] + r'/(\w+)"[^>]*>.*?<td>([^<]*)</td>\s*<td>([^<]*)</td>',
            html_, re.S)
        return [{"id": i, "from": s.strip(), "subject": sub.strip(), "preview": ""}
                for i, s, sub in rows[:30]]

    def read(self, sess, mid):
        html_ = self._get(f"/mailbox/{sess['local']}/{mid}")
        m = re.search(r'<div[^>]*id="mail"[^>]*>(.*?)</div>\s*(?:<div|<footer|$)', html_, re.S)
        body = strip_html(m.group(1)) if m else strip_html(html_)
        return {"id": mid, "from": "", "subject": "", "text": body[:6000], "html": ""}


class InboxKitten(BaseProvider):
    name = "inboxkitten"
    note = "open-source service, JSON API; public mailbox"

    def health(self):
        st, j = jhttp("GET", "https://inboxkitten.com/api/v1/mail/list?recipient=healthchecktmp",
                      timeout=12)
        if st != 200:
            raise ProviderError(f"health HTTP {st}")
        return True

    def create(self, prefix="tmp"):
        local = rand_local(prefix)
        return {"provider": self.name, "address": f"{local}@inboxkitten.com", "local": local}

    def list(self, sess):
        st, j = jhttp("GET",
                      f"https://inboxkitten.com/api/v1/mail/list?recipient={sess['local']}")
        if st != 200 or not isinstance(j, dict):
            raise ProviderError(f"list HTTP {st}")
        out = []
        for i, m in enumerate(j.get("mails") or []):
            out.append({
                "id": str(m.get("id") or m.get("storage_key") or i),
                "from": (m.get("from") or {}).get("address", "") if isinstance(m.get("from"), dict) else str(m.get("from", "")),
                "subject": m.get("subject", ""),
                "preview": "",
            })
        return out

    def read(self, sess, mid):
        st, j = jhttp("GET", f"https://inboxkitten.com/api/v1/mail/{mid}?recipient={sess['local']}")
        if st != 200:
            raise ProviderError(f"read HTTP {st}")
        text = j.get("text") or j.get("body") or strip_html(j.get("html") or "")
        return {"id": mid, "from": "", "subject": j.get("subject", ""), "text": text[:6000],
                "html": (j.get("html") or "")[:8000]}


class TempMailLol(BaseProvider):
    name = "tempmail_lol"
    note = "v1 generate/auth endpoints; may require key now — auto-fallback handles"

    def health(self):
        st, j = jhttp("POST", "https://api.tempmail.lol/generate", timeout=12)
        if st != 200 or not (isinstance(j, dict) and (j.get("address") or j.get("email"))):
            raise ProviderError(f"health HTTP {st}")
        return True

    def create(self, prefix="tmp"):
        st, j = jhttp("POST", "https://api.tempmail.lol/generate")
        if st != 200 or not isinstance(j, dict):
            raise ProviderError(f"create HTTP {st}")
        return {"provider": self.name, "address": j.get("address") or j.get("email", ""),
                "token": j.get("token", "")}

    def list(self, sess):
        tok = sess.get("token", "")
        if not tok:
            raise ProviderError("no inbox token")
        st, j = jhttp("GET", f"https://api.tempmail.lol/auth/{tok}")
        if st != 200:
            raise ProviderError(f"list HTTP {st}")
        mails = j.get("email") if isinstance(j, dict) else j
        out = []
        for i, m in enumerate(mails or []):
            out.append({"id": str(i), "from": m.get("from", ""), "subject": m.get("subject", ""),
                        "preview": (m.get("body") or "")[:140]})
        return out

    def read(self, sess, mid):
        msgs = self.list(sess)
        idx = int(mid)
        if idx >= len(msgs):
            raise ProviderError("id out of range")
        st, j = jhttp("GET", f"https://api.tempmail.lol/auth/{sess['token']}")
        mails = (j.get("email") if isinstance(j, dict) else j) or []
        m = mails[idx]
        return {"id": mid, "from": m.get("from", ""), "subject": m.get("subject", ""),
                "text": m.get("body") or "", "html": (m.get("html") or "")[:8000]}


PROVIDERS = {
    p.name: p
    for p in [
        Guerrilla(),
        Dropmail(),
        MailTmLike("mailtm", "https://api.mail.tm"),
        MailTmLike("mailgw", "https://api.mail.gw"),
        TempMailIo(),
        Maildrop(),
        Mailnesia(),
        InboxKitten(),
        TempMailLol(),
    ]
}
AUTO_ORDER = ["guerrilla", "mailtm", "mailgw", "tempmail_io", "mailnesia", "inboxkitten"]
DISABLED = {
    "dropmail": "legacy public GraphQL token disabled upstream ('legacy_token_disabled')",
    "maildrop": "v2 API route removed upstream",
    "tempmail_lol": "API requires a key now (returns HTML info page keyless)",
}

# ---------------------------------------------------------------- text utils
def strip_html(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_links(text):
    raw = re.findall(r"https?://[^\s<>\"')\]]+", text or "")
    seen, out = set(), []
    for u in raw:
        u = u.rstrip(".,;")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:20]


def extract_codes(text):
    """Likely OTP codes: 3-8 digit numbers (from text, de-duped)."""
    cand = re.findall(r"(?<![\w./])(\d{3,8})(?![\w.])", text or "")
    seen = list(dict.fromkeys(cand))
    return seen[:10]


# ---------------------------------------------------------------- sessions
SESSIONS = {}


def tool_providers():
    enabled = {name: {"note": p.note} for name, p in PROVIDERS.items() if name in AUTO_ORDER}
    return {"enabled": enabled, "disabled": DISABLED}


def tool_health():
    out = {}
    for name in AUTO_ORDER:
        try:
            PROVIDERS[name].health()
            out[name] = "OK"
        except Exception as e:
            out[name] = f"FAIL: {str(e)[:100]}"
    return out


def tool_create(provider="auto", prefix="tmp"):
    order = [provider] if provider != "auto" else AUTO_ORDER
    errors = {}
    for name in order:
        p = PROVIDERS.get(name)
        if not p:
            return {"error": f"unknown provider '{name}'"}
        try:
            sess = p.create(prefix=prefix)
            sid = secrets.token_hex(4)
            SESSIONS[sid] = sess
            return {"session": sid, "address": sess["address"], "provider": name}
        except Exception as e:
            errors[name] = str(e)[:120]
            if provider != "auto":
                break
    return {"error": "all providers failed", "details": errors}


def _sess(sid):
    sess = SESSIONS.get(sid)
    if not sess:
        raise ProviderError(f"unknown session '{sid}' — create an inbox first")
    return sess


def tool_list(sid):
    sess = _sess(sid)
    msgs = PROVIDERS[sess["provider"]].list(sess)
    return {"address": sess["address"], "provider": sess["provider"],
            "count": len(msgs), "messages": msgs}


def tool_read(sid, mid):
    sess = _sess(sid)
    msg = PROVIDERS[sess["provider"]].read(sess, mid)
    text = msg.get("text") or ""
    msg["links"] = extract_links(text + " " + (msg.get("html") or ""))
    msg["codes"] = extract_codes(text)
    return msg


def tool_wait(sid, from_contains=None, subject_contains=None, timeout_s=90, interval_s=6):
    sess = _sess(sid)
    p = PROVIDERS[sess["provider"]]
    deadline = time.time() + min(int(timeout_s), 300)
    seen = set()
    while time.time() < deadline:
        try:
            msgs = p.list(sess)
            for m in msgs:
                key = f"{m['id']}|{m['subject']}|{m['from']}"
                if key in seen:
                    continue
                seen.add(key)
                if from_contains and from_contains.lower() not in (m["from"] or "").lower():
                    continue
                if subject_contains and subject_contains.lower() not in (m["subject"] or "").lower():
                    continue
                m["links"] = extract_links((m.get("preview") or "") + " " + (m.get("subject") or ""))
                m["codes"] = extract_codes(m.get("preview") or "")
                return {"matched": True, "address": sess["address"], **m}
        except Exception:
            pass  # transient provider hiccup — keep polling
        time.sleep(max(2, int(interval_s)))
    return {"matched": False, "address": sess["address"],
            "note": f"timeout after {timeout_s}s"}


def tool_delete(sid):
    sess = _sess(sid)
    result = PROVIDERS[sess["provider"]].delete(sess)
    SESSIONS.pop(sid, None)
    return {"session": sid, "provider": sess["provider"], "cleanup": result}


# ---------------------------------------------------------------- MCP layer
TOOLS = [
    {
        "name": "tempmail_providers",
        "description": "List all supported disposable-email providers with notes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tempmail_health",
        "description": "Live health-check every provider (light request each). Returns OK/FAIL map.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "tempmail_create",
        "description": "Create a disposable inbox. provider='auto' tries providers in reliability "
                       "order until one succeeds. Returns {session, address, provider}.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "enum": ["auto"] + AUTO_ORDER,
                             "description": "default: auto"},
                "prefix": {"type": "string", "description": "local-part prefix, default 'tmp'"},
            },
        },
    },
    {
        "name": "tempmail_list",
        "description": "List messages in an inbox session.",
        "inputSchema": {"type": "object",
                        "properties": {"session": {"type": "string"}},
                        "required": ["session"]},
    },
    {
        "name": "tempmail_read",
        "description": "Read one message fully: body text, extracted links[] and OTP codes[].",
        "inputSchema": {"type": "object",
                        "properties": {"session": {"type": "string"},
                                       "id": {"type": "string", "description": "message id from list"}},
                        "required": ["session", "id"]},
    },
    {
        "name": "tempmail_wait",
        "description": "Poll inbox until a message matches optional from_contains/subject_contains "
                       "filters — ideal for verification/OTP emails. Returns matched message or timeout.",
        "inputSchema": {"type": "object",
                        "properties": {
                            "session": {"type": "string"},
                            "from_contains": {"type": "string"},
                            "subject_contains": {"type": "string"},
                            "timeout_s": {"type": "number", "description": "default 90, max 300"},
                            "interval_s": {"type": "number", "description": "default 6"},
                        },
                        "required": ["session"]},
    },
    {
        "name": "tempmail_delete",
        "description": "Cleanup a session inbox (best effort) and drop it from the registry.",
        "inputSchema": {"type": "object",
                        "properties": {"session": {"type": "string"}},
                        "required": ["session"]},
    },
]


def call_tool(name, args):
    if name == "tempmail_providers":
        return tool_providers()
    if name == "tempmail_health":
        return tool_health()
    if name == "tempmail_create":
        return tool_create(args.get("provider", "auto"), args.get("prefix", "tmp"))
    if name == "tempmail_list":
        return tool_list(args["session"])
    if name == "tempmail_read":
        return tool_read(args["session"], args["id"])
    if name == "tempmail_wait":
        return tool_wait(args["session"], args.get("from_contains"),
                         args.get("subject_contains"), args.get("timeout_s", 90),
                         args.get("interval_s", 6))
    if name == "tempmail_delete":
        return tool_delete(args["session"])
    raise ProviderError(f"unknown tool {name}")


def logerr(msg):
    sys.stderr.write(f"[tempmail-mcp] {msg}\n")
    sys.stderr.flush()


def serve():
    logerr(f"starting (requests={HAVE_REQUESTS}); providers: {', '.join(AUTO_ORDER)}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            logerr(f"bad json: {line[:120]}")
            continue
        if msg.get("jsonrpc") != "2.0" or "id" not in msg:
            continue  # notification — ignore
        mid, method = msg["id"], msg.get("method", "")
        result, error = None, None
        try:
            if method == "initialize":
                client_pv = (msg.get("params") or {}).get("protocolVersion", "2024-11-05")
                result = {
                    "protocolVersion": client_pv,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "tempmail", "version": "1.0.0"},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = msg.get("params") or {}
                try:
                    data = call_tool(params.get("name", ""), params.get("arguments") or {})
                    result = {"content": [{"type": "text", "text": json.dumps(data, indent=2)}],
                              "isError": False}
                except Exception as e:
                    result = {"content": [{"type": "text", "text": f"error: {e}"}],
                              "isError": True}
            else:
                error = {"code": -32601, "message": f"method not found: {method}"}
        except Exception as e:  # defensive
            error = {"code": -32603, "message": str(e)}
        resp = {"jsonrpc": "2.0", "id": mid}
        if error:
            resp["error"] = error
        else:
            resp["result"] = result
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


# ---------------------------------------------------------------- CLI
def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--health":
            print(json.dumps(tool_health(), indent=2))
            return 0
        if sys.argv[1] == "--smoke":
            return smoke()
        print(__doc__)
        return 0
    serve()
    return 0


def smoke():
    """End-to-end MCP handshake self-test via subprocess."""
    import subprocess
    p = subprocess.Popen([sys.executable, __file__], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()
        return json.loads(p.stdout.readline())

    ok = True
    r = send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05"}})
    ok &= "serverInfo" in r.get("result", {})
    r = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    ok &= len(names) == 7
    r = send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "tempmail_create", "arguments": {"provider": "guerrilla"}}})
    body = json.loads(r["result"]["content"][0]["text"])
    ok &= bool(body.get("address"))
    if body.get("session"):
        r = send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                  "params": {"name": "tempmail_list", "arguments": {"session": body["session"]}}})
        ok &= "messages" in json.loads(r["result"]["content"][0]["text"])
        send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
              "params": {"name": "tempmail_delete", "arguments": {"session": body["session"]}}})
    p.stdin.close()
    p.wait(timeout=10)
    print(f"SMOKE: {'PASS' if ok else 'FAIL'} (inbox={body.get('address', '-')})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
