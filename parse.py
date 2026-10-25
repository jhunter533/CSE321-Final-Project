# table format: row contains: CRN,Course, Campus,Days, Date, Time, Location, Hrs,Type,Title,Instructor,Seats,Limit,Enroll,Waitlist,Course Fees, Bookstore Link
# any cell can be empty so we need fall through for each
# if there is row next to another row without a break row (idk if thats a consistent measurement)
# if a row has no CRN it's content is part of the previous row with a CRN and must be kept together
#same thing but sometimes its just a second instructor, sometimes its recitation, sometimes its a second meeting time with a new location but no second instruction
# Type can be CLAS or RCT
# Course Name is SUBJ TAG number-section
# For some reason Labs are labeled as CLAS type but the Course Name is subj tag numberL-section
# Time is given as start-end (no colon just string), in 24h time using NM time zone
# Date is formated as mm/dd/yyyy-mm/dd/yyyy
# Days are M,T,W,R,F separated by spaces for when it occurs (any combination possible)
# An instructor is 1 per row but if more than 1 row than morethan 1 instructor, if the data cells before instructor have independent meeting time use instructor from that row if not combine them
# Title is the human readable name and there are duplicates and its inconsistently named
# each section has unique CRN, sections are identified by Course Name in the -section part
# if campus is M, its in person at location if given, if campus is DE its online location may or may not say WEB WEBV, may or may not have course name of subjecttag number-sectionD if DE.
# *Campus 	Description A 	Albuquerque DE 	Distance Education E 	DO NOT USE M 	Main O 	Off-campus SLF 	Sandia Labs Off Campus SLO 	Sandia Labs On Campus V 	Video Lectures-Live & Recorded
# if location is WEB-V WEBV WEB V etc or no time in independent row in general how do I display that?
# But then like for CSE 4089 means special topics so many different courses are listed under it as new sections (makes sense for transcript things to know) but titles are different and can take multiple so section restriction should not apply? cross reference course name to title?
# while many labs are required to be taken not all labs are inherently required so dont assume

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import requests
import urllib3
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
url="https://banweb7.nmt.edu/pls/PROD/hwzkcrof.P_UncgSrchCrsOff?p_term=202630&p_subj=PHYS"
html=requests.get(url,verify=False).text
COURSE_RE=re.compile(r"^([A-Z]+)\s+(\d+[A-Z]?)-(\S+)$")
DATE_RANGE_RE=re.compile(r"^(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})$")
TIME_RANGE_RE=re.compile(r"^(\d{4})-(\d{4})$")
TITLE_PREFIX_RE=re.compile(r"^[a-z]+\d*:")

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
    return int(v)

def parse_hours(v:str)->float|None:
    v=v.strip()
    if not v or v=="N/A":
        return None
    return float(v)

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
                credit_hours=parse_hours(r[col["Hrs"]]),
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

with open("physics_202630.html","w",encoding="utf-8") as f:
    f.write(html)
soup=BeautifulSoup(html,"html.parser")
print(soup.prettify())
table=None
for t in soup.find_all("table"):
    ths=[th.get_text(strip=True) for th in t.find_all("th")]
    if "CRN" in ths and "Course" in ths:
        table=t
        break
assert table is not None, "results table not found"

header_cells=table.find("tr").find_all("th")
headers=[th.get_text(strip=True) for th in header_cells]
col={name:i for i, name in enumerate(headers)}

print(len(headers),"headers")
print(len(col),"col")
print(col,"cols")
data_rows=[]
for tr in table.find_all("tr"):
    if tr.find("th"):
        continue
    cells=tr.find_all("td")
    texts=[td.get_text(strip=True) for td in cells]
    if not any(texts):
        continue
    data_rows.append(texts)
print(len(data_rows),"data_rows len")
sections=group_rows(data_rows,col)
print(len(sections),"section len")
print(sections)
