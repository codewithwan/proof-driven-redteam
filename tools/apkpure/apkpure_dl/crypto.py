import hashlib


def build_signature(body: bytes, timestamp_ms: int, nonce: int, key: str) -> str:
    """Ual-Access-Signature — s4/l.java AccessSignature.

    MD5( body_bytes + str(ts_ms) + key + str(nonce) ) as hex.
    """
    raw = body + str(timestamp_ms).encode() + key.encode() + str(nonce).encode()
    return hashlib.md5(raw).hexdigest()