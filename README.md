# Computer science and high-tech jobs in Israel: website, crawler and newsletter

A searchable board of tech openings in Israel: software, data and AI, security, DevOps, QA, embedded, chip design, IT and technical product roles. The jobs come straight from each company's own career board, and the site can flag the ones that are **not** on LinkedIn, Indeed or Glassdoor.

| Path | What it is |
|---|---|
| `index.html` | The website. It has search, area, level, date, job-type, company-size and source filters, and a "not on LinkedIn/Indeed" filter. |
| `data/companies.json` | Every company, its size and where its jobs are posted (`ats`). |
| `data/jobs.json` | Current Israeli tech jobs. Each job has a category, level, area, the date it was first seen and, once checked, `coverage`. |
| `data/feed.xml` | RSS feed of jobs that are new in the latest run. |
| `crawler/crawl.py` | The crawler. It needs only Python 3 and no extra packages. |
| `crawler/illoc.py` | Decides whether a location is in Israel and which area it belongs to. It reads Hebrew place names too. |
| `crawler/cs.py` | Sorts job titles into tech categories and levels, including Hebrew titles. Sales, HR, finance and other non-tech jobs are dropped. |
| `crawler/coverage_check.py` | Marks which jobs also appear on LinkedIn, Indeed or Glassdoor. |
| `crawler/publish.py` | Writes the weekly digest and can post it to Buttondown or WordPress. |

## Where the jobs come from

- **Comeet** is used by most Israeli startups. The crawler reads the public positions list on each company's Comeet careers page and keeps the Israeli ones.
- **Greenhouse, Lever, Ashby and SmartRecruiters** are read through their public job-board APIs.
- **Workday** is used by large multinationals such as NVIDIA, Intel, Applied Materials, KLA, Marvell, Salesforce and Broadcom. Each Workday site is searched for Israeli city names.

