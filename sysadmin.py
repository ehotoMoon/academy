import csv
import io
import json
import os
from functools import wraps

from flask import Blueprint, Response as FlaskResponse, redirect, render_template, request, session, url_for

from models import Course, Instructor, Program, Response, Slot, db

sysadmin_bp = Blueprint("sysadmin", __name__, url_prefix="/sysadmin")

SYSADMIN_SESSION_KEY = "sysadmin_auth"

TABLES = {
    "programs": Program,
    "courses": Course,
    "slots": Slot,
    "responses": Response,
    "instructors": Instructor,
}


def _configured():
    return bool(os.environ.get("SYSADMIN_USERNAME") and os.environ.get("SYSADMIN_PASSWORD"))


def sysadmin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get(SYSADMIN_SESSION_KEY):
            return redirect(url_for("sysadmin.login"))
        return fn(*args, **kwargs)

    return wrapper


@sysadmin_bp.route("/login", methods=["GET", "POST"])
def login():
    if not _configured():
        return (
            "시스템어드민 계정이 설정되지 않았습니다 "
            "(SYSADMIN_USERNAME / SYSADMIN_PASSWORD 환경변수가 필요합니다)",
            503,
        )
    error = None
    if request.method == "POST":
        if (request.form.get("username") == os.environ.get("SYSADMIN_USERNAME")
                and request.form.get("password") == os.environ.get("SYSADMIN_PASSWORD")):
            session[SYSADMIN_SESSION_KEY] = True
            return redirect(url_for("sysadmin.dashboard"))
        error = "아이디 또는 비밀번호가 올바르지 않습니다"
    return render_template("sysadmin_login.html", error=error)


@sysadmin_bp.route("/logout", methods=["POST"])
def logout():
    session.pop(SYSADMIN_SESSION_KEY, None)
    return redirect(url_for("sysadmin.login"))


@sysadmin_bp.route("/")
@sysadmin_required
def dashboard():
    counts = {name: model.query.count() for name, model in TABLES.items()}
    return render_template("sysadmin_dashboard.html", tables=list(TABLES.keys()), counts=counts)


def _model_columns(model):
    return [c.name for c in model.__table__.columns]


def _row_to_csv_value(model, row, col):
    val = getattr(row, col)
    column = model.__table__.columns[col]
    type_name = column.type.__class__.__name__
    # Serialize by column type (not by the Python value's type) so a JSON column
    # holding a plain string (e.g. Program.view_courses == "all") round-trips
    # correctly - json.loads() on import always expects a JSON-encoded value.
    if type_name == "JSON":
        return "" if val is None else json.dumps(val, ensure_ascii=False)
    if isinstance(val, bool):
        return "true" if val else "false"
    return "" if val is None else val


@sysadmin_bp.route("/export/<table>")
@sysadmin_required
def export_csv(table):
    if table not in TABLES:
        return "unknown table", 404
    model = TABLES[table]
    cols = _model_columns(model)
    buf = io.StringIO()
    buf.write(chr(0xFEFF))
    writer = csv.writer(buf)
    writer.writerow(cols)
    for row in model.query.all():
        writer.writerow([_row_to_csv_value(model, row, c) for c in cols])
    return FlaskResponse(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}.csv"},
    )


def _parse_csv_value(model, col, raw):
    column = model.__table__.columns[col]
    type_name = column.type.__class__.__name__
    if raw is None or raw == "":
        return None
    if type_name == "JSON":
        return json.loads(raw)
    if type_name == "Boolean":
        return raw.strip().lower() in ("true", "1", "yes")
    if type_name == "Integer":
        return int(raw)
    return raw


@sysadmin_bp.route("/import/<table>", methods=["POST"])
@sysadmin_required
def import_csv(table):
    if table not in TABLES:
        return "unknown table", 404
    model = TABLES[table]
    file = request.files.get("file")
    if not file or not file.filename:
        return redirect(url_for("sysadmin.dashboard"))

    text = file.stream.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    valid_cols = set(_model_columns(model))
    header_cols = set(reader.fieldnames or [])
    if not header_cols or not header_cols <= valid_cols:
        return (
            f"CSV 헤더가 테이블 컬럼과 일치하지 않습니다.<br>"
            f"기대한 컬럼: {sorted(valid_cols)}<br>업로드된 헤더: {sorted(header_cols)}"
            f'<br><a href="{url_for("sysadmin.dashboard")}">돌아가기</a>',
            400,
        )

    rows = list(reader)
    try:
        model.query.delete()
        for row in rows:
            kwargs = {col: _parse_csv_value(model, col, raw) for col, raw in row.items()}
            db.session.add(model(**kwargs))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f'업로드 실패: {e}<br><a href="{url_for("sysadmin.dashboard")}">돌아가기</a>', 400

    return redirect(url_for("sysadmin.dashboard"))
