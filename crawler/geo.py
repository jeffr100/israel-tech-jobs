"""Turn job locations into map coordinates, for the "near a place, within a distance" search.

Place names and coordinates come from GeoNames (geonames.org, CC BY 4.0), saved in
crawler/places_<country>.tsv (every place with 500 or more people, with other spellings, including
Hebrew for Israel).

    coords("South San Francisco, CA; Boston, MA")  ->  [[37.6547, -122.4077], [42.3584, -71.0598]]
    anchors()   the place list the website's "Near" box offers: [[label, lat, lon, other names], ...]
    anchor("Waltham, MA")  ->  (42.3765, -71.2356)
"""
import math
import os
import re
import unicodedata

COUNTRY = "il"   # "us" or "il"
HERE = os.path.dirname(os.path.abspath(__file__))
_PLACES = None

ST = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
      "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
      "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
      "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
      "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
      "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
      "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
      "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
      "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
      "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico"}
_ST_NAME = {v.lower(): k for k, v in ST.items()}
_ST_RX = re.compile(r"\b(" + "|".join(ST) + r")\b|\b(" + "|".join(ST.values()) + r")\b", re.I)

# Common ways job boards name a metro area instead of a town.
US_ALIASES = {"bay area": ("San Francisco", "CA"), "sf bay area": ("San Francisco", "CA"),
              "san francisco bay area": ("San Francisco", "CA"), "silicon valley": ("San Jose", "CA"),
              "greater boston": ("Boston", "MA"), "boston area": ("Boston", "MA"), "boston metro": ("Boston", "MA"),
              "research triangle park": ("Durham", "NC"), "rtp": ("Durham", "NC"), "research triangle": ("Durham", "NC"),
              "nyc": ("New York City", "NY"), "new york city": ("New York City", "NY"),
              "washington dc": ("Washington", "DC"), "washington d c": ("Washington", "DC"), "dc metro": ("Washington", "DC"),
              "south sf": ("South San Francisco", "CA"), "ssf": ("South San Francisco", "CA"),
              "greater philadelphia": ("Philadelphia", "PA"), "twin cities": ("Minneapolis", "MN"),
              "greater seattle": ("Seattle", "WA"), "greater chicago": ("Chicago", "IL"), "la jolla": ("San Diego", "CA"),
              "torrey pines": ("San Diego", "CA"), "kendall square": ("Cambridge", "MA")}
# Israel: places the job boards use that GeoNames doesn't list as towns.
IL_ALIASES = {"matam": "Haifa", "mtm": "Haifa", "har hotzvim": "Jerusalem", "malha": "Jerusalem",
              "airport city": "Lod", "kiryat atidim": "Tel Aviv", "sarona": "Tel Aviv", "tlv": "Tel Aviv",
              "glil yam": "Herzliya", "herzliya pituach": "Herzliya", "herzeliya": "Herzliya", "herzelia": "Herzliya",
              "petach tikva": "Petah Tikva", "petach tikvah": "Petah Tikva", "petah tikvah": "Petah Tikva",
              "kfar saba": "Kfar Saba", "raanana": "Ra'anana", "yokneam": "Yoqne‘am ‘Illit", "yoqneam": "Yoqne‘am ‘Illit",
              "caesarea": "Caesarea", "beer sheva": "Beersheba", "beersheva": "Beersheba", "rishon lezion": "Rishon LeZiyyon",
              "rishon le zion": "Rishon LeZiyyon", "rishon": "Rishon LeZiyyon", "ness ziona": "Nes Ziyyona", "nes ziona": "Nes Ziyyona",
              "modiin": "Modi‘in Makkabbim Re‘ut", "hod hasharon": "Hod HaSharon", "ramat hasharon": "Ramat HaSharon",
              "tel aviv yafo": "Tel Aviv", "tel aviv jaffa": "Tel Aviv", "jaffa": "Tel Aviv", "bnei brak": "Bnei Brak",
              "tefen": "Ma'alot Tarshiha", "misgav": "Karmiel", "kiryat gat": "Kiryat Gat", "migdal haemek": "Migdal Ha‘Emeq",
              "nazareth illit": "Nof HaGalil", "or yehuda": "Or Yehuda", "rosh haayin": "Rosh Ha‘Ayin",
              "kiryat ono": "Kiryat Ono", "givatayim": "Giv‘atayim", "bat yam": "Bat Yam", "zichron yaakov": "Zikhron Ya‘aqov"}
