#!/usr/bin/env python3
"""Find more companies hiring in Israel and add them to data/companies.json.

Reads crawler/candidates.txt (one company per line, see the notes at its top). For every company that
isn't tracked yet it tries likely board names on Greenhouse, Lever, Ashby and SmartRecruiters, and the
Workday sites listed in the file, and keeps the board with the most jobs located in Israel. Companies
with at least one Israeli job are added; the rest are listed in data/discover-report.json so the file
can be corrected by hand (for example a different board name).

    python3 crawler/discover.py             # add what it finds
    python3 crawler/discover.py --dry-run   # only report

Runs from GitHub Actions ("Find more companies" workflow) because it needs to reach the job boards.
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crawl  # noqa: E402
from illoc import is_il  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
crawl.TIMEOUT = 12   # seconds; many small company websites are slow, and there are thousands to check
DATA = os.path.join(os.path.dirname(HERE), "data")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def read_candidates(path):
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        name = parts[0]
        large = len(parts) > 1 and parts[1].lower() == "large"
        hints, workday, site, boards = [], None, None, []
        for d in (parts[2].split(";") if len(parts) > 2 else []):
            d = d.strip()
            if not d:
                continue
            kind, _, val = d.partition(" ")
            kind, val = kind.lower(), val.strip()
            if kind == "workday":
                workday = val
            elif kind == "site":
                site = val
            elif kind in ("comeet", "greenhouse", "lever", "ashby", "smartrecruiters"):
                boards.append((kind, val))
            else:
                hints += [h.strip() for h in d.split(",") if h.strip()]
        out.append({"name": name, "large": large, "hints": hints, "workday": workday, "site": site, "boards": boards})
    return out


def slugs(c):
    base = re.sub(r"\s*\(.*?\)", "", c["name"]).lower()
    base = re.sub(r"\.(com|io|ai)$", "", base)
    joined = re.sub(r"[^a-z0-9]", "", base)
    dashed = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    out = c["hints"] + [joined, dashed, joined + "israel"]
    return [s for s in dict.fromkeys(out) if len(s) > 1]


def _get(url, body=None):
    try:
        return crawl.http_json(url, body=body, tries=1)
    except Exception:
        return None


def try_greenhouse(slug):
    d = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if not d or "jobs" not in d:
        return None
    il = sum(1 for j in d["jobs"] if is_il((j.get("location") or {}).get("name", "")))
    return {"platform": "greenhouse", "slug": slug}, il, f"https://job-boards.greenhouse.io/{slug}"


def try_lever(slug):
    d = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not isinstance(d, list):
        return None
    il = 0
    for j in d:
        c = j.get("categories") or {}
        locs = [c.get("location") or ""] + list(c.get("allLocations") or [])
        il += any(is_il(x) for x in locs)
    return {"platform": "lever", "slug": slug}, il, f"https://jobs.lever.co/{slug}"


def try_ashby(slug):
    d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if not d or "jobs" not in d:
        return None
    il = 0
    for j in d["jobs"]:
        locs = [j.get("location") or ""] + [(x or {}).get("location", "") for x in (j.get("secondaryLocations") or [])]
        il += any(is_il(x) for x in locs)
    return {"platform": "ashby", "slug": slug}, il, f"https://jobs.ashbyhq.com/{slug}"


def try_smartrecruiters(slug):
    d = _get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?country=il&limit=1")
    if not d or "totalFound" not in d:
        return None
    return {"platform": "smartrecruiters", "slug": slug}, d["totalFound"], f"https://jobs.smartrecruiters.com/{slug}"


def try_workday(spec):
    host, site = spec.split("/", 1)
    tenant = host.split(".")[0]
    il = 0
    ok = False
    for q in ("Israel", "Tel Aviv", "Haifa", "Yokneam", "Petah Tikva"):
        d = _get(f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
                 body={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q})
        if d is None:
            continue
        ok = True
        il = max(il, sum(1 for j in d.get("jobPostings", [])
                         if is_il(j.get("locationsText") or "") or is_il((j.get("externalPath") or "").replace("-", " "))))
    if not ok:
        return None
    return {"platform": "workday", "host": host, "tenant": tenant, "site": site}, il, f"https://{host}/en-US/{site}"


def try_comeet(slug, uid):
    try:
        jobs = crawl.comeet({"platform": "comeet", "slug": slug, "uid": uid})
    except Exception:
        return None
    il = sum(1 for j in jobs if is_il(j.get("location") or ""))
    return {"platform": "comeet", "slug": slug, "uid": uid}, il, f"https://www.comeet.com/jobs/{slug}/{uid}"


# Links to job boards the crawler can read, as they appear on companies' own careers pages.
_BOARD_LINKS = [
    (re.compile(r"(?:job-boards|boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)", re.I), lambda m: try_greenhouse(m.group(1).lower())),
    (re.compile(r"greenhouse\.io/embed/job_board(?:/js)?\?for=([a-z0-9_-]+)", re.I), lambda m: try_greenhouse(m.group(1).lower())),
    (re.compile(r"jobs\.lever\.co/([a-z0-9_.-]+)", re.I), lambda m: try_lever(m.group(1).lower())),
    (re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)", re.I), lambda m: try_ashby(m.group(1))),
    (re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)", re.I), lambda m: try_smartrecruiters(m.group(1))),
    (re.compile(r"([a-z0-9-]+\.wd\d+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)"), lambda m: try_workday(m.group(1) + "/" + m.group(2))),
    (re.compile(r"comeet\.(?:com|co)/jobs/([a-z0-9_.-]+)/([0-9A-F]{2}\.[0-9A-F]{3})", re.I), lambda m: try_comeet(m.group(1), m.group(2))),
]
_CAREER_PATHS = ["", "careers", "jobs", "career", "he/careers", "join-us", "%D7%93%D7%A8%D7%95%D7%A9%D7%99%D7%9D"]


def try_site(site):
    """Read a company's own home and careers pages and test every job-board link found there."""
    base = site if site.startswith("http") else "https://" + site.strip("/")
    pages = [base] if "/" in base.split("://", 1)[1] else [base.rstrip("/") + "/" + p for p in _CAREER_PATHS]
    seen, results = set(), []
    for url in pages:
        try:
            html = crawl.http_text(url, tries=1)
        except Exception:
            continue
        for rx, test in _BOARD_LINKS:
            for m in rx.finditer(html):
                key = m.group(0).lower()
                if key in seen or len(seen) > 20:
                    continue
                seen.add(key)
                r = test(m)
                if r:
                    results.append(r)
        if results:
            break
    return results


