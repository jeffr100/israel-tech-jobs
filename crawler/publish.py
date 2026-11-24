#!/usr/bin/env python3
"""Turn the latest crawl into a newsletter post and (optionally) publish it.

    python3 crawler/publish.py                 # daily digest every day, weekly on Mondays, monthly on the 1st
    python3 crawler/publish.py --only weekly   # build/send just one of daily | weekly | monthly
    python3 crawler/publish.py --since 7       # one digest of jobs first seen in the last 7 days

Sign-ups from the website go into one of three Brevo lists (daily, weekly, monthly), and each
digest is sent only to its own list. Files: data/digest-<frequency>.md/.html.

The digest lists new jobs grouped by company. With COVERAGE data present, jobs that were
NOT found on LinkedIn, Indeed or Glassdoor are listed first ("Only here").

Optional destinations (set the environment variables / GitHub secrets to switch one on):

  Brevo        BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_LIST_DAILY / _WEEKLY / _MONTHLY (list IDs)
                                           -> creates a campaign per frequency (draft unless BREVO_SEND=1)
               BREVO_SENDER_NAME (optional, default "Tech Jobs in Israel")
  Buttondown   BUTTONDOWN_API_KEY          -> creates an email per frequency (draft unless BUTTONDOWN_SEND=1)
  Job alerts   BREVO_ALERT_LIST (+ the Brevo settings above) -> personal alerts, see crawler/alerts.py
  WordPress    WP_URL, WP_USER, WP_APP_PASSWORD
                                           -> posts the weekly digest (draft unless WP_STATUS=publish)
  Any newsletter that does RSS-to-email can also send data/feed.xml.
"""
import base64
import datetime as dt
import html
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def collect(since_days=None):
    jobs = json.load(open(os.path.join(DATA, "jobs.json")))
    latest = jobs["generated"]
    first = min((j["first_seen"] for c in jobs["companies"].values() for j in c["jobs"]), default=latest)
    if since_days:
        cutoff = (dt.date.fromisoformat(latest) - dt.timedelta(days=since_days)).isoformat()
        keep = lambda j: j["first_seen"] > cutoff and j["first_seen"] != first
    else:
        keep = lambda j: j["first_seen"] == latest and latest != first
    out = {}
    for name, c in jobs["companies"].items():
        # technology jobs only: the digests and alerts belong to the tech site
        sel = [j for j in c["jobs"] if keep(j) and (j.get("category") or "group" not in j)]
        if sel:
            out[name] = sel
    return latest, out


def only_here(j):
    """Not found on any job site we were able to search, and at least LinkedIn or Indeed was searched."""
    cov = j.get("coverage")
    if not cov or (cov.get("linkedin") is None and cov.get("indeed") is None):
        return False
    return not (cov.get("linkedin") or cov.get("indeed") or cov.get("glassdoor"))


PERIOD = {"daily": (1, "today"), "weekly": (7, "this week"), "monthly": (30, "this month")}


def render(latest, by_co, site_url="", period=""):
    n = sum(len(v) for v in by_co.values())
    exclusive = sum(1 for v in by_co.values() for j in v if only_here(j))
    when = PERIOD[period][1] if period in PERIOD else latest
    title = f"{n} new tech jobs in Israel {when}" if period else f"{n} new tech jobs in Israel — {latest}"
    md = [f"# {title}", ""]
    hl = [f"<h1>{html.escape(title)}</h1>"]
    if exclusive:
        md += [f"**{exclusive}** of these were not found on LinkedIn, Indeed or Glassdoor (marked ★).", ""]
        hl.append(f"<p><b>{exclusive}</b> of these were not found on LinkedIn, Indeed or Glassdoor (marked ★).</p>")
    for name in sorted(by_co, key=lambda k: (-sum(only_here(j) for j in by_co[k]), k.lower())):
        md.append(f"## {name}")
        hl.append(f"<h2>{html.escape(name)}</h2><ul>")
        for j in sorted(by_co[name], key=lambda j: (not only_here(j), j["title"].lower())):
            star = "★ " if only_here(j) else ""
            md.append(f"- {star}[{j['title']}]({j['url']}) — {j.get('location', '')}")
            hl.append(f"<li>{star}<a href=\"{html.escape(j['url'])}\">{html.escape(j['title'])}</a> — {html.escape(j.get('location', ''))}</li>")
        md.append("")
        hl.append("</ul>")
    if site_url:
        md.append(f"Search every open job: {site_url}")
        hl.append(f"<p>Search every open job: <a href=\"{html.escape(site_url)}\">{html.escape(site_url)}</a></p>")
    return title, "\n".join(md), "\n".join(hl), n


