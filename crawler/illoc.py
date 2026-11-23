"""Decide whether a job location is in Israel, and which region it's in."""
import re

CITIES = {
    "Tel Aviv": r"tel[ -]?aviv|\btlv\b|tel-aviv-yafo|jaffa|toha|sarona|hashmonaim|תל[ -]?אביב",
    "Herzliya": r"herzl?iy?y?a|herzelia|herzeliya|glil[ -]?yam|הרצליה",
    "Petah Tikva": r"pet[ae]c?h[ -]?tikv?a|petach|kiryat arye|kiryat aryeh|פתח[ -]?תקו",
    "Ramat Gan / Givatayim / Bnei Brak": r"ramat[ -]?gan|giv'?atayim|bnei[ -]?brak|bursa|kiryat[ -]?ono|רמת[ -]?גן",
    "Haifa": r"haifa|matam|\bmtm\b|חיפה",
    "Jerusalem": r"jerusalem|har hotzvim|malha|mevaseret|beit[ -]?shemesh|ירושלים",
    "Ra'anana / Kfar Saba / Hod Hasharon": r"ra'?anana|k[e]?f[ae]r[ -]?sa[bv]a|hod[ -]?ha'?[ -]?sharon|ramat[ -]?hasharon|\bsharon\b|שרון|רעננה|כפר[ -]?סבא",
    "Netanya": r"netanya|נתניה",
    "Yokneam / Caesarea / North": r"yo[kq]ne'?am|caesarea|migdal[ -]?ha'?emek|nazareth|nof hagalil|karmiel|tefen|kiryat[ -]?shmona|misgav|tirat carmel|zichron|afula|nesher|or akiva|tel hai|kiryat[ -]?bialik|yagur|yizr[ae]'?el|beit[ -]?she'?an|krayot|kiryat[ -]?(ata|motzkin|yam|tivon)|יקנעם",
    "Rehovot / Ness Ziona / Yavne": r"rehovot|ne?ss?[ -]?ziona|yavne|gedera|רחובות",
    "Rishon / Holon / Bat Yam": r"rishon|holon|bat[ -]?yam|be'?er[ -]?ya'?a?kov",
    "Airport City / Or Yehuda / Lod / Modi'in": r"airport|or[ -]?yehuda|\blod\b|modi'?in|yehud|shoham|rosh[ -]?ha'?ayin|el'?ad",
    "South (Be'er Sheva / Kiryat Gat / Ashdod)": r"be'?er[ -]?sheva|beersheba|kiryat[ -]?gat|ashdod|ashkelon|sderot|dimona|omer|yeruham|eilat|באר[ -]?שבע",
}
_CITY_RX = {k: re.compile(v, re.I) for k, v in CITIES.items()}
_IL = re.compile(r"\bisrael\b|\bisr\b|^il\s*[-,:]|\(il\)|"
                 + "|".join(CITIES.values()), re.I)
# Places whose names clash with the "IL" abbreviation (Illinois) etc.
_NOT = re.compile(r"illinois|chicago|\bil \d{5}|, il,? (usa|us|united states)", re.I)


def is_il(location):
    loc = location or ""
    if not loc.strip():
        return False
    if _NOT.search(loc) and not re.search(r"israel", loc, re.I):
        return False
    return bool(_IL.search(loc))


def region(location):
    for name, rx in _CITY_RX.items():
        if rx.search(location or ""):
            return name
    if re.search(r"remote|hybrid|home", location or "", re.I):
        return "Remote / hybrid"
    if re.search(r"\bcenter\b|central", location or "", re.I):
        return "Center (unspecified)"
    return "Israel (other / unspecified)"


if __name__ == "__main__":
    for t in ["Tel Aviv-Yafo", "Israel - Tel Aviv", "Chicago, IL", "IL - Petah Tikva", "Rehovot,ISR",
              "Migdal Ha'emek, Israel", "Springfield, IL", "Yokneam", "TLV - ISR", "London, UK"]:
        print(f"{t:28s} {is_il(t)!s:6s} {region(t)}")
