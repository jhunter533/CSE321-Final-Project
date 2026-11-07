from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path

import parse

REQUIREMENTS = [
    (
        "AREA1",
        "Communications",
        "New Mexico General Education Area 1",
    ),
    (
        "AREA2",
        "Mathematics",
        "New Mexico General Education Area 2",
    ),
    (
        "AREA3",
        "Basic Laboratory Sciences",
        "New Mexico General Education Area 3",
    ),
    (
        "AREA4",
        "Social Sciences",
        "New Mexico General Education Area 4",
    ),
    (
        "AREA5",
        "Humanities",
        "New Mexico General Education Area 5",
    ),
    (
        "AREA6",
        "Creative and Fine Arts",
        "New Mexico General Education Area 6",
    ),
    (
        "AREA7",
        "Additional Humanities/Social Science",
        "Additional courses from Areas 4, 5, and 6",
    ),
]
REQUIREMENT_SUBJECTS = {
    "AREA1":[
        "ENGL",
    ],
    "AREA2":[
        "MATH",
    ],
    "AREA3":[
        "PHYS",
        "CHEM",
    ],
    "AREA4": [
        "PSYC",
        "POLS",
        "ECON",
        "ANTH",
        "SOSC",
        "GNDR",
    ],
    "AREA5": [
        "HIST",
        "PHIL",
        "COMM",
        "ENGL",
        "HUMA",
        "TCOM",
        "SPAN",
        "PORT",
        "GRMN",
    ],
    "AREA6": [
        "MUSC",
        "ARTS",
        "ARTH",
        "THEA",
        "FDMA",
    ],
}
REQUIREMENT_INCLUDES = {
    "AREA7": [
        "AREA4",
        "AREA5",
        "AREA6",
    ],
}

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

