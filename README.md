# KTU Activity Point Verification Assistant

## Project Overview

KTU Activity Point Verification Assistant is an AI-assisted certificate verification system designed to reduce the manual workload involved in verifying student activity point certificates.

The system does not replace faculty verification. Instead, it automatically extracts information from uploaded certificates, validates the data using predefined KTU activity point rules, and provides a recommendation for approval. The final decision remains with the faculty advisor.

---

# Problem Statement

Verification of activity point certificates is currently a manual process that requires faculty to inspect every uploaded certificate individually. This process is time-consuming, repetitive, and prone to human error.

The proposed system automates certificate screening, information extraction, and preliminary validation while keeping faculty in control of the final approval process.

---

# Objectives

* Reduce manual verification effort.
* Automatically extract information from certificates.
* Detect incomplete or duplicate submissions.
* Calculate suggested activity points.
* Recommend approval status based on confidence scores.
* Provide a centralized faculty dashboard.
* Export approved records for reporting.

---

# System Workflow

## Student Side

1. Student opens the application.
2. Student enters Register Number.
3. Student selects Activity Category.
4. Student uploads a certificate (PDF/JPG/PNG).
5. Student submits the application.

### Input

* Register Number
* Activity Category
* Certificate File

---

## Certificate Processing

### Step 1: File Upload

The uploaded certificate is stored securely in the system.

### Step 2: OCR/Text Extraction

The system extracts text using:

* pdfplumber (for PDFs)
* Tesseract OCR (for images)

### Step 3: Information Extraction

The system identifies:

* Student Name
* Activity Name
* Date
* Issuing Organization
* Certificate Number (if available)

---

## Validation Engine

The extracted information is checked against predefined rules.

### Validation Checks

#### Required Field Check

Verify that:

* Student Name exists
* Activity Name exists
* Date exists
* Organization exists

#### Duplicate Detection

Check for existing records using:

* Register Number
* Activity Name
* Date

If a duplicate is found, the certificate is flagged.

---

## Activity Point Calculation

The system maps the selected activity category to predefined KTU activity points.

Example:

| Activity Category | Points |
| ----------------- | ------ |
| NPTEL Course      | 20     |
| Workshop          | 10     |
| Internship        | 20     |
| Technical Quiz    | 5      |

The calculated points are displayed to the faculty.

---

## Confidence Score Generation

The system calculates a confidence score based on:

* OCR quality
* Field extraction success
* Data completeness

### Status Assignment

| Confidence Score | Status                       |
| ---------------- | ---------------------------- |
| Above 90%        | Recommended                  |
| 60% – 90%        | Manual Verification Required |
| Below 60%        | Flagged                      |

---

## Faculty Dashboard

Faculty members log in to review submissions.

### Dashboard Features

* View all certificates
* Search by Register Number
* Filter by status
* View uploaded certificate
* View extracted information
* Approve submission
* Reject submission

### Status Categories

* Pending
* Recommended
* Flagged
* Approved
* Rejected

---

## Export Module

Faculty can export approved records to:

* Excel (.xlsx)
* CSV (.csv)

Exported fields:

* Register Number
* Student Name
* Activity Category
* Points Awarded
* Approval Status

---

# Database Design

## Students Table

* id
* register_number
* student_name

## Certificates Table

* id
* register_number
* file_path
* activity_category
* upload_date

## Extraction Table

* id
* certificate_id
* extracted_name
* extracted_activity
* extracted_date
* extracted_organization
* confidence_score

## Verification Table

* id
* certificate_id
* suggested_points
* status
* faculty_remark

---

# Technology Stack

## Frontend

* Streamlit

## Backend

* Python

## Database

* SQLite

## OCR

* Tesseract OCR

## PDF Processing

* pdfplumber

## Data Processing

* Pandas

## Report Export

* OpenPyXL

---

# Project Flow Diagram

Student Upload Certificate
↓
OCR / PDF Text Extraction
↓
Information Extraction
↓
Validation Engine
↓
Duplicate Detection
↓
Activity Point Calculation
↓
Confidence Score Generation
↓
Recommended / Manual Verification / Flagged
↓
Faculty Dashboard
↓
Approve or Reject
↓
Export Approved Records

---

# Expected Outcome

The system assists faculty by automatically screening certificates, extracting important information, calculating activity points, and recommending actions. This reduces verification time while maintaining faculty control over final approval decisions.
