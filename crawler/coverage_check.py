#!/usr/bin/env python3
"""Mark which jobs also appear on LinkedIn, Indeed or Glassdoor, so the site can show
the ones that are *missing* from those sites.

It asks a job-search source (the same one crawl.py uses, set by JOBSEARCH_PROVIDER: jsearch,
serpapi, or the free JobSpy library)
for each company's current listings, reads which sites each listing is published on,
and matches them to the company's own-board jobs by title (and city when available).

Each job in data/jobs.json gets:
    "coverage": {"checked": "2026-11-23", "linkedin": true, "indeed": false, "glassdoor": false}

Cost: one query per company per run (JSEARCH_PAGES pages each for JSearch).
By default only companies with at least one job that has never been checked are queried,
so after the first full pass a weekly run only costs queries for companies with new jobs.

    python3 crawler/coverage_check.py            # check new/unchecked jobs
    python3 crawler/coverage_check.py --all      # re-check everything
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crawl  # noqa: E402  (reuses http_json and the provider settings)

SITES = {"linkedin": "linkedin", "indeed": "indeed", "glassdoor": "glassdoor", "google": "google"}
# Which sites the last search really covered. None = all of them (paid APIs read Google for Jobs,
# which lists LinkedIn, Indeed and Glassdoor postings). With JobSpy a site can refuse a search
# (LinkedIn often blocks GitHub's servers); that site is then recorded as "not checked" (None),
# never as "not listed".
SEARCHED = None


def _searched_after(provider):
    global SEARCHED
    if provider == "jobspy":
        import jobspy_source
        SEARCHED = set(jobspy_source.LAST_SEARCHED)
    else:
        SEARCHED = None
STOP = set("senior sr junior jr lead principal staff associate i ii iii iv v the a an of and for to in at - , / ( )".split())


def norm_title(t):
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", (t or "").lower())
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return " ".join(w for w in t.split() if w not in STOP)


def similar(a, b):
    a, b = set(norm_title(a).split()), set(norm_title(b).split())
    if not a or not b:
        return False
    return len(a & b) / max(len(a), len(b)) >= 0.75


def listings_for(company):
    """Return [(title, city, set_of_sites)] for the company from the job-search API."""
    provider = (os.environ.get("JOBSEARCH_PROVIDER") or "").lower()
    key = (os.environ.get("JOBSEARCH_API_KEY") or "")
    out = []
    if provider == "jsearch":
        url = (os.environ.get("JOBSEARCH_URL") or "https://api.openwebninja.com/jsearch/search-v2")
        q = {"query": f'jobs at "{company}"', "page": 1, "num_pages": int((os.environ.get("JSEARCH_PAGES") or "3")),
             "country": (os.environ.get("JOBSEARCH_COUNTRY") or "il"), "date_posted": "all"}
        headers = {"x-api-key": key}
        if "rapidapi" in url:
            headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": urllib.parse.urlparse(url).netloc}
        d = crawl.http_json(url + "?" + urllib.parse.urlencode(q), headers=headers)
        rows = d.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("jobs") or []
        for j in rows:
            if not crawl._same_employer(company, j.get("employer_name")):
                continue
            pubs = {(j.get("job_publisher") or "").lower()}
            for o in j.get("apply_options") or []:
                pubs.add((o.get("publisher") or "").lower())
                pubs.add((o.get("apply_link") or "").lower())
            out.append((j.get("job_title"), (j.get("job_city") or "").lower(), pubs))
    elif provider == "serpapi":
        q = {"engine": "google_jobs", "q": f"{company} jobs", "gl": (os.environ.get("JOBSEARCH_COUNTRY") or "il"), "api_key": key}
        d = crawl.http_json("https://serpapi.com/search.json?" + urllib.parse.urlencode(q))
        for j in d.get("jobs_results", []):
            if not crawl._same_employer(company, j.get("company_name")):
                continue
            pubs = {(j.get("via") or "").lower()}
            for o in j.get("apply_options") or []:
                pubs.add((o.get("title") or "").lower())
                pubs.add((o.get("link") or "").lower())
            out.append((j.get("title"), (j.get("location") or "").lower(), pubs))
    elif provider == "jobspy":
        import jobspy_source
        for j in jobspy_source.listings(company, (os.environ.get("JOBSEARCH_COUNTRY") or "il")):
            if crawl._same_employer(company, j["company"]):
                out.append((j["title"], j["location"].lower(), {j["site"].lower(), j["url"].lower()}))
    return out


def listings_for_job(company, title):
    """Targeted search for one job: '<title> <company>'. Returns [(title, city, set_of_sites)]."""
    provider = (os.environ.get("JOBSEARCH_PROVIDER") or "").lower()
    key = (os.environ.get("JOBSEARCH_API_KEY") or "")
    country = (os.environ.get("JOBSEARCH_COUNTRY") or "il")
    out = []
    if provider == "jsearch":
        url = (os.environ.get("JOBSEARCH_URL") or "https://api.openwebninja.com/jsearch/search-v2")
        q = {"query": f"{title} at {company}", "page": 1, "num_pages": 1, "country": country, "date_posted": "all"}
        headers = {"x-api-key": key}
        if "rapidapi" in url:
            headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": urllib.parse.urlparse(url).netloc}
        d = crawl.http_json(url + "?" + urllib.parse.urlencode(q), headers=headers)
        rows = d.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("jobs") or []
        for j in rows:
            if crawl._same_employer(company, j.get("employer_name")):
                pubs = {"google", (j.get("job_publisher") or "").lower()}   # JSearch results are Google for Jobs listings
                for o in j.get("apply_options") or []:
                    pubs.add((o.get("publisher") or "").lower()); pubs.add((o.get("apply_link") or "").lower())
                out.append((j.get("job_title"), (j.get("job_city") or "").lower(), pubs))
    elif provider == "serpapi":
        q = {"engine": "google_jobs", "q": f"{title} {company}", "gl": country, "api_key": key}
        d = crawl.http_json("https://serpapi.com/search.json?" + urllib.parse.urlencode(q))
        for j in d.get("jobs_results", []):
            if crawl._same_employer(company, j.get("company_name")):
                pubs = {"google", (j.get("via") or "").lower()}
                for o in j.get("apply_options") or []:
                    pubs.add((o.get("title") or "").lower()); pubs.add((o.get("link") or "").lower())
                out.append((j.get("title"), (j.get("location") or "").lower(), pubs))
    elif provider == "jobspy":
        import jobspy_source
        for j in jobspy_source.listings_for_job(company, title, country):
            if crawl._same_employer(company, j["company"]):
                out.append((j["title"], j["location"].lower(), {j["site"].lower(), j["url"].lower()}))
    return out


def _mark(j, found, today, method):
    """Record where the job was found. Returns False (and changes nothing) if no site answered."""
    if SEARCHED is not None and not SEARCHED:
        return False
    hits = {s: (False if SEARCHED is None or s in SEARCHED else None) for s in SITES}
    for title, city, pubs in found:
        if similar(j["title"], title):
            blob = " ".join(pubs)
            for s, needle in SITES.items():
                if needle in blob:
                    hits[s] = True
    old = j.get("coverage") or {}
    for s_ in SITES:   # a site seen before stays "seen" even if it couldn't be searched this time
        if hits[s_] is None and old.get(s_):
            hits[s_] = True
    j["coverage"] = {"checked": today, "method": method, **hits}
    return True


def run(data_dir, only_new=True):
    if (os.environ.get("JOBSEARCH_PROVIDER") or "").lower() == "jobspy":
        import jobspy_source
        jobspy_source._count = 0   # the LinkedIn/Indeed check gets its own allowance of company searches
    path = os.path.join(data_dir, "jobs.json")
    jobs = json.load(open(path))
    today = dt.date.today().isoformat()
    checked = 0
    for name, c in jobs["companies"].items():
        own = [j for j in c["jobs"] if j.get("source") != "aggregator"]
        if not own or (only_new and all("coverage" in j for j in own)):
            continue
        try:
            found = listings_for(name)
            _searched_after((os.environ.get("JOBSEARCH_PROVIDER") or "").lower())
        except Exception as e:
            print(f"coverage: {name}: {e}")
            continue
        if SEARCHED is not None and not SEARCHED:
            print(f"coverage: {name}: every site refused the search; will retry next run")
            continue
        checked += 1
        for j in own:
            if only_new and "coverage" in j and j["coverage"].get("method") == "job":
                continue   # already confirmed by an individual search
            _mark(j, found, today, "company")
    json.dump(crawl.nan_safe(jobs), open(path, "w"), indent=0, ensure_ascii=False)
    print(f"coverage: checked {checked} companies")
    per_job(jobs, today)
    json.dump(crawl.nan_safe(jobs), open(path, "w"), indent=0, ensure_ascii=False)


def per_job(jobs, today):
    """Second pass: search for each job on its own ('<title> <company>') when the company-wide
    search didn't find it on LinkedIn/Indeed/Glassdoor. Company-wide searches only return a
    company's first few dozen listings, so large employers' jobs are often missed there.
    COVERAGE_PER_JOB=0 turns this off; COVERAGE_PER_JOB_MAX caps searches per run (default 200;
    unchecked jobs are picked up on later runs, newest first)."""
    if (os.environ.get("COVERAGE_PER_JOB") or "1") == "0":
        return
    default_cap = "100" if (os.environ.get("JOBSEARCH_PROVIDER") or "").lower() == "jobspy" else "200"
    cap = int((os.environ.get("COVERAGE_PER_JOB_MAX") or default_cap) or 0)
    todo = []
    for name, c in jobs["companies"].items():
        for j in c["jobs"]:
            cov = j.get("coverage") or {}
            if j.get("source") == "aggregator" or cov.get("method") == "job":
                continue
            if cov and (cov.get("linkedin") or cov.get("indeed") or cov.get("glassdoor")):
                continue   # already found elsewhere; nothing to confirm
            todo.append((j.get("first_seen", ""), name, j))
    todo.sort(key=lambda x: x[0], reverse=True)
    done = 0
    for _, name, j in todo[:cap or None]:
        try:
            found = listings_for_job(name, j["title"])
            _searched_after((os.environ.get("JOBSEARCH_PROVIDER") or "").lower())
        except Exception as e:
            print(f"coverage (per job): {name} / {j['title']}: {e}")
            continue
        if _mark(j, found, today, "job"):
            done += 1
    print(f"coverage: searched {done} jobs individually ({max(len(todo) - done, 0)} left for later runs)")
    if (os.environ.get("JOBSEARCH_PROVIDER") or "").lower() == "jobspy":
        import jobspy_source
        for site, n in sorted(jobspy_source.BLOCKED.items()):
            print(f"coverage: {site} refused {n} searches this run (recorded as 'not checked', not as 'not listed')")


if __name__ == "__main__":
    run(crawl.DATA, only_new="--all" not in sys.argv)
