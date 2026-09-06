import re
from datetime import datetime
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from models import Course, Instructor, Program, Response, Slot, db, gen_id

api_bp = Blueprint("api", __name__, url_prefix="/api")

ADMIN_SESSION_KEY = "admin_auth"
CONTACT_RE = re.compile(r"^010\d{8}$")


def digits_only(s):
    return re.sub(r"\D", "", s or "")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get(ADMIN_SESSION_KEY):
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)

    return wrapper


# ---------------- auth ----------------
@api_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    admin_user = current_app.config.get("ADMIN_USERNAME", "admin")
    admin_pass = current_app.config.get("ADMIN_PASSWORD", "test")
    if data.get("id") == admin_user and data.get("pw") == admin_pass:
        session[ADMIN_SESSION_KEY] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "invalid credentials"}), 401


@api_bp.route("/logout", methods=["POST"])
def logout():
    session.pop(ADMIN_SESSION_KEY, None)
    return jsonify({"ok": True})


@api_bp.route("/session", methods=["GET"])
def get_session():
    is_admin = bool(session.get(ADMIN_SESSION_KEY))
    data = {"admin": is_admin}
    if is_admin:
        # Diagnostic: lets an authenticated admin confirm the app is actually
        # writing to Postgres (persists across redeploys) and not a SQLite
        # fallback file on Render's ephemeral disk (wiped on every redeploy).
        data["db_engine"] = db.engine.dialect.name
    return jsonify(data)


# ---------------- admin: whole-DB read/replace ----------------
# The academy admin is this app's single trusted operator (same trust level the
# old client-only prototype assumed for anyone with access to the page). All
# create/edit/delete business rules (instructor-conflict check, 30-min grid,
# calendar range, cascade deletes) already live in static/index.html and keep
# working unchanged against this in-memory DB shape - we don't duplicate that
# validation server-side because the admin isn't an untrusted boundary here.
@api_bp.route("/db", methods=["GET"])
@admin_required
def get_db():
    return jsonify(_full_db_dict())


