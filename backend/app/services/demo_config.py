import os


def demo_enabled() -> bool:
    environment = os.getenv("SMARTRESOLVE_ENV", "").strip().casefold()
    enabled = os.getenv("SMARTRESOLVE_DEMO_ENABLED", "").strip().casefold()
    return environment not in {"production", "prod"} and enabled in {"1", "true", "yes", "on"}
