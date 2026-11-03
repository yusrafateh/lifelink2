"""Application factory - wires config, database, controllers (MVC) and workers."""
import logging
import os

from flask import Flask, jsonify, render_template

from .config import Config
from .db import close_db, init_db
from .controllers import admin_controller, auth_controller, request_controller
from .services import worker


def create_app(overrides=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    if app.config["SECRET_KEY"] == "dev-only-change-me" and not app.config["TESTING"]:
        app.logger.warning("Using the default SECRET_KEY. Set SECRET_KEY env var in production!")

    init_db(app.config["DATABASE_PATH"])
    app.teardown_appcontext(close_db)

    # Controllers (C of MVC)
    app.register_blueprint(auth_controller.bp)
    app.register_blueprint(request_controller.bp)
    app.register_blueprint(admin_controller.bp)

    # View (V of MVC): single-page HTML that talks to the REST API
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():          # used by cloud load balancers / uptime checks
        return jsonify(status="ok", worker_threads=worker.active_thread_count())

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'")
        return resp

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="Not found."), 404

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify(error="Internal server error."), 500

    if app.config["START_WORKERS"] and not app.config["TESTING"]:
        worker.start_workers(app)
    return app
