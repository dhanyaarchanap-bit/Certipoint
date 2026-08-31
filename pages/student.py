"""
Student Portal - KTU Activity Point Verification Assistant.
Allows students to register, upload certificates, screen OCR extraction in real-time,
and track submission verification status.
"""

import os
import sys
import io
from datetime import datetime
import streamlit as st
from PIL import Image

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from utils.database import (
    init_db, upsert_student, insert_certificate,
    insert_extraction, insert_verification, calculate_file_hash,
    get_student, get_certificates_by_student, get_rules, DB_PATH
)
from utils.ocr import process_certificate_file, is_tesseract_installed
from utils.extractor import extract_all_certificate_info
from utils.validator import validate_and_screen_certificate
from utils.rules import calculate_suggested_points, get_all_categories, DEFAULT_KTU_RULES

# Ensure database is initialized
init_db(DB_PATH)


def load_css():
    """Load styling rules."""
    css_path = os.path.join(BASE_DIR, "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_student_page():
    """Render Student Upload & Tracking Portal."""
    load_css()

    st.markdown("""
        <div class="ktu-header">
            <h1>🎓 KTU Activity Point Student Portal</h1>
            <p>Upload your certificates for AI-assisted screening, activity point recommendation, and faculty advisor verification.</p>
        </div>
    """, unsafe_allow_html=True)

    tab_upload, tab_status, tab_guide = st.tabs([
        "📤 Submit Certificate",
        "📊 Track My Submissions",
        "ℹ️ Activity Points Guidelines"
    ])

    # ---------------- TAB 1: SUBMIT CERTIFICATE ----------------
    with tab_upload:
        st.markdown("### 📄 Certificate Submission Form")
        st.caption("Fill in your student details, choose the category, and attach your certificate file (PDF, PNG, JPG).")

        # Demo Quick-Fill Assistant
        with st.expander("⚡ Quick Demo / Sample Certificate Loader", expanded=False):
            st.info("Select a pre-configured sample to test the OCR extraction and validation pipeline instantly:")
            demo_cols = st.columns(4)
            sample_files_dir = os.path.join(BASE_DIR, "assets", "sample_certificates")
            
            selected_demo_file = None
            if demo_cols[0].button("📄 NPTEL Course (PDF)", use_container_width=True):
                st.session_state["demo_reg"] = "TVE21CS001"
                st.session_state["demo_name"] = "Rahul Nair"
                st.session_state["demo_cat"] = "NPTEL Course"
                st.session_state["demo_file_path"] = os.path.join(sample_files_dir, "TVE21CS001_nptel_course.pdf")
                st.rerun()

            if demo_cols[1].button("📄 Workshop (PDF)", use_container_width=True):
                st.session_state["demo_reg"] = "TVE21CS045"
                st.session_state["demo_name"] = "Ananya Menon"
                st.session_state["demo_cat"] = "Workshop"
                st.session_state["demo_file_path"] = os.path.join(sample_files_dir, "TVE21CS045_workshop.pdf")
                st.rerun()

            if demo_cols[2].button("🚀 Hackathon (PDF)", use_container_width=True):
                st.session_state["demo_reg"] = "TVE21ME034"
                st.session_state["demo_name"] = "Sneha Suresh"
                st.session_state["demo_cat"] = "Hackathon"
                st.session_state["demo_file_path"] = os.path.join(sample_files_dir, "TVE21ME034_hackathon.pdf")
                st.rerun()

            if demo_cols[3].button("💼 Internship (PNG)", use_container_width=True):
                st.session_state["demo_reg"] = "TVE21EC012"
                st.session_state["demo_name"] = "Gokul Krishna"
                st.session_state["demo_cat"] = "Internship"
                st.session_state["demo_file_path"] = os.path.join(sample_files_dir, "TVE21EC012_internship.png")
                st.rerun()

        col_left, col_right = st.columns([1, 1], gap="large")

        with col_left:
            st.markdown("#### 1. Student Identification")
            default_reg = st.session_state.get("demo_reg", "")
            default_name = st.session_state.get("demo_name", "")
            default_cat = st.session_state.get("demo_cat", "NPTEL Course")

            reg_number = st.text_input(
                "Register Number (e.g. TVE21CS001)*",
                value=default_reg,
                placeholder="Enter your KTU Register Number",
                help="KTU 10-character alphanumeric registration code."
            ).strip().upper()

            # Auto-fetch student name if registered
            if reg_number and not default_name:
                student_record = get_student(reg_number)
                if student_record:
                    default_name = student_record["student_name"]

            student_name = st.text_input(
                "Full Name (as per KTU records)*",
                value=default_name,
                placeholder="e.g. Rahul Nair"
            ).strip()

            c_branch, c_sem = st.columns(2)
            with c_branch:
                branch = st.selectbox("Branch / Department", [
                    "Computer Science and Engineering",
                    "Electronics and Communication",
                    "Electrical and Electronics",
                    "Mechanical Engineering",
                    "Civil Engineering",
                    "Information Technology",
                    "Artificial Intelligence and Data Science"
                ])
            with c_sem:
                semester = st.selectbox("Semester", ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"], index=5)

            st.markdown("#### 2. Activity Category")
            categories = get_all_categories()
            cat_index = categories.index(default_cat) if default_cat in categories else 0
            activity_category = st.selectbox("Select Activity Category*", categories, index=cat_index)

            # Show category rule badge
            rule_info = DEFAULT_KTU_RULES.get(activity_category, {})
            if rule_info:
                st.info(f"📌 **KTU Rule Policy:** {rule_info.get('description', '')} (Base: **{rule_info.get('default_points', 10)} pts**, Max Cap: **{rule_info.get('max_points', 20)} pts**)")

        with col_right:
            st.markdown("#### 3. Upload Certificate Document")
            
            uploaded_file = st.file_uploader(
                "Upload Certificate (PDF, JPG, JPEG, PNG)*",
                type=["pdf", "png", "jpg", "jpeg"],
                help="Ensure the student name, event title, date, and organization are clearly legible."
            )

            # Handle Demo File Path if active
            demo_bytes = None
            demo_filename = None
            if not uploaded_file and "demo_file_path" in st.session_state and os.path.exists(st.session_state["demo_file_path"]):
                demo_filepath = st.session_state["demo_file_path"]
                demo_filename = os.path.basename(demo_filepath)
                with open(demo_filepath, "rb") as f:
                    demo_bytes = f.read()
                st.success(f"Loaded demo certificate: `{demo_filename}`")

            active_file_bytes = uploaded_file.getvalue() if uploaded_file else demo_bytes
            active_file_name = uploaded_file.name if uploaded_file else demo_filename

            if active_file_bytes and active_file_name:
                st.markdown("##### 🔍 Certificate Document Preview")
                file_ext = os.path.splitext(active_file_name)[1].lower()
                
                if file_ext in [".png", ".jpg", ".jpeg"]:
                    try:
                        pil_img = Image.open(io.BytesIO(active_file_bytes))
                        st.image(pil_img, caption=f"Preview: {active_file_name}", use_container_width=True)
                    except Exception as e:
                        st.error(f"Image preview error: {e}")
                elif file_ext == ".pdf":
                    st.caption(f"📄 PDF Attached: **{active_file_name}** ({len(active_file_bytes)/1024:.1f} KB)")
                    # Render first page if possible
                    try:
                        import pdfplumber
                        with pdfplumber.open(io.BytesIO(active_file_bytes)) as pdf:
                            if len(pdf.pages) > 0:
                                p0_img = pdf.pages[0].to_image(resolution=150).original
                                st.image(p0_img, caption="PDF Page 1 Preview", use_container_width=True)
                    except Exception:
                        st.info("PDF document uploaded ready for OCR extraction.")

        # ---------------- REAL-TIME OCR & SCREENING PREVIEW ----------------
        if active_file_bytes and reg_number and student_name:
            st.markdown("---")
            st.markdown("### 🤖 Real-time AI Certificate Screening")

            with st.spinner("Extracting text and screening certificate..."):
                # Compute file hash
                f_hash = calculate_file_hash(active_file_bytes)

                # Process OCR
                ocr_result = process_certificate_file(active_file_bytes, active_file_name)
                raw_text = ocr_result.get("raw_text", "")
                ocr_conf = ocr_result.get("ocr_confidence", 50.0)

                # Extract entities
                extracted = extract_all_certificate_info(
                    raw_text=raw_text,
                    student_name_input=student_name,
                    activity_category_input=activity_category
                )

                # Validate & check duplicates
                validation = validate_and_screen_certificate(
                    extracted_data=extracted,
                    ocr_quality=ocr_conf,
                    register_number=reg_number,
                    student_name=student_name,
                    file_hash=f_hash
                )

                # Calculate suggested points
                suggested_pts, pts_reason = calculate_suggested_points(activity_category, raw_text)

            # Display Screening Results
            res_col1, res_col2, res_col3 = st.columns([1.2, 1, 1])

            with res_col1:
                st.markdown("##### 📋 Extracted Certificate Data")
                ext_name = extracted.get("extracted_name") or "⚠️ Not detected"
                ext_act = extracted.get("extracted_activity") or "⚠️ Not detected"
                ext_date = extracted.get("extracted_date") or "⚠️ Not detected"
                ext_org = extracted.get("extracted_organization") or "⚠️ Not detected"
                ext_cert = extracted.get("certificate_number") or "N/A"

                st.write(f"**Student Name:** {ext_name}")
                st.write(f"**Activity / Topic:** {ext_act}")
                st.write(f"**Date:** {ext_date}")
                st.write(f"**Issuing Body:** {ext_org}")
                st.write(f"**Certificate No:** `{ext_cert}`")

            with res_col2:
                st.markdown("##### 🎯 Suggested Activity Points")
                st.metric("Recommended Points", f"{suggested_pts} Pts", help=pts_reason)
                st.caption(f"**Rule:** {pts_reason}")

            with res_col3:
                st.markdown("##### 🛡️ Verification Status")
                conf_score = validation["confidence_score"]
                status = validation["status"]

                if status == "Recommended":
                    st.markdown(f'<div class="status-pill status-recommended">✅ {status} ({conf_score}%)</div>', unsafe_allow_html=True)
                elif status == "Manual Verification Required":
                    st.markdown(f'<div class="status-pill status-manual">⚠️ {status} ({conf_score}%)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="status-pill status-flagged">🚩 {status} ({conf_score}%)</div>', unsafe_allow_html=True)

                st.write("")
                st.caption(validation["status_message"])

            # Warning if duplicate
            if validation["is_duplicate"]:
                st.error(f"🚨 **DUPLICATE DETECTED:** {validation['duplicate_reason']}")

            # Missing fields warning
            missing = validation["completeness"].get("missing_fields", [])
            if missing:
                st.warning(f"⚠️ **Missing / Unclear Fields:** {', '.join(missing)}. You can still submit, and your faculty advisor will manually review the uploaded file.")

            # Raw OCR Text Viewer
            with st.expander("🔍 View Raw OCR Extracted Text", expanded=False):
                st.code(raw_text if raw_text else "(No text could be extracted from the file)")
                st.caption(f"Extraction method: `{ocr_result.get('method')}` | OCR confidence: `{ocr_conf:.1f}%`")

            # Final Submission Button
            st.markdown("---")
            btn_submit = st.button("🚀 Final Submit Certificate for Faculty Verification", type="primary", use_container_width=True)

            if btn_submit:
                with st.spinner("Submitting certificate to KTU verification queue..."):
                    # 1. Upsert Student Record
                    upsert_student(
                        register_number=reg_number,
                        student_name=student_name,
                        email=f"{reg_number.lower()}@college.edu",
                        branch=branch,
                        semester=semester,
                        db_path=DB_PATH
                    )

                    # 2. Save File locally in uploads directory
                    uploads_dir = os.path.join(BASE_DIR, "uploads")
                    os.makedirs(uploads_dir, exist_ok=True)
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_filename = f"{reg_number}_{timestamp_str}_{active_file_name}"
                    saved_path = os.path.join(uploads_dir, clean_filename)

                    with open(saved_path, "wb") as f:
                        f.write(active_file_bytes)

                    # 3. Insert Certificate Record
                    cert_id = insert_certificate(
                        register_number=reg_number,
                        activity_category=activity_category,
                        file_path=saved_path,
                        file_name=active_file_name,
                        file_type=ocr_result.get("file_type", "Document"),
                        file_hash=f_hash,
                        db_path=DB_PATH
                    )

                    # 4. Insert Extraction Record
                    insert_extraction(
                        certificate_id=cert_id,
                        extracted_name=extracted.get("extracted_name"),
                        extracted_activity=extracted.get("extracted_activity"),
                        extracted_date=extracted.get("extracted_date"),
                        extracted_organization=extracted.get("extracted_organization"),
                        certificate_number=extracted.get("certificate_number"),
                        confidence_score=validation["confidence_score"],
                        raw_text=raw_text,
                        db_path=DB_PATH
                    )

                    # 5. Insert Verification Record
                    initial_status = validation["status"]
                    faculty_remark = f"Auto-Screened: {validation['status_message']}"
                    if validation["is_duplicate"]:
                        faculty_remark = f"DUPLICATE FLAG: {validation['duplicate_reason']}"

                    insert_verification(
                        certificate_id=cert_id,
                        suggested_points=suggested_pts,
                        awarded_points=0,
                        status=initial_status,
                        faculty_remark=faculty_remark,
                        db_path=DB_PATH
                    )

                st.success(f"🎉 Certificate submitted successfully! Your Certificate Tracking ID is **#{cert_id}**.")
                st.balloons()

                # Clean up demo state if any
                for k in ["demo_reg", "demo_name", "demo_cat", "demo_file_path"]:
                    st.session_state.pop(k, None)

        elif not active_file_bytes:
            st.info("👆 Please upload a certificate document or load a sample demo certificate above to preview automatic extraction.")
        else:
            st.warning("⚠️ Please provide your Register Number and Student Name to proceed.")

    # ---------------- TAB 2: TRACK SUBMISSIONS ----------------
    with tab_status:
        st.markdown("### 📊 Track My Certificate Submissions")
        search_reg = st.text_input("Enter Register Number to Check Status", value=st.session_state.get("demo_reg", ""), placeholder="e.g. TVE21CS001").strip().upper()

        if search_reg:
            submissions = get_certificates_by_student(search_reg, DB_PATH)
            if submissions:
                total_awarded = sum(s["awarded_points"] for s in submissions if s["status"] == "Approved")
                st.markdown(f"#### Submissions for **{search_reg}** — Total Approved Points: **{total_awarded} pts**")

                for sub in submissions:
                    with st.container():
                        st.markdown(f"""
                        <div class="card-panel">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <h4>#{sub['certificate_id']} - {sub['activity_category']} ({sub['extracted_activity'] or 'Activity'})</h4>
                                <span class="status-pill status-{ 'approved' if sub['status']=='Approved' else ('recommended' if sub['status']=='Recommended' else ('manual' if sub['status']=='Manual Verification Required' else 'flagged'))}">
                                    {sub['status']}
                                </span>
                            </div>
                            <p style="color: #64748B; font-size: 13px; margin: 4px 0 12px 0;">
                                📅 Submitted on {sub['upload_date']} | Organization: <b>{sub['extracted_organization'] or 'N/A'}</b> | Event Date: <b>{sub['extracted_date'] or 'N/A'}</b>
                            </p>
                            <div style="display: flex; gap: 20px; font-size: 14px;">
                                <div><b>Suggested Points:</b> {sub['suggested_points']} pts</div>
                                <div><b>Awarded Points:</b> <span style="color: #2563EB; font-weight: 700;">{sub['awarded_points']} pts</span></div>
                                <div><b>AI Confidence:</b> {sub['confidence_score']:.1f}%</div>
                            </div>
                            {f'<div style="margin-top: 10px; padding: 8px 12px; background: #F8FAFC; border-radius: 6px; font-size: 13px;"><b>Faculty Remarks:</b> {sub["faculty_remark"]}</div>' if sub.get('faculty_remark') else ''}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info(f"No certificate submissions found for register number **{search_reg}**.")
        else:
            st.info("Enter your Register Number above to view all your past submissions and verification statuses.")

    # ---------------- TAB 3: GUIDELINES ----------------
    with tab_guide:
        st.markdown("### 📘 KTU Activity Point Policy & Category Matrix")
        st.write("According to APJ Abdul Kalam Technological University regulations, students must acquire minimum activity points for the award of B.Tech Degree.")

        rules = get_rules(DB_PATH)
        for r in rules:
            with st.expander(f"{r['category_name']} — Default: {r['default_points']} Pts (Max Cap: {r['max_points']} Pts)"):
                st.write(f"**Description:** {r['description']}")
                st.write(f"**Recommended Evidence:** Certificate of completion with organization seal, dates, and student register number/name.")


if __name__ == "__main__":
    st.set_page_config(page_title="Student Portal - KTU Activity Points", page_icon="🎓", layout="wide")
    render_student_page()
