"""Per-package JSON response cache. Valid while the asset URL token is unexpired."""

import json
import os
import time
from datetime import datetime
from pathlib import Path

CACHE_DIR = Path(os.environ.get("APKPURE_CACHE_DIR", str(Path.home() / ".cache" / "apkpure-dl")))
FALLBACK_TTL = 6 * 3600


def _file(pkg: str) -> Path:
    return CACHE_DIR / f"{pkg}.json"


def load(pkg: str):
    try:
        j = json.loads(_file(pkg).read_text(encoding="utf-8"))
    except Exception:
        return None
    asset = (j.get("app_detail") or {}).get("asset") or {}
    expiry = asset.get("expiry_date")
    saved = j.get("_saved_at", 0)
    if expiry:
        try:
            if time.time() < datetime.fromisoformat(expiry).timestamp():
                return j
            return None
        except Exception:
            pass
    if saved and (time.time() - saved) < FALLBACK_TTL:
        return j
    return None


def save(pkg: str, j: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    j["_saved_at"] = time.time()
    _file(pkg).write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")