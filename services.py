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

def _get_meetings(conn,section_id:int)->list[dict]:
    rows=conn.execute(
        """
        SELECT meeting_id,days,start_time,end_time, location, meeting_type FROM Meeting
        WHERE section_id=?
        ORDER BY meeting_id
        """,
        (section_id,),
    ).fetchall()
    meetings = []
    for row in rows:
        meeting_id = row[0]
        instructor_rows = conn.execute(
            """
            SELECT i.name
            FROM MeetingInstructor AS mi
            JOIN Instructor AS i
                ON mi.instructor_id =
                   i.instructor_id
            WHERE mi.meeting_id = ?
            ORDER BY i.name
            """,
            (meeting_id,),
        ).fetchall()
        instructors = [
            instructor[0]
            for instructor in instructor_rows
        ]
        meetings.append(
            {
                "meeting_id": meeting_id,
                "days":row[1],
                "start_time":row[2],
                "end_time":row[3],
                "location":row[4],
                "meeting_type":row[5],
                "instructors":instructors,
            }
        )
    return meetings

def _section_dict(conn,row)->dict:
    section_id=row[4]
    return {
            "course_id":row[0],
            "subject":row[1],
            "course_number":row[2],
            "title":row[3],
            "section_id":section_id,
            "crn":row[5],
            "section_number":row[6],
            "credit_hours":row[7],
            "term":row[8],
            "meetings":_get_meetings(conn,section_id)
    }

def search_courses(conn,requirement_or_subject: str,term:str|None=None)->dict:
    value=requirement_or_subject.strip().upper().replace("AREA ","AREA")

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
    sections=[_section_dict(conn,row) for row in rows]
    return {
        "success":True,
        "filter":value,
        "term":term,
        "sections":sections,
    }

def get_sections(conn,course_id:int,term:str|None=None)->dict:
    if not isinstance(course_id,int) or course_id<=0:
        return {
                "success":False,
                "error":"course_id must be positive integer"
        }
    if term is None:
        row=conn.execute(
            """
            SELECT MAX(term)
            FROM Section
            """
        ).fetchone()
        if row is None or row[0] is None:
            return {
                    "success":False,
                    "error":"No semester data exits"
            }
        term=row[0]
    rows=conn.execute(
        """
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
        JOIN Section AS s
            ON c.course_id = s.course_id
        WHERE
            c.course_id = ?
            AND s.term = ?
        ORDER BY s.section_number
        """,
        (course_id,term),
    ).fetchall()
    if not rows:
        return{
                "success":False,
                "error":"Course or sections do not exist"
        }
    return {
            "success":True,
            "course_id":course_id,
            "term":term,
            "section":[_section_dict(conn,row) for row in rows],
    }

def check_conflicts(conn,schedule_id:str,section_id:int,avoid_day:str|None=None)->dict:
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

def get_schedule(conn,schedule_id:str)->dict:
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
                "error":"Schedule does not exist"
        }
    sections=database.get_schedule(conn,schedule_id)
    for section in sections:
        section["meetings"]=(_get_meetings(conn,section["section_id"]))
    return {
            "success":True,
            "schedule_id":schedule_id,
            "sections":sections
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

def remove_from_schedule(conn,schedule_id:str,section_id:int)->dict:
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
                "error":"schedule does not exist"
        }
    return (database.remove_section_from_schedule(conn,schedule_id,section_id))