# Region names from illoc.py: a stand-in town when a job names only the region.
IL_REGION_TOWN = {"Tel Aviv": "Tel Aviv", "Herzliya": "Herzliya", "Petah Tikva": "Petah Tikva",
                  "Ramat Gan / Givatayim / Bnei Brak": "Ramat Gan", "Haifa": "Haifa", "Jerusalem": "Jerusalem",
                  "Ra'anana / Kfar Saba / Hod Hasharon": "Ra'anana", "Netanya": "Netanya",
                  "Rehovot / Ness Ziona / Yavne": "Rehovot", "Rishon / Holon / Bat Yam": "Holon",
                  "Airport City / Or Yehuda / Lod / Modi'in": "Lod"}
# Words that are also (tiny) place names but in a job location mean something else.
_STOP = {"israel", "center", "central", "north", "south", "remote", "hybrid", "office", "home", "main", "global",
         "headquarters", "hq", "campus", "site", "plant", "area", "region", "district", "office", "any", "multiple",
         "united states", "usa", "us", "america", "onsite", "on site", "field", "national", "nationwide", "virtual"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"['’‘`\"״׳]", "", s.lower())
    s = re.sub(r"\bst\.?\s", "saint ", s)
    s = re.sub(r"\bft\.?\s", "fort ", s)
    s = re.sub(r"\bmt\.?\s", "mount ", s)
    return re.sub(r"[^a-z0-9֐-׿]+", " ", s).strip()


def key(s):
    return norm(s).replace(" ", "")


def _load():
    """name index: (key, region) -> (lat, lon, pop, name); for Israel region is ""."""
    global _PLACES
    if _PLACES is not None:
        return _PLACES
    idx, by_name, rows = {}, {}, []
    for line in open(os.path.join(HERE, f"places_{COUNTRY}.tsv"), encoding="utf-8"):
        if line.startswith("#"):
            continue
        name, reg, lat, lon, pop, alts = (line.rstrip("\n").split("\t") + [""])[:6]
        rec = (float(lat), float(lon), int(pop), name, reg)
        rows.append(rec)
        names = [name, name.split(",")[0]] + [a for a in alts.split("|") if a]
        for n in names:
            k = key(n)
            # very short or common-word names would match ordinary words in a location
            if len(k) < (3 if re.search(r"[֐-׿]", k) else 5 if n != name else 3) or norm(n) in _STOP:
                continue
            if (k, reg) not in idx or idx[(k, reg)][2] < rec[2]:
                idx[(k, reg)] = rec
            if n in (name, name.split(",")[0]):   # a town named without its state: official names only
                by_name.setdefault(k, []).append(rec)
    _PLACES = (idx, by_name, rows)
    return _PLACES


def _find(name, reg=""):
    return _load()[0].get((key(name), reg))


_COUNTRY_WORDS = {"us", "usa", "u s", "u s a", "united states", "united states of america", "america"}
_NOISE = re.compile(r"\b(remote|hybrid|on.?site|onsite|office|campus|headquarters|hq|site|plant|lab|area|metro|"
                    r"greater|downtown|location|locations|field based|home based|virtual)\b", re.I)


def _city(text, st):
    """A town in state st named at the end of text ("Hybrid in South San Francisco")."""
    idx = _load()[0]
    words = norm(_NOISE.sub(" ", text)).split()
    for start in range(0, len(words)):
        for n in range(min(4, len(words) - start), 0, -1):   # longest run of words first
            r = idx.get(("".join(words[start:start + n]), st))
            if r:
                return r
    return None


