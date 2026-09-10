import os

from flask import Flask
from sqlalchemy import inspect, text

from models import db


def _run_light_migrations():
    # No Alembic/Flask-Migrate in this project. db.create_all() only creates
    # tables that don't exist yet - it never adds columns to a table that
    # already exists. Whenever a model gains a new column, the already-deployed
    # Postgres table falls out of sync and every query against it starts
    # raising "column does not exist" (500s), even though the underlying rows
    # are untouched. Patch that gap here by adding any missing columns.
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    for table in db.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            col_type = col.type.compile(dialect=db.engine.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
            default = col.default
            if default is not None and getattr(default, "is_scalar", False):
                value = default.arg
                if isinstance(value, str):
                    ddl += f" DEFAULT '{value.replace(chr(39), chr(39) * 2)}'"
                elif isinstance(value, bool):
                    ddl += f" DEFAULT {str(value).upper()}"
                elif isinstance(value, (int, float)):
                    ddl += f" DEFAULT {value}"
            with db.engine.begin() as conn:
                conn.execute(text(ddl))


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
        _run_light_migrations()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
