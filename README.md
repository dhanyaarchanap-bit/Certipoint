# 🎓 KTU Activity Point Verification Assistant (CertiPoint)

An AI-assisted certificate screening, OCR extraction, KTU activity point recommendation, duplicate detection, and faculty approval web application built with **Streamlit**, **Python**, **SQLite**, **pdfplumber**, and **OpenCV**.

---

## 📌 Features & System Overview

1. **Student Certificate Portal**
   - Streamlined submission form: Register Number, Student Name, Branch, Semester, Activity Category.
   - Drag-and-drop file upload for **PDF, PNG, JPG, and JPEG** certificates.
   - Real-time instant OCR screening and entity extraction preview.
   - Built-in one-click demo certificate loader for instant testing.
   - Certificate tracking status and history view for students.

2. **AI & OCR Information Extraction**
   - Hybrid PDF stream parser (`pdfplumber`) & image OCR pipeline (`pytesseract` + OpenCV).
   - Extracts: **Student Name**, **Activity / Course Title**, **Event Date**, **Issuing Organization**, and **Certificate Serial / Number**.
   - Advanced OpenCV image preprocessing (Grayscale, Bilateral Filtering, CLAHE Contrast Enhancement, Otsu Binarization).

3. **Validation & Duplicate Detection Engine**
   - Multi-field completeness verification (Missing fields detection).
   - Duplicate submission detection via **cryptographic SHA-256 file hashes** and **fuzzy matching** on `Register Number + Activity Title + Date`.
   - Automated confidence scoring (0 - 100%) and KTU recommendation classification:
     - **Confidence > 90%** ➜ `Recommended` (Green)
     - **Confidence 60% – 90%** ➜ `Manual Verification Required` (Yellow)
     - **Confidence < 60% or Duplicate** ➜ `Flagged` (Red)

4. **KTU Activity Point Recommendation Engine**
   - Configurable rule engine mapping categories to KTU points:
     - **NPTEL Course** ➜ 20 - 50 points (with Elite / Gold bonuses)
     - **Workshop** ➜ 10 - 20 points
     - **Internship** ➜ 20 - 40 points
     - **Technical Quiz** ➜ 5 - 15 points
     - **Hackathon** ➜ 15 - 30 points (Winner / Finalist heuristics)
     - **Paper Presentation** ➜ 15 - 30 points
     - **Industrial Visit** ➜ 5 - 10 points
     - **NSS / NCC / Community Service** ➜ 15 - 30 points
     - **Professional Body Activity** ➜ 10 - 20 points
     - **Sports / Cultural Competition** ➜ 10 - 25 points
   - Category point capping and validation.

5. **Faculty Verification Dashboard & Studio**
   - Secure faculty authentication (`faculty` / `admin123`).
   - Real-time KPI summary (Total Uploads, Pending, Recommended, Manual Review, Flagged, Approved).
   - Search & multi-parameter filtering (by Register No, status, category, date).
   - Split-screen verification studio:
     - **Left**: Document viewer with high-resolution PDF/image rendering and download option.
     - **Right**: Extracted metadata editor, point adjustment slider, faculty remarks, and approval/rejection buttons.
   - 1-Click Batch Approval for all recommended certificates.

6. **Reporting & Auditing Module**
   - Export approved records or complete database records to **Excel (`.xlsx`)** with OpenPyXL custom styling (colored headers, status pills, auto-fit columns, summary totals).
   - Export to **CSV (`.csv`)**.

---

## 🏗️ Project Architecture & File Structure