The company list was built from three sources:
- public Comeet career pages;
- the [LastRound AI ATS Company Directory](https://datahub.io/lastroundai-hiring-data/lastroundai-hiring-data/ats-directory) (CC BY 4.0), filtered to boards with jobs in Israel;
- a list of well-known Israeli tech companies.

To add a company, add an entry to `data/companies.json`:

```json
{"name": "Upwind Security", "ats": {"platform": "comeet", "slug": "upwind", "uid": "49.004"}, "careers": "https://www.comeet.com/jobs/upwind/49.004", "size": "small"}
{"name": "Wiz", "ats": {"platform": "greenhouse", "slug": "wizinc"}, "size": "large"}
{"name": "NVIDIA", "ats": {"platform": "workday", "host": "nvidia.wd5.myworkdayjobs.com", "tenant": "nvidia", "site": "NVIDIAExternalCareerSite"}, "size": "large"}
```

A Comeet company's `slug` and `uid` are the last two parts of its careers address, `comeet.com/jobs/<slug>/<uid>`.

Settings:
- `IL_ONLY=0` keeps jobs in every country.
- `CS_ONLY=0` keeps non-tech jobs.

## Running it on GitHub (free)

From this folder, in Terminal:
```bash
git init -b main
git add .
git commit -m "First version of the Israel tech jobs site"
gh repo create israel-tech-jobs --public --source=. --push
gh api -X POST "repos/{owner}/{repo}/pages" -f build_type=workflow
gh workflow run "Job crawl"
```
The site appears at `https://<you>.github.io/israel-tech-jobs/` and is updated every day at 6:00 am Israel time, all year round (the workflow allows for daylight saving time). GitHub sometimes starts scheduled runs a little late.

To re-publish the site without crawling again, for example after changing `index.html`, run `gh workflow run "Job crawl" -f crawl=false`. It takes about a minute. If only the "deploy" step of a run fails, open the run on GitHub and choose **Re-run failed jobs**: only the publishing step runs again.

To view the site on your own computer, double-click `start_site.command` (Mac) or `start_site.bat` (Windows).

## Email updates (daily, weekly or monthly) with Brevo

Each run writes `data/digest-daily.md`, `-weekly.md` and `-monthly.md`. To email them through [Brevo](https://www.brevo.com) (free for up to 300 emails a day):
1. In Brevo, verify a sender address and create three lists (daily, weekly, monthly). Then create an API key under **SMTP & API → API keys**.
2. From this folder, run:
```bash
gh secret set BREVO_API_KEY                      # paste the key when asked
gh variable set BREVO_SENDER_EMAIL --body you@yourdomain.com
gh variable set BREVO_SENDER_NAME  --body "Tech Jobs in Israel"
gh variable set BREVO_LIST_DAILY   --body <list ID>
gh variable set BREVO_LIST_WEEKLY  --body <list ID>
gh variable set BREVO_LIST_MONTHLY --body <list ID>
gh variable set BREVO_SEND --body 1              # leave out at first to get drafts you can check in Brevo
```
- The daily email goes out every day, the weekly one on Mondays, and the monthly one on the 1st.
- People join a list through a Brevo sign-up form; Brevo can give you a link to share.
- `data/feed.xml` also works with any RSS-to-email service.

## Hosting on Netlify instead of GitHub Pages

GitHub Actions still runs the crawler every morning; Netlify only hosts the finished site. Netlify's free plan has 300 credits a month and each production deploy costs 15, so the workflow deploys once a week (Mondays) by default. Daily deploys (~450 credits/month) need the Personal plan or `NETLIFY_DEPLOY=daily` with enough credits.

1. Create a Netlify account and an empty site, and install the Netlify CLI: `brew install netlify-cli`, then `netlify login`.
2. In this folder run `netlify sites:create --name <pick-a-name>` and copy the **Site ID** it prints (also under Site configuration → General).
3. Create a personal access token in Netlify (User settings → Applications → Personal access tokens).
4. Tell GitHub to deploy to Netlify:
   ```bash
   gh variable set HOSTING --body netlify
   gh variable set SITE_URL --body https://<pick-a-name>.netlify.app/
   gh secret set NETLIFY_SITE_ID --body <site-id>
   gh secret set NETLIFY_AUTH_TOKEN          # paste the token when asked
   gh workflow run "Job crawl"
   ```
5. New Netlify projects may start private; publish the site in Netlify if it asks.

Don't also link the GitHub repository to Netlify for automatic builds: the daily data commit would trigger a paid deploy every day. To test by hand instead, run `netlify deploy --dir . --prod` from this folder, or drag the folder onto https://app.netlify.com/drop.

For Google ads, connect your own domain in Netlify (Domain management) so `ads.txt` sits at the root of that domain.

## Checking LinkedIn, Indeed and Google Jobs

Add these repository secrets:

| Secret | Value |
|---|---|
| `JOBSEARCH_PROVIDER` | `jsearch` or `serpapi` |
| `JOBSEARCH_API_KEY` | Your key from that provider |
| `JOBSEARCH_COUNTRY` | `il` (the default) |

Each run then marks every job as found or not found on LinkedIn, Indeed and Glassdoor. The website's **Only jobs not on LinkedIn or Indeed** button shows the jobs you can't find elsewhere, and the weekly digest lists them first.

### Checking jobs one at a time

After the company-wide search, the crawler searches again for each job that wasn't found elsewhere. The query is the job title plus the company name ("Senior Scientist, Assay Development GRAIL"), run against Google Jobs, Indeed and LinkedIn. A company-wide search only returns a company's first few dozen listings, so jobs at large employers are often missed there. The individual search fills that gap.

- Each job gets `coverage.method` set to `company` or `job`, so you can see how it was checked. The site shows "also on LinkedIn, Indeed, Google Jobs" or "not on LinkedIn, Indeed or Google Jobs".
- `COVERAGE_PER_JOB_MAX` (default 200, or 100 with JobSpy) caps the individual searches per run. The newest jobs go first and the rest are picked up on later runs.
- `COVERAGE_PER_JOB=0` turns this pass off.
- Cost: one search per job. That is roughly $0.002–0.015 per job, depending on the plan, with JSearch or SerpApi, or free with JobSpy but slow, at about 4 seconds per job to avoid blocking.

### Free option: JobSpy (no API key)

Set the repository secret `JOBSEARCH_PROVIDER` to `jobspy` and leave out `JOBSEARCH_API_KEY`. The workflow installs the open-source [JobSpy](https://github.com/speedyapply/JobSpy) library, which reads LinkedIn and Indeed listings directly. It powers both features: the "not on LinkedIn or Indeed" check and the LinkedIn/Indeed job feed.

Limits to know:
- **Blocking.** LinkedIn starts blocking one computer after a few hundred requests. To avoid that, each run looks up only 75 companies per pass (`JOBSPY_MAX_COMPANIES`) and the rest are checked on later runs. GitHub's servers get blocked more often than a home connection; adding proxies (`JOBSPY_PROXIES`) helps.
- **Terms of use.** Reading LinkedIn and Indeed this way may break their terms of use. The paid APIs above avoid that.
- **Other optional settings.** `JOBSPY_SITES` defaults to `indeed,linkedin`; `glassdoor` and `google` also work.
- **Mac.** JobSpy needs Python 3.10 or newer. macOS's built-in Python is 3.9, so install a newer one (for example `brew install python`). `mac/run_weekly.sh` uses it automatically when `JOBSEARCH_PROVIDER=jobspy`.

## Running it on a Mac

Run `bash mac/install_weekly_job.sh`. It schedules the crawler for every Monday morning with launchd. To run it straight away, use `bash mac/run_weekly.sh`.

## Personal job alerts

Visitors can set filters and click **Email me these jobs**. Their filters (the text after `#` in the
page address) are saved on their Brevo contact, and each crawl emails them only the new jobs that
match, daily, weekly or monthly. Every alert email has a "Stop this alert" link.

Setup (once):
1. In Brevo, two text contact attributes: `IL_ALERT` and `IL_ALERT_FREQ`; a list for alert sign-ups.
2. A Brevo sign-up form that puts contacts in that list and has the email field plus the two attributes.
   Copy its address (Share > HTML) into `site.config.js` > `newsletter.alerts.form`.
3. Repository variable `BREVO_ALERT_LIST` = that list's ID (currently 13). `BREVO_SEND=1` sends for real.

Alert emails are sent one per person through Brevo's transactional email, which shares the free plan's
300-a-day limit with the digests; `ALERT_MAX` (default 200) caps alert emails per run.

## Checking LinkedIn reliably (paid proxy, a few dollars a month)

LinkedIn refuses searches from GitHub's servers, so without help jobs show "LinkedIn not checked".
Routing only the LinkedIn searches through a rotating residential proxy fixes this; Indeed and Google
are still searched directly, which keeps the proxy traffic small.

1. Buy a rotating residential proxy plan billed per GB (for example Webshare, about $3.50 for 1 GB).
2. Copy its connection string, `username:password@host:port`.
3. Repository secret `JOBSPY_PROXIES` = that string; variable `JOBSPY_SITES` = `indeed,linkedin`
   (and secret `JOBSEARCH_PROVIDER` = `jobspy` if it isn't set).

Optional: `JOBSPY_PROXY_SITES` lists the sites sent through the proxy (default `linkedin`).

## Location search

Visitors can tick several areas at once (for example Herzliya and Ramat Gan / Givatayim / Bnei Brak),
and/or pick a town in the **Near** box (English or Hebrew) with a distance (5, 10, 20 or 40 km). A job
matches if it is in any ticked area or within the distance of the town. "Nearest first" sorts by distance.

Job locations are turned into map coordinates when the site is built (`crawler/geo.py`), using
`crawler/places_il.tsv`: every Israeli place with 500+ people from [GeoNames](https://www.geonames.org)
(CC BY 4.0), with Hebrew and other spellings. Office parks and odd spellings (Matam, Har Hotzvim,
"Petach Tikva") are in `IL_ALIASES` in `crawler/geo.py`; add more there.

## Security jobs

Security jobs are split into four groups (`SECURITY_KINDS` in `crawler/cs.py`):
- **Security: hardware & chips**: silicon, firmware, embedded and device security (hardware engineers). An
  unspecific title such as "Security Architect" at a chip or device maker (NVIDIA, Intel, Apple...) counts here.
- **Security: application & product**: AppSec, product security, DevSecOps and engineers building
  security products (programmers).
- **Security: research & offensive**: vulnerability, malware and threat research, red team, penetration testing.
- **Security: network, cloud & SOC**: everything else: SOC, incident response, network/cloud/IT security,
  GRC and CISOs ("classic" security).

## Finding more companies

`crawler/candidates.txt` lists companies to look for. Run **Actions > Find more companies > Run workflow**:
it tries each new name on Greenhouse, Lever, Ashby and SmartRecruiters (and the Workday sites listed),
adds the ones with jobs in Israel to `data/companies.json`, and lists the rest in
`data/discover-report.json`. Add names to the file any time and run it again.

## All jobs in Israel (/all/)

The crawler keeps every job located in Israel. Technology jobs (types in `crawler/cs.py`) are shown on
the main page and are the only ones in the email digests, alerts and RSS feed. Every job, including
sales, finance, healthcare, retail and other non-technology roles (types in `crawler/jobtypes.py`),
is shown on the "All jobs in Israel" page at `/all/`.

`all/index.html` is generated from `index.html` by `crawler/make_all_page.py` (the publish workflow
runs it), so edit `index.html` only. The data files are `data/site.json` (technology jobs) and
`data/site-all.json` (every job).

### Company sources and data license

`data/companies.json` combines companies found by the finder from `crawler/candidates.txt`, the
[Israeli Tech Map](https://github.com/mluggy/techmap) (about 8,000 Israeli companies, Open Database
License) and the LastRound AI ATS Company Directory (CC BY 4.0). Because it includes Tech Map data,
the company list is shared under the Open Database License (ODbL) too: anyone may reuse it, with
credit, under the same license. The site footer carries the credit.