def _us_segment(seg, prefer=()):
    idx, by_name, _ = _load()
    out = []
    low = norm(seg)
    for a, (city, st) in US_ALIASES.items():
        if re.search(r"\b" + a + r"\b", low):
            r = _find(city, st)
            if r:
                out.append(r)
    # "US-CA-South San Francisco" -> "US, CA, South San Francisco"; "Burlington NC" -> "Burlington, NC"
    t = re.sub(r"\b(USA?|[A-Z]{2})-(?=[A-Z])", r"\1, ", seg)
    t = re.sub(r"\b([A-Z]{2})\s+(USA?|United States)\b", r"\1, \2", t)   # "Cambridge, MA USA"
    t = re.sub(r"([a-z.])\s+([A-Z]{2})\b(?![a-z])", lambda m: m.group(1) + ", " + m.group(2) if m.group(2) in ST else m.group(0), t)
    tokens = [x.strip() for x in re.split(r"\s*,\s*|\s+[-–—|]\s+|\s*[()]\s*|\s*:\s*", t) if x and x.strip()]
    states = []
    for i, x in enumerate(tokens):
        if re.fullmatch(r"[A-Z]{2}", x) and x in ST and x not in ("US",):
            states.append((i, x))
        elif x.lower() in _ST_NAME:
            states.append((i, _ST_NAME[x.lower()]))
    abbr_at = {k for k, x in states if re.fullmatch(r"[A-Z]{2}", tokens[k])}
    # a spelled-out state name can also be a town ("New York, NY", "Washington, DC")
    places = [(i, x) for i, x in enumerate(tokens) if norm(x) not in _COUNTRY_WORDS and i not in abbr_at]
    if states:
        for si, st in states:
            # the town is usually right before the state ("Boston, MA"), else after it ("US - MA - Boston")
            order = sorted((p for p in places if p[0] != si), key=lambda p: (p[0] > si, abs(p[0] - si)))
            for _, x in order:
                r = _city(x, st)
                if r:
                    out.append(r)
                    break
    elif not out:
        # no state: a town name that is unique enough ("TARRYTOWN", "San Francisco")
        for _, x in places:
            k = key(_NOISE.sub(" ", x))
            if len(k) < 4 or norm(x) in _STOP:
                continue
            cands = sorted({(r[3], r[4]): r for r in by_name.get(k, [])}.values(), key=lambda r: -r[2])
            liked = [r for r in cands if r[4] in prefer]   # a state where the company has other jobs
            if liked:
                out.append(liked[0])
                break
            if cands and (len(cands) == 1 or cands[1][2] * 5 < cands[0][2]):
                out.append(cands[0])
                break
    return out


def _il_segment(seg):
    idx, _, _ = _load()
    out = []
    low = norm(seg)
    for a, town in IL_ALIASES.items():
        if re.search(r"(?<![a-z])" + a + r"(?![a-z])", low):
            r = _find(town)
            if r:
                out.append(r)
    words = low.split()
    i = 0
    while i < len(words):
        hit = None
        for n in range(min(4, len(words) - i), 0, -1):
            g = "".join(words[i:i + n])
            r = idx.get((g, "")) or (idx.get((g[1:], "")) if n == 1 and g[:1] in "בלמו" and len(g) > 3 else None)
            if r:
                hit = (r, n)
                break
        if hit:
            out.append(hit[0])
            i += hit[1]
        else:
            i += 1
    return out


def _records(location, region=None, prefer=()):
    out = []
    for seg in re.split(r";|\||\n|\s/\s|\bor\b|•", location or ""):
        if seg.strip():
            out += _us_segment(seg, prefer) if COUNTRY == "us" else _il_segment(seg)
    if not out and COUNTRY == "il" and region in IL_REGION_TOWN:
        r = _find(IL_REGION_TOWN[region])
        if r:
            out.append(r)
    return out


def coords(location, region=None, prefer=()):
    """[[lat, lon], ...] for every place a job location names (empty if none is known)."""
    seen, res = set(), []
    for r in _records(location, region, prefer):
        p = (round(r[0], 3), round(r[1], 3))
        if p not in seen:
            seen.add(p)
            res.append(list(p))
    return res[:15]