def try_board(kind, val):
    if kind == "comeet":
        slug, _, uid = val.partition("/")
        return try_comeet(slug, uid) if uid else None
    return {"greenhouse": try_greenhouse, "lever": try_lever, "ashby": try_ashby,
            "smartrecruiters": try_smartrecruiters}[kind](val)


def probe(c):
    """Best board for one company: (ats, israel_jobs, careers_url) or None."""
    if c.get("boards"):   # the board is already known: just check it
        found = [try_board(k, v) for k, v in c["boards"]]
        seen = [{"board": r[0], "israel_jobs": r[1]} for r in found if r]
        best = max((r for r in found if r and r[1]), key=lambda r: r[1], default=None)
        return best, seen
    tries = []
    if c["workday"]:
        tries.append(lambda: try_workday(c["workday"]))
    for s in slugs(c):
        tries += [lambda s=s: try_greenhouse(s), lambda s=s: try_lever(s), lambda s=s: try_ashby(s)]
    sr = c["hints"] + [re.sub(r"[^A-Za-z0-9]", "", c["name"])]
    tries += [lambda s=s: try_smartrecruiters(s) for s in dict.fromkeys(sr) if s]
    best, seen = None, []
    found = []
    if c.get("site"):
        found += try_site(c["site"])
    for t in tries:
        found.append(t())
    for r in found:
        if r:
            seen.append({"board": r[0], "israel_jobs": r[1]})
            if r[1] and (not best or r[1] > best[1]):
                best = r
    return best, seen


def board_key(ats):
    """Same board regardless of capitalisation (SmartRecruiters 'NielsenIQ' == 'nielseniq')."""
    return json.dumps({k: (str(v).lower() if k in ("slug", "host", "tenant", "site") else v)
                       for k, v in (ats or {}).items()}, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--limit", type=int, default=0, help="check at most this many new companies (0 = all)")
    a = ap.parse_args()
    path = os.path.join(DATA, "companies.json")
    companies = json.load(open(path))
    # Remove companies that point at a board already tracked under another name.
    kept, have_boards, dupes = [], set(), []
    for c in companies:
        k = board_key(c.get("ats")) if c.get("ats") else None
        if k and k in have_boards:
            dupes.append(c["name"])
            continue
        if k:
            have_boards.add(k)
        kept.append(c)
    if dupes:
        print("removed duplicate boards:", ", ".join(dupes))
    companies = kept
    have = {norm(c["name"]) for c in companies}
    cands = read_candidates(os.path.join(HERE, "candidates.txt"))
    extra = os.path.join(HERE, "candidates_techmap.txt")     # see import_techmap.py
    if os.path.exists(extra):
        cands += read_candidates(extra)
    todo, queued = [], set()
    for c in cands:
        k = norm(c["name"])
        if k and k not in have and k not in queued:
            queued.add(k)
            todo.append(c)
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo)} candidate companies not tracked yet")
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(probe, todo))
    added, report = [], {"added": [], "no_israel_jobs": [], "no_board_found": []}
    for c, (best, seen) in zip(todo, results):
        if best:
            ats, n, careers = best
            if board_key(ats) in have_boards:
                continue        # already tracked under another name
            have_boards.add(board_key(ats))
            added.append({"name": c["name"], "careers": careers, "ats": ats, "size": "large" if c["large"] else "small"})
            report["added"].append({"name": c["name"], "board": ats, "israel_jobs": n})
            print(f"  + {c['name']:40s} {ats['platform']:16s} {n} jobs in Israel")
        elif seen:
            report["no_israel_jobs"].append({"name": c["name"], "boards": seen})
        else:
            report["no_board_found"].append(c["name"])
    print(f"added {len(added)}; {len(report['no_israel_jobs'])} boards without Israeli jobs; "
          f"{len(report['no_board_found'])} with no board found")
    json.dump(report, open(os.path.join(DATA, "discover-report.json"), "w"), indent=1, ensure_ascii=False)
    if (added or dupes) and not a.dry_run:
        companies = sorted(companies + added, key=lambda c: c["name"].lower())
        json.dump(companies, open(path, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
