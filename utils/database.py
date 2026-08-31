"""
Database utility module for KTU Activity Point Verification Assistant.
Handles SQLite database connection, initialization, migrations, and CRUD operations.
"""

import os
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

# Default Database Path
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database")
DB_PATH = os.path.join(DB_DIR, "certipoint.db")
SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Create and return a SQLite database connection with row factory enabled."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize database tables and default activity point rules if not already present."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            cursor.executescript(f.read())
    else:
        # Fallback inline schema
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_number TEXT UNIQUE NOT NULL,
            student_name TEXT NOT NULL,
            email TEXT,
            branch TEXT DEFAULT 'Computer Science and Engineering',
            semester TEXT DEFAULT 'S6',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_number TEXT NOT NULL,
            activity_category TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT,
            file_hash TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (register_number) REFERENCES students(register_number) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS extraction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_id INTEGER NOT NULL UNIQUE,
            extracted_name TEXT,
            extracted_activity TEXT,
            extracted_date TEXT,
            extracted_organization TEXT,
            certificate_number TEXT,
            confidence_score REAL DEFAULT 0.0,
            raw_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (certificate_id) REFERENCES certificates(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_id INTEGER NOT NULL UNIQUE,
            suggested_points INTEGER DEFAULT 0,
            awarded_points INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Manual Verification Required',
            faculty_remark TEXT,
            approved_by TEXT,
            approval_date TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (certificate_id) REFERENCES certificates(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS activity_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL,
            default_points INTEGER NOT NULL,
            max_points INTEGER NOT NULL,
            description TEXT
        );
        """)

    # Seed standard KTU Activity Point rules if empty
    cursor.execute("SELECT COUNT(*) as count FROM activity_rules")
    if cursor.fetchone()["count"] == 0:
        default_rules = [
            ("NPTEL Course", 20, 50, "NPTEL / SWAYAM / Coursera MOOC online certification courses with minimum 4-12 weeks duration."),
            ("Workshop", 10, 20, "Technical workshops organized by recognized colleges, universities, or tech organizations (1-5 days)."),
            ("Internship", 20, 40, "Industrial / Corporate internship in recognized company or research organization (min 5-14 days)."),
            ("Technical Quiz", 5, 15, "Inter-college or State/National level technical quiz and competition events."),
            ("Hackathon", 15, 30, "Software or Hardware hackathon participation, finalist, or prize winner."),
            ("Paper Presentation", 15, 30, "Technical paper publication or presentation in IEEE/Springer/National/International conference."),
            ("Industrial Visit", 5, 10, "Approved industrial training or industry visit organized by department."),
            ("NSS / NCC / Community Service", 15, 30, "National Service Scheme, NCC camps, blood donation, or social outreach activities."),
            ("Professional Body Activity", 10, 20, "Active membership and leadership in IEEE, CSI, ACM, IEDC, or ISTE student chapters."),
            ("Sports / Cultural Competition", 10, 25, "University, State, or National level sports / arts / cultural competition representation.")
        ]
        cursor.executemany(
            "INSERT INTO activity_rules (category_name, default_points, max_points, description) VALUES (?, ?, ?, ?)",
            default_rules
        )

    conn.commit()
    conn.close()


def calculate_file_hash(file_bytes: bytes) -> str:
    """Compute SHA-256 hash of file content for exact duplicate detection."""
    return hashlib.sha256(file_bytes).hexdigest()


# ------------------- Student Operations -------------------

def upsert_student(register_number: str, student_name: str, email: Optional[str] = None,
                   branch: str = "Computer Science and Engineering", semester: str = "S6",
                   db_path: str = DB_PATH) -> int:
    """Insert or update a student record."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO students (register_number, student_name, email, branch, semester)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(register_number) DO UPDATE SET
            student_name = excluded.student_name,
            email = COALESCE(excluded.email, students.email),
            branch = excluded.branch,
            semester = excluded.semester
    """, (register_number.strip().upper(), student_name.strip(), email, branch, semester))
    conn.commit()
    cursor.execute("SELECT id FROM students WHERE register_number = ?", (register_number.strip().upper(),))
    student_id = cursor.fetchone()["id"]
    conn.close()
    return student_id


def get_student(register_number: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve student information by register number."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE register_number = ?", (register_number.strip().upper(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_students(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve all students."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY student_name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ------------------- Certificate & Workflow Operations -------------------

def insert_certificate(register_number: str, activity_category: str, file_path: str,
                       file_name: str, file_type: str, file_hash: Optional[str] = None,
                       db_path: str = DB_PATH) -> int:
    """Insert a new certificate upload record."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO certificates (register_number, activity_category, file_path, file_name, file_type, file_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (register_number.strip().upper(), activity_category.strip(), file_path, file_name, file_type, file_hash))
    cert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return cert_id


def insert_extraction(certificate_id: int, extracted_name: Optional[str],
                      extracted_activity: Optional[str], extracted_date: Optional[str],
                      extracted_organization: Optional[str], certificate_number: Optional[str],
                      confidence_score: float, raw_text: Optional[str],
                      db_path: str = DB_PATH) -> int:
    """Insert extracted metadata from certificate OCR."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO extraction (
            certificate_id, extracted_name, extracted_activity, extracted_date,
            extracted_organization, certificate_number, confidence_score, raw_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(certificate_id) DO UPDATE SET
            extracted_name = excluded.extracted_name,
            extracted_activity = excluded.extracted_activity,
            extracted_date = excluded.extracted_date,
            extracted_organization = excluded.extracted_organization,
            certificate_number = excluded.certificate_number,
            confidence_score = excluded.confidence_score,
            raw_text = excluded.raw_text
    """, (certificate_id, extracted_name, extracted_activity, extracted_date,
          extracted_organization, certificate_number, confidence_score, raw_text))
    ext_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ext_id