def place_jobs(jobs):
    """Set j["geo"] on one company's jobs. A town named without its state ("Sleepy Hollow") is taken
    to be in a state where the same company has other jobs."""
    states = {}
    for j in jobs:
        for r in _records(j.get("location"), j.get("region")):
            states[r[4]] = states.get(r[4], 0) + 1
    prefer = sorted(states, key=lambda s: -states[s])
    for j in jobs:
        g = coords(j.get("location"), j.get("region"), prefer)
        if g:
            j["geo"] = g
        else:
            j.pop("geo", None)


def anchors():
    """Places offered in the website's "Near" box: [[label, lat, lon, other names], ...], biggest first."""
    _, _, rows = _load()
    out = []
    if COUNTRY == "us":
        nick = {}
        for a, (city, st) in US_ALIASES.items():
            nick.setdefault((city, st), []).append(a)
        for lat, lon, pop, name, st in rows:
            if pop >= 8000:
                out.append([f"{name}, {st}", round(lat, 3), round(lon, 3), " ".join(nick.get((name, st), []))])
    else:
        seen_labels = set()
        rows_il = []
        for line in open(os.path.join(HERE, "places_il.tsv"), encoding="utf-8"):
            if not line.startswith("#"):
                rows_il.append(line)
        rows_il.sort(key=lambda l: -int(l.split("\t")[4]))
        for line in rows_il:
            if line.startswith("#"):
                continue
            name, _, lat, lon, pop, alts = (line.rstrip("\n").split("\t") + [""])[:6]
            if int(pop) >= 1000:
                heb = sorted({re.sub("[\u0591-\u05c7]", "", a) for a in alts.split("|") if re.search("[\u05d0-\u05ea]", a)}, key=len)[:2]
                lat_alts = [a for a in alts.split("|") if re.fullmatch(r"[A-Za-z' -]{5,}", a) and "Lungsod" not in a][:4]
                label = il_label(name)
                if label in seen_labels:
                    continue   # two places with one everyday name: keep the bigger (listed first)
                seen_labels.add(label)
                out.append([label, round(float(lat), 3), round(float(lon), 3), " ".join(([name] if name != label else []) + heb + lat_alts)])
    return out


# Everyday English spellings for Israeli towns whose GeoNames name is a scholarly one.
IL_LABELS = {"Rishon LeTsiyyon": "Rishon LeZion", "Petaẖ Tiqva": "Petah Tikva", "H̱olon": "Holon", "Reẖovot": "Rehovot",
             "Modi‘in Makkabbim Re‘ut": "Modi'in", "Rosh Ha‘Ayin": "Rosh HaAyin", "Nahariyya": "Nahariya", "Yavné": "Yavne",
             "Karmi’el": "Karmiel", "Pardés H̱anna Karkur": "Pardes Hanna-Karkur", "Naẕerat ‘Illit": "Nof HaGalil",
             "Qiryat Motsqin": "Kiryat Motzkin", "Ofaqim": "Ofakim", "Yehud-Monosson": "Yehud-Monosson",
             "Be’er Ya‘aqov": "Be'er Ya'akov", "Qiryat Mal’akhi": "Kiryat Malakhi", "Mevasseret Tsiyyon": "Mevaseret Zion",
             "Yoqne‘am ‘Illit": "Yokneam", "Zikhron Ya‘aqov": "Zichron Ya'akov", "maalot Tarshīhā": "Ma'alot-Tarshiha",
             "Migdal Ha‘Emeq": "Migdal HaEmek", "El‘ad": "Elad", "Beersheba": "Be'er Sheva", "Acre": "Akko",
             "Safed": "Tzfat", "Yoqne‘am": "Yokneam Moshava", "Qazrin": "Katzrin", "Ma‘ale Adummim": "Ma'ale Adumim"}


def il_label(name):
    if name in IL_LABELS:
        return IL_LABELS[name]
    t = unicodedata.normalize("NFKD", name)
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).replace("‘", "'").replace("’", "'")
    t = re.sub(r"^Qiryat\b", "Kiryat", t)
    return t[:1].upper() + t[1:]


def anchor(label):
    for a in anchors():
        if a[0] == label:
            return a[1], a[2]
    return None


def distance(a, b):
    """Great-circle distance in km."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))
