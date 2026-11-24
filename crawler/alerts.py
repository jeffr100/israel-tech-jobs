#!/usr/bin/env python3
"""Personal job alerts: each subscriber gets only the new jobs matching the filters they saved.

On the website, a visitor sets filters (job type, seniority, area, search words, company size...) and
clicks "Email me these jobs". The filters are saved on their Brevo contact as the same text the site
keeps after the # in its address (for example  level=Senior&field=3&area=Tel+Aviv&q=python ), together
with how often they want emails. Every run, this script reads the alert list from Brevo, finds the new
jobs that match each person's filters, and sends each person one email (skipped when nothing matches).

Settings (GitHub variables / secrets):
  BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME   as for the digests
  BREVO_ALERT_LIST     Brevo list that alert sign-ups go into
  ALERT_ATTR           contact attribute holding the filters (default IL_ALERT); the frequency is
                       in <ALERT_ATTR>_FREQ (daily | weekly | monthly)
  BREVO_SEND=1         actually send (otherwise it only reports what it would send)
  ALERT_MAX            most alert emails per run (default 200; Brevo's free plan sends 300 a day)
"""
import html
import json
import os
import re
import urllib.parse
import urllib.request

# Job types and levels as the crawler sets them (crawler/cs.py); the website uses the same order.
FIELDS = ["Backend & software engineering", "Frontend & full stack", "Mobile", "Data & AI", "Algorithms & research", "Security", "DevOps, cloud & SRE", "QA & testing", "Embedded & firmware", "Chip design & silicon", "IT & systems", "Technical product", "Electronics & hardware", "Optics, physics & systems", "Mechanical & manufacturing", "Medtech & life sciences", "Technical sales & solutions", "Design & UX", "Other"]
LEVELS = {"Student / intern": "Student / intern", "Junior": "Junior", "Mid-level / unspecified": "Mid-level",
          "Senior": "Senior", "Lead / manager": "Lead / manager"}


def parse(saved):
    p = urllib.parse.parse_qs((saved or "").lstrip("#"))
    g = lambda k: (p.get(k) or [""])[0]
    return {"q": g("q").lower().split(), "area": g("area"), "size": g("size"), "only": g("only") == "1",
            "levels": {x for x in g("level").split("|") if x in LEVELS},
            "fields": {int(x) for x in g("field").split(",") if x.isdigit() and int(x) < len(FIELDS)}}


def matches(f, j, company, size):
    if f["size"] and size != f["size"]: return False
    if f["levels"] and (j.get("level") or "Mid-level / unspecified") not in f["levels"]: return False
    if f["fields"]:
        cat = {"Chip design & hardware": "Chip design & silicon"}.get(j.get("category"), j.get("category")) or "Other"
        if cat not in FIELDS: cat = "Other"
        if cat not in {FIELDS[i] for i in f["fields"]}: return False
    if f["q"]:
        hay = " ".join([j.get("title") or "", company, j.get("location") or "", j.get("department") or "",
                        j.get("category") or "", j.get("region") or ""]).lower()
        if not all(t in hay for t in f["q"]): return False
    if f["area"] and (j.get("region") or "") != f["area"]: return False
    if f["only"]:
        from publish import only_here
        if not only_here(j): return False
    return True


def describe(f):
    parts = [LEVELS[k] for k in LEVELS if k in f["levels"]] + [FIELDS[i] for i in sorted(f["fields"])]
    if f["area"]: parts.append(f["area"])
    if f["q"]: parts.append("\u201c" + " ".join(f["q"]) + "\u201d")
    if f["size"]: parts.append("large companies" if f["size"] == "large" else "startups and mid-size")
    if f["only"]: parts.append("not on LinkedIn or Indeed")
    return " \u00b7 ".join(parts) or "all tech jobs"