def update_extraction(certificate_id: int, extracted_name: Optional[str],
                      extracted_activity: Optional[str], extracted_date: Optional[str],
                      extracted_organization: Optional[str], certificate_number: Optional[str],
                      db_path: str = DB_PATH) -> None:
    """Allow faculty or user to edit/correct extracted metadata."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE extraction
        SET extracted_name = ?,
            extracted_activity = ?,
            extracted_date = ?,
            extracted_organization = ?,
            certificate_number = ?
        WHERE certificate_id = ?
    """, (extracted_name, extracted_activity, extracted_date, extracted_organization, certificate_number, certificate_id))
    conn.commit()
    conn.close()


def insert_verification(certificate_id: int, suggested_points: int,
                        awarded_points: int = 0, status: str = "Manual Verification Required",
                        faculty_remark: Optional[str] = None, approved_by: Optional[str] = None,
                        approval_date: Optional[str] = None, db_path: str = DB_PATH) -> int:
    """Insert initial verification record."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO verification (certificate_id, suggested_points, awarded_points, status, faculty_remark, approved_by, approval_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(certificate_id) DO UPDATE SET
            suggested_points = excluded.suggested_points,
            status = excluded.status,
            faculty_remark = excluded.faculty_remark
    """, (certificate_id, suggested_points, awarded_points, status, faculty_remark, approved_by, approval_date))
    verif_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return verif_id


