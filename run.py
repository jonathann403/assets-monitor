"""Development entry point for Assets Monitor.

For production, serve the app factory with a WSGI server, e.g.:
    gunicorn "app:create_app()"
"""
from app import create_app
from config import Config


def main():
    config = Config()
    app = create_app(config)
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)


if __name__ == "__main__":
    main()
