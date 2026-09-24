from conftest import wait_until


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_index_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Assets Monitor" in resp.data


def test_list_scans_empty(client):
    data = client.get("/api/scans").get_json()
    assert data["scans"] == []
    assert data["capacity"]["max"] == 2


def test_create_scan_validation_error(client):
    resp = client.post("/api/scans", json={"domain": "a.com; rm -rf /"})
    assert resp.status_code == 400
    assert "valid domain" in resp.get_json()["error"]


def test_create_scan_empty_domain(client):
    resp = client.post("/api/scans", json={"domain": ""})
    assert resp.status_code == 400


def test_create_and_complete_scan(client, app):
    resp = client.post("/api/scans", json={"domain": "example.com"})
    assert resp.status_code == 202
    assert resp.get_json()["scan"]["domain"] == "example.com"

    assert wait_until(lambda: app.scan_manager.get("example.com")["status"] == "completed")

    # now it appears in the list with counts
    listing = client.get("/api/scans").get_json()
    domains = {s["domain"]: s for s in listing["scans"]}
    assert domains["example.com"]["hosts_live"] == 2
    assert domains["example.com"]["running"] is False

    # detail endpoint returns results + summary
    detail = client.get("/api/scans/example.com").get_json()
    assert len(detail["results"]) == 2
    assert detail["summary"]["status_classes"]["2xx"] == 1
    assert detail["summary"]["status_classes"]["4xx"] == 1


def test_duplicate_scan_conflict(client, app):
    client.post("/api/scans", json={"domain": "example.com"})
    # immediately request again; may still be running -> 409, or done -> 202.
    resp = client.post("/api/scans", json={"domain": "example.com"})
    assert resp.status_code in (202, 409)


def test_get_missing_scan_404(client):
    assert client.get("/api/scans/missing.com").status_code == 404
    assert client.get("/api/scans/missing.com/status").status_code == 404


def test_delete_scan(client, app):
    client.post("/api/scans", json={"domain": "example.com"})
    assert wait_until(lambda: app.scan_manager.get("example.com")["status"] == "completed")
    resp = client.delete("/api/scans/example.com")
    assert resp.status_code == 200
    assert client.get("/api/scans/example.com").status_code == 404


def test_delete_missing_404(client):
    assert client.delete("/api/scans/missing.com").status_code == 404


def test_export_csv(client, app):
    client.post("/api/scans", json={"domain": "example.com"})
    assert wait_until(lambda: app.scan_manager.get("example.com")["status"] == "completed")
    resp = client.get("/api/scans/example.com/export.csv")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith("text/csv")
    body = resp.get_data(as_text=True)
    assert "input,url,status_code" in body.splitlines()[0]
    assert "www.example.com" in body


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