def post_json(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def send_buttondown(title, md, tag=None):
    status = "about_to_send" if os.environ.get("BUTTONDOWN_SEND") == "1" else "draft"
    payload = {"subject": title, "body": md, "status": status}
    if tag:
        payload["filters"] = {"predicate": "and", "groups": [],
                              "filters": [{"operator": "contains", "field": "subscriber.tags", "value": tag}]}
    r = post_json("https://api.buttondown.com/v1/emails", payload,
                  {"Authorization": f"Token {os.environ['BUTTONDOWN_API_KEY']}"})
    print(f"buttondown ({tag or 'all'}):", r.get("id", r))


BREVO_FREE_DAILY_LIMIT = 300   # Brevo's free plan sends at most 300 emails a day


def send_brevo(title, body_html, freq):
    """Create a Brevo email campaign for one list and (with BREVO_SEND=1) send it now."""
    list_id = os.environ.get(f"BREVO_LIST_{freq.upper()}", "").strip()
    sender = (os.environ.get("BREVO_SENDER_EMAIL") or "").strip()
    if not list_id or not sender:
        print(f"brevo ({freq}): skipped - set BREVO_LIST_{freq.upper()} and BREVO_SENDER_EMAIL")
        return
    key = {"api-key": os.environ["BREVO_API_KEY"], "accept": "application/json"}
    site = (os.environ.get("SITE_URL") or "")
    content = (f"<html><body style=\"font-family:Arial,sans-serif;max-width:680px;margin:auto\">{body_html}"
               f"<hr><p style=\"font-size:12px;color:#666\">You get this {freq} because you signed up"
               f"{' at <a href=\"' + html.escape(site) + '\">' + html.escape(site) + '</a>' if site else ''}. "
               f"<a href=\"{{{{ unsubscribe }}}}\">Unsubscribe</a></p></body></html>")
    camp = post_json("https://api.brevo.com/v3/emailCampaigns", {
        "name": f"{title} ({freq}, {dt.date.today().isoformat()})",
        "subject": title,
        "sender": {"name": os.environ.get("BREVO_SENDER_NAME") or "Tech Jobs in Israel", "email": sender},
        "htmlContent": content,
        "recipients": {"listIds": [int(list_id)]},
    }, key)
    cid = camp.get("id")
    print(f"brevo ({freq}): created campaign {cid}")
    if cid and os.environ.get("BREVO_SEND") == "1":
        post_json(f"https://api.brevo.com/v3/emailCampaigns/{cid}/sendNow", {}, key)
        print(f"brevo ({freq}): sending to list {list_id}")


def send_wordpress(title, body_html):
    tok = base64.b64encode(f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode()).decode()
    r = post_json(os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2/posts",
                  {"title": title, "content": body_html, "status": (os.environ.get("WP_STATUS") or "draft")},
                  {"Authorization": f"Basic {tok}"})
    print("wordpress:", r.get("link", r))


def due_today(today):
    out = ["daily"]
    if today.weekday() == int((os.environ.get("WEEKLY_DAY") or "0")):   # 0 = Monday
        out.append("weekly")
    if today.day == 1:
        out.append("monthly")
    return out


def main():
    site = (os.environ.get("SITE_URL") or "")
    if "--since" in sys.argv:                       # one-off digest, sent to everyone
        since = int(sys.argv[sys.argv.index("--since") + 1])
        latest, by_co = collect(since)
        title, md, body_html, n = render(latest, by_co, site)
        open(os.path.join(DATA, "digest.md"), "w").write(md)
        open(os.path.join(DATA, "digest.html"), "w").write(body_html)
        print(f"digest: {n} new jobs")
        if n and os.environ.get("BUTTONDOWN_API_KEY"):
            send_buttondown(title, md)
        return

    if "--only" in sys.argv:
        freqs = [sys.argv[sys.argv.index("--only") + 1]]
    else:
        freqs = due_today(dt.date.today())
    for f in freqs:
        latest, by_co = collect(PERIOD[f][0])
        title, md, body_html, n = render(latest, by_co, site, f)
        open(os.path.join(DATA, f"digest-{f}.md"), "w").write(md)
        open(os.path.join(DATA, f"digest-{f}.html"), "w").write(body_html)
        print(f"{f} digest: {n} new jobs -> data/digest-{f}.md")
        if not n:
            continue
        if os.environ.get("BREVO_API_KEY"):
            try:
                send_brevo(title, body_html, f)
            except Exception as e:   # one failed list shouldn't stop the others
                print(f"brevo ({f}): failed: {e}")
        if os.environ.get("BUTTONDOWN_API_KEY"):
            send_buttondown(title, md, f)
        if f == "weekly" and os.environ.get("WP_URL") and os.environ.get("WP_APP_PASSWORD"):
            send_wordpress(title, body_html)

    # Personal alerts: each subscriber gets only the new jobs matching the filters they saved on the site.
    if os.environ.get("BREVO_ALERT_LIST"):
        import alerts
        meta = {m["name"]: m for m in json.load(open(os.path.join(DATA, "site.json"))).get("meta", [])}
        try:
            alerts.send_alerts({f: PERIOD[f][0] for f in freqs}, collect, only_here, alerts.parse, alerts.matches,
                               alerts.describe, meta, site, os.environ.get("BREVO_SENDER_NAME") or "Tech Jobs in Israel", "IL_ALERT")
        except Exception as e:   # alerts must never stop the digests or the site update
            print(f"alerts: failed: {e}")


if __name__ == "__main__":
    main()
