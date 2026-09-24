"""Thread-safe management of scan lifecycles.

The original app tracked running scans in a bare module-level list with no
status, no completion signal and races between threads. This manager keeps a
lock-guarded registry of scans, exposes their live status/phase/progress, and
persists metadata to disk when each scan ends so state survives a restart.

Scan status values:
    queued       - accepted, waiting for a worker thread
    enumerating  - subdomain enumeration in progress
    probing      - httpx probing in progress
    completed    - finished successfully
    failed       - stopped with an error (see ``error``)
"""
import threading
from datetime import datetime, timezone

from src.common import ScannerError
from src.httpx_scanner import HttpxScanner
from src.subdomains_scanner import SubdomainScanner

from .validators import normalize_domain

ACTIVE_STATES = ("queued", "enumerating", "probing")
TERMINAL_STATES = ("completed", "failed")


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat() if dt else None


class ScanError(Exception):
    """Base class for user-facing scan-management errors."""


class ScanAlreadyRunning(ScanError):
    pass


class TooManyScans(ScanError):
    pass


class Scan:
    def __init__(self, domain):
        self.domain = domain
        self.status = "queued"
        self.message = "Queued"
        self.subdomains_found = 0
        self.hosts_live = 0
        self.error = None
        self.created_at = _now()
        self.started_at = None
        self.finished_at = None

    @property
    def is_active(self):
        return self.status in ACTIVE_STATES

    @property
    def duration_seconds(self):
        if not self.started_at:
            return None
        end = self.finished_at or _now()
        return round((end - self.started_at).total_seconds(), 1)

    def to_dict(self):
        return {
            "domain": self.domain,
            "status": self.status,
            "message": self.message,
            "subdomains_found": self.subdomains_found,
            "hosts_live": self.hosts_live,
            "error": self.error,
            "created_at": _iso(self.created_at),
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "duration_seconds": self.duration_seconds,
        }


class _Context:
    """Handed to the runner so it can report progress under the lock."""

    def __init__(self, manager, scan):
        self._manager = manager
        self._scan = scan

    @property
    def domain(self):
        return self._scan.domain

    def update(self, **fields):
        self._manager._update(self._scan, **fields)


class ScanManager:
    def __init__(self, config, store, runner=None):
        self.config = config
        self.store = store
        self._runner = runner or self._default_runner
        self._scans = {}
        self._lock = threading.Lock()

    # -- queries -----------------------------------------------------------
    def get(self, domain):
        with self._lock:
            scan = self._scans.get(domain)
            return scan.to_dict() if scan else None

    def active_count(self):
        with self._lock:
            return sum(1 for s in self._scans.values() if s.is_active)

    def is_running(self, domain):
        with self._lock:
            scan = self._scans.get(domain)
            return bool(scan and scan.is_active)

    def all(self):
        with self._lock:
            return [s.to_dict() for s in self._scans.values()]

    def active(self):
        with self._lock:
            return [s.to_dict() for s in self._scans.values() if s.is_active]

    # -- commands ----------------------------------------------------------
    def start(self, domain):
        """Validate, register and launch a scan. Returns the scan dict.

        Raises :class:`ScanAlreadyRunning` if one is already in flight for the
        domain, or :class:`TooManyScans` if the concurrency cap is reached.
        """
        domain = normalize_domain(domain)
        with self._lock:
            existing = self._scans.get(domain)
            if existing and existing.is_active:
                raise ScanAlreadyRunning(
                    "A scan for %s is already running." % domain
                )
            active = sum(1 for s in self._scans.values() if s.is_active)
            if active >= self.config.MAX_CONCURRENT_SCANS:
                raise TooManyScans(
                    "Too many scans running (limit %d). Try again shortly."
                    % self.config.MAX_CONCURRENT_SCANS
                )
            scan = Scan(domain)
            self._scans[domain] = scan

        thread = threading.Thread(
            target=self._run, args=(scan,), name="scan-%s" % domain, daemon=True
        )
        thread.start()
        return scan.to_dict()

    # -- internals ---------------------------------------------------------
    def _update(self, scan, **fields):
        with self._lock:
            for key, value in fields.items():
                setattr(scan, key, value)

    def _run(self, scan):
        self._update(scan, status="enumerating", message="Starting…",
                     started_at=_now())
        try:
            self._runner(_Context(self, scan))
        except ScannerError as exc:
            self._finish(scan, "failed", str(exc), error=str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - surface as a failed scan
            self._finish(scan, "failed", "Scan failed unexpectedly.",
                         error=str(exc))
            return
        self._finish(
            scan,
            "completed",
            "Completed: %d live of %d subdomains"
            % (scan.hosts_live, scan.subdomains_found),
        )

    def _finish(self, scan, status, message, error=None):
        # Persist the terminal metadata BEFORE exposing the terminal status
        # in memory, so any reader that observes "completed"/"failed" is
        # guaranteed to be able to load the corresponding meta.json.
        with self._lock:
            scan.message = message
            scan.error = error
            scan.finished_at = _now()
        snapshot = scan.to_dict()
        snapshot["status"] = status
        try:
            self.store.save_meta(scan.domain, snapshot)
        except Exception:  # noqa: BLE001 - persistence is best-effort
            pass
        with self._lock:
            scan.status = status

    def forget(self, domain):
        """Drop a non-active scan from the in-memory registry.

        Called after its on-disk results are deleted so the manager stops
        reporting it. Active scans are never forgotten.
        """
        with self._lock:
            scan = self._scans.get(domain)
            if scan and not scan.is_active:
                del self._scans[domain]

    def _default_runner(self, ctx):
        domain = ctx.domain
        cfg = self.config

        ctx.update(status="enumerating", message="Enumerating subdomains…")
        sub = SubdomainScanner(
            domain,
            cfg.WORDLIST,
            results_dir=cfg.RESULTS_DIR,
            recon_script=cfg.RECON_SCRIPT,
            python_bin=cfg.PYTHON_BIN,
        )
        found = sub.run()
        ctx.update(subdomains_found=found,
                   message="Found %d subdomains" % found)

        ctx.update(status="probing",
                   message="Probing %d hosts with httpx…" % found)
        httpx = HttpxScanner(
            sub.output_file,
            domain,
            results_dir=cfg.RESULTS_DIR,
            httpx_bin=cfg.HTTPX_BIN,
        )
        live = httpx.run()
        ctx.update(hosts_live=live)