# ---------------------------------------------------------------- sending (shared with the Israel site)
def _brevo(method, path, payload=None):
    req = urllib.request.Request("https://api.brevo.com/v3" + path, method=method,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"api-key": os.environ["BREVO_API_KEY"], "accept": "application/json",
                                          "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def alert_contacts(list_id):
    out, offset = [], 0
    while True:
        d = _brevo("GET", f"/contacts/lists/{list_id}/contacts?limit=500&offset={offset}")
        rows = d.get("contacts") or []
        out += rows
        if len(rows) < 500:
            return out
        offset += 500


def email_html(title, saved, by_co, site, email, freq, only_here, site_name):
    link = lambda frag: html.escape(site.rstrip("/") + "/#" + frag)
    rows = []
    for co in sorted(by_co, key=str.lower):
        rows.append(f"<h3 style=\"margin:18px 0 4px\">{html.escape(co)}</h3><ul style=\"margin:0;padding-left:18px\">")
        for j in sorted(by_co[co], key=lambda j: j["title"].lower()):
            star = "\u2605 " if only_here(j) else ""
            rows.append(f"<li>{star}<a href=\"{html.escape(j['url'])}\">{html.escape(j['title'])}</a>"
                        f" \u2014 {html.escape(j.get('location', ''))}</li>")
        rows.append("</ul>")
    stop = urllib.parse.urlencode({"stopalert": email})
    return (f"<html><body style=\"font-family:Arial,sans-serif;max-width:680px;margin:auto;color:#1d1630\">"
            f"<h2>{html.escape(title)}</h2>{''.join(rows)}"
            f"<p style=\"margin-top:22px\"><a href=\"{link(saved)}\">See every job matching this alert</a></p>"
            f"<hr><p style=\"font-size:12px;color:#666\">You get this {freq} because you set up a job alert on "
            f"{html.escape(site_name)}. To change it, open the link above, adjust the filters and save the alert again. "
            f"<a href=\"{link(stop)}\">Stop this alert</a></p></body></html>")


def send_alerts(due, collect, only_here, parse, matches, describe, meta, site, site_name, default_attr):
    list_id = (os.environ.get("BREVO_ALERT_LIST") or "").strip()
    sender = (os.environ.get("BREVO_SENDER_EMAIL") or "").strip()
    if not (os.environ.get("BREVO_API_KEY") and list_id and sender):
        print("alerts: skipped - set BREVO_API_KEY, BREVO_ALERT_LIST and BREVO_SENDER_EMAIL")
        return
    attr = (os.environ.get("ALERT_ATTR") or default_attr).upper()
    live = os.environ.get("BREVO_SEND") == "1"
    cap = int(os.environ.get("ALERT_MAX") or 200)
    new = {f: collect(days)[1] for f, days in due.items()}
    sent = skipped = 0
    for c in alert_contacts(list_id):
        a = c.get("attributes") or {}
        saved, freq = (a.get(attr) or "").strip(), (a.get(attr + "_FREQ") or "weekly").strip().lower()
        if c.get("emailBlacklisted") or not saved or saved == "stop" or freq not in new:
            continue
        f = parse(saved)
        by_co = {}
        for co, jobs in new[freq].items():
            size = (meta.get(co) or {}).get("size", "small")
            hit = [j for j in jobs if matches(f, j, co, size)]
            if hit:
                by_co[co] = hit
        n = sum(len(v) for v in by_co.values())
        if not n:
            skipped += 1
            continue
        if sent >= cap:
            print(f"alerts: reached ALERT_MAX={cap}; the rest wait for the next run")
            break
        title = f"{n} new job{'s' if n != 1 else ''} for your alert: {describe(f)}"
        if live:
            _brevo("POST", "/smtp/email", {
                "sender": {"name": os.environ.get("BREVO_SENDER_NAME") or site_name, "email": sender},
                "to": [{"email": c["email"]}], "subject": title, "tags": ["job-alert"],
                "htmlContent": email_html(title, saved, by_co, site, c["email"], freq, only_here, site_name)})
        sent += 1
    print(f"alerts: {'sent' if live else 'would send (set BREVO_SEND=1 to send)'} {sent} email(s); "
          f"{skipped} alert(s) had no new matching jobs")
