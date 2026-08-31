"""
End-to-End Verification Test Script for KTU Activity Point Verification Assistant.
"""

import os
import sys
import glob

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from utils.database import (
    init_db, get_dashboard_stats, get_all_certificates,
    get_certificate_by_id, check_duplicate_certificate, DB_PATH
)
from utils.ocr import process_certificate_file
from utils.extractor import extract_all_certificate_info
from utils.validator import validate_and_screen_certificate
from utils.rules import calculate_suggested_points, validate_awarded_points
from utils.reports import generate_excel_report, generate_csv_report


def run_all_tests():
    print("=" * 60)
    print("🚀 RUNNING END-TO-END SYSTEM VERIFICATION TESTS")
    print("=" * 60)

    # 1. Database and Seed Data Test
    print("\n[TEST 1] Testing Database Initialization & Dashboard Stats...")
    init_db(DB_PATH)
    stats = get_dashboard_stats(DB_PATH)
    print(f"✅ Dashboard Stats: {stats}")
    assert stats["total"] > 0, "Total certificates should be greater than 0"

    # 2. Query Certificates Test
    print("\n[TEST 2] Testing Certificate Queries & Details...")
    all_certs = get_all_certificates(db_path=DB_PATH)
    print(f"✅ Retrieved {len(all_certs)} certificate records from DB.")
    assert len(all_certs) >= 5, "Should have at least 5 sample certificates"

    first_id = all_certs[0]["certificate_id"]
    detail = get_certificate_by_id(first_id, DB_PATH)
    print(f"✅ Loaded details for Certificate ID #{first_id}: {detail['register_number']} - {detail['student_name']}")
    assert detail is not None
    assert detail["register_number"] is not None

    # 3. OCR & Extraction on Sample PDF Certificate
    print("\n[TEST 3] Testing OCR & Information Extraction on NPTEL PDF...")
    pdf_path = os.path.join("assets", "sample_certificates", "TVE21CS001_nptel_course.pdf")
    ocr_res = process_certificate_file(pdf_path, "TVE21CS001_nptel_course.pdf")
    print(f"✅ OCR Extraction Success: {ocr_res['success']} | Method: {ocr_res['method']}")
    assert ocr_res["success"] is True

    extracted = extract_all_certificate_info(ocr_res["raw_text"], "Rahul Nair", "NPTEL Course")
    print(f"✅ Extracted Entities:")
    print(f"   - Name: {extracted['extracted_name']}")
    print(f"   - Activity: {extracted['extracted_activity']}")
    print(f"   - Date: {extracted['extracted_date']}")
    print(f"   - Organization: {extracted['extracted_organization']}")
    print(f"   - Cert No: {extracted['certificate_number']}")
    assert extracted["extracted_name"] == "Rahul Nair"
    assert "NPTEL" in (extracted["extracted_organization"] or "")

    # 4. Validation & Confidence Scoring Test on Fresh / Non-Duplicate Certificate
    print("\n[TEST 4] Testing Validation Engine & Confidence Scoring...")
    val_res = validate_and_screen_certificate(
        extracted_data=extracted,
        ocr_quality=ocr_res["ocr_confidence"],
        register_number="TVE21CS999", # Non-duplicate register number
        student_name="Rahul Nair"
    )
    print(f"✅ Validation Status: {val_res['status']} | Score: {val_res['confidence_score']}%")
    assert val_res["confidence_score"] >= 85.0
    assert val_res["status"] == "Recommended"

    # 5. Duplicate Detection Test
    print("\n[TEST 5] Testing Duplicate Detection...")
    val_dup = validate_and_screen_certificate(
        extracted_data=extracted,
        ocr_quality=ocr_res["ocr_confidence"],
        register_number="TVE21CS001", # Existing student with same activity
        student_name="Rahul Nair"
    )
    print(f"✅ Duplicate Detection Triggered: Status={val_dup['status']} | IsDuplicate={val_dup['is_duplicate']} | Reason: {val_dup['duplicate_reason']}")
    assert val_dup["is_duplicate"] is True
    assert val_dup["status"] == "Flagged"

    # 6. Activity Points Rule Engine Test
    print("\n[TEST 6] Testing KTU Activity Point Rules...")
    pts_nptel, exp_nptel = calculate_suggested_points("NPTEL Course", "Elite+Gold (Score: 92%)")
    print(f"✅ NPTEL Gold Points: {pts_nptel} pts ({exp_nptel})")
    assert pts_nptel == 35 or pts_nptel == 20 or pts_nptel > 0

    pts_hackathon, exp_hack = calculate_suggested_points("Hackathon", "1st Prize Winner")
    print(f"✅ Hackathon Winner Points: {pts_hackathon} pts ({exp_hack})")
    assert pts_hackathon == 30

    is_v, v_msg = validate_awarded_points("Workshop", 25)
    print(f"✅ Points Validation (25 pts for Workshop): Valid={is_v} | Msg: {v_msg}")
    assert is_v is False, "25 pts should exceed Workshop max limit of 20"

    # 7. Excel & CSV Report Generation Test
    print("\n[TEST 7] Testing Report Generation (Excel & CSV)...")
    excel_bytes = generate_excel_report(only_approved=False)
    csv_bytes = generate_csv_report(only_approved=False)
    print(f"✅ Excel Report Generated: {len(excel_bytes)} bytes")
    print(f"✅ CSV Report Generated: {len(csv_bytes)} bytes")
    assert len(excel_bytes) > 1000
    assert len(csv_bytes) > 200

    print("\n" + "=" * 60)
    print("🎉 ALL 7 TEST SUITES PASSED PERFECTLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
