"""Classify a job title (and department) into a computer-science category, or None if it isn't a tech job."""
import re

# Order matters: the first match wins.
CATEGORIES = [
    ("Security", r"סייבר|אבטחת מידע|secur|cyber|penetration|pentest|red team|offensive|malware|threat|vulnerab|appsec|devsecops|soc analyst|\bsoc\b|incident respon|forensic|cryptograph"),
    ("Data & AI", r"data analyst|bi analyst|bi developer|analytics|ראי?יה ממוחשבת|נתונים|דאטה|בינה מלאכותית|למידת מכונה|\bai\b|\bml\b|machine learning|deep learning|data scien|data engineer|\bllm|nlp|computer vision|\bcv\b|genai|gen ai|mlops|ai engineer|ai research|data platform|data infra|big data|analytics engineer|\bbi\b developer|bi engineer|applied scien|research scien|data architect|prompt|inference|reinforcement|recommend"),
    ("Algorithms & research", r"אלגוריתמ|head of research|algorithm|research engineer|researcher|optimi[sz]ation|signal processing|\bdsp\b|image processing|quant(itative)? (dev|research)|physicist.*(software|algorithm)"),
    ("DevOps, cloud & SRE", r"techops|release manager|release engineer|דבאופס|devops|\bsre\b|site reliab|platform engineer|infrastructure engineer|infra engineer|cloud engineer|cloud architect|kubernetes|finops|production engineer|build engineer|release engineer|\bnoc\b|devex|developer experience|ci/cd|systems? engineer.*(linux|cloud)|dba|database (admin|engineer)|network engineer|network architect"),
    ("Chip design & hardware", r"ic design|digital design|analog ic|מהנדס.{0,3} (חשמל|אלקטרוניקה|חומרה)|asic|fpga|vlsi|rtl|\bdft\b|physical design|design verification|verification engineer|dv engineer|logic design|analog design|mixed.?signal|silicon|soc architect|chip|post.?silicon|pre.?silicon|layout engineer|cad engineer|signal integrity|board design|hardware engineer|hw engineer|electrical engineer|electronics engineer|rf engineer|\bpcb\b"),
    ("QA & testing", r"בודק|בדיקות תוכנה|\bqa\b|quality assurance|test(ing)? engineer|automation engineer|sdet|\bin test\b|verification(?!.*design)|validation engineer|tester"),
    ("Embedded & firmware", r"embedded|firmware|\bbsp\b|kernel|device driver|linux driver|real.?time|\brtos\b|low.?level|c\+\+.*(embedded|firmware)|robotics software|autonomous"),
    ("Mobile", r"android|\bios\b|mobile|swift|kotlin|flutter|react native"),
    ("Frontend & full stack", r"front.?end|frontend|full.?stack|fullstack|\bui\b engineer|ui developer|web developer|react|angular|javascript|typescript"),
    ("Backend & software engineering", r"engineering (team )?lead|head of (platform|engineering|r&d)|מפתח|תוכניתן|תכניתן|מהנדס.{0,3} תוכנה|פיתוח תוכנה|ראש.{0,3} צוות פיתוח|software|developer|programmer|back.?end|backend|engineer.*(java|python|golang|\bgo\b|c#|\.net|node|scala|rust|c\+\+)|\bswe\b|tech lead|team lead.*(r&d|dev|software|backend|engineering)|r&d (team )?lead|architect|engineering manager|group manager.*(r&d|software|engineering)|vp r&d|vp engineering|head of (engineering|r&d)|cto|member of technical staff|forward deployed|solutions? engineer|integration engineer|implementation engineer|support engineer|application engineer|compiler|game (developer|engineer)|unity developer|blockchain|smart contract|salesforce developer|sap (developer|abap)|erp developer"),
    ("IT & systems", r"\bit junior|junior it|^it\b|information systems|sap (developer|consultant|implement|abap|basis|crm)|entry-level sap|\berp\b|netsuite (developer|admin)|מערכות מידע|מנתח.{0,3} מערכות|סיסטם|תמיכה טכנית|\bit\b (engineer|specialist|manager|administrator|support|infrastructure|team)|system administrator|sysadmin|helpdesk|help desk|technical support|it operations|netsuite admin|salesforce admin|system analyst|systems analyst"),
    ("Technical product", r"product manager|product owner|technical program manager|\btpm\b|technical project manager|r&d project manager|program manager.*(r&d|software|engineering)|product designer|ux|ui/ux"),
]
_RX = [(n, re.compile(p, re.I)) for n, p in CATEGORIES]
# Titles that match a tech keyword but aren't tech jobs.
_EXCLUDE = re.compile(r"account (executive|manager)|sales (manager|director|representative|development)|\bsdr\b|\bbdr\b|recruit|talent acquisition|\bhr\b|human resources|payroll|accountant|bookkeep|controller|legal|counsel|paralegal|office manager|marketing manager|content (writer|manager)|copywriter|social media|customer success manager|buyer|procurement|planner|logistics|warehouse|technician|mechanical|chemist|biolog|clinical|nurse|physician|driver|operator|cook|cleaner|receptionist|executive assistant|administrative assistant|financial analyst|\bfp&a\b|tax|audit(?!.*it)|investor relations|public relations|\bpr\b|event", re.I)
_WEAK_EXCLUDE_OK = re.compile(r"engineer|developer|software|data|security|devops|\bqa\b|algorithm", re.I)


def category(title, department=""):
    t = title or ""
    if _EXCLUDE.search(t) and not _WEAK_EXCLUDE_OK.search(t):
        return None
    for name, rx in _RX:
        if rx.search(t):
            return name
    # Fall back on the department for generic titles ("Team Lead", "Student")
    d = department or ""
    if re.search(r"r&d|engineering|software|development|\bdev\b|data|algorithm|research|devops|security|it\b|technology", d, re.I) \
            and re.search(r"engineer|developer|lead|student|intern|architect|scientist|analyst|manager", t, re.I) \
            and not _EXCLUDE.search(t):
        return "Backend & software engineering" if not re.search(r"data|algorithm|research|security|devops", d, re.I) else \
            next((n for n, rx in _RX if rx.search(d)), "Backend & software engineering")
    return None


def level(title):
    t = title or ""
    if re.search(r"\bintern\b|internship|student|\bco-?op\b", t, re.I):
        return "Student / intern"
    if re.search(r"junior|\bjr\b|entry|graduate|new grad|associate", t, re.I):
        return "Junior"
    if re.search(r"director|\bvp\b|vice president|head of|\bcto\b|\bciso\b|group manager|(?<!product )(?<!program )(?<!project )manager|team lead|tech lead|team leader|\blead\b", t, re.I):
        return "Lead / manager"
    if re.search(r"senior|\bsr\b|staff|principal|expert|architect|distinguished", t, re.I):
        return "Senior"
    return "Mid-level / unspecified"


if __name__ == "__main__":
    for t in ["Senior Backend Engineer", "Account Executive", "Senior Malware Researcher", "Design Verification- Intern",
              "QA Automation Test Engineer", "Data Scientist", "Product Manager", "Mechanical Engineer", "Talent Acquisition Partner",
              "Algorithm Developer", "Senior DevOps Engineer", "Android App Developer", "Buyer", "Physicist", "Team Lead"]:
        print(f"{t:35s} {category(t, 'R&D')!s:30s} {level(t)}")
