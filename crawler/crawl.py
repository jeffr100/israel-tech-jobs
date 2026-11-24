#!/usr/bin/env python3
"""Daily crawler for computer science and high-tech jobs in Israel (software, data & AI, security, chips,
hardware, engineering, medtech and more).

Standard library only (Python 3.8+), so it runs on macOS's system python3,
on GitHub Actions, or anywhere else without installing packages.

    python3 crawler/crawl.py                # crawl every company, update data/
    python3 crawler/crawl.py --only Natera  # crawl one company (name substring)

Inputs : data/companies.json  (company list + where its jobs live)
Outputs: data/jobs.json        (current jobs + first-seen dates, read by index.html)
         data/changes.json     (what was added/removed in each run, newest first)

Supported job boards (public JSON endpoints, no login, no scraping of HTML):
  greenhouse, lever, ashby, smartrecruiters, workday, comeet
Only jobs located in Israel are kept (IL_ONLY=0 keeps every country). Each is labelled as a technology type (cs.py) or a general type (jobtypes.py); the tech
site shows only the technology jobs, the "All jobs in Israel" page shows everything.
Companies with any other board keep a "careers" link and are listed without jobs.

Optional: jobs posted on Indeed, LinkedIn and Google Jobs, through a licensed
job-search API (no scraping of those sites). Off unless these are set:
  JOBSEARCH_PROVIDER = jsearch   (OpenWeb Ninja JSearch, Google-for-Jobs data)
                     | serpapi   (SerpApi Google Jobs API)
                     | jobspy    (free JobSpy library: reads LinkedIn/Indeed directly, no key; see jobspy_source.py)
  JOBSEARCH_API_KEY  = your key
  JOBSEARCH_SCOPE    = untracked (default: only companies without a supported board)
                     | all       (every company; costs one query per company per run)
  JOBSEARCH_COUNTRY  = il        (default; two-letter country code)
Those jobs are stored with "source": "aggregator" and "via": "LinkedIn" etc.
"""
import argparse
import datetime as dt
import json
import os
import re
import urllib.parse
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from illoc import is_il, region  # noqa: E402
import cs  # noqa: E402
import jobtypes  # noqa: E402

IL_ONLY = (os.environ.get("IL_ONLY") or "1") != "0"   # set IL_ONLY=0 to keep jobs in every country
CS_ONLY = (os.environ.get("CS_ONLY") or "0") == "1"   # CS_ONLY=1 drops non-technology jobs entirely
US_ONLY = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UA = "Mozilla/5.0 (israel-tech-jobs-crawler; weekly; contact: repo owner)"
TIMEOUT = 30
MAX_JOBS_PER_COMPANY = 3000  # safety cap for very large employers


