"""JSON API.

Endpoints (all under ``/api``):

    GET    /api/scans                 list every domain with status + counts
    POST   /api/scans                 start a scan for {"domain": ...}
    GET    /api/scans/<domain>        results + summary for one domain
    GET    /api/scans/<domain>/status live status of one scan (for polling)
    DELETE /api/scans/<domain>        delete a domain's results
    GET    /api/scans/<domain>/export.csv   download results as CSV
"""
import csv
import io

from flask import Blueprint, current_app, jsonify, request

from .scan_manager import ScanAlreadyRunning, TooManyScans
from .validators import ValidationError, normalize_domain

bp = Blueprint("api", __name__, url_prefix="/api")

# Columns exported to CSV, in order.
CSV_FIELDS = [
    "input", "url", "status_code", "title", "webserver",
    "content_type", "content_length", "host", "scheme",
]


def _store():
    return current_app.store


def _manager():
    return current_app.scan_manager


def _error(message, status):
    return jsonify({"error": message}), status


def _domain_entry(domain, live_scan, store):
    """Merge persisted metadata with any live scan state for one domain."""
    if live_scan:
        entry = dict(live_scan)
    else:
        entry = dict(store.load_meta(domain))
    entry["domain"] = domain
    entry["running"] = entry.get("status") in ("queued", "enumerating", "probing")
    return entry


@bp.route("/scans", methods=["GET"])
def list_scans():
    store = _store()
    manager = _manager()

    live = {s["domain"]: s for s in manager.all()}
    entries = {}

    for domain in store.list_domains():
        entries[domain] = _domain_entry(domain, live.get(domain), store)

    # Include in-flight scans whose results aren't on disk yet.
    for domain, scan in live.items():
        if domain not in entries:
            entries[domain] = _domain_entry(domain, scan, store)

    scans = sorted(entries.values(), key=lambda e: e["domain"])
    return jsonify({
        "scans": scans,
        "capacity": {
            "active": manager.active_count(),
            "max": current_app.config["APP_CONFIG"].MAX_CONCURRENT_SCANS,
        },
    })


@bp.route("/scans", methods=["POST"])
def create_scan():
    payload = request.get_json(silent=True) or request.form
    raw = payload.get("domain") if payload else None

    try:
        domain = normalize_domain(raw)
    except ValidationError as exc:
        return _error(str(exc), 400)

    try:
        scan = _manager().start(domain)
    except ScanAlreadyRunning as exc:
        return _error(str(exc), 409)
    except TooManyScans as exc:
        return _error(str(exc), 429)

    return jsonify({"scan": scan}), 202


@bp.route("/scans/<domain>", methods=["GET"])
def get_scan(domain):
    store = _store()
    manager = _manager()
    try:
        domain = normalize_domain(domain)
    except ValidationError as exc:
        return _error(str(exc), 400)

    live = manager.get(domain)
    if not store.domain_exists(domain) and not live:
        return _error("No scan found for %s" % domain, 404)

    results = store.load_results(domain)
    meta = live or store.load_meta(domain)
    return jsonify({
        "domain": domain,
        "meta": meta,
        "summary": store.summary(results),
        "results": results,
        "subdomains": store.load_subdomains(domain),
    })


@bp.route("/scans/<domain>/status", methods=["GET"])
def get_status(domain):
    store = _store()
    manager = _manager()
    try:
        domain = normalize_domain(domain)
    except ValidationError as exc:
        return _error(str(exc), 400)

    live = manager.get(domain)
    if live:
        return jsonify({"scan": live})
    if store.domain_exists(domain):
        return jsonify({"scan": store.load_meta(domain)})
    return _error("No scan found for %s" % domain, 404)


@bp.route("/scans/<domain>", methods=["DELETE"])
def delete_scan(domain):
    store = _store()
    manager = _manager()
    try:
        domain = normalize_domain(domain)
    except ValidationError as exc:
        return _error(str(exc), 400)

    if manager.is_running(domain):
        return _error("Cannot delete %s while a scan is running." % domain, 409)

    deleted = store.delete_domain(domain)
    manager.forget(domain)
    if deleted:
        return jsonify({"deleted": domain})
    return _error("No scan found for %s" % domain, 404)


@bp.route("/scans/<domain>/export.csv", methods=["GET"])
def export_csv(domain):
    store = _store()
    try:
        domain = normalize_domain(domain)
    except ValidationError as exc:
        return _error(str(exc), 400)
    if not store.domain_exists(domain):
        return _error("No scan found for %s" % domain, 404)

    results = store.load_results(domain)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for item in results:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        tech = row.get("tech")
        if isinstance(tech, list):
            row["tech"] = ", ".join(tech)
        writer.writerow(row)

    return (
        buffer.getvalue(),
        200,
        {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=%s.csv" % domain,
        },
    )
