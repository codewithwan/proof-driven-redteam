"""Generic v3 API client. All commands issued over the same signed channel."""

import json

from . import cache, transport
from .config import Config
from .fingerprint import build_headers


class APIError(RuntimeError):
    pass


def call(cfg: Config, command: str, params: dict = None, use_cache: bool = False,
         cache_key: str = None) -> dict:
    """POST {host}/{command}. Params become the JSON body (protobuf also accepted)."""
    body = json.dumps(params or {}, separators=(",", ":")).encode()
    key = cache_key or command + ":" + json.dumps(params or {}, sort_keys=True)

    if use_cache:
        cached = cache.load(key)
        if cached is not None:
            print(f"[cache] HIT {key}")
            return cached

    url = f"{cfg.host}/{command}"
    headers = build_headers(cfg, body)
    if cfg.verbose:
        print(f"[net] POST {url}")
    r = transport.post(cfg, url, headers, body)
    if cfg.verbose:
        print(f"[net] {r.status_code} transport={transport.last_transport}")
    try:
        j = r.json()
    except Exception:
        raise APIError(f"HTTP {r.status_code} non-JSON: {r.content[:600]!r}")
    if r.status_code != 200:
        raise APIError(f"HTTP {r.status_code}: {j}")
    if j.get("retcode") != 0:
        raise APIError(f"retcode={j.get('retcode')} errmsg={j.get('errmsg')}")

    if use_cache:
        cache.save(key, j)
        print(f"[cache] SAVED {key}")
    return j


def app_detail(cfg: Config, package: str, page: str = "Detail", use_cache: bool = True) -> dict:
    return call(cfg, "get_app_detail", {"packageName": package, "page": page},
                use_cache=use_cache, cache_key=package)


def app_his_version(cfg: Config, package: str) -> dict:
    return call(cfg, "get_app_his_version", {"packageName": package})


def extract_asset(resp: dict) -> dict:
    d = resp.get("app_detail") or resp
    asset = d.get("asset", {})
    return {
        "title": d.get("title"),
        "package_name": d.get("package_name"),
        "version_name": d.get("version_name"),
        "version_code": d.get("version_code"),
        "native_code": d.get("native_code"),
        "asset_type": asset.get("type"),
        "asset_url": asset.get("url"),
        "asset_urls": asset.get("urls", []),
        "asset_url_seed": asset.get("url_seed"),
        "file_sha256": asset.get("file_sha256"),
        "file_size": asset.get("size"),
        "expiry": asset.get("expiry_date"),
        "sha1": asset.get("sha1"),
    }