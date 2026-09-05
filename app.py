import os

from flask import Flask

from models import db


def create_app():
    app = Flask(__name__)

    db_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["ADMIN_USERNAME"] = os.environ.get("ADMIN_USERNAME", "admin")
    app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "test")
    app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("RENDER"))

    db.init_app(app)

    from api import api_bp
    from sysadmin import sysadmin_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(sysadmin_bp)

    @app.route("/")
    def index():
        resp = app.make_response(app.send_static_file("index.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