CREATE TABLE IF NOT EXISTS RequirementSubject (
    requirement_id INTEGER NOT NULL,
    subject TEXT NOT NULL,

    PRIMARY KEY (
        requirement_id,
        subject
    ),

    FOREIGN KEY (requirement_id)
        REFERENCES Requirement(requirement_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS RequirementIncludes (
    parent_requirement_id INTEGER NOT NULL,
    child_requirement_id INTEGER NOT NULL,

    PRIMARY KEY (
        parent_requirement_id,
        child_requirement_id
    ),

    FOREIGN KEY (parent_requirement_id)
        REFERENCES Requirement(requirement_id)
        ON DELETE CASCADE,

    FOREIGN KEY (child_requirement_id)
        REFERENCES Requirement(requirement_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Schedule (
    schedule_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_accessed TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ScheduleSection (
    schedule_id TEXT NOT NULL,
    section_id INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (
        schedule_id,
        section_id
    ),

    FOREIGN KEY (schedule_id)
        REFERENCES Schedule(schedule_id)
        ON DELETE CASCADE,
    FOREIGN KEY (section_id)
        REFERENCES Section(section_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS AgentLog (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id TEXT,
    user_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input TEXT NOT NULL,
    output TEXT NOT NULL,
    iteration_number INTEGER NOT NULL DEFAULT 1,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (schedule_id)
        REFERENCES Schedule(schedule_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_section_course
    ON Section(course_id);


CREATE INDEX IF NOT EXISTS idx_section_term
    ON Section(term);


CREATE INDEX IF NOT EXISTS idx_meeting_section
    ON Meeting(section_id);


CREATE INDEX IF NOT EXISTS idx_meeting_time
    ON Meeting(days, start_time, end_time);


CREATE INDEX IF NOT EXISTS idx_requirement_subject
    ON RequirementSubject(subject);


CREATE INDEX IF NOT EXISTS idx_schedule_section_section
    ON ScheduleSection(section_id);


CREATE INDEX IF NOT EXISTS idx_agentlog_schedule
    ON AgentLog(schedule_id);


CREATE INDEX IF NOT EXISTS idx_agentlog_user
    ON AgentLog(user_id);


CREATE INDEX IF NOT EXISTS idx_agentlog_timestamp
    ON AgentLog(timestamp);
"""
def connect(path: str|Path=DB_PATH)->sqlite3.Connection:
    conn=sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
def create_database(path:str|Path=DB_PATH)->None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        seed_requirements(conn)
        conn.commit()
def clean_title(title:str)->str:
    title=title.strip()
    return re.sub(r"^[a-z]+\d*:","",title).strip()
def get_requirement_id(conn, code: str) -> int:
    row = conn.execute(
        """
        SELECT requirement_id
        FROM Requirement
        WHERE code = ?
        """,
        (code,),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"Requirement {code!r} does not exist"
        )

    return row[0]


def seed_requirements(conn) -> None:
    for code, name, description in REQUIREMENTS:
        conn.execute(
            """
            INSERT OR IGNORE INTO Requirement (
                code,
                name,
                description
            )
            VALUES (?, ?, ?)
            """,
            (
                code,
                name,
                description,
            ),
        )
    for requirement_code, subjects in REQUIREMENT_SUBJECTS.items():

        requirement_id = get_requirement_id(
            conn,
            requirement_code,
        )

        for subject in subjects:
            conn.execute(
                """
                INSERT OR IGNORE INTO RequirementSubject (
                    requirement_id,
                    subject
                )
                VALUES (?, ?)
                """,
                (
                    requirement_id,
                    subject,
                ),
            )
    for parent_code, child_codes in REQUIREMENT_INCLUDES.items():

        parent_id = get_requirement_id(
            conn,
            parent_code,
        )

        for child_code in child_codes:

            child_id = get_requirement_id(
                conn,
                child_code,
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO RequirementIncludes (
                    parent_requirement_id,
                    child_requirement_id
                )
                VALUES (?, ?)
                """,
                (
                    parent_id,
                    child_id,
                ),
            )
def get_or_create_schedule(conn,session_id:str)->str:
    row=conn.execute(
        """
        SELECT schedule_id FROM Schedule WHERE session_id=?
        """,
        (session_id,)).fetchone()
    if row is not None:
        schedule_id=row[0]
        conn.execute(
            """
            UPDATE Schedule
            SET last_accessed=CURRENT_TIMESTAMP
            WHERE schedule_id=?
            """,
            (schedule_id,),
        )
        return schedule_id
    schedule_id=str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO Schedule (
            schedule_id,
            session_id
        )
        VALUES (?,?)
        """,
        (
            schedule_id,
            session_id,
        ),
    )
    return schedule_id

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
def add_section_to_schedule(conn,schedule_id: str, section_id: int)->dict:
    section=conn.execute(
        """
        SELECT section_id
        FROM Section
        WHERE section_id=?
        """,
        (section_id,)).fetchone()
    if section is None:
        return {
            "success":False,
            "error":"Section does not exist",
        }
    existing=conn.execute(
        """
        SELECT 1
        FROM ScheduleSection
        WHERE schedule_id=? AND section_id=?
        """,
        (
            schedule_id,
            section_id,
        )).fetchone()
    if existing is not None:
        return {
                "success":False,
                "error":"Section already in schedule",
        }
    conn.execute(
        """
        INSERT INTO ScheduleSection(schedule_id,section_id)
        VALUES (?,?)
        """,
        (
            schedule_id,
            section_id,
        ),
    )
    return {
            "success":True,
            "section_id":section_id,
    }
def remove_section_from_schedule(conn,schedule_id: str, section_id: int)->dict:
    cursor=conn.execute(
        """
        DELETE FROM ScheduleSection
        WHERE schedule_id=? AND section_id=?
        """,
        (
            schedule_id,
            section_id,
        ),
    )
    if cursor.rowcount==0:
        return {
                "success":False,
                "error":"Section not in schedule",
        }
    return {
            "success":True,
            "section_id":section_id,
    }
def get_schedule(conn,schedule_id:str)->list[dict]:
    rows=conn.execute(
        """
        SELECT
            s.section_id,
            s.crn,
            s.term,
            s.section_number,
            s.credit_hours,
            c.course_id,
            c.subject,
            c.course_number,
            c.title
        FROM ScheduleSection AS ss
        JOIN Section AS s ON ss.section_id=s.section_id
        JOIN Course As c ON s.course_id=c.course_id
        WHERE ss.schedule_id=?
        ORDER BY c.subject, c.course_number, s.section_number
        """,
        (schedule_id,),
    ).fetchall()
    return [
        {
            "section_id":row[0],
            "crn":row[1],
            "term":row[2],
            "section_number":row[3],
            "credit_hours":row[4],
            "course_id":row[5],
            "subject":row[6],
            "course_number":row[7],
            "title":row[8],
        }
        for row in rows
    ]
def log_agent_tool(conn,user_id:str,tool_name:str,tool_input,tool_output,schedule_id,iteration_number:int=1)->int:
    cursor=conn.execute(
        """
        INSERT INTO AgentLog(schedule_id,user_id,tool_name,input,output,iteration_number)
        VALUES (?,?,?,?,?,?)
        """,
        (
            schedule_id,
            user_id,
            tool_name,
            json.dumps(tool_input),
            json.dumps(tool_output),
            iteration_number,
        ),
    )
    return cursor.lastrowid

def print_database_summary(path)->None:
    with connect(path) as conn:
        tables = [
            "Course",
            "Section",
            "Meeting",
            "Instructor",
            "MeetingInstructor",
            "Requirement",
            "RequirementSubject",
            "RequirementIncludes",
            "Schedule",
            "ScheduleSection",
            "AgentLog",
        ]

        print("\nDatabase contents:")

        for table in tables:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"  {table:20} {count:6}")
