PRAGMA foreign_keys = ON;


-- =========================================================
-- Course catalog
-- =========================================================

CREATE TABLE IF NOT EXISTS Course (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    course_number TEXT NOT NULL,
    title TEXT NOT NULL,

    UNIQUE (
        subject,
        course_number,
        title
    )
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

    UNIQUE (
        term,
        crn
    )
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

    PRIMARY KEY (
        meeting_id,
        instructor_id
    ),

    FOREIGN KEY (meeting_id)
        REFERENCES Meeting(meeting_id)
        ON DELETE CASCADE,

    FOREIGN KEY (instructor_id)
        REFERENCES Instructor(instructor_id)
        ON DELETE CASCADE
);


-- =========================================================
-- General education requirements
-- =========================================================

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


-- =========================================================
-- Browser/session schedule state
-- =========================================================

CREATE TABLE IF NOT EXISTS Schedule (
    schedule_id TEXT PRIMARY KEY,

    session_id TEXT NOT NULL UNIQUE,

    created_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    last_accessed TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS ScheduleSection (
    schedule_id TEXT NOT NULL,
    section_id INTEGER NOT NULL,

    added_at TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

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


-- =========================================================
-- Agent logging
-- =========================================================

CREATE TABLE IF NOT EXISTS AgentLog (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,

    schedule_id TEXT,

    user_id TEXT NOT NULL,

    tool_name TEXT NOT NULL,

    input TEXT NOT NULL,

    output TEXT NOT NULL,

    iteration_number INTEGER NOT NULL
        DEFAULT 1,

    timestamp TEXT NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (schedule_id)
        REFERENCES Schedule(schedule_id)
        ON DELETE SET NULL
);


-- =========================================================
-- Indexes
-- =========================================================

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
