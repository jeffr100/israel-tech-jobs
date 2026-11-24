"""Free alternative to the paid job-search APIs, using the open-source JobSpy library
(https://github.com/speedyapply/JobSpy, `pip install python-jobspy`).

JobSpy reads LinkedIn, Indeed, Glassdoor and Google Jobs listings directly. It needs no API key,
but those sites limit how much one computer can read: LinkedIn usually starts blocking after
roughly 10 pages from one IP address, so runs are kept small and slow, and you can add proxies.
Reading those sites this way may break their terms of use; using it is your decision.

Settings (environment variables):
  JOBSEARCH_PROVIDER = jobspy          turns this on (no JOBSEARCH_API_KEY needed)
  JOBSPY_SITES       = indeed,linkedin (default; glassdoor and google also work)
  JOBSPY_RESULTS     = 40              listings to read per company per site
  JOBSPY_DELAY       = 4               seconds to wait between companies
  JOBSPY_PROXIES     = user:pass@host:port,host2:port   optional, comma-separated. Only LinkedIn searches
                       use them (JOBSPY_PROXY_SITES=linkedin), since paid proxies are billed per GB
  JOBSPY_MAX_COMPANIES = 75            companies to look up per run (per pass) (0 = no limit); the rest are
                                       picked up on later runs, which keeps LinkedIn from blocking
"""
import logging
import os
import time

COUNTRY = {"il": ("Israel", "israel"), "us": ("United States", "usa")}
_count = 0


def _v(x):
    """A clean string from a pandas cell: missing values come back as NaN, which is truthy."""
    if x is None or (isinstance(x, float) and x != x):
        return ""
    return str(x)

LAST_SEARCHED = set()   # sites that actually answered during the most recent search
_FAILED = set()
BLOCKED = {}            # site -> number of searches it refused this run
_STREAK = {}            # site -> searches refused in a row
GIVE_UP = int(os.environ.get("JOBSPY_GIVE_UP") or "3")   # stop asking a site after this many refusals in a row
LAST_REASON = ""        # why the most recent search returned nothing: "", "limit" or "blocked"


def stopped_sites():
    """Sites that refused GIVE_UP searches in a row and aren't asked again this run."""
    return {s for s, n in _STREAK.items() if GIVE_UP and n >= GIVE_UP}


class _Watch(logging.Handler):
    """JobSpy logs an error (e.g. "response status code 429 (blocked: use a proxy)") when a site
    refuses a search. Note which site it was, so a block isn't mistaken for "job not listed there"."""
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            site = record.name.split(".")[-1].lower()
            _FAILED.add(site)
            BLOCKED[site] = BLOCKED.get(site, 0) + 1


_watch = _Watch()


def _search(**kw):
    from jobspy import scrape_jobs
    global LAST_SEARCHED
    lg = logging.getLogger("jobspy")
    if _watch not in lg.handlers:
        lg.addHandler(_watch)
    global LAST_REASON
    _FAILED.clear()
    LAST_REASON = ""
    # A site that keeps refusing has blocked this server for now; asking again only prolongs it.
    kw = dict(kw, site_name=[x for x in kw["site_name"] if x not in stopped_sites()])
    if not kw["site_name"]:
        LAST_SEARCHED, LAST_REASON = set(), "blocked"
        return _empty()
    # Paid proxies are billed by the gigabyte, so only the sites that need them (LinkedIn by default,
    # JOBSPY_PROXY_SITES to change) go through them; the others are searched directly.
    via = {x.strip() for x in (os.environ.get("JOBSPY_PROXY_SITES") or "linkedin").split(",") if x.strip()}
    sites = list(kw["site_name"])
    if kw.get("proxies") and set(sites) - via and set(sites) & via:
        import pandas as pd
        direct = dict(kw, site_name=[x for x in sites if x not in via], proxies=None)
        proxied = dict(kw, site_name=[x for x in sites if x in via])
        frames = [f for f in (scrape_jobs(**direct), scrape_jobs(**proxied)) if f is not None and len(f)]
        df = pd.concat(frames, ignore_index=True) if frames else _empty()
    else:
        df = scrape_jobs(**kw)
    LAST_SEARCHED = {x for x in sites if x not in _FAILED}
    for x in sites:
        _STREAK[x] = _STREAK.get(x, 0) + 1 if x in _FAILED else 0
    if not LAST_SEARCHED:
        LAST_REASON = "blocked"
    return df


