import pytest

from app.scan_manager import ScanAlreadyRunning, ScanManager, TooManyScans
from app.validators import ValidationError
from src.common import ScannerError

from conftest import wait_until


def test_full_scan_lifecycle(manager, store):
    scan = manager.start("example.com")
    assert scan["status"] in ("queued", "enumerating", "probing")

    assert wait_until(lambda: manager.get("example.com")["status"] == "completed")
    final = manager.get("example.com")
    assert final["subdomains_found"] == 2
    assert final["hosts_live"] == 2
    assert final["duration_seconds"] is not None
    # metadata persisted to disk
    assert store.load_meta("example.com")["status"] == "completed"


def test_duplicate_scan_blocked_while_running(config, store):
    started = []

    def slow_runner(ctx):
        import time
        ctx.update(status="enumerating")
        started.append(ctx.domain)
        time.sleep(0.3)

    mgr = ScanManager(config, store, runner=slow_runner)
    mgr.start("example.com")
    assert wait_until(lambda: started)
    with pytest.raises(ScanAlreadyRunning):
        mgr.start("example.com")


def test_concurrency_limit(config, store):
    def slow_runner(ctx):
        import time
        ctx.update(status="enumerating")
        time.sleep(0.4)

    config.MAX_CONCURRENT_SCANS = 2
    mgr = ScanManager(config, store, runner=slow_runner)
    mgr.start("a.com")
    mgr.start("b.com")
    assert wait_until(lambda: mgr.active_count() == 2)
    with pytest.raises(TooManyScans):
        mgr.start("c.com")


def test_failed_scan_records_error(config, store):
    def boom(ctx):
        ctx.update(status="enumerating")
        raise ScannerError("httpx not found")

    mgr = ScanManager(config, store, runner=boom)
    mgr.start("example.com")
    assert wait_until(lambda: mgr.get("example.com")["status"] == "failed")
    assert manager_error(mgr, "example.com") == "httpx not found"
    assert store.load_meta("example.com")["status"] == "failed"


def manager_error(mgr, domain):
    return mgr.get(domain)["error"]


def test_start_validates_domain(manager):
    with pytest.raises(ValidationError):
        manager.start("not a domain")


def test_rescan_allowed_after_completion(manager):
    manager.start("example.com")
    assert wait_until(lambda: manager.get("example.com")["status"] == "completed")
    scan = manager.start("example.com")  # should not raise
    assert scan["status"] in ("queued", "enumerating", "probing")
