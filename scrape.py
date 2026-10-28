from __future__ import annotations

import time
from pathlib import Path

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE="https://banweb7.nmt.edu/pls/PROD"
SEARCH_PAGE=f"{BASE}/hwzkcrof.p_uncgslctcrsoff"
RESULTS_PAGE=f"{BASE}/hwzkcrof.P_UncgSrchCrsOff"
CACHE_DIR=Path("cache")

def _session()->requests.Session:
    s=requests.Session()
    s.verify=False
    return s
def fetch_term_options(session:requests.Session|None=None)->list[tuple[str,str]]:
    sess=session or _session()
    soup=BeautifulSoup(sess.get(SEARCH_PAGE).text,"html.parser")
    sel=soup.find("select",{"name":"p_term"})
    assert sel is not None,"p_term select not found"
    out=[]
    for opt in sel.find_all("option"):
        value=(opt.get("value")or "").strip()
        if value:
            out.append((value,opt.get_text(strip=True)))
    return out
def fetch_subject_options(session:requests.Session|None=None)->list[str]:
    sess=session or _session()
    soup=BeautifulSoup(sess.get(SEARCH_PAGE).text,"html.parser")
    sel=soup.find("select",{"name":"p_subj"})
    assert sel is not None, "p_subj select not found"
    out = []
    for opt in sel.find_all("option"):
        value = (opt.get("value") or "").strip()
        if value and value.upper() != "ALL":
            out.append(value)
    return out
def fetch_subject_html(term: str,subject: str,session:requests.Session|None=None,*,use_cache:bool=True)->str:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file=CACHE_DIR/f"{term}_{subject}.html"
    if use_cache and cache_file.exists() and cache_file.stat().st_size>0:
        return cache_file.read_text(encoding="utf-8")
    sess=session or _session()
    url=f"{RESULTS_PAGE}?p_term={term}&p_subj={subject}"
    r=sess.get(url)
    r.raise_for_status()
    cache_file.write_text(r.text,encoding="utf-8")
    time.sleep(0.25)
    return r.text

def fetch_term(term:str,*,use_cache:bool=True)->dict[str,str]:
    subjects=fetch_subject_options()
    return {subj: fetch_subject_html(term,subj,use_cache=use_cache) for subj in subjects}

