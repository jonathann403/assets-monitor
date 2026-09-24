"""Web (HTML) routes.

The page is a thin shell; all data is loaded and refreshed from the JSON API
(see :mod:`app.api`) so scan progress updates live without reloads.
"""
from flask import Blueprint, current_app, render_template, request

from .validators import ValidationError, normalize_domain

bp = Blueprint("main", __name__)


@bp.route("/", methods=["GET"])
def index():
    # Allow ?domain=example.com to deep-link to a scan; ignore invalid values.
    preselect = None
    raw = request.args.get("domain")
    if raw:
        try:
            preselect = normalize_domain(raw)
        except ValidationError:
            preselect = None

    config = current_app.config["APP_CONFIG"]
    return render_template(
        "index.html",
        preselect=preselect,
        max_scans=config.MAX_CONCURRENT_SCANS,
    )


@bp.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}
