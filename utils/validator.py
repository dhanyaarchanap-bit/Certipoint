"""
Validation Engine and Confidence Scoring Module.
Performs field completeness checks, duplicate detection, computes multi-factor confidence scores,
and determines automated workflow recommendation status.
"""

from typing import Dict, Any, Tuple, Optional, List
from rapidfuzz import fuzz
from utils.database import check_duplicate_certificate


def validate_certificate_completeness(extracted_data: Dict[str, Any],
                                      student_name_input: str,
                                      register_number_input: str) -> Dict[str, Any]:
    """
    Validate completeness of extracted certificate metadata against student inputs.
    Returns completeness flags, missing fields, and name match score.
    """
    missing_fields: List[str] = []
    field_status: Dict[str, bool] = {}

    # 1. Student Name Check & Name Similarity
    extracted_name = extracted_data.get("extracted_name")
    name_similarity = 0.0
    if not extracted_name:
        missing_fields.append("Student Name")
        field_status["name"] = False
    else:
        field_status["name"] = True
        if student_name_input:
            name_similarity = fuzz.token_set_ratio(student_name_input.lower(), extracted_name.lower())
        else:
            name_similarity = 80.0

    # 2. Activity Name Check
    extracted_activity = extracted_data.get("extracted_activity")
    if not extracted_activity or len(extracted_activity.strip()) < 3:
        missing_fields.append("Activity / Event Name")
        field_status["activity"] = False
    else:
        field_status["activity"] = True

    # 3. Date Check
    extracted_date = extracted_data.get("extracted_date")
    if not extracted_date:
        missing_fields.append("Date of Event / Issue")
        field_status["date"] = False
    else:
        field_status["date"] = True

    # 4. Organization Check
    extracted_org = extracted_data.get("extracted_organization")
    if not extracted_org:
        missing_fields.append("Issuing Organization")
        field_status["organization"] = False
    else:
        field_status["organization"] = True

    # 5. Certificate Number (Bonus optional field)
    field_status["certificate_number"] = bool(extracted_data.get("certificate_number"))

    is_complete = len(missing_fields) == 0

    return {
        "is_complete": is_complete,
        "missing_fields": missing_fields,
        "field_status": field_status,
        "name_similarity": name_similarity
    }


def calculate_confidence_score(ocr_quality: float,
                               completeness_result: Dict[str, Any],
                               is_duplicate: bool = False,
                               raw_text_len: int = 0) -> float:
    """
    Multi-factor weighted confidence calculation:
    - OCR Quality / Text Legibility: 25%
    - Field Completeness (Name: 25%, Activity: 20%, Date: 15%, Org: 15%): 50%
    - Name Match Ratio between Input & Certificate: 15%
    - Certificate Serial / ID Bonus: 10%
    - Penalties for duplicates or severe text absence
    """
    if is_duplicate:
        # Flagged duplicate certificates are capped at 25% confidence
        return 25.0

    if raw_text_len < 20:
        return 20.0

    field_status = completeness_result.get("field_status", {})
    name_similarity = completeness_result.get("name_similarity", 0.0)

    # 1. OCR Quality Score (0 to 25)
    # Normalize ocr_quality (0-100) -> (0-25)
    ocr_score = (max(0.0, min(100.0, ocr_quality)) / 100.0) * 25.0

    # 2. Field Presence Weights (0 to 50)
    field_weights = 0.0
    if field_status.get("name", False):
        field_weights += 18.0
    if field_status.get("activity", False):
        field_weights += 14.0
    if field_status.get("date", False):
        field_weights += 10.0
    if field_status.get("organization", False):
        field_weights += 8.0

    # 3. Name Similarity Alignment (0 to 15)
    name_score = (name_similarity / 100.0) * 15.0

    # 4. Certificate ID Presence (0 to 10)
    cert_id_score = 10.0 if field_status.get("certificate_number", False) else 3.0

    total_score = ocr_score + field_weights + name_score + cert_id_score

    # Hard penalties
    if name_similarity < 40 and field_status.get("name", False):
        # Name on cert is completely different from applicant name
        total_score -= 30.0

    if len(completeness_result.get("missing_fields", [])) >= 3:
        total_score = min(total_score, 45.0)

    return float(max(10.0, min(98.5, round(total_score, 1))))


def determine_recommendation_status(confidence_score: float, is_duplicate: bool = False,
                                    missing_fields: Optional[List[str]] = None) -> Tuple[str, str, str]:
    """
    Map confidence score and validation state to KTU recommendation status.
    Returns (status_label, badge_color_theme, explanation_message).
    - Confidence > 90% → Recommended (Green)
    - Confidence 60% – 90% → Manual Verification Required (Yellow)
    - Confidence < 60% or Duplicate → Flagged (Red)
    """
    if is_duplicate:
        return (
            "Flagged",
            "red",
            "Duplicate Submission Detected: An identical file or identical event record exists."
        )

    if missing_fields and len(missing_fields) >= 3:
        return (
            "Flagged",
            "red",
            f"Severe Data Incompleteness: Missing {', '.join(missing_fields)}."
        )

    if confidence_score > 90.0:
        return (
            "Recommended",
            "green",
            "High confidence extraction. All required fields verified with high OCR fidelity."
        )
    elif 60.0 <= confidence_score <= 90.0:
        return (
            "Manual Verification Required",
            "yellow",
            f"Moderate confidence ({confidence_score:.1f}%). Faculty review required for missing/partial fields."
        )
    else:
        return (
            "Flagged",
            "red",
            f"Low confidence ({confidence_score:.1f}%). Possible OCR ambiguity or unverified certificate details."
        )


def validate_and_screen_certificate(extracted_data: Dict[str, Any],
                                    ocr_quality: float,
                                    register_number: str,
                                    student_name: str,
                                    file_hash: Optional[str] = None,
                                    exclude_cert_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Complete end-to-end certificate screening pipeline.
    Returns full validation summary, duplicate report, confidence score, and status.
    """
    # 1. Check Completeness
    completeness = validate_certificate_completeness(
        extracted_data=extracted_data,
        student_name_input=student_name,
        register_number_input=register_number
    )

    # 2. Check Duplicates
    is_duplicate, dup_reason, matched_id = check_duplicate_certificate(
        register_number=register_number,
        activity_name=extracted_data.get("extracted_activity"),
        date_str=extracted_data.get("extracted_date"),
        file_hash=file_hash,
        exclude_cert_id=exclude_cert_id
    )

    # 3. Calculate Confidence Score
    confidence_score = calculate_confidence_score(
        ocr_quality=ocr_quality,
        completeness_result=completeness,
        is_duplicate=is_duplicate,
        raw_text_len=extracted_data.get("raw_text_length", 0)
    )

    # 4. Determine Status
    status, color, status_msg = determine_recommendation_status(
        confidence_score=confidence_score,
        is_duplicate=is_duplicate,
        missing_fields=completeness.get("missing_fields")
    )

    return {
        "confidence_score": confidence_score,
        "status": status,
        "color": color,
        "status_message": status_msg,
        "is_duplicate": is_duplicate,
        "duplicate_reason": dup_reason,
        "matched_cert_id": matched_id,
        "completeness": completeness
    }
