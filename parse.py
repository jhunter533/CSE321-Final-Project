from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Course:
    subject: str
    course_number: str
    title: str
    @property
    def key(self)->tuple[str,str]:
        return (self.subject,self.course_number)

@dataclass(frozen=True)
class Instructor:
    name: str
    @property
    def key(self)->str:
        return " ".join(self.name.split())

@dataclass
class Meeting:
    days: str
    start_date: date | None
    end_date: date | None
    start_time: int | None
    end_time: int | None
    time_raw:str
    location: str
    meeting_type: str
    instructors: list[Instructor]=field(default_factory=list)

@dataclass
class Section:
    crn: str
    course: Course
    section_number: str
    campus: str
    credit_hours: int | None
    title_raw: str
    seats: int | None
    limit: int | None
    enroll: int | None
    waitlist: int | None
    fee_raw: str
    bookstore: str
    meetings: list[Meeting]=field(default_factory=list)

@dataclass
class Requirement:
    code: str
    name: str
    description: str

COURSE_RE=re.compile(r"^([A-Z]+)\s+(\d+[A-Z]?)-(\S+)$")
DATE_RANGE_RE=re.compile(r"^(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})$")
TIME_RANGE_RE=re.compile(r"^(\d{4})-(\d{4})$")
TITLE_PREFIX_RE=re.compile(r"^[a-z]+\d*:")

def find_results_table(soup:BeautifulSoup):
    for t in soup.find_all("table"):
        ths=[th.get_text(strip=True) for th in t.find_all("th")]
        if "CRN" in ths and "Course" in ths:
            return t 
    return None

def extract_rows(html: str)->tuple[dict[str,int],list[list[str]]]:
    soup=BeautifulSoup(html,"html.parser")
    table=find_results_table(soup)
    if table is None:
        return {},[]
    header_row=table.find(lambda tr:tr.find("th") is not None)
    headers=[th.get_text(strip=True) for th in header_row.find_all("th")]
    col={name:i for i,name in enumerate(headers)}
    rows: list[list[str]]=[]
    
    for tr in table.find_all("tr"):
        if tr.find("th"):
            continue
        texts=[td.get_text(strip=True) for td in tr.find_all("td")]
        if any(texts):
            rows.append(texts)
    return col,rows



def split_course(course_str: str)->tuple[str,str,str]:
    m=COURSE_RE.match(course_str.strip())
    if not m:
        raise ValueError(f"bad course string: {course_str!r}")
    return m.group(1),m.group(2),m.group(3)

def is_blank(v):
    return v is None or v==""

def strip_title_prefix(title:str)->str:
    return TITLE_PREFIX_RE.sub("",title.strip()).strip()

def parse_int(v:str)->int|None:
    v=v.strip()
    if not v or v=="N/A":
        return None
    try:
        return int(v)
    except ValueError:
        return None

def parse_date_range(v: str) -> tuple[date | None, date | None]:
    v = v.strip()
    m = DATE_RANGE_RE.match(v)
    if not m:
        return None, None
    fmt = "%m/%d/%Y"
    return datetime.strptime(m.group(1), fmt).date(), datetime.strptime(m.group(2), fmt).date()


def parse_time_range(v: str) -> tuple[int | None, int | None]:
    v = v.strip()
    m = TIME_RANGE_RE.match(v)
    if not m:
        return None, None
    hhmm = lambda s: int(s[:2]) * 60 + int(s[2:])
    return hhmm(m.group(1)), hhmm(m.group(2))

def group_rows(data_rows,col):
    sections:list[Section]=[]
    course_cache:dict[tuple[str,str],Course]={}
    curr: Section | None=None

    def get_course(course_str: str, title_raw: str) -> Course:
        subject, number, _ = split_course(course_str)
        key = (subject, number)
        if key not in course_cache:
            course_cache[key] = Course(
                subject=subject,
                course_number=number,
                title=strip_title_prefix(title_raw),
            )
        return course_cache[key]
    def make_meeting(r)->Meeting:
        days_raw=r[col["Days"]]
        time_raw=r[col["Time"]]
        sd,ed=parse_date_range(r[col["Date"]])
        st,en=parse_time_range(time_raw)
        instr=r[col["Instructor"]]
        return Meeting(days=days_raw,
                       start_date=sd,
                       end_date=ed,
                       start_time=st,
                       end_time=en,
                       time_raw=time_raw,
                       location=r[col["Location"]],
                       meeting_type=r[col["Type"]],
                       instructors=[Instructor(instr)] if not is_blank(instr) else [],
                       )
    for r in data_rows:
        crn=r[col["CRN"]]
        instructor=r[col["Instructor"]]
        has_meeting=any(not is_blank(r[col[k]]) for k in ("Days","Time","Location","Type"))
        if not is_blank(crn):
            course=get_course(r[col["Course"]],r[col["Title"]])
            _,_,section_number=split_course(r[col["Course"]])
            curr = Section(
                crn=crn,
                course=course,
                section_number=section_number,
                campus=r[col["*Campus"]],
                credit_hours=parse_int(r[col["Hrs"]]),
                title_raw=r[col["Title"]],
                seats=parse_int(r[col["Seats"]]),
                limit=parse_int(r[col["Limit"]]),
                enroll=parse_int(r[col["Enroll"]]),
                waitlist=parse_int(r[col["Waitlist"]]),
                fee_raw=(r[col["Course Fees"]]),
                bookstore=r[col["Bookstore Link"]],
                meetings=[make_meeting(r)]
            )
            sections.append(curr)
        elif curr is None:
            continue
        elif has_meeting:
            curr.meetings.append(make_meeting(r))
        elif not is_blank(instructor):
            curr.meetings[-1].instructors.append(Instructor(instructor))
    return sections
def parse_subject_html(html:str)->list[Section]:
    col,rows=extract_rows(html)
    if not col:
        return []
    return group_rows(rows,col)

def validate(sections: list[Section]) -> None:
    seen = set()
    for s in sections:
        assert re.fullmatch(r"\d+", s.crn), f"bad CRN {s.crn!r}"
        assert s.crn not in seen, f"duplicate CRN {s.crn}"
        seen.add(s.crn)
        assert s.meetings, f"{s.crn} has no meetings"
        for m in s.meetings:
            if m.start_time is not None and m.end_time is not None:
                assert m.end_time > m.start_time, f"{s.crn} bad time {m.time_raw}"

#NOTE TO FUTURE SELF: UI SHOULD DISPLAY SECTION.TITLE maybe as 4089 have several courses under one number

