import os
import random


class Config:
    """All tunables live here. Every field can be overridden by its env var or a CLI flag."""

    # Defaults reversed from APKPure 3.20.77 (rotatable — see extract_keys).
    DEFAULT_SIGN_KEY = "d33cb23fd17fda8ea38be504929b77ef"
    DEFAULT_AUTH_KEY = "qNKrYmW8SSUqJ73k3P2yfMxRTo3sJTR"
    DEFAULT_CV = "3207737"
    DEFAULT_SV = "34"
    DEFAULT_HOST = "https://hyapi.pureapk.com/v3"
    DEFAULT_AID = "com.apkpure.aegon"
    DEFAULT_FLAVOR = "advertisingArmallNativeCrash"

    COUNTRY_POOL = ["ID", "US", "SG", "MY", "PH", "TH", "VN", "JP"]

    UA_POOL = [
        "APKPure/{cv} (Android 14; Pixel 7 Build/UP1A.231005.007)",
        "APKPure/{cv} (Android 14; Pixel 6 Build/UP1A.231005.007)",
        "APKPure/{cv} (Android 13; Pixel 6a Build/TQ3A.230901.001)",
        "APKPure/{cv} (Android 13; SM-S918B Build/TP1A.220624.014)",
        "APKPure/{cv} (Android 14; SM-S911B Build/UWDB.230905.005)",
        "APKPure/{cv} (Android 13; RMX3363 Build/SP1A.210812.016)",
        "APKPure/{cv} (Android 14; 23127PN0CC Build/UP1A.231005.007)",
        "APKPure/{cv} (Android 12; M2007J3SY Build/SKQ1.211006.001)",
    ]

    def __init__(self, sign_key=None, auth_key=None, cv=None, sv=None, host=None,
                 aid=None, flavor=None, country=None, no_tls=False, verbose=False):
        self.sign_key = self._pick("APKPURE_SIGN_KEY", sign_key, self.DEFAULT_SIGN_KEY)
        self.auth_key = self._pick("APKPURE_AUTH_KEY", auth_key, self.DEFAULT_AUTH_KEY)
        self.cv = self._pick("APKPURE_CV", cv, self.DEFAULT_CV)
        self.sv = self._pick("APKPURE_SV", sv, self.DEFAULT_SV)
        self.host = self._pick("APKPURE_HOST", host, self.DEFAULT_HOST)
        self.aid = self._pick("APKPURE_AID", aid, self.DEFAULT_AID)
        self.flavor = self._pick("APKPURE_FLAVOR", flavor, self.DEFAULT_FLAVOR)
        self.country = self._pick("APKPURE_COUNTRY", country, random.choice(self.COUNTRY_POOL))
        self.no_tls = no_tls
        self.verbose = verbose

    @staticmethod
    def _pick(env, cli, default):
        return cli or os.environ.get(env) or default