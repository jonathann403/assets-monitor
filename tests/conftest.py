import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config  # noqa: E402
from app import create_app  # noqa: E402
from app.scan_manager import ScanManager  # noqa: E402
from app.store import Store  # noqa: E402


@pytest.fixture
def config(tmp_path):
    cfg = Config()
    cfg.RESULTS_DIR = str(tmp_path / "results")
    cfg.MAX_CONCURRENT_SCANS = 2
    return cfg


@pytest.fixture
def store(config):
    s = Store(config.RESULTS_DIR)
    s.ensure_root()
    return s


def fake_runner_factory(store):
    """A runner that simulates a fast, successful scan writing real files."""
    def runner(ctx):
        ctx.update(status="enumerating", message="enumerating")
        subs = [f"www.{ctx.domain}", f"api.{ctx.domain}"]
        domain_dir = os.path.join(store.results_dir, ctx.domain)
        os.makedirs(domain_dir, exist_ok=True)
        with open(os.path.join(domain_dir, "subdomains.txt"), "w") as fh:
            fh.write("\n".join(subs))
        ctx.update(subdomains_found=len(subs), status="probing")
        results = [
            {"input": subs[0], "url": f"https://{subs[0]}", "status_code": 200,
             "title": "Home", "webserver": "nginx", "tech": ["nginx"],
             "content_length": 1200, "host": "1.2.3.4"},
            {"input": subs[1], "url": f"https://{subs[1]}", "status_code": 404,
             "title": "", "webserver": "nginx", "tech": [], "host": "1.2.3.5"},
        ]
        import json
        with open(os.path.join(domain_dir, "httpx.json"), "w") as fh:
            json.dump(results, fh)
        ctx.update(hosts_live=len(results))
    return runner


@pytest.fixture
def app(config, store):
    application = create_app(config)
    application.scan_manager = ScanManager(config, store, runner=fake_runner_factory(store))
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def manager(config, store):
    return ScanManager(config, store, runner=fake_runner_factory(store))


def wait_until(predicate, timeout=3.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False