@api_bp.route("/db", methods=["POST"])
@admin_required
def replace_db():
    data = request.get_json(force=True, silent=True) or {}
    try:
        _replace_all(
            data.get("programs", []), data.get("courses", []), data.get("slots", []),
            data.get("responses", []), data.get("instructors", []),
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


def _full_db_dict():
    return {
        "programs": [p.to_dict() for p in Program.query.all()],
        "courses": [c.to_dict() for c in Course.query.all()],
        "slots": [s.to_dict() for s in Slot.query.all()],
        "responses": [r.to_dict() for r in Response.query.all()],
        "instructors": [i.to_dict() for i in Instructor.query.all()],
    }


def _replace_all(programs, courses, slots, responses, instructors=None):
    Response.query.delete()
    Slot.query.delete()
    Course.query.delete()
    Program.query.delete()
    Instructor.query.delete()
    db.session.flush()

    for i in (instructors or []):
        db.session.add(Instructor(
            id=i["id"], name=i.get("name", ""), subject=i.get("subject", ""),
            memo=i.get("memo", ""), etc=i.get("etc", ""), unavailable=i.get("unavailable", []),
        ))
    for p in programs:
        db.session.add(Program(
            id=p["id"], name=p.get("name", ""), owner=p.get("owner", ""), owner_tel=p.get("ownerTel", ""),
            date_from=p.get("from", ""), date_to=p.get("to", ""), desc=p.get("desc", ""),
            survey_open=bool(p.get("surveyOpen", False)), cal_start=int(p.get("calStart", 9) or 9),
            cal_end=int(p.get("calEnd", 19) or 19), view_days=p.get("viewDays", [0, 1, 2, 3, 4, 5, 6]),
            view_courses=p.get("viewCourses", "all"),
        ))
    for c in courses:
        db.session.add(Course(
            id=c["id"], program_id=c["programId"], name=c.get("name", ""),
            instructor=c.get("instructor", ""), color=c.get("color", "#4C6FA5"), desc=c.get("desc", ""),
        ))
    for s in slots:
        db.session.add(Slot(
            id=s["id"], course_id=s["courseId"], day=int(s.get("day", 0)),
            start=s.get("start", "09:00"), end=s.get("end", "10:00"),
            price=int(s.get("price", 0) or 0), cap=max(1, int(s.get("cap", 20) or 20)),
        ))
    for r in responses:
        db.session.add(Response(
            id=r["id"], program_id=r["programId"], name=r.get("name", ""), org=r.get("org", ""),
            years=r.get("years", ""), contact=r.get("contact", ""), memo=r.get("memo", ""),
            picks=r.get("picks", []), at=r.get("at", ""), note=r.get("note", ""),
            note_at=r.get("noteAt", ""), src=r.get("src", "web"),
        ))
    db.session.commit()


@api_bp.route("/seed-demo", methods=["POST"])
@admin_required
def seed_demo():
    p = Program(
        id=gen_id("pg"), name="2026 상반기 프로젝트 역량강화 과정", owner="김민준 교육담당", owner_tel="010-2222-3333",
        date_from="2026-10-05", date_to="2026-10-30",
        desc="업무 역량 향상을 위한 상반기 정기 교육과정입니다. 참여 가능한 시간대를 선택해 주세요.",
        survey_open=True, cal_start=9, cal_end=19, view_days=[0, 1, 2, 3, 4, 5, 6], view_courses="all",
    )
    c1 = Course(id=gen_id("co"), program_id=p.id, name="Java 백엔드 심화 (3~5년차)", instructor="박서준",
                color="#4C6FA5", desc="스프링 부트 기반 실무 백엔드 심화 과정")
    c2 = Course(id=gen_id("co"), program_id=p.id, name="정보보안 기본 (전사원)", instructor="이하은",
                color="#0E7C7B", desc="전사 필수 정보보안 기초 교육")
    c3 = Course(id=gen_id("co"), program_id=p.id, name="데이터 분석 입문 (1~2년차)", instructor="박서준",
                color="#B8860B", desc="엑셀·SQL 기반 데이터 분석 입문")
    c4 = Course(id=gen_id("co"), program_id=p.id, name="리더십 워크숍 (6년차 이상)", instructor="최유진",
                color="#8A4FBE", desc="팀 리딩을 위한 리더십 워크숍")

    s1 = Slot(id=gen_id("sl"), course_id=c1.id, day=1, start="09:00", end="11:00", price=120000, cap=15)
    s2 = Slot(id=gen_id("sl"), course_id=c1.id, day=3, start="09:00", end="11:00", price=120000, cap=15)
    s3 = Slot(id=gen_id("sl"), course_id=c2.id, day=6, start="10:00", end="12:00", price=50000, cap=30)
    s4 = Slot(id=gen_id("sl"), course_id=c3.id, day=2, start="14:00", end="16:00", price=80000, cap=20)
    s5 = Slot(id=gen_id("sl"), course_id=c4.id, day=4, start="13:00", end="14:30", price=150000, cap=12)

    r1 = Response(id=gen_id("rs"), program_id=p.id, name="홍길동", org="디지털플랫폼사업부", years="3",
                   contact="01012345678", memo="오전 시간대를 선호합니다", picks=[s1.id, s3.id], at=now_str(),
                   note="", note_at="", src="web")
    r2 = Response(id=gen_id("rs"), program_id=p.id, name="김영희", org="플랫폼운영팀", years="6~10",
                   contact="01099998888", memo="", picks=[s5.id], at=now_str(), note="", note_at="", src="web")

    i1 = Instructor(id=gen_id("in"), name="박서준", subject="백엔드/데이터", memo="", etc="")
    i2 = Instructor(id=gen_id("in"), name="이하은", subject="정보보안", memo="", etc="")
    i3 = Instructor(id=gen_id("in"), name="최유진", subject="리더십", memo="", etc="")

    programs_payload = [dict(
        id=p.id, name=p.name, owner=p.owner, ownerTel=p.owner_tel, **{"from": p.date_from, "to": p.date_to},
        desc=p.desc, surveyOpen=p.survey_open, calStart=p.cal_start, calEnd=p.cal_end,
        viewDays=p.view_days, viewCourses=p.view_courses,
    )]
    courses_payload = [dict(id=c.id, programId=c.program_id, name=c.name, instructor=c.instructor,
                             color=c.color, desc=c.desc) for c in (c1, c2, c3, c4)]
    slots_payload = [dict(id=s.id, courseId=s.course_id, day=s.day, start=s.start, end=s.end,
                           price=s.price, cap=s.cap) for s in (s1, s2, s3, s4, s5)]
    responses_payload = [dict(id=r.id, programId=r.program_id, name=r.name, org=r.org, years=r.years,
                               contact=r.contact, memo=r.memo, picks=r.picks, at=r.at, note=r.note,
                               noteAt=r.note_at, src=r.src) for r in (r1, r2)]
    instructors_payload = [dict(id=i.id, name=i.name, subject=i.subject, memo=i.memo, etc=i.etc)
                            for i in (i1, i2, i3)]

    _replace_all(programs_payload, courses_payload, slots_payload, responses_payload, instructors_payload)
    return jsonify(_full_db_dict())


# ---------------- public survey ----------------
@api_bp.route("/public/<pid>", methods=["GET"])
def public_program(pid):
    p = Program.query.get(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    courses = Course.query.filter_by(program_id=pid).all()
    course_ids = [c.id for c in courses]
    slots = Slot.query.filter(Slot.course_id.in_(course_ids)).all() if course_ids else []
    return jsonify({
        "program": p.to_dict(),
        "courses": [c.to_dict() for c in courses],
        "slots": [s.to_dict() for s in slots],
    })


@api_bp.route("/public/<pid>/responses", methods=["POST"])
def submit_public_response(pid):
    program = Program.query.get(pid)
    if not program:
        return jsonify({"message": "존재하지 않는 수요조사입니다"}), 404
    if not program.survey_open:
        return jsonify({"message": "마감된 수요조사입니다"}), 403

    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    org = (data.get("org") or "").strip()
    contact = digits_only(data.get("contact"))
    picks = data.get("picks") or []

    if not name or not org:
        return jsonify({"message": "이름/소속을 입력해 주세요"}), 400
    if not CONTACT_RE.match(contact):
        return jsonify({"message": "연락처 형식이 올바르지 않습니다 (010 + 8자리)"}), 400
    if not picks:
        return jsonify({"message": "시간대를 1건 이상 선택해 주세요"}), 400

    valid_slot_ids = {s.id for s in Slot.query.join(Course).filter(Course.program_id == pid).all()}
    picks = [pk for pk in picks if pk in valid_slot_ids]
    if not picks:
        return jsonify({"message": "유효한 시간대 선택이 없습니다"}), 400

    # BR-06: program + name + contact(digits only) is the dedup key
    for existing in Response.query.filter_by(program_id=pid, name=name, contact=contact).all():
        db.session.delete(existing)

    r = Response(
        program_id=pid, name=name, org=org, years=data.get("years", ""), contact=contact,
        memo=data.get("memo", ""), picks=picks, at=now_str(), note="", note_at="",
        src=data.get("src", "web"),
    )
    db.session.add(r)
    db.session.commit()
    return jsonify(r.to_dict()), 201
