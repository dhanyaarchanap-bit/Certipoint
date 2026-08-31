"""
Information Extraction Engine for Certificates.
Extracts Student Name, Activity/Event Name, Date, Issuing Organization,
and Certificate Identification Numbers from raw OCR/PDF text.
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from rapidfuzz import fuzz


# Known prominent educational and technical organizations for fuzzy detection
KNOWN_ORGANIZATIONS = [
    "NPTEL", "SWAYAM", "IIT Madras", "IIT Bombay", "IIT Kharagpur", "IIT Delhi", "IIT Roorkee",
    "Coursera", "edX", "Udemy", "Great Learning", "Simplilearn", "Cognitive Class",
    "APJ Abdul Kalam Technological University", "KTU",
    "IEEE", "IEEE Computer Society", "ACM", "CSI", "Computer Society of India",
    "ISTE", "IEDC", "TinkerHub Foundation", "ICFOSS", "Kerala Startup Mission (KSUM)",
    "Google", "Google Cloud", "Microsoft", "AWS", "Amazon Web Services", "Oracle", "IBM", "Intel",
    "Cisco Networking Academy", "HackerRank", "LeetCode", "Kaggle", "Postman", "Red Hat",
    "College of Engineering Trivandrum", "TKM College of Engineering", "Government Engineering College",
    "Model Engineering College", "Mar Athanasius College of Engineering", "NSS College of Engineering",
    "NIT Calicut", "National Institute of Technology"
]


def clean_text_whitespace(text: str) -> str:
    """Normalize repeated whitespace, tabs, and newlines."""
    if not text:
        return ""
    return re.sub(r"[ \t]+", " ", text).strip()


def extract_student_name(raw_text: str, candidate_name: Optional[str] = None) -> Optional[str]:
    """
    Extract student name from certificate text using regex heuristics and optional fuzzy matching.
    """
    if not raw_text:
        return candidate_name

    # 1. Look for standard certificate phrasing patterns
    patterns = [
        r"(?:this is to certify that|certifies that|awarded to|presented to|proudly presented to|this certificate is presented to)\s+(?:Mr\.|Ms\.|Mrs\.|Dr\.)?\s*([A-Za-z\.\s]{3,40}?)(?:\s+(?:of|has|bearing|student|register|from|successfully|participated|son|daughter|completed|in recognition|\n))",
        r"(?:conferred upon|is awarded to)\s+(?:Mr\.|Ms\.|Mrs\.|Dr\.)?\s*([A-Za-z\.\s]{3,40}?)(?:\s+(?:of|has|for|bearing|\n))",
        r"(?:Name\s*:\s*)([A-Za-z\.\s]{3,40})",
        r"(?:Student Name\s*:\s*)([A-Za-z\.\s]{3,40})",
        r"(?:Participant\s*:\s*)([A-Za-z\.\s]{3,40})"
    ]

    for pat in patterns:
        match = re.search(pat, raw_text, re.IGNORECASE)
        if match:
            extracted = clean_text_whitespace(match.group(1))
            # Filter out non-name false positives
            if len(extracted) >= 3 and not any(bad in extracted.lower() for bad in ["successfully", "completion", "workshop", "course", "college", "university"]):
                # Clean prefix titles
                extracted = re.sub(r"^(?:Mr\.|Ms\.|Mrs\.|Dr\.|Shri|Smt)\s+", "", extracted, flags=re.IGNORECASE).strip()
                return extracted.title()

    # 2. Fuzzy match candidate name against lines if provided
    if candidate_name and candidate_name.strip():
        lines = [line.strip() for line in raw_text.splitlines() if len(line.strip()) > 3]
        best_match = None
        best_score = 0
        cand_clean = candidate_name.strip().lower()

        for line in lines:
            score = fuzz.partial_ratio(cand_clean, line.lower())
            if score > best_score and score >= 80:
                best_score = score
                best_match = candidate_name.strip().title()

        if best_match:
            return best_match

    return None


def extract_activity_name(raw_text: str, selected_category: Optional[str] = None) -> Optional[str]:
    """
    Extract the title of the event, course, workshop, or competition.
    """
    if not raw_text:
        return selected_category

    # 1. Search for quoted strings (often the exact title of the event or course)
    quoted_matches = re.findall(r'["“]([^"”\n\r]{4,90})["”]', raw_text)
    for q in quoted_matches:
        q_clean = clean_text_whitespace(q)
        if len(q_clean) >= 4 and not any(bad in q_clean.lower() for bad in ["certificate", "completion", "merit", "excellence", "presented to"]):
            return q_clean.title()

    # 2. Structured labeled lines
    label_patterns = [
        r"(?:Course Title|Course Name|Event Name|Activity Name|Topic|Subject|Title|Workshop on|Webinar on|Hackathon)\s*:\s*([^\n\r]+)",
        r"(?:completed a course on|for successfully completing the course|course on|workshop on|bootcamp on|training on|internship on)\s+[\"“']?([^\"\n\r\.\,]+)[\"”']?",
        r"(?:participated in|completed the|attended the)\s+(?:and active[a-z\s]+in\s+)?(?:the\s+)?(?:[A-Za-z\s]+:\s*[\n\r]+)?[\"“']?([^\"\n\r\.\,]+(?:Workshop|Bootcamp|Course|Hackathon|Internship|Training|Program|Competition|Conference|Presentation|Symposium|Quiz)?[^\"\n\r\.\,]*)[\"”']?",
        r"(?:online course on|certification on|masterclass on)\s+[\"“']?([^\n\r\"'\,]+)[\"”']?"
    ]

    for pat in label_patterns:
        match = re.search(pat, raw_text, re.IGNORECASE)
        if match:
            activity = clean_text_whitespace(match.group(1))
            # Clean common trailing artifacts
            activity = re.sub(r"(?:organized by|conducted by|held on|from|during).*$", "", activity, flags=re.IGNORECASE).strip()
            # If it captured a generic label like "NPTEL Course:", skip
            if activity.lower().endswith("course:") or activity.lower().endswith("workshop:") or activity.lower() in ["the nptel course", "the workshop", "the internship", "the hackathon"]:
                continue
            if len(activity) >= 4 and len(activity) <= 90:
                return activity.title()

    # 3. Heuristic search based on technical and event keywords
    lines = [clean_text_whitespace(line) for line in raw_text.splitlines() if len(clean_text_whitespace(line)) > 4]
    for line in lines:
        line_clean = line.strip('"“\' ')
        if any(keyword in line_clean.lower() for keyword in ["programming", "data structures", "deep learning", "machine learning", "artificial intelligence", "data science", "cybersecurity", "cloud computing", "iot", "robotics", "web development", "hacksphere", "hackathon", "internship", "workshop", "embedded systems"]):
            if len(line_clean) < 80 and not any(header in line_clean.lower() for header in ["certificate", "certify", "presented to", "participated in"]):
                return line_clean.title()

    return selected_category


def extract_date(raw_text: str) -> Optional[str]:
    """
    Extract date from certificate text and format as standardized string.
    """
    if not raw_text:
        return None

    # 1. DD/MM/YYYY or DD-MM-YYYY
    match = re.search(r"\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{2,4})\b", raw_text)
    if match:
        day, month, year = match.groups()
        if len(year) == 2:
            year = f"20{year}"
        try:
            # Check if day and month are valid
            d, m, y = int(day), int(month), int(year)
            if 1 <= d <= 31 and 1 <= m <= 12 and 2015 <= y <= 2030:
                return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass

    # 2. Month DD, YYYY or DD Month YYYY (e.g. August 15, 2023 or 15 August 2023)
    months = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    
    # Example: 15 August 2023 / 15th August 2023
    match_named_1 = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({months})\s*,?\s*(\d{{4}})\b", raw_text, re.IGNORECASE)
    if match_named_1:
        d_str, m_str, y_str = match_named_1.groups()
        return f"{d_str} {m_str[:3].title()} {y_str}"

    # Example: August 15, 2023
    match_named_2 = re.search(rf"\b({months})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", raw_text, re.IGNORECASE)
    if match_named_2:
        m_str, d_str, y_str = match_named_2.groups()
        return f"{d_str} {m_str[:3].title()} {y_str}"

    # 3. NPTEL session formats like Jul-Oct 2023 or Jan-Apr 2024
    match_session = re.search(rf"\b({months})\s*[-–]\s*({months})\s+(\d{{4}})\b", raw_text, re.IGNORECASE)
    if match_session:
        m1, m2, yr = match_session.groups()
        return f"{m1[:3].title()}-{m2[:3].title()} {yr}"

    # 4. YYYY-MM-DD format
    match_iso = re.search(r"\b(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})\b", raw_text)
    if match_iso:
        y, m, d = match_iso.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    return None


def extract_organization(raw_text: str) -> Optional[str]:
    """
    Extract issuing body, university, or organizing institution.
    """
    if not raw_text:
        return None

    # 1. Check known organizations list
    for org in KNOWN_ORGANIZATIONS:
        if re.search(rf"\b{re.escape(org)}\b", raw_text, re.IGNORECASE):
            return org

    # 2. Regex for 'Organized by' / 'Issued by' / 'Offered by'
    patterns = [
        r"(?:organized by|conducted by|offered by|issued by|presented by)\s+([A-Za-z0-9\s,\.\-&]{4,60}?)(?:\s+(?:in association|held on|on|at|during|\n))",
        r"(?:Department of\s+[A-Za-z\s]+,\s*([A-Za-z\s]{4,60}))",
        r"([A-Za-z\s]+(?:College of Engineering|Institute of Technology|University|Solutions Pvt Ltd|Technologies))\b"
    ]

    for pat in patterns:
        match = re.search(pat, raw_text, re.IGNORECASE)
        if match:
            org_extracted = clean_text_whitespace(match.group(1))
            if len(org_extracted) >= 4:
                return org_extracted.title()

    return None


def extract_certificate_number(raw_text: str) -> Optional[str]:
    """
    Extract Certificate ID / Serial Number / Roll No / Credential Code.
    """
    if not raw_text:
        return None

    # 1. NPTEL standard ID format (e.g., NPTEL23CS45S12345678)
    nptel_match = re.search(r"\b(NPTEL\d{2}[A-Z]{2}\d{2,4}[A-Z0-9]{4,12})\b", raw_text, re.IGNORECASE)
    if nptel_match:
        return nptel_match.group(1).upper()

    # 2. Explicit labels (Certificate No, Cert ID, Roll No, Verification Code, Credential ID)
    patterns = [
        r"(?:Certificate\s*(?:No|Number|ID|Code)|Cert\s*ID|Credential\s*ID|Verification\s*(?:Code|ID)|Ref\s*(?:No|ID))\s*[:#\-]?\s*([A-Z0-9\-_/]{5,35})\b",
        r"(?:Roll\s*No|Reg\s*No)\s*[:#\-]?\s*([A-Z0-9\-_/]{6,25})\b"
    ]

    for pat in patterns:
        match = re.search(pat, raw_text, re.IGNORECASE)
        if match:
            cert_no = match.group(1).strip().strip(".:-")
            if len(cert_no) >= 5 and not cert_no.isdigit():
                return cert_no.upper()
            elif len(cert_no) >= 5:
                return cert_no

    return None


def extract_all_certificate_info(raw_text: str, student_name_input: Optional[str] = None,
                                 activity_category_input: Optional[str] = None) -> Dict[str, Any]:
    """
    Unified extraction pipeline that parses all certificate entities and aggregates metadata.
    """
    extracted_name = extract_student_name(raw_text, student_name_input)
    extracted_activity = extract_activity_name(raw_text, activity_category_input)
    extracted_date = extract_date(raw_text)
    extracted_org = extract_organization(raw_text)
    cert_no = extract_certificate_number(raw_text)

    return {
        "extracted_name": extracted_name,
        "extracted_activity": extracted_activity,
        "extracted_date": extracted_date,
        "extracted_organization": extracted_org,
        "certificate_number": cert_no,
        "raw_text_length": len(raw_text) if raw_text else 0
    }
