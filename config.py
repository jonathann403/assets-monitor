"""Application configuration.

Values are read from environment variables so the app can be configured for
different deployments without code changes. Every setting has a sensible
default that works out of the box for local use.
"""
import os

# Project root (directory that contains this file).
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _abspath(path):
    """Resolve a possibly-relative path against the project root."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(BASE_DIR, path))


class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DEBUG = _env_bool("ASSETS_MONITOR_DEBUG", False)
    HOST = os.environ.get("ASSETS_MONITOR_HOST", "127.0.0.1")
    PORT = _env_int("ASSETS_MONITOR_PORT", 5000)

    # Where scan results are written. One sub-directory per scanned domain.
    RESULTS_DIR = _abspath(
        os.environ.get("ASSETS_MONITOR_RESULTS_DIR", "results")
    )

    # Subdomain wordlist used by the enumeration step.
    WORDLIST = _abspath(
        os.environ.get(
            "ASSETS_MONITOR_WORDLIST",
            "wordlists/subdomains/httparchive_subdomains_2024_04_28.txt",
        )
    )

    # External tooling.
    RECON_SCRIPT = _abspath(
        os.environ.get("ASSETS_MONITOR_RECON", "src/massdns_scripts/recon.py")
    )
    HTTPX_BIN = os.environ.get("ASSETS_MONITOR_HTTPX_BIN", "httpx")
    PYTHON_BIN = os.environ.get("ASSETS_MONITOR_PYTHON_BIN", "python3")

    # How many scans may run concurrently.
    MAX_CONCURRENT_SCANS = _env_int("ASSETS_MONITOR_MAX_SCANS", 3)

    def as_dict(self):
        return {
            key: getattr(self, key)
            for key in dir(self)
            if key.isupper() and not key.startswith("_")
        }