def _empty():
    import pandas as pd
    return pd.DataFrame(columns=["site", "title", "company", "location", "job_url", "job_url_direct"])


def available():
    try:
        import jobspy  # noqa: F401
        return True
    except ImportError:
        return False


def listings(company, country="il"):
    """Return [{title, location, url, site, company}] for one company, or [] if blocked/limited."""
    global _count
    from jobspy import scrape_jobs
    cap = int((os.environ.get("JOBSPY_MAX_COMPANIES") or "75") or 0)
    if cap and _count >= cap:
        global LAST_SEARCHED, LAST_REASON
        LAST_SEARCHED, LAST_REASON = set(), "limit"
        return []
    if not {x.strip() for x in (os.environ.get("JOBSPY_SITES") or "indeed,linkedin").split(",") if x.strip()} - stopped_sites():
        LAST_SEARCHED, LAST_REASON = set(), "blocked"   # every site has blocked this server for now
        return []
    if _count:
        time.sleep(float((os.environ.get("JOBSPY_DELAY") or "4")))
    _count += 1
    where, indeed_country = COUNTRY.get(country, COUNTRY["us"])
    sites = [s.strip() for s in (os.environ.get("JOBSPY_SITES") or "indeed,linkedin").split(",") if s.strip()]
    proxies = [p.strip() for p in (os.environ.get("JOBSPY_PROXIES") or "").split(",") if p.strip()] or None
    kw = dict(site_name=sites, search_term=f'"{company}"', location=where, country_indeed=indeed_country,
              results_wanted=int((os.environ.get("JOBSPY_RESULTS") or "40")), proxies=proxies, verbose=0)
    if "google" in sites:
        kw["google_search_term"] = f"{company} jobs in {where}"
    df = _search(**kw)
    out = []
    for r in df.to_dict("records"):
        loc = r.get("location")
        if isinstance(loc, dict):
            loc = {k: _v(v) for k, v in loc.items()}
            loc = ", ".join(str(v) for v in (loc.get("city"), loc.get("state"), loc.get("country")) if v)
        out.append({"title": _v(r.get("title")), "location": _v(loc), "company": _v(r.get("company")),
                    "url": _v(r.get("job_url_direct")) or _v(r.get("job_url")), "site": _v(r.get("site"))})
    return out


def listings_sites():
    return [s.strip() for s in (os.environ.get("JOBSPY_JOB_SITES") or ((os.environ.get("JOBSPY_SITES") or "indeed,linkedin") + ",google")).split(",") if s.strip()]


def listings_for_job(company, title, country="us"):
    """Search for one job title at one company on Indeed, LinkedIn and Google Jobs."""
    from jobspy import scrape_jobs
    global LAST_SEARCHED, LAST_REASON
    if not set(listings_sites()) - stopped_sites():
        LAST_SEARCHED, LAST_REASON = set(), "blocked"
        return []
    time.sleep(float((os.environ.get("JOBSPY_DELAY") or "4")))
    where, indeed_country = COUNTRY.get(country, COUNTRY["us"])
    sites = listings_sites()
    proxies = [p.strip() for p in (os.environ.get("JOBSPY_PROXIES") or "").split(",") if p.strip()] or None
    kw = dict(site_name=sites, search_term=f'{title} "{company}"', location=where, country_indeed=indeed_country,
              results_wanted=10, proxies=proxies, verbose=0)
    if "google" in sites:
        kw["google_search_term"] = f"{title} {company} jobs in {where}"
    out = []
    for r in _search(**kw).to_dict("records"):
        loc = r.get("location")
        if isinstance(loc, dict):
            loc = {k: _v(v) for k, v in loc.items()}
            loc = ", ".join(str(v) for v in (loc.get("city"), loc.get("state"), loc.get("country")) if v)
        out.append({"title": _v(r.get("title")), "location": _v(loc), "company": _v(r.get("company")),
                    "url": _v(r.get("job_url_direct")) or _v(r.get("job_url")), "site": _v(r.get("site"))})
    return out