def http_json(url, body=None, headers=None, tries=3):
    data = None
    h = {"User-Agent": UA, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    if headers:
        h.update(headers)
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise
            last = e
        except Exception as e:  # network hiccup: back off and retry
            last = e
        time.sleep(2 * (attempt + 1))
    raise last


def http_text(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise
            last = e
        except Exception as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise last


def nan_safe(o):
    """Replace NaN/inf (which json.dump writes but browsers can't read) with empty values."""
    if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))):
        return ""
    if isinstance(o, dict):
        return {k: nan_safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [nan_safe(v) for v in o]
    return o


def job(title, location, dept, url, posted, source="board", via=""):
    d = {
        "title": (title or "").strip(),
        "location": (location or "").strip() if isinstance(location, str) else ", ".join(filter(None, location or [])),
        "department": (dept or "").strip() if isinstance(dept, str) else "",
        "url": url or "",
        "posted": (posted or "")[:10],
    }
    if source != "board":
        d["source"] = source
        d["via"] = via
    return d


# ---------- board adapters ----------

def greenhouse(ats):
    d = http_json(f"https://boards-api.greenhouse.io/v1/boards/{ats['slug']}/jobs?content=true")
    out = []
    for j in d.get("jobs", []):
        dept = ", ".join(x.get("name", "") for x in (j.get("departments") or []))
        out.append(job(j.get("title"), (j.get("location") or {}).get("name"), dept,
                       j.get("absolute_url"), j.get("first_published") or j.get("updated_at")))
    return out


def lever(ats):
    host = ats.get("host", "api.lever.co")
    d = http_json(f"https://{host}/v0/postings/{ats['slug']}?mode=json")
    out = []
    for j in d:
        c = j.get("categories") or {}
        posted = ""
        if j.get("createdAt"):
            posted = dt.datetime.fromtimestamp(j["createdAt"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
        out.append(job(j.get("text"), c.get("location"), c.get("team") or c.get("department"),
                       j.get("hostedUrl"), posted))
    return out


def ashby(ats):
    d = http_json(f"https://api.ashbyhq.com/posting-api/job-board/{ats['slug']}")
    out = []
    for j in d.get("jobs", []):
        loc = j.get("location") or ""
        if IL_ONLY and not is_il(loc):   # Israel may be one of the job's other locations
            loc = next((x.get("location") for x in (j.get("secondaryLocations") or [])
                        if is_il((x or {}).get("location", ""))), loc)
        out.append(job(j.get("title"), loc, j.get("department") or j.get("team"), j.get("jobUrl"), j.get("publishedAt")))
    return out


def smartrecruiters(ats):
    slug, out, off = ats["slug"], [], 0
    while True:
        country = "&country=il" if IL_ONLY else ""
        d = http_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={off}{country}")
        for j in d.get("content", []):
            loc = j.get("location") or {}
            out.append(job(j.get("name"), ", ".join(filter(None, [loc.get("city"), loc.get("region"), loc.get("country", "").upper()])),
                           (j.get("department") or {}).get("label"),
                           f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}", j.get("releasedDate")))
        off += 100
        if off >= d.get("totalFound", 0) or off >= MAX_JOBS_PER_COMPANY:
            return out


def workday(ats):
    # ats: {"host": "illumina.wd1.myworkdayjobs.com", "tenant": "illumina", "site": "illumina-careers"}
    base = f"https://{ats['host']}"
    api = f"{base}/wday/cxs/{ats['tenant']}/{ats['site']}/jobs"
    out, off, total = [], 0, None
    # Workday has no reliable country filter across tenants, so search for Israeli place names.
    searches = ats.get("search") or (WORKDAY_IL_SEARCHES if IL_ONLY else [""])
    if isinstance(searches, str):
        searches = [searches]
    seen = set()
    for q in searches:
        off, total = 0, None
        while True:
            d = http_json(api, body={"appliedFacets": {}, "limit": 20, "offset": off, "searchText": q})
            if total is None:
                total = d.get("total", 0)
            posts = d.get("jobPostings", [])
            for j in posts:
                if not (j.get("title") or "").strip():
                    continue   # Workday sometimes returns empty placeholder rows
                path = j.get("externalPath", "")
                if path in seen:
                    continue
                seen.add(path)
                loc = j.get("locationsText") or ""
                if loc.endswith("Locations") and IL_ONLY:
                    loc = path.split("/")[2].replace("-", " ") if path.count("/") >= 2 else loc  # first location is in the path
                out.append(job(j.get("title"), loc, "", f"{base}/en-US/{ats['site']}{path}", workday_date(j.get("postedOn", ""))))
            off += 20
            if not posts or off >= total or off >= MAX_JOBS_PER_COMPANY:
                break
            time.sleep(0.3)
    return out


WORKDAY_IL_SEARCHES = ["Israel", "Tel Aviv", "Haifa", "Jerusalem", "Petah Tikva", "Herzliya",
                       "Yokneam", "Raanana", "Kiryat Gat", "Netanya", "Rehovot", "Yavne", "Migdal Haemek"]


def _grab_js(html, key):
    """Pull a JSON value assigned in the page, e.g. COMPANY_POSITIONS_DATA = [...];"""
    i = html.find(key + " = ")
    if i < 0:
        return None
    j = html.index("=", i) + 1
    while html[j] == " ":
        j += 1
    start, depth, ins, esc = j, 0, False, False
    for j in range(start, len(html)):
        c = html[j]
        if ins:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                ins = False
            continue
        if c == '"':
            ins = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                break
    try:
        return json.loads(html[start:j + 1])
    except ValueError:
        return None


def comeet(ats):
    # ats: {"platform": "comeet", "slug": "upwind", "uid": "49.004"}
    page = f"https://www.comeet.com/jobs/{ats['slug']}/{ats['uid']}"
    html = http_text(page)
    out = []
    for p in _grab_js(html, "COMPANY_POSITIONS_DATA") or []:
        loc = p.get("location") or {}
        where = loc.get("city") or loc.get("name") or ""
        if loc.get("country") == "IL" and "israel" not in where.lower():
            where = (where + ", Israel").strip(", ")
        url = p.get("urlActivePage") or p.get("urlComeetHostedPage")
        if not url and p.get("uid"):
            title_slug = re.sub(r"[^a-z0-9]+", "-", (p.get("name") or "job").lower()).strip("-") or "job"
            url = f"{page}/{title_slug}/{p['uid']}"
        out.append(job(p.get("name"), where, p.get("department") or "",
                       url or page + "#" + urllib.parse.quote(p.get("name") or ""), p.get("timeUpdated") or ""))
    return out


def workday_date(text):
    """Turn Workday's 'Posted 3 Days Ago' into a date (blank for '30+ Days Ago')."""
    import re
    today = dt.date.today()
    if "Today" in text:
        return today.isoformat()
    if "Yesterday" in text:
        return (today - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)(\+?) Days? Ago", text)
    if m and not m.group(2):
        return (today - dt.timedelta(days=int(m.group(1)))).isoformat()
    return ""


# ---------- optional: Indeed / LinkedIn / Google Jobs via a licensed API ----------

def _norm(s):
    import re
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _same_employer(company, employer):
    import re
    strip = lambda x: re.sub(r"\b(inc|llc|ltd|corp|corporation|co|company|plc|gmbh|ag|sa|the|laboratories|laboratory|labs|holdings|group|usa|international)\b", "", (x or "").lower())
    a, b = _norm(strip(company)), _norm(strip(employer))
    if not a or not b:
        return False
    if a == b:
        return True
    # "10x Genomics" vs "10x Genomics Inc" is the same employer, but "AccuGenomics" vs "Genomics"
    # or "Abbott Molecular" vs "Abbott" is not: one name may only add a short suffix to the other.
    short, long_ = sorted((a, b), key=len)
    return long_.startswith(short) and len(short) >= 5 and len(short) >= 0.75 * len(long_)


def jobsearch(company):
    provider = (os.environ.get("JOBSEARCH_PROVIDER") or "").lower()
    key = (os.environ.get("JOBSEARCH_API_KEY") or "")
    country = (os.environ.get("JOBSEARCH_COUNTRY") or "")
    if not provider or (not key and provider != "jobspy"):
        return None
    import urllib.parse
    out = []
    if provider == "jsearch":
        url = (os.environ.get("JOBSEARCH_URL") or "https://api.openwebninja.com/jsearch/search-v2")
        q = {"query": f'jobs at "{company}"', "page": 1, "num_pages": 1, "date_posted": "month"}
        q["country"] = country or ("il" if IL_ONLY else "")
        if not q["country"]:
            q.pop("country")
        headers = {"x-api-key": key}
        if "rapidapi" in url:
            headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": urllib.parse.urlparse(url).netloc}
        d = http_json(url + "?" + urllib.parse.urlencode(q), headers=headers)
        rows = d.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("jobs") or []
        for j in rows:
            if not _same_employer(company, j.get("employer_name")):
                continue
            loc = ", ".join(filter(None, [j.get("job_city"), j.get("job_state"), j.get("job_country")]))
            if j.get("job_is_remote"):
                loc = (loc + " (Remote)").strip()
            out.append(job(j.get("job_title"), loc, "", j.get("job_apply_link"),
                           j.get("job_posted_at_datetime_utc"), "aggregator", j.get("job_publisher") or "Google Jobs"))
            out[-1]["employer"] = j.get("employer_name") or ""
    elif provider == "jobspy":
        import jobspy_source
        names = {"linkedin": "LinkedIn", "indeed": "Indeed", "glassdoor": "Glassdoor", "google": "Google Jobs"}
        for j in jobspy_source.listings(company, country or "il"):
            if _same_employer(company, j["company"]):
                out.append(job(j["title"], j["location"], "", j["url"], "", "aggregator", names.get(j["site"], j["site"])))
                out[-1]["employer"] = j["company"]
    elif provider == "serpapi":
        q = {"engine": "google_jobs", "q": f"{company} jobs", "api_key": key}
        if country or IL_ONLY:
            q["gl"] = country or "il"
        d = http_json("https://serpapi.com/search.json?" + urllib.parse.urlencode(q))
        for j in d.get("jobs_results", []):
            if not _same_employer(company, j.get("company_name")):
                continue
            opts = j.get("apply_options") or []
            link = opts[0].get("link") if opts else j.get("share_link", "")
            via = (j.get("via") or "Google Jobs").replace("via ", "")
            out.append(job(j.get("title"), j.get("location"), "", link, "", "aggregator", via))
            out[-1]["employer"] = j.get("company_name") or ""
    return out


SEARCH_ALLOWED = None   # with JobSpy: the companies allowed a LinkedIn/Indeed search this run


def merge_aggregator(c, board_jobs):
    """Add aggregator jobs that aren't already on the company's own board."""
    scope = (os.environ.get("JOBSEARCH_SCOPE") or "untracked")
    if scope != "all" and board_jobs is not None:
        return board_jobs, None
    if SEARCH_ALLOWED is not None and c["name"] not in SEARCH_ALLOWED:
        return board_jobs, None   # its turn comes on a later run
    try:
        extra = jobsearch(c["name"])
    except Exception as e:
        return board_jobs, f"job search: {type(e).__name__}: {e}"[:200]
    if extra is None:
        return board_jobs, None
    have = {_norm(j["title"]) for j in (board_jobs or [])}
    merged = list(board_jobs or [])
    for j in extra:
        if _norm(j["title"]) not in have:
            have.add(_norm(j["title"]))
            merged.append(j)
    return merged, None


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby,
            "smartrecruiters": smartrecruiters, "workday": workday, "comeet": comeet}


def keep(jobs):
    """Keep Israeli jobs and label each with its type, level and region.

    Technology jobs get a "category" (cs.py) and appear on the tech site; every other job gets a
    general "group" (jobtypes.py) and appears only on the "All jobs in Israel" page."""
    out = []
    for j in jobs:
        if IL_ONLY and not is_il(j["location"]):
            continue
        cat = cs.category(j["title"], j.get("department", ""))
        if CS_ONLY and not cat:
            continue
        j["category"] = cat
        if not cat:
            j["group"] = jobtypes.general(j["title"], j.get("department", ""))
        j["level"] = cs.level(j["title"])
        j["region"] = region(j["location"])
        out.append(j)
    return out


def crawl_company(c):
    ats = c.get("ats")
    if not ats or ats.get("platform") not in ADAPTERS:
        merged, err = merge_aggregator(c, None)
        if merged:
            merged = keep(merged)
        if merged:
            return c["name"], merged, None
        return c["name"], None, err or "no supported job board"
    try:
        jobs = ADAPTERS[ats["platform"]](ats)
        jobs, _ = merge_aggregator(c, jobs)
        jobs = keep(jobs)
        # de-duplicate on URL
        seen, uniq = set(), []
        for j in jobs:
            k = (j["url"] or "") + "|" + j["title"] + "|" + j["location"]
            if k not in seen:
                seen.add(k)
                uniq.append(j)
        return c["name"], uniq, None
    except Exception as e:
        return c["name"], None, f"{type(e).__name__}: {e}"[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="crawl only companies whose name contains this text")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()

    companies = json.load(open(os.path.join(DATA, "companies.json")))
    jobs_path = os.path.join(DATA, "jobs.json")
    prev = json.load(open(jobs_path)) if os.path.exists(jobs_path) else {"companies": {}}
    today = dt.date.today().isoformat()

    todo = [c for c in companies if not a.only or a.only.lower() in c["name"].lower()]
    global SEARCH_ALLOWED
    if (os.environ.get("JOBSEARCH_PROVIDER") or "").lower() == "jobspy":
        # JobSpy can only search a limited number of companies per run without being blocked,
        # so take turns: the companies searched longest ago (or never) go first.
        scope = (os.environ.get("JOBSEARCH_SCOPE") or "untracked")
        cap = int((os.environ.get("JOBSPY_MAX_COMPANIES") or "75") or 0) or len(todo)
        wants = [c for c in todo if scope == "all" or not c.get("ats") or c["ats"].get("platform") not in ADAPTERS]
        wants.sort(key=lambda c: prev.get("companies", {}).get(c["name"], {}).get("searched", ""))
        SEARCH_ALLOWED = {c["name"] for c in wants[:cap]}
    results = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for name, jobs, err in ex.map(crawl_company, todo):
            results[name] = (jobs, err)
            if err != "no supported job board":
                status = f"{len(jobs)} jobs" if jobs is not None else err
                print(f"{name:45s} {status}", flush=True)

    out_companies = dict(prev.get("companies", {}))
    added, removed = [], []
    for c in todo:
        name = c["name"]
        jobs, err = results[name]
        old = prev.get("companies", {}).get(name, {})
        old_by_url = {j["url"]: j for j in old.get("jobs", [])}
        old_by_title = {(j["title"], j.get("location", "")): j for j in old.get("jobs", [])}
        entry = {"checked": today, "error": err}
        searched = SEARCH_ALLOWED is None or name in SEARCH_ALLOWED
        if old.get("searched") or searched:
            entry["searched"] = today if searched and (os.environ.get("JOBSEARCH_PROVIDER") or "") else old.get("searched", "")
        if jobs is None:
            # keep last good list if the board failed this week. Drop LinkedIn/Indeed listings saved
            # before the employer name was recorded: an earlier name match was too loose.
            entry["jobs"] = [j for j in old.get("jobs", []) if j.get("source") != "aggregator" or j.get("employer")]
            entry["last_ok"] = old.get("last_ok")
        else:
            for j in jobs:
                o = old_by_url.get(j["url"]) or old_by_title.get((j["title"], j.get("location", "")))
                j["first_seen"] = o["first_seen"] if o else today
                if o and "coverage" in o:
                    j["coverage"] = o["coverage"]
                if not o and old:
                    added.append({"company": name, "title": j["title"], "url": j["url"]})
            new_urls = {j["url"] for j in jobs}
            new_titles = {(j["title"], j.get("location", "")) for j in jobs}
            for u, o in old_by_url.items():
                if u not in new_urls and (o["title"], o.get("location", "")) not in new_titles:
                    removed.append({"company": name, "title": o["title"], "url": u})
            entry["jobs"] = jobs
            entry["last_ok"] = today
        out_companies[name] = entry

    total = sum(len(v["jobs"]) for v in out_companies.values())
    json.dump(nan_safe({"generated": today, "total_jobs": total, "companies": out_companies}),
              open(jobs_path, "w"), indent=0, ensure_ascii=False)

    ch_path = os.path.join(DATA, "changes.json")
    changes = json.load(open(ch_path)) if os.path.exists(ch_path) else []
    if not a.only:
        changes.insert(0, {"date": today, "added": len(added), "removed": len(removed),
                           "added_jobs": added[:500], "removed_jobs": removed[:500]})
        json.dump(changes[:52], open(ch_path, "w"), indent=0, ensure_ascii=False)
    if os.environ.get("JOBSEARCH_PROVIDER") and (os.environ.get("COVERAGE_CHECK") or "1") != "0":
        try:
            import coverage_check
            coverage_check.run(DATA, only_new=os.environ.get("COVERAGE_ALL") != "1")
        except Exception as e:
            print("coverage check skipped:", e)
    write_site(companies)
    print(f"\n{total} jobs total; {len(added)} new, {len(removed)} removed since last run.")


def is_tech(j):
    """A technology job (shown on the tech site). Jobs saved before non-tech jobs were kept all count."""
    return bool(j.get("category")) or "group" not in j


def write_site(companies=None):
    """Bundle everything index.html needs into data/site.json."""
    if companies is None:
        companies = json.load(open(os.path.join(DATA, "companies.json")))
    jobs = json.load(open(os.path.join(DATA, "jobs.json")))
    ch_path = os.path.join(DATA, "changes.json")
    changes = json.load(open(ch_path)) if os.path.exists(ch_path) else []
    first = min((j["first_seen"] for c in jobs["companies"].values() for j in c["jobs"]), default=jobs["generated"])
    meta = [{"name": c["name"], "size": c.get("size", "small"), "careers": c.get("careers", ""),
             "ats": (c.get("ats") or {}).get("platform", ""),
             "partial_total": c.get("partial_total") if c.get("partial_total") and len(jobs["companies"].get(c["name"], {}).get("jobs", [])) < c.get("partial_total", 0) else None}
            for c in companies]
    hist = [{k: v for k, v in c.items() if k in ("date", "added", "removed")} for c in changes]
    # site.json: technology jobs only (the tech site, digests and alerts); site-all.json: every job.
    tech = {n: {"jobs": [j for j in c["jobs"] if is_tech(j)]} for n, c in jobs["companies"].items()}
    every = {n: {"jobs": c["jobs"]} for n, c in jobs["companies"].items()}
    for fname, comp in (("site.json", tech), ("site-all.json", every)):
        json.dump(nan_safe({"generated": jobs["generated"], "first_run": first, "meta": meta, "companies": comp,
                            "changes": hist}),
                  open(os.path.join(DATA, fname), "w"), separators=(",", ":"), ensure_ascii=False)
    write_feed({"generated": jobs["generated"], "companies": tech})


def write_feed(jobs, site_url=None, limit=500):
    """RSS feed of jobs first seen in the latest run, for RSS-to-email newsletters."""
    from xml.sax.saxutils import escape
    site_url = site_url or (os.environ.get("SITE_URL") or "")
    latest = jobs["generated"]
    items = [(n, j) for n, c in jobs["companies"].items() for j in c["jobs"] if j.get("first_seen") == latest]
    first_run = all(j.get("first_seen") == latest for c in jobs["companies"].values() for j in c["jobs"])
    if first_run:
        items = []  # nothing is "new" on the very first crawl
    items.sort(key=lambda x: (x[0].lower(), x[1]["title"].lower()))
    pub = dt.datetime.strptime(latest, "%Y-%m-%d").strftime("%a, %d %b %Y 06:00:00 +0000")
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           "<title>New tech jobs in Israel</title>", f"<link>{escape(site_url)}</link>",
           f"<description>{len(items)} jobs first seen on {latest}</description>", f"<lastBuildDate>{pub}</lastBuildDate>"]
    for n, j in items[:limit]:
        desc = escape(f"{n} · {j.get('category', '')} · {j.get('location', '')}" + (f" · via {j['via']}" if j.get("via") else ""))
        out.append(f"<item><title>{escape(j['title'] + ' — ' + n)}</title><link>{escape(j['url'])}</link>"
                   f"<guid isPermaLink=\"false\">{escape(j['url'] or n + j['title'])}</guid><pubDate>{pub}</pubDate>"
                   f"<description>{desc}</description></item>")
    out.append("</channel></rss>")
    open(os.path.join(DATA, "feed.xml"), "w").write("\n".join(out))


if __name__ == "__main__":
    sys.exit(main())
