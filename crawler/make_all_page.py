#!/usr/bin/env python3
"""Write all/index.html (the "All jobs in Israel" page) from index.html.

Both pages share one source: this copies index.html, points it at data/site-all.json and the shared
files one folder up, and swaps the headline and descriptions. Run after editing index.html; the
publish workflow also runs it, so the live pages always match.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()

def swap(a, b):
    global s
    if a not in s:
        raise SystemExit(f"make_all_page: can't find {a[:60]!r} in index.html")
    s = s.replace(a, b)

swap('<script src="site.config.js"></script>',
     '<script src="../site.config.js"></script>\n<script>window.PAGE={all:true,data:"../data/site-all.json"}</script>')
swap('href="data/feed.xml"', 'href="../data/feed.xml"')
swap('<a class="brand" href="./">', '<a class="brand" href="../">')
swap('<a class="nav" href="all/" id="otherpage">All jobs in Israel</a>', '<a class="nav" href="../" id="otherpage">Tech jobs only</a>')
start = s.index("<title>"); end = s.index("</title>") + len("</title>")
s = s[:start] + "<title>All jobs in Israel — openings from company career pages</title>" + s[end:]
start = s.index('<meta name="description"'); end = s.index(">", start) + 1
s = s[:start] + '<meta name="description" content="Every job in Israel we can read straight from company career pages: technology, sales, finance, healthcare, operations, retail and more, checked every day.">' + s[end:]
start = s.index('<h1 id="headline">'); end = s.index("</h1>", start) + len("</h1>")
s = s[:start] + '<h1 id="headline">All jobs in Israel</h1>' + s[end:]
start = s.index('<p class="lede">'); end = s.index("</p>", start) + len("</p>")
s = s[:start] + ('<p class="lede">Every opening in Israel we can read straight from company career pages, technology '
                 'and everything else: sales, finance, healthcare, operations, retail and more. Checked every morning.</p>') + s[end:]
start = s.index('<p>Each company is matched to its public job board'); end = s.index("</p>", start) + len("</p>")
s = s[:start] + ('<p>Each company is matched to its public job board (Comeet, Greenhouse, Lever, Ashby, SmartRecruiters or '
                 'Workday), and a crawler reads those boards every morning at 6:00 Israel time. Every job located in Israel '
                 'is listed here; the tech site shows only the technology roles. Job types and seniority are worked out from '
                 'the job title, so some jobs may be misfiled. Many Israeli employers post only on general job sites such as '
                 'AllJobs or Drushim, or through staffing agencies; those jobs are not included. "Large" means about 1,000 or '
                 'more employees. Dates are the employer\'s posting date when the job board gives one, otherwise the first day '
                 'this site saw the job.</p>') + s[end:]
os.makedirs(os.path.join(ROOT, "all"), exist_ok=True)
open(os.path.join(ROOT, "all", "index.html"), "w", encoding="utf-8").write(s)
print("wrote all/index.html")