```
c:/Users/DHANYA/Desktop/Certipoint-1/
├── app.py                      # Main entry application & unified navigation hub
├── pages/
│   ├── student.py              # Student upload and tracking portal
│   ├── 1_🎓_Student.py          # Streamlit multi-page student wrapper
│   ├── faculty.py              # Faculty dashboard and verification studio
│   └── 2_👨‍🏫_Faculty.py          # Streamlit multi-page faculty wrapper
├── utils/
│   ├── __init__.py
│   ├── database.py             # SQLite database layer & CRUD helper functions
│   ├── ocr.py                  # OCR & PDF/image preprocessing pipeline
│   ├── extractor.py            # NLP entity extraction (Name, Activity, Date, Org, Cert ID)
│   ├── validator.py            # Validation rules, duplicate detection, and confidence scoring
│   ├── rules.py                # KTU activity point rules & heuristics engine
│   └── reports.py              # Styled Excel (.xlsx) & CSV export generator
├── database/
│   ├── schema.sql              # Clean SQLite DDL schema
│   ├── sample_data.py          # Sample data seeder & certificate generator
│   └── certipoint.db           # SQLite database file
├── assets/
│   ├── style.css               # Modern CSS styling
│   └── sample_certificates/    # Synthetic test certificates (PDF & PNG)
├── uploads/                    # Secure student upload storage directory
├── requirements.txt            # Python dependencies
└── README.md                   # System documentation
```

---

## 💾 Database Schema

### 1. `students`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `register_number` TEXT UNIQUE NOT NULL
- `student_name` TEXT NOT NULL
- `email` TEXT
- `branch` TEXT
- `semester` TEXT
- `created_at` TIMESTAMP

### 2. `certificates`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `register_number` TEXT NOT NULL (FK -> `students.register_number`)
- `activity_category` TEXT NOT NULL
- `file_path` TEXT NOT NULL
- `file_name` TEXT NOT NULL
- `file_type` TEXT
- `file_hash` TEXT (SHA-256 for exact duplicates)
- `upload_date` TIMESTAMP

### 3. `extraction`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `certificate_id` INTEGER NOT NULL UNIQUE (FK -> `certificates.id`)
- `extracted_name` TEXT
- `extracted_activity` TEXT
- `extracted_date` TEXT
- `extracted_organization` TEXT
- `certificate_number` TEXT
- `confidence_score` REAL
- `raw_text` TEXT
- `created_at` TIMESTAMP

### 4. `verification`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `certificate_id` INTEGER NOT NULL UNIQUE (FK -> `certificates.id`)
- `suggested_points` INTEGER
- `awarded_points` INTEGER
- `status` TEXT (`Recommended`, `Manual Verification Required`, `Flagged`, `Approved`, `Rejected`)
- `faculty_remark` TEXT
- `approved_by` TEXT
- `approval_date` TIMESTAMP
- `updated_at` TIMESTAMP

### 5. `activity_rules`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `category_name` TEXT UNIQUE NOT NULL
- `default_points` INTEGER NOT NULL
- `max_points` INTEGER NOT NULL
- `description` TEXT

---

## 🚀 Installation & Setup Instructions

### 1. Prerequisites
- Python 3.9+
- (Optional for scanned image OCR) Tesseract OCR engine

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Seed Sample Data & Generate Test Certificates
```bash
python database/sample_data.py
```

### 4. Launch the Web Application
```bash
streamlit run app.py
```

The application will be accessible at: `http://localhost:8501`

---

## 🔑 Demo Credentials

| Role | Username | Password | Purpose |
|------|----------|----------|---------|
| **Faculty Advisor** | `faculty` | `admin123` | Certificate review, point awarding & approval |
| **Faculty Advisor** | `advisor` | `ktu2024` | Review queue access |
| **Head of Department** | `hod` | `cetcsdept` | Final auditing & reports |
| **Student** | *(No login required)* | — | Open submission & tracking portal |

---

## 🧪 Testing the Application

1. **Student Flow**:
   - Open **Student Portal** from navigation.
   - Click **"Quick Demo / Sample Certificate Loader"** and choose any test certificate (e.g. `NPTEL Course (PDF)`).
   - Review the instant real-time OCR extraction, confidence score, and suggested activity points.
   - Click **"Final Submit Certificate for Faculty Verification"**.
2. **Duplicate Detection**:
   - Re-submit the same certificate file or same event name/date for the student.
   - The system immediately triggers a duplicate warning and flags the certificate with `Flagged`.
3. **Faculty Verification Flow**:
   - Navigate to **Faculty Hub** and log in with `faculty` / `admin123`.
   - Inspect submissions with split-screen document preview.
   - Edit metadata if needed, adjust points, and click **"Approve Certificate"**.
   - Download the styled Excel audit report.
