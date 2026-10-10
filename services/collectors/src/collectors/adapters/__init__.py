from .akasa import AkasaCollector
from .easemytrip import EaseMyTripCollector
from .serpapi_gf import SerpApiCollector
from .spicejet import SpiceJetCollector

REGISTRY = {
    "serpapi": SerpApiCollector,
    "akasa": AkasaCollector,        # live: calendar schema; rich schema pending results-URL
    "spicejet": SpiceJetCollector,  # live: deep-link + interception (lowfare + rich archive)
    "easemytrip": EaseMyTripCollector,  # --from-file only (compliance + session gating)
}

# Remaining direct-site adapters (yatra, airindia — robots-clean, Akamai-gated)
# register here as they come online (see adapters/README.md).
