import secrets

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def gen_id(prefix):
    return f"{prefix}_{secrets.token_hex(3)}"


class Program(db.Model):
    __tablename__ = "programs"
    id = db.Column(db.String(40), primary_key=True, default=lambda: gen_id("pg"))
    name = db.Column(db.String(200), nullable=False)
    owner = db.Column(db.String(100))
    owner_tel = db.Column(db.String(50))
    date_from = db.Column(db.String(20))
    date_to = db.Column(db.String(20))
    desc = db.Column(db.Text)
    survey_open = db.Column(db.Boolean, default=False)
    cal_start = db.Column(db.Integer, default=9)
    cal_end = db.Column(db.Integer, default=19)
    view_days = db.Column(db.JSON, default=lambda: [0, 1, 2, 3, 4, 5, 6])
    view_courses = db.Column(db.JSON, default=lambda: "all")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner or "",
            "ownerTel": self.owner_tel or "",
            "from": self.date_from or "",
            "to": self.date_to or "",
            "desc": self.desc or "",
            "surveyOpen": bool(self.survey_open),
            "calStart": self.cal_start if self.cal_start is not None else 9,
            "calEnd": self.cal_end if self.cal_end is not None else 19,
            "viewDays": self.view_days if self.view_days is not None else [0, 1, 2, 3, 4, 5, 6],
            "viewCourses": self.view_courses if self.view_courses is not None else "all",
        }


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.String(40), primary_key=True, default=lambda: gen_id("co"))
    program_id = db.Column(db.String(40), db.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    instructor = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(20))
    desc = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "programId": self.program_id,
            "name": self.name,
            "instructor": self.instructor,
            "color": self.color or "#4C6FA5",
            "desc": self.desc or "",
        }


class Instructor(db.Model):
    __tablename__ = "instructors"
    id = db.Column(db.String(40), primary_key=True, default=lambda: gen_id("in"))
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100))
    memo = db.Column(db.Text)
    etc = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "subject": self.subject or "",
            "memo": self.memo or "",
            "etc": self.etc or "",
        }


class Slot(db.Model):
    __tablename__ = "slots"
    id = db.Column(db.String(40), primary_key=True, default=lambda: gen_id("sl"))
    course_id = db.Column(db.String(40), db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    start = db.Column(db.String(5), nullable=False)
    end = db.Column(db.String(5), nullable=False)
    price = db.Column(db.Integer, default=0)
    cap = db.Column(db.Integer, default=20)

    def to_dict(self):
        return {
            "id": self.id,
            "courseId": self.course_id,
            "day": self.day,
            "start": self.start,
            "end": self.end,
            "price": self.price or 0,
            "cap": self.cap or 20,
        }


class Response(db.Model):
    __tablename__ = "responses"
    id = db.Column(db.String(40), primary_key=True, default=lambda: gen_id("rs"))
    program_id = db.Column(db.String(40), db.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    org = db.Column(db.String(100))
    years = db.Column(db.String(20))
    contact = db.Column(db.String(20))
    memo = db.Column(db.Text)
    picks = db.Column(db.JSON, default=list)
    at = db.Column(db.String(30))
    note = db.Column(db.Text)
    note_at = db.Column(db.String(30))
    src = db.Column(db.String(20), default="web")

    def to_dict(self):
        return {
            "id": self.id,
            "programId": self.program_id,
            "name": self.name,
            "org": self.org or "",
            "years": self.years or "",
            "contact": self.contact or "",
            "memo": self.memo or "",
            "picks": self.picks if self.picks is not None else [],
            "at": self.at or "",
            "note": self.note or "",
            "noteAt": self.note_at or "",
            "src": self.src or "web",
        }
