"""
Sample Data & Synthetic Certificate Generator for KTU Activity Point Verification Assistant.
Generates realistic sample students, synthetic PDF and PNG certificates,
and seeds the SQLite database with diverse validation states (Approved, Recommended, Flagged, Duplicate).
"""

import os
import sys
import io
from datetime import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from utils.database import (
    init_db, upsert_student, insert_certificate,
    insert_extraction, insert_verification, calculate_file_hash, DB_PATH
)
from utils.rules import calculate_suggested_points
from utils.validator import validate_and_screen_certificate

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(BASE_DIR, "assets", "sample_certificates")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")


def create_sample_pdf_certificate(file_path: str, student_name: str, activity_name: str,
                                  category: str, organization: str, date_str: str,
                                  cert_no: str, extra_notes: str = "") -> None:
    """Generate a clean, high-resolution PDF certificate using ReportLab."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    doc = SimpleDocTemplate(
        file_path,
        pagesize=landscape(letter),
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CertTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        alignment=1, # Center
        textColor=colors.HexColor('#1E3A8A')
    )
    subtitle_style = ParagraphStyle(
        'CertSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        alignment=1,
        textColor=colors.HexColor('#4B5563')
    )
    body_style = ParagraphStyle(
        'CertBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=18,
        alignment=1,
        textColor=colors.HexColor('#1F2937')
    )
    name_style = ParagraphStyle(
        'CertName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        alignment=1,
        textColor=colors.HexColor('#047857')
    )
    activity_style = ParagraphStyle(
        'CertActivity',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        alignment=1,
        textColor=colors.HexColor('#1E40AF')
    )
    meta_style = ParagraphStyle(
        'CertMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor('#6B7280')
    )

    elements = []
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(organization.upper(), subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("CERTIFICATE OF COMPLETION & MERIT", title_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("This is to certify that", body_style))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(student_name, name_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"has successfully completed and actively participated in the {category}:", body_style))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(f'"{activity_name}"', activity_style))

    if extra_notes:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Performance:</b> {extra_notes}", body_style))

    elements.append(Spacer(1, 25))

    # Footer Table with Date and Certificate ID
    footer_data = [
        [
            Paragraph(f"<b>Date of Issue:</b> {date_str}", meta_style),
            Paragraph(f"<b>Organized By:</b> {organization}", meta_style),
            Paragraph(f"<b>Certificate ID:</b> {cert_no}", meta_style)
        ],
        [
            Paragraph("Authorized Signatory", meta_style),
            Paragraph("Program Coordinator", meta_style),
            Paragraph("Verification Officer", meta_style)
        ]
    ]

    footer_table = Table(footer_data, colWidths=[2.5 * inch, 2.5 * inch, 2.5 * inch])
    footer_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(footer_table)

    doc.build(elements)


def create_sample_image_certificate(file_path: str, student_name: str, activity_name: str,
                                    category: str, organization: str, date_str: str,
                                    cert_no: str, extra_notes: str = "") -> None:
    """Generate a high-contrast certificate image (PNG) using Pillow."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    width, height = 1200, 850
    img = Image.new("RGB", (width, height), color="#FAF8F5")
    draw = ImageDraw.Draw(img)

    # Decorative Border
    draw.rectangle([20, 20, width - 20, height - 20], outline="#1E3A8A", width=5)
    draw.rectangle([30, 30, width - 30, height - 30], outline="#D97706", width=2)
    draw.rectangle([35, 35, width - 35, height - 35], outline="#1E3A8A", width=1)

    # Try default fonts
    try:
        font_lg = ImageFont.truetype("arial.ttf", 36)
        font_md = ImageFont.truetype("arial.ttf", 26)
        font_sm = ImageFont.truetype("arial.ttf", 20)
        font_name = ImageFont.truetype("arialbd.ttf", 38)
        font_bold = ImageFont.truetype("arialbd.ttf", 26)
    except Exception:
        font_lg = font_md = font_sm = font_name = font_bold = ImageFont.load_default()

    # Draw Text
    draw.text((width // 2, 80), organization.upper(), fill="#1E3A8A", font=font_bold, anchor="mm")
    draw.text((width // 2, 140), "CERTIFICATE OF EXCELLENCE", fill="#111827", font=font_lg, anchor="mm")
    draw.text((width // 2, 210), "This is to certify that", fill="#4B5563", font=font_md, anchor="mm")

    draw.text((width // 2, 275), student_name, fill="#047857", font=font_name, anchor="mm")
    draw.text((width // 2, 340), f"has successfully participated in and completed the {category}:", fill="#374151", font=font_md, anchor="mm")

    draw.text((width // 2, 410), f'"{activity_name}"', fill="#1D4ED8", font=font_bold, anchor="mm")

    if extra_notes:
        draw.text((width // 2, 475), f"Achievement / Score: {extra_notes}", fill="#B45309", font=font_bold, anchor="mm")

    # Meta Box at bottom
    draw.rectangle([80, 580, width - 80, 750], fill="#FFFFFF", outline="#E5E7EB", width=2)

    draw.text((120, 620), f"Date: {date_str}", fill="#1F2937", font=font_sm)
    draw.text((120, 670), f"Issuing Body: {organization}", fill="#1F2937", font=font_sm)

    draw.text((width - 450, 620), f"Certificate No: {cert_no}", fill="#1F2937", font=font_sm)
    draw.text((width - 450, 670), "Status: Verified Credential", fill="#059669", font=font_bold)

    draw.line([(width // 2 - 150, 790), (width // 2 + 150, 790)], fill="#9CA3AF", width=2)
    draw.text((width // 2, 810), "Authorized Signatory / KTU Verification Cell", fill="#6B7280", font=font_sm, anchor="mm")

    img.save(file_path, "PNG")


def seed_database_and_samples() -> None:
    """Seed sample students, generate sample certificates, and populate DB with various workflow states."""
    init_db(DB_PATH)
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    # 1. Seed Students
    sample_students = [
        ("TVE21CS001", "Rahul Nair", "rahul.cs21@cet.ac.in", "Computer Science and Engineering", "S6"),
        ("TVE21CS045", "Ananya Menon", "ananya.cs21@cet.ac.in", "Computer Science and Engineering", "S6"),
        ("TVE21EC012", "Gokul Krishna", "gokul.ec21@cet.ac.in", "Electronics and Communication Engineering", "S6"),
        ("TVE21ME034", "Sneha Suresh", "sneha.me21@cet.ac.in", "Mechanical Engineering", "S6"),
        ("TVE21CS089", "Mohammed Faizal", "faizal.cs21@cet.ac.in", "Computer Science and Engineering", "S6"),
    ]

    for reg, name, email, branch, sem in sample_students:
        upsert_student(reg, name, email, branch, sem, DB_PATH)

    # 2. Sample Certificate Definitions
    samples = [
        {
            "reg": "TVE21CS001",
            "name": "Rahul Nair",
            "cat": "NPTEL Course",
            "activity": "Programming, Data Structures and Algorithms in Python",
            "org": "NPTEL",
            "date": "15 Oct 2023",
            "cert_no": "NPTEL23CS45S1298457",
            "notes": "Elite+Gold (Score: 92%)",
            "fmt": "pdf",
            "initial_status": "Approved",
            "faculty_remark": "Verified with NPTEL portal. Excellent score (92%). Approved.",
            "approved_by": "Dr. Suresh Kumar (Faculty Advisor)",
            "awarded_pts": 20
        },
        {
            "reg": "TVE21CS045",
            "name": "Ananya Menon",
            "cat": "Workshop",
            "activity": "Hands-on Workshop on Deep Learning with PyTorch",
            "org": "IEEE Computer Society",
            "date": "22 Nov 2023",
            "cert_no": "IEEE-DL-2023-8841",
            "notes": "2-Day Intensive Technical Bootcamp",
            "fmt": "pdf",
            "initial_status": "Recommended",
            "faculty_remark": "High OCR confidence, all fields verified.",
            "approved_by": None,
            "awarded_pts": 0
        },
        {
            "reg": "TVE21EC012",
            "name": "Gokul Krishna",
            "cat": "Internship",
            "activity": "Embedded Systems and IoT Engineering Internship",
            "org": "Kerala Startup Mission (KSUM)",
            "date": "10 Aug 2023",
            "cert_no": "KSUM/INT/2023/1102",
            "notes": "4 Weeks Industrial Training Completed",
            "fmt": "png",
            "initial_status": "Manual Verification Required",
            "faculty_remark": "Requires verification of company registration credentials.",
            "approved_by": None,
            "awarded_pts": 0
        },
        {
            "reg": "TVE21ME034",
            "name": "Sneha Suresh",
            "cat": "Hackathon",
            "activity": "KTU HackSphere State Level Hackathon 2023",
            "org": "APJ Abdul Kalam Technological University",
            "date": "05 Dec 2023",
            "cert_no": "KTU-HS23-WIN-01",
            "notes": "1st Prize Winner / Champion Team",
            "fmt": "pdf",
            "initial_status": "Recommended",
            "faculty_remark": "Verified KTU official hackathon winner list.",
            "approved_by": None,
            "awarded_pts": 0
        },
        {
            "reg": "TVE21CS089",
            "name": "Mohammed Faizal",
            "cat": "Technical Quiz",
            "activity": "National Engineering Quiz Championship",
            "org": "ISTE Student Chapter",
            "date": "18 Sep 2023",
            "cert_no": "ISTE-QZ-993",
            "notes": "Finalist Certificate",
            "fmt": "png",
            "initial_status": "Approved",
            "faculty_remark": "Approved for 5 points as per KTU Quiz guidelines.",
            "approved_by": "Prof. Deepa V (HOD)",
            "awarded_pts": 5
        }
    ]

    for item in samples:
        filename = f"{item['reg']}_{item['cat'].replace(' ', '_').lower()}.{item['fmt']}"
        filepath = os.path.join(SAMPLES_DIR, filename)

        if item["fmt"] == "pdf":
            create_sample_pdf_certificate(
                file_path=filepath,
                student_name=item["name"],
                activity_name=item["activity"],
                category=item["cat"],
                organization=item["org"],
                date_str=item["date"],
                cert_no=item["cert_no"],
                extra_notes=item["notes"]
            )
        else:
            create_sample_image_certificate(
                file_path=filepath,
                student_name=item["name"],
                activity_name=item["activity"],
                category=item["cat"],
                organization=item["org"],
                date_str=item["date"],
                cert_no=item["cert_no"],
                extra_notes=item["notes"]
            )

        # Compute hash
        with open(filepath, "rb") as f:
            file_bytes = f.read()
            f_hash = calculate_file_hash(file_bytes)

        # Insert Certificate record
        cert_id = insert_certificate(
            register_number=item["reg"],
            activity_category=item["cat"],
            file_path=filepath,
            file_name=filename,
            file_type="PDF Document" if item["fmt"] == "pdf" else "PNG Image",
            file_hash=f_hash,
            db_path=DB_PATH
        )

        # Calculate suggested points
        sug_pts, _ = calculate_suggested_points(item["cat"], item["notes"])
        raw_text_sample = f"CERTIFICATE OF COMPLETION This is to certify that {item['name']} has completed {item['activity']} on {item['date']} organized by {item['org']}. Certificate ID: {item['cert_no']}. {item['notes']}"

        # Insert Extraction record
        conf = 96.0 if item["initial_status"] in ["Approved", "Recommended"] else 78.5
        insert_extraction(
            certificate_id=cert_id,
            extracted_name=item["name"],
            extracted_activity=item["activity"],
            extracted_date=item["date"],
            extracted_organization=item["org"],
            certificate_number=item["cert_no"],
            confidence_score=conf,
            raw_text=raw_text_sample,
            db_path=DB_PATH
        )

        # Insert Verification record
        approval_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if item["initial_status"] == "Approved" else None
        insert_verification(
            certificate_id=cert_id,
            suggested_points=sug_pts,
            awarded_points=item["awarded_pts"],
            status=item["initial_status"],
            faculty_remark=item["faculty_remark"],
            approved_by=item["approved_by"],
            approval_date=approval_dt,
            db_path=DB_PATH
        )

    print("Sample database seeded and certificates created successfully!")


if __name__ == "__main__":
    seed_database_and_samples()
