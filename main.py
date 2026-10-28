from __future__ import annotations

import argparse
from collections import Counter
from datetime import date

import parse
import scrape


def current_term(today: date|None=None)->str:
    d=today or date.today()
    y,m=d.year,d.month
    if 1<=m<=5:
        return f"{y}30"
    if 6<=m<=7:
        return f"{y+1}10"
    return f"{y+1}20"
def resolve_term(arg:str|None)->str:
    if arg:
        return arg
    candidate=current_term()
    options=dict(scrape.fetch_term_options())
    if candidate in options:
        print(f"Using current term {candidate} ({options[candidate]})")
        return candidate
    for code,label in sorted(options.items()):
        if code>=candidate:
            print(f"Term {candidate} not offered; using {code} ({label})")
            return code
    raise SystemExit(f"No term >= {candidate} available")
def parse_term(term: str)->list[parse.Section]:
    html_by_subject=scrape.fetch_term(term)
    all_sections:list[parse.Section]=[]
    for subject,html in html_by_subject.items():
        sections=parse.parse_subject_html(html)
        print(f"{subject:6} {len(sections):4} sections")
        all_sections.extend(sections)
    return all_sections
def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--term", help="p_term code, e.g. 202630")
    ap.add_argument("--subject", help="single subject for a quick test, e.g. PHYS")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    if args.subject:
        term = resolve_term(args.term)
        html = scrape.fetch_subject_html(term, args.subject, use_cache=not args.no_cache)
        sections = parse.parse_subject_html(html)
        parse.validate(sections)
        print(f"{len(sections)} sections in {args.subject} {term}")
        for s in sections[:5]:
            print(" ", s.crn, s.course.subject, s.course.course_number,
                  s.section_number, s.title_raw)
        return

    term = resolve_term(args.term)
    print(f"Parsing term {term}")
    sections = parse_term(term)
    parse.validate(sections)
    print(f"\nTotal: {len(sections)} sections")
    print("By subject:", Counter(s.course.subject for s in sections).most_common(5))
    print("By campus:", Counter(s.campus for s in sections).most_common())
if __name__=="__main__":
    main()