def update_verification_status(certificate_id: int, status: str, awarded_points: int,
                               faculty_remark: Optional[str], approved_by: str,
                               db_path: str = DB_PATH) -> None:
    """Update approval/rejection decision and faculty remarks."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    approval_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status in ["Approved", "Rejected"] else None
    cursor.execute("""
        UPDATE verification
        SET status = ?,
            awarded_points = ?,
            faculty_remark = ?,
            approved_by = ?,
            approval_date = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE certificate_id = ?
    """, (status, awarded_points, faculty_remark, approved_by, approval_date, certificate_id))
    conn.commit()
    conn.close()


# ------------------- Query & Fetch Operations -------------------

def get_certificate_by_id(cert_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Get complete details of a certificate joining all related tables."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            c.id AS certificate_id,
            c.register_number,
            c.activity_category,
            c.file_path,
            c.file_name,
            c.file_type,
            c.file_hash,
            c.upload_date,
            s.student_name,
            s.email,
            s.branch,
            s.semester,
            e.id AS extraction_id,
            e.extracted_name,
            e.extracted_activity,
            e.extracted_date,
            e.extracted_organization,
            e.certificate_number,
            e.confidence_score,
            e.raw_text,
            v.id AS verification_id,
            v.suggested_points,
            v.awarded_points,
            v.status,
            v.faculty_remark,
            v.approved_by,
            v.approval_date
        FROM certificates c
        LEFT JOIN students s ON c.register_number = s.register_number
        LEFT JOIN extraction e ON c.id = e.certificate_id
        LEFT JOIN verification v ON c.id = v.certificate_id
        WHERE c.id = ?
    """, (cert_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_certificates(status: Optional[str] = None, search: Optional[str] = None,
                         category: Optional[str] = None, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Fetch certificates with optional filters for status, search query, and category."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    query = """
        SELECT
            c.id AS certificate_id,
            c.register_number,
            c.activity_category,
            c.file_path,
            c.file_name,
            c.file_type,
            c.upload_date,
            s.student_name,
            s.branch,
            s.semester,
            e.extracted_name,
            e.extracted_activity,
            e.extracted_date,
            e.extracted_organization,
            e.certificate_number,
            e.confidence_score,
            v.suggested_points,
            v.awarded_points,
            v.status,
            v.faculty_remark,
            v.approved_by,
            v.approval_date
        FROM certificates c
        LEFT JOIN students s ON c.register_number = s.register_number
        LEFT JOIN extraction e ON c.id = e.certificate_id
        LEFT JOIN verification v ON c.id = v.certificate_id
        WHERE 1=1
    """
    params = []

    if status and status != "All Statuses":
        query += " AND v.status = ?"
        params.append(status)

    if category and category != "All Categories":
        query += " AND c.activity_category = ?"
        params.append(category)

    if search:
        search_term = f"%{search.strip()}%"
        query += """ AND (
            c.register_number LIKE ? OR
            s.student_name LIKE ? OR
            e.extracted_name LIKE ? OR
            e.extracted_activity LIKE ? OR
            e.certificate_number LIKE ?
        )"""
        params.extend([search_term] * 5)

    query += " ORDER BY c.id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_certificates_by_student(register_number: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve all submissions made by a specific student."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            c.id AS certificate_id,
            c.register_number,
            c.activity_category,
            c.file_name,
            c.upload_date,
            e.extracted_activity,
            e.extracted_date,
            e.extracted_organization,
            e.confidence_score,
            v.suggested_points,
            v.awarded_points,
            v.status,
            v.faculty_remark
        FROM certificates c
        LEFT JOIN extraction e ON c.id = e.certificate_id
        LEFT JOIN verification v ON c.id = v.certificate_id
        WHERE c.register_number = ?
        ORDER BY c.id DESC
    """, (register_number.strip().upper(),))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ------------------- Duplicate Detection -------------------

def check_duplicate_certificate(register_number: str, activity_name: Optional[str],
                               date_str: Optional[str], file_hash: Optional[str] = None,
                               exclude_cert_id: Optional[int] = None,
                               db_path: str = DB_PATH) -> Tuple[bool, str, Optional[int]]:
    """
    Check if a certificate submission is a duplicate based on:
    1. Exact File SHA-256 Hash match
    2. Same Student Register Number + Same/Similar Activity Name + Same Date
    Returns (is_duplicate, reason_message, matched_certificate_id).
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Exact file hash check
    if file_hash:
        query = "SELECT id, register_number FROM certificates WHERE file_hash = ?"
        params = [file_hash]
        if exclude_cert_id:
            query += " AND id != ?"
            params.append(exclude_cert_id)
        cursor.execute(query, params)
        match = cursor.fetchone()
        if match:
            conn.close()
            return True, f"Identical file already uploaded by {match['register_number']} (Cert ID #{match['id']})", match["id"]

    # 2. Activity Name + Date + Student Check
    if activity_name and date_str and len(activity_name.strip()) > 3:
        query = """
            SELECT c.id, c.register_number, e.extracted_activity, e.extracted_date, v.status
            FROM certificates c
            JOIN extraction e ON c.id = e.certificate_id
            JOIN verification v ON c.id = v.certificate_id
            WHERE c.register_number = ?
        """
        params = [register_number.strip().upper()]
        if exclude_cert_id:
            query += " AND c.id != ?"
            params.append(exclude_cert_id)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        clean_act = activity_name.strip().lower()
        clean_date = date_str.strip().lower()

        for r in rows:
            exist_act = (r["extracted_activity"] or "").strip().lower()
            exist_date = (r["extracted_date"] or "").strip().lower()

            # Exact or high similarity on activity name & date
            if exist_act and exist_date:
                from rapidfuzz import fuzz
                act_similarity = fuzz.token_set_ratio(clean_act, exist_act)
                if act_similarity >= 85 and (clean_date in exist_date or exist_date in clean_date or clean_date == exist_date):
                    conn.close()
                    return True, f"Duplicate activity detected: '{r['extracted_activity']}' on {r['extracted_date']} (Cert ID #{r['id']} - Status: {r['status']})", r["id"]

    conn.close()
    return False, "No duplicate detected.", None


# ------------------- Dashboard Statistics -------------------

def get_dashboard_stats(db_path: str = DB_PATH) -> Dict[str, int]:
    """Calculate aggregated metrics for faculty dashboard."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM certificates")
    total = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT
            SUM(CASE WHEN v.status = 'Recommended' THEN 1 ELSE 0 END) AS recommended,
            SUM(CASE WHEN v.status = 'Manual Verification Required' THEN 1 ELSE 0 END) AS manual_verification,
            SUM(CASE WHEN v.status = 'Approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN v.status = 'Rejected' THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN v.status = 'Flagged' THEN 1 ELSE 0 END) AS flagged,
            SUM(CASE WHEN v.status IN ('Recommended', 'Manual Verification Required', 'Flagged') THEN 1 ELSE 0 END) AS pending,
            COALESCE(SUM(v.awarded_points), 0) AS total_awarded_points
        FROM verification v
    """)
    row = cursor.fetchone()
    conn.close()

    return {
        "total": total or 0,
        "pending": row["pending"] or 0,
        "recommended": row["recommended"] or 0,
        "manual_verification": row["manual_verification"] or 0,
        "approved": row["approved"] or 0,
        "rejected": row["rejected"] or 0,
        "flagged": row["flagged"] or 0,
        "total_awarded_points": row["total_awarded_points"] or 0
    }


# ------------------- Rules Operations -------------------

def get_rules(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve all configured KTU activity point rules."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM activity_rules ORDER BY default_points DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_rule_by_category(category_name: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve a rule by its category name."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM activity_rules WHERE category_name = ?", (category_name.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ------------------- Export DataFrames -------------------

def get_export_dataframe(only_approved: bool = True, db_path: str = DB_PATH) -> pd.DataFrame:
    """Generate pandas DataFrame formatted for Excel/CSV exports."""
    conn = get_db_connection(db_path)
    query = """
        SELECT
            c.id AS 'Certificate ID',
            c.register_number AS 'Register Number',
            s.student_name AS 'Student Name',
            s.branch AS 'Branch',
            s.semester AS 'Semester',
            c.activity_category AS 'Activity Category',
            e.extracted_activity AS 'Activity Name',
            e.extracted_organization AS 'Organization / Issuer',
            e.extracted_date AS 'Event Date',
            e.certificate_number AS 'Certificate No',
            ROUND(e.confidence_score, 1) AS 'Confidence (%)',
            v.suggested_points AS 'Suggested Points',
            v.awarded_points AS 'Awarded Points',
            v.status AS 'Status',
            v.faculty_remark AS 'Faculty Remarks',
            v.approved_by AS 'Verified By',
            v.approval_date AS 'Verification Date',
            c.upload_date AS 'Submission Date'
        FROM certificates c
        LEFT JOIN students s ON c.register_number = s.register_number
        LEFT JOIN extraction e ON c.id = e.certificate_id
        LEFT JOIN verification v ON c.id = v.certificate_id
    """
    if only_approved:
        query += " WHERE v.status = 'Approved'"
    query += " ORDER BY c.id DESC"

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
