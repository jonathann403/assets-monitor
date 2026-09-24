import json
import os

import pytest

from app.store import summarize
from app.validators import ValidationError


def _seed(store, domain, results, subs=None):
    domain_dir = os.path.join(store.results_dir, domain)
    os.makedirs(domain_dir, exist_ok=True)
    with open(os.path.join(domain_dir, "httpx.json"), "w") as fh:
        json.dump(results, fh)
    if subs is not None:
        with open(os.path.join(domain_dir, "subdomains.txt"), "w") as fh:
            fh.write("\n".join(subs))


def test_list_and_load_results(store):
    _seed(store, "example.com", [{"input": "www.example.com", "status_code": 200}],
          subs=["www.example.com", "api.example.com"])
    assert store.list_domains() == ["example.com"]
    assert store.domain_exists("example.com")
    results = store.load_results("example.com")
    assert len(results) == 1
    assert store.load_subdomains("example.com") == ["www.example.com", "api.example.com"]


def test_load_results_handles_jsonl_legacy(store):
    # A file written as JSON-lines under a .json name should still parse.
    domain_dir = os.path.join(store.results_dir, "legacy.com")
    os.makedirs(domain_dir)
    with open(os.path.join(domain_dir, "httpx.json"), "w") as fh:
        fh.write('{"input":"a.legacy.com","status_code":200}\n')
        fh.write('{"input":"b.legacy.com","status_code":301}\n')
    results = store.load_results("legacy.com")
    assert len(results) == 2
    assert results[0]["input"] == "a.legacy.com"


def test_meta_synthesized_when_absent(store):
    _seed(store, "example.com", [{"input": "www", "status_code": 200}], subs=["www"])
    meta = store.load_meta("example.com")
    assert meta["status"] == "completed"
    assert meta["synthesized"] is True
    assert meta["hosts_live"] == 1


def test_save_and_load_meta_roundtrip(store):
    store.save_meta("example.com", {"domain": "example.com", "status": "failed", "error": "boom"})
    meta = store.load_meta("example.com")
    assert meta["status"] == "failed"
    assert meta["error"] == "boom"


def test_delete_domain(store):
    _seed(store, "example.com", [{"input": "www", "status_code": 200}])
    assert store.delete_domain("example.com") is True
    assert not store.domain_exists("example.com")
    assert store.delete_domain("example.com") is False


def test_path_traversal_is_confined(store):
    # Inputs that cannot be reduced to a valid host are rejected outright.
    for bad in ["../../../etc", "..", "/etc/passwd"]:
        with pytest.raises(ValidationError):
            store._domain_dir(bad)
    # A URL-ish value with a path normalizes to the bare host and stays inside
    # the results root (the path portion is stripped, never traversed).
    path = store._domain_dir("a.com/../../etc")
    assert path == os.path.join(store.results_dir, "a.com")
    assert path.startswith(store.results_dir + os.sep)


def test_summarize_counts_status_classes_and_tech():
    results = [
        {"status_code": 200, "tech": ["nginx", "PHP"], "webserver": "nginx", "cdn": True},
        {"status_code": 301, "tech": ["nginx"], "webserver": "nginx"},
        {"status_code": 404, "tech": []},
        {"status_code": 500},
        {"status_code": None},  # unresponsive -> "other"
    ]
    s = summarize(results)
    assert s["total"] == 5
    assert s["status_classes"] == {"2xx": 1, "3xx": 1, "4xx": 1, "5xx": 1, "other": 1}
    assert s["live"] == 4
    assert s["cdn_count"] == 1
    tech = {t["name"]: t["count"] for t in s["technologies"]}
    assert tech["nginx"] == 2 and tech["PHP"] == 1
    assert s["unique_technologies"] == 2
