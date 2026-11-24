"""General job types for jobs that aren't technology roles (used by the "All jobs in Israel" page).

Technology jobs get their type from cs.py; everything else gets one of these, worked out from the
job title (English and Hebrew). Order matters: the first match wins.
"""
import re

GENERAL = [
    ("Healthcare & medical", r"nurse|אח(ות)? |אחות|physician|רופא|doctor|pharmacist|רוקח|therapist|מטפל|dental|שיניים|psycholog|פסיכולוג|social worker|עובד(ת)? סוציאלי|paramedic|חובש|caregiver|occupational therap|physiotherap|פיזיותרפ|dietitian|דיאטנ|optometr|midwife|מיילד|radiograph|clinic"),
    ("Sales & business development", r"sales|מכירות|איש מכירות|נציג(ת)? מכירות|business development|account executive|account manager|key account|פיתוח עסקי|telemarket|טלמרקטינג|partnerships|channel manager|merchandis"),
    ("Marketing & communications", r"marketing|שיווק|brand|מותג|content|תוכן|social media|רשתות חברתיות|\bpr\b|public relations|communications|דוברות|דובר|copywriter|קופירייטר|seo|sem|ppc|growth|campaign|קמפיין|media buyer|graphic|גרפיק"),
    ("Finance & accounting", r"financ|כספים|accountant|רואה חשבון|רו\"ח|חשב|הנהלת חשבונות|bookkeep|controller|payroll|חשב(ת)? שכר|\bשכר\b|audit|ביקורת|\btax\b|מיסוי|treasur|economist|כלכלן|actuar|אקטואר|credit analyst|אשראי|billing|גבייה|accounts (payable|receivable)|fp&a|investment|השקעות|underwrit|risk analyst|ניהול סיכונים"),
    ("HR & recruiting", r"\bhr\b|human resources|משאבי אנוש|recruit|גיוס|talent|people (partner|operations)|hrbp|רווחה|compensation|benefits|learning and development|הדרכה ופיתוח"),
    ("Customer service & support", r"customer service|שירות לקוחות|call center|מוקד|מוקדנ|customer support|customer success|נציג(ת)? שירות|customer experience|help desk(?!.*it)|client services|member services"),
    ("Legal & compliance", r"legal|משפט|lawyer|עורך דין|עורכת דין|עו\"ד|attorney|counsel|יועץ משפטי|paralegal|compliance|ציות|regulatory affairs|רגולציה|contracts? manager|חוזים|privacy officer"),
    ("Operations, logistics & supply chain", r"operations|תפעול|logistic|לוגיסטיקה|supply chain|שרשרת אספקה|warehouse|מחסן|מחסנאי|procurement|רכש|קניין|buyer|planner|תכנון|shipping|import|export|יבוא|יצוא|dispatcher|סדרן|fleet|inventory|מלאי|purchas|distribution|הפצה|customs|מכס"),
    ("Manufacturing & production", r"production|ייצור|operator|מפעיל|assembly|הרכבה|machinist|חרט|welder|רתך|maintenance|אחזקה|quality control|בקרת איכות|\bqc\b|line worker|packag|אריזה|plant|מפעל|technician|טכנאי|lab assistant|מעבדה|cnc|electrician|חשמלאי|mechanic|מכונאי"),
    ("Retail, food & hospitality", r"store|חנות|cashier|קופאי|קופאית|sales associate|retail|קמעונ|waiter|waitress|מלצר|cook|טבח|chef|שף|barista|bartender|ברמן|hotel|מלון|restaurant|מסעדה|kitchen|מטבח|shift (manager|supervisor)|אחראי(ת)? משמרת|branch manager|מנהל(ת)? סניף|מנהל(ת)? חנות|housekeep|cleaner|ניקיון|host(ess)?|reception desk|front desk|קבלה|baker|אופה|butcher|קצב|deli|מעדניה|supermarket|סופרמרקט"),
    ("Construction & real estate", r"construction|בנייה|בניה|civil engineer|מהנדס(ת)? אזרחי|הנדסה אזרחית|site manager|מנהל(ת)? עבודה|מנהל(ת)? פרויקט(ים)? בנייה|real estate|נדל\"?ן|plumber|אינסטלטור|hvac|מיזוג|surveyor|מודד|architect(?!.*(software|solution|cloud|data|system|security|enterprise))|אדריכל|interior design|property manager|ניהול נכסים|facilit"),
    ("Transport & driving", r"driver|נהג|courier|שליח|delivery|משלוחים|forklift|מלגזן|truck|משאית|bus|אוטובוס|pilot|טייס|flight attendant|דייל|aviation|תעופה|ship|maritime|ימי|port|נמל|railway|רכבת"),
    ("Security & safety", r"security guard|guard|מאבטח|מאבטחת|שמירה|שומר|קב\"ט|security officer(?!.*(information|cyber|it))|safety|בטיחות|emergency|firefight|כבאי|loss prevention"),
    ("Education & training", r"teacher|מורה|instructor|מדריך|מדריכה|trainer|tutor|גננת|kindergarten|גן ילדים|educat|חינוך|lecturer|מרצה|professor|course|academ"),
    ("Admin & office", r"office|משרד|secretary|מזכיר|מזכירה|receptionist|פקיד|פקידה|admin|אדמיניסטרציה|executive assistant|עוזר(ת)? אישי|personal assistant|clerk|data entry|הקלדה|back office|בק אופיס|coordinator|רכז|רכזת|scheduler"),
    ("Management", r"general manager|\bceo\b|\bcoo\b|\bcfo\b|managing director|מנכ\"?ל|סמנכ\"?ל|vp |vice president|director|מנהל(ת)? (כללי|אגף|מחלקה)|head of|country manager|branch director"),
]
_RX = [(n, re.compile(r, re.I)) for n, r in GENERAL]
NAMES = [n for n, _ in GENERAL] + ["Other"]


def general(title, department=""):
    """General job type for a non-technology job."""
    t = title or ""
    for name, rx in _RX:
        if rx.search(t):
            return name
    d = department or ""
    for name, rx in _RX:
        if d and rx.search(d):
            return name
    return "Other"


if __name__ == "__main__":
    for t in ["Store Manager", "נציג/ת שירות לקוחות", "Registered Nurse", "Account Executive", "מנהל/ת חשבונות",
              "Forklift Driver", "מאבטח/ת", "Payroll Specialist", "Production Operator", "HRBP", "Barista",
              "Legal Counsel", "Logistics Coordinator", "Office Manager", "Civil Engineer", "VP Marketing"]:
        print(f"{t:32s} -> {general(t)}")
