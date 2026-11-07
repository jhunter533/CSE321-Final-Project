PRAGMA foreign_keys = ON;
-- Remove any old copy of the demo session if this script has already been run.
DELETE FROM Schedule
WHERE schedule_id = 'demo-schedule-001';

-- Create one demonstration browser schedule.

INSERT INTO Schedule (
    schedule_id,
    session_id
)
VALUES (
    'demo-schedule-001',
    'demo-session-001'
);

-- Add two REAL sections from the populated course database.
-- These are chosen from the newest semester currently stored.

INSERT INTO ScheduleSection (
    schedule_id,
    section_id
)
SELECT
    'demo-schedule-001',
    section_id
FROM Section
WHERE term = (
    SELECT MAX(term)
    FROM Section
)
ORDER BY section_id
LIMIT 2;

-- VERIFCATION SECTION

SELECT
    sch.schedule_id,
    c.subject,
    c.course_number,
    c.title,
    s.section_number,
    s.crn

FROM Schedule AS sch
JOIN ScheduleSection AS ss ON sch.schedule_id = ss.schedule_id
JOIN Section AS s ON ss.section_id = s.section_id
JOIN Course AS c ON s.course_id = c.course_id
WHERE sch.schedule_id = 'demo-schedule-001';
