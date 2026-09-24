"""Application factory."""
import os
import sys

from flask import Flask

# Ensure the project root is importable so ``src`` packages resolve regardless
# of the working directory the server is started from.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import Config  # noqa: E402
from .scan_manager import ScanManager  # noqa: E402
from .store import Store  # noqa: E402


def create_app(config=None):
    app = Flask(__name__)
    config = config or Config()
    app.config.from_object(config)
    app.config["APP_CONFIG"] = config

    store = Store(config.RESULTS_DIR)
    store.ensure_root()
    manager = ScanManager(config, store)

    app.store = store
    app.scan_manager = manager

    from .routes import bp as web_bp
    from .api import bp as api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    return app
