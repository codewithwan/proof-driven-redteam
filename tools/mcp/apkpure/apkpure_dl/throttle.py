import random
import time

_last_req = {"ts": 0.0}


def throttle(enabled: bool, rng=(2.0, 5.0)):
    """Sequential jitter between network calls. No-op in the same second."""
    if not enabled or rng[1] <= 0:
        return
    elapsed = time.time() - _last_req["ts"]
    want = random.uniform(*rng)
    if elapsed < want:
        time.sleep(want - elapsed)
    _last_req["ts"] = time.time()