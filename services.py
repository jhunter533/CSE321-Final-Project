from __future__ import annotations

import database

DAY_CODES={
        "Monday":"M",
        "Tuesday":"T",
        "Wednesday":"W",
        "Thursday":"R",
        "Friday":"F",
        "Saturday":"S",
        "Sunday":"U",
}
def _meeting_days(days:str)->set[str]:
    if not days:
        return set()
    valid=set(DAY_CODES.values())
    return {ch for ch in days.upper() if ch in valid}

def _subjects_for_requirements(conn,requirement_code:str)->list[str]:
    requirement_code=requirement_code.strip().upper()
    subjects={
        row[0]
        for row in conn.execute(
            """
            SELECT rs.subject FROM RequirementSubject AS rs
            JOIN Requirement AS r ON rs.requirement_id=r.requirement_id
            WHERE r.code=?
            """,
            (requirement_code,),
        ).fetchall()
    }
    children=conn.execute(
        """
        SELECT child.code
        FROM RequirementIncludes AS ri
        JOIN Requirement AS parent ON ri.parent_requirement_id=parent.requirement_id
        JOIN Requirement AS child ON ri.child_requirement_id=child.requirement_id
        WHERE parent.code=?
        """,
        (requirement_code,),
    ).fetchall()
    for (child_code,) in children:
        subjects.update(_subjects_for_requirements(conn,child_code))
    return sorted(subjects)
def search_courses(conn,requirement_or_subject: str,term:str|None=None)->dict:
    value=requirement_or_subject.strip().upper()
    if not value:
        return {
                "success":False,
                "error":"Requirement or subject is required",
        }
    if term is None:
        row=conn.execute(
            """
            SELECT MAX(term)
            FROM Section
            """
        ).fetchone()
        if row is None or row[0] is None:
            return{
                    "success":False,
                    "error":"No semster data exists",
            }
        term=row[0]
    if value.startswith("AREA"):
        subjects=_subjects_for_requirements(conn,value)
        if not subjects:
            return{
                    "success":False,
                    "error":f"Unknown requirement {value}",
            }
    else:
        subjects=[value]
    placeholder=",".join("?" for _ in subjects)
    rows=conn.execute(
        f"""
        SELECT
            c.course_id,
            c.subject,
            c.course_number,
            c.title,
            s.section_id,
            s.crn,
            s.section_number,
            s.credit_hours,
            s.term
        FROM Course AS c
        JOIN Section AS s ON c.course_id=s.course_id
        WHERE c.subject IN ({placeholder}) AND s.term=?
        ORDER BY
            c.subject,
            c.course_number,
            s.section_number
        """,
        (*subjects,term),
    ).fetchall()
    sections=[]
    for row in rows:
        section_id=row[4]
        meeting_rows=conn.execute(
            """
            SELECT
                days,
                start_time,
                end_time,
                location,
                meeting_type
            FROM Meeting
            WHERE section_id=?
            ORDER BY meeting_id
            """,
            (section_id,),
        ).fetchall()
        meetings=[
            {
                "days":meeting[0],
                "start_time":meeting[1],
                "end_time":meeting[2],
                "location":meeting[3],
                "meeting_type":meeting[4],
            }
            for meeting in meeting_rows
        ]
        sections.append(
            {
                "course_id":row[0],
                "subject":row[1],
                "course_number":row[2],
                "title":row[3],
                "section_id":row[4],
                "crn":row[5],
                "section_number":row[6],
                "credit_hours":row[7],
                "term":row[8],
                "meetings":meetings,
            }
        )
    return {
            "success":True,
            "filter":value,
            "term":term,
            "sections":sections,
    }
def check_conflicts(conn,schedule_id,section_id,avoid_day)->dict:
    candidate=conn.execute(
        """
        SELECT
            s.section_id,
            c.subject,
            c.course_number,
            s.section_number
        FROM Section AS s
        JOIN Course AS c ON s.course_id=c.course_id
        WHERE s.section_id=?
        """,
        (section_id,),
    ).fetchone()
    if candidate is None:
        return {
                "success":False,
                "error":"Section does not exist",
        }
    candidate_name=(
            f"{candidate[1]} "
            f"{candidate[2]}-"
            f"{candidate[3]}"
    )
    candidate_meetings=conn.execute(
        """
        SELECT
            days,
            start_time,
            end_time
        FROM Meeting
        WHERE section_id=?
        """,
        (section_id,),
    ).fetchall()
    reasons=[]
    if avoid_day:
        avoid_code=DAY_CODES.get(avoid_day,avoid_day.upper())
        for days, start ,end in candidate_meetings:
            if avoid_code in _meeting_days(days):
                reasons.append(
                    f"{candidate_name} meets on "
                    f"{avoid_day}"
                )
                break
    existing_meetings=conn.execute(
        """
        SELECT
            s.section_id,
            c.subject,
            c.course_number,
            s.section_number,
            m.days,
            m.start_time,
            m.end_time
        FROM ScheduleSection AS ss
        JOIN Section AS s ON ss.section_id=s.section_id
        JOIN Course AS c ON s.course_id=c.course_id
        JOIN Meeting AS m ON s.section_id=m.section_id
        WHERE ss.schedule_id=? AND s.section_id!=?
        """,
        (
            schedule_id,
            section_id,
        ),
    ).fetchall()
    for (candidate_days,candidate_start,candidate_end) in candidate_meetings:
        candidate_day_set=_meeting_days(candidate_days)
        if (candidate_start is None or candidate_end is None):
            continue
        for existing in existing_meetings:
            existing_section_id=existing[0]
            existing_subject=existing[1]
            existing_number=existing[2]
            existing_section=existing[3]
            existing_days=existing[4]
            existing_start=existing[5]
            existing_end=existing[6]
            if (existing_start is None or existing_end is None):
                continue
            existing_day_set=_meeting_days(existing_days)
            same_day=bool(candidate_day_set&existing_day_set)
            time_overlap=(candidate_start<existing_end and existing_start<candidate_end)
            if same_day and time_overlap:
                existing_name=(
                    f"{existing_subject} "
                    f"{existing_number}-"
                    f"{existing_section}"
                )
                reason=(
                    f"{candidate_name} conflicts "
                    f"with {existing_name}"
                )
                if reason not in reasons:
                    reasons.append(reason)
    return {
            "success":True,
            "section_id":section_id,
            "conflict":bool(reasons),
            "reasons":reasons,
    }
def add_to_schedule(conn,schedule_id:str,section_id:int)->dict:
    schedule=conn.execute(
        """
        SELECT schedule_id
        FROM Schedule
        WHERE schedule_id=?
        """,
        (schedule_id,),
    ).fetchone()
    if schedule is None:
        return {
                "success":False,
                "error":"Schedule does not exist",
        }
    return database.add_section_to_schedule(conn,schedule_id,section_id)
