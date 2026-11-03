from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import parse

DB_PATH=Path("nmt_scheduler.db")

SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS Course (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    course_number TEXT NOT NULL,
    title TEXT NOT NULL,

    UNIQUE(subject, course_number, title)
);

CREATE TABLE IF NOT EXISTS Section (
    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,

    term TEXT NOT NULL,
    crn TEXT NOT NULL,
    section_number TEXT NOT NULL,
    campus TEXT,
    credit_hours INTEGER,

    FOREIGN KEY (course_id)
        REFERENCES Course(course_id),

    UNIQUE(term, crn)
);

CREATE TABLE IF NOT EXISTS Meeting (
    meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL,

    days TEXT,
    start_date TEXT,
    end_date TEXT,
    start_time INTEGER,
    end_time INTEGER,
    location TEXT,
    meeting_type TEXT,

    FOREIGN KEY (section_id)
        REFERENCES Section(section_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Instructor (
    instructor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS MeetingInstructor (
    meeting_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,

    PRIMARY KEY (meeting_id, instructor_id),

    FOREIGN KEY (meeting_id)
        REFERENCES Meeting(meeting_id)
        ON DELETE CASCADE,

    FOREIGN KEY (instructor_id)
        REFERENCES Instructor(instructor_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Requirement (
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS CourseRequirement (
    course_id INTEGER NOT NULL,
    requirement_id INTEGER NOT NULL,

    PRIMARY KEY (course_id, requirement_id),

    FOREIGN KEY (course_id)
        REFERENCES Course(course_id)
        ON DELETE CASCADE,

    FOREIGN KEY (requirement_id)
        REFERENCES Requirement(requirement_id)
        ON DELETE CASCADE
);
"""
def connect(path: str|Path=DB_PATH)->sqlite3.Connection:
    conn=sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
def create_database(path:str|Path=DB_PATH)->None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
def clean_title(title:str)->str:
    title=title.strip()
    return re.sub(r"^[a-z]+\d*:","",title).strip()
def get_or_create_course(conn,section)->int:
    subject=section.course.subject
    number=section.course.course_number
    title=clean_title(section.title_raw)
    conn.execute(
        """
        INSERT OR IGNORE INTO Course(
        subject,
        course_number,
        title
        )
        VALUES (?,?,?)
        """,
        (
            subject,
            number,
            title
        ),
    )
    row=conn.execute(
        """SELECT course_id FROM Course WHERE subject=? AND course_number=? AND title=?""",
        (
            subject,
            number,
            title,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError(
            f"Could not retrieve course "
            f"{subject} {number}:{title}"
        )
    return row[0]
def valid_instructor_name(name: str)->bool:
    if name is None:
        return False
    name=name.strip()
    if not name:
        return False
    if name.upper()=="N/A":
        return False
    return True
def get_or_create_instructor(conn,instructor)->int|None:
    name = instructor.key.strip()

    if not valid_instructor_name(name):
        return None

    conn.execute(
        """
        INSERT OR IGNORE INTO Instructor (name)
        VALUES (?)
        """,
        (name,),
    )

    row = conn.execute(
        """
        SELECT instructor_id
        FROM Instructor
        WHERE name = ?
        """,
        (name,),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"Could not retrieve instructor {name!r}"
        )

    return row[0]
def insert_section(conn,term,section)->int:
    course_id=get_or_create_course(conn,section)
    cursor=conn.execute(
        """
        INSERT INTO Section (
            course_id,
            term,
            crn,
            section_number,
            campus,
            credit_hours
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            course_id,
            term,
            section.crn,
            section.section_number,
            section.campus,
            section.credit_hours,
        ),
    )

    section_id = cursor.lastrowid

    for meeting in section.meetings:

        cursor = conn.execute(
            """
            INSERT INTO Meeting (
                section_id,
                days,
                start_date,
                end_date,
                start_time,
                end_time,
                location,
                meeting_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                section_id,
                meeting.days.strip(),

                (
                    meeting.start_date.isoformat()
                    if meeting.start_date is not None
                    else None
                ),

                (
                    meeting.end_date.isoformat()
                    if meeting.end_date is not None
                    else None
                ),

                meeting.start_time,
                meeting.end_time,
                meeting.location.strip(),
                meeting.meeting_type.strip(),
            ),
        )

        meeting_id = cursor.lastrowid

        for instructor in meeting.instructors:

            instructor_id = get_or_create_instructor(
                conn,
                instructor,
            )

            if instructor_id is None:
                continue

            conn.execute(
                """
                INSERT OR IGNORE INTO MeetingInstructor (
                    meeting_id,
                    instructor_id
                )
                VALUES (?, ?)
                """,
                (
                    meeting_id,
                    instructor_id,
                ),
            )

    return section_id
def insert_term(term,sections,path)->None:
    create_database(path)
    with connect(path) as conn:
        for section in sections:
            insert_section(conn,term,section)
        conn.commit()
def print_database_summary(path)->None:
    with connect(path) as conn:
        tables = [
            "Course",
            "Section",
            "Meeting",
            "Instructor",
            "MeetingInstructor",
            "Requirement",
            "CourseRequirement",
        ]

        print("\nDatabase contents:")

        for table in tables:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"  {table:20} {count:6}")
