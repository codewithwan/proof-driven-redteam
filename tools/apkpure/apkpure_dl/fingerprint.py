import json
import random
import string
import time
import uuid

from .config import Config


def rand_qimei() -> str:
    return "".join(random.choices(string.hexdigits[:16], k=32))


def rand_gaid() -> str:
    return uuid.uuid4().hex


def rand_nonce() -> int:
    return random.randint(10000000, 99999999)


def build_headers(cfg: Config, body: bytes) -> dict:
    """Fresh, per-request device fingerprint. Mirrors od/a.java interceptor."""
    from .crypto import build_signature

    nonce = rand_nonce()
    ts = int(time.time() * 1000)
    gaid = rand_gaid()
    ext = {"gaid": gaid, "oaid": ""}
    project_info = {"deviceInfo": {}, "hostAppInfo": {}, "userInfo": {},
                    "netInfo": {}, "extInfo": ext}
    ua = random.choice(cfg.UA_POOL).format(cv=cfg.cv)

    headers = {
        "User-Agent": ua,
        "User-Agent-WebView": "Mozilla/5.0 (Linux; Android 14; Pixel 6) AppleWebKit/537.36",
        "Ual-Access-Businessid": "projecta",
        "Ual-Access-ProjectA": json.dumps(project_info, separators=(",", ":")),
        "Ual-Access-ExtInfo": json.dumps(ext, separators=(",", ":")),
        "Ual-Access-Sequence": str(uuid.uuid4()),
        "Ual-Access-Signature": build_signature(body, ts, nonce, cfg.sign_key),
        "Ual-Access-Nonce": str(nonce),
        "Ual-Access-Timestamp": str(ts),
        "X-Auth-Key": cfg.auth_key,
        "X-Country": cfg.country,
        "X-Aid": cfg.aid,
        "X-Flavor": cfg.flavor,
        "X-Cv": cfg.cv,
        "X-Sv": cfg.sv,
        "X-Qimei": rand_qimei(),
        "Content-Type": "application/json; charset=utf-8",
        "Cookie": "",
    }
    if cfg.verbose:
        print(f"[verbose] UA={ua}")
        print(f"[verbose] country={cfg.country} qimei={headers['X-Qimei']} gaid={gaid}")
    return headers