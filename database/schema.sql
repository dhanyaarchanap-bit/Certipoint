-- KTU Activity Point Verification Assistant Database Schema

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
    status TEXT NOT NULL DEFAULT 'Manual Verification Required', -- 'Recommended', 'Manual Verification Required', 'Flagged', 'Approved', 'Rejected'
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

CREATE INDEX IF NOT EXISTS idx_cert_reg ON certificates(register_number);
CREATE INDEX IF NOT EXISTS idx_cert_hash ON certificates(file_hash);
CREATE INDEX IF NOT EXISTS idx_verif_status ON verification(status);
