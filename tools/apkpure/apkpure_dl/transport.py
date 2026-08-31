"""HTTP transport with TLS impersonation chain."""

try:
    from curl_cffi import requests as _creq
    _HTTPLIB = "curl_cffi"
except ImportError:
    import requests as _creq
    _HTTPLIB = "requests"

import requests as _plain_requests

from .config import Config

# Device-accurate targets first; chrome*_android are supported by most builds.
IMPERSONATE_CHAIN = [
    "okhttp4_android_14", "okhttp4_android_13", "okhttp4_android_12",
    "chrome131_android", "chrome99_android", "chrome131", "chrome120",
]

last_transport = None


def post(cfg: Config, url: str, headers: dict, body: bytes, timeout: int = 20):
    global last_transport
    if cfg.no_tls or _HTTPLIB == "requests":
        last_transport = last_transport or f"plain {_HTTPLIB}"
        return _creq.post(url, headers=headers, data=body, timeout=timeout)
    err = None
    for target in IMPERSONATE_CHAIN:
        try:
            r = _creq.post(url, headers=headers, data=body, timeout=timeout, impersonate=target)
            last_transport = f"impersonate:{target}"
            return r
        except Exception as e:
            err = e
    last_transport = f"plain requests ({repr(err)[:80]})"
    return _creq.post(url, headers=headers, data=body, timeout=timeout)


def get(url: str, timeout=(10, 300)):
    """Streaming GET for CDN assets — plain requests (stable for big files).

    Impersonation only matters on the signed API (POSTs); CDN stream with
    curl_cffi hits curl:28 low-speed limits on big XAPKs.
    """
    return _plain_requests.get(url, stream=True, timeout=timeout)