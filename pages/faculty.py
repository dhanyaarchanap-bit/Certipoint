"""
Faculty Verification Dashboard & Decision Studio.
Provides secure faculty authentication, KPI overview, search/filtering, split-screen certificate inspection,
metadata editing, point adjustment, approval workflows, batch actions, and Excel/CSV report exports.
"""

import os
import sys
import io
from datetime import datetime
import streamlit as st
import pandas as pd
from PIL import Image

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from utils.database import (
    init_db, get_dashboard_stats, get_all_certificates,
    get_certificate_by_id, update_verification_status,
    update_extraction, get_rules, DB_PATH
)
from utils.rules import validate_awarded_points, get_all_categories
from utils.reports import generate_excel_report, generate_csv_report

# Ensure database is initialized
init_db(DB_PATH)

# Demo Faculty Credentials
FACULTY_USERS = {
    "faculty": "admin123",
    "advisor": "ktu2024",
    "hod": "cetcsdept"
}


def load_css():
    """Load UI stylesheets."""
    css_path = os.path.join(BASE_DIR, "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def check_faculty_auth() -> bool:
    """Handle secure faculty login session state."""
    if st.session_state.get("faculty_logged_in", False):
        return True

    st.markdown("""
        <div class="ktu-header">
            <h1>👨‍🏫 Faculty Verification Portal Login</h1>
            <p>Access KTU Activity Point Verification Dashboard, Certificate Screening, and Student Point Approval Queue.</p>
        </div>
    """, unsafe_allow_html=True)

    col_l, col_center, col_r = st.columns([1, 1.4, 1])
    with col_center:
        st.markdown("### 🔐 Faculty Advisor Authentication")
        with st.form("faculty_login_form"):
            username = st.text_input("Faculty ID / Username", placeholder="e.g. faculty").strip()
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Sign In to Faculty Dashboard", type="primary", use_container_width=True)

            if submit:
                if username in FACULTY_USERS and FACULTY_USERS[username] == password:
                    st.session_state["faculty_logged_in"] = True
                    st.session_state["faculty_username"] = username
                    st.session_state["faculty_role"] = "Faculty Advisor" if username != "hod" else "Head of Department"
                    st.success(f"Welcome, {username.title()}!")
                    st.rerun()
                else:
                    st.error("Invalid Faculty ID or Password. (Demo: `faculty` / `admin123`)")

        st.info("💡 **Demo Access:** Username: `faculty` | Password: `admin123`")

    return False


def render_faculty_page():
    """Main Faculty Verification Page."""
    load_css()

    if not check_faculty_auth():
        return

    # Top Navigation & User Bar
    faculty_user = st.session_state.get("faculty_username", "Faculty Advisor")
    faculty_role = st.session_state.get("faculty_role", "Faculty Advisor")

    st.markdown(f"""
        <div class="ktu-header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h1>👨‍🏫 KTU Faculty Verification Dashboard</h1>
                    <p>Welcome back, <b>{faculty_user.title()}</b> ({faculty_role}) | Department of Computer Science & Engineering</p>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Logout button in sidebar
    with st.sidebar:
        st.markdown(f"**Logged in as:** `{faculty_user}`")
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state["faculty_logged_in"] = False
            st.session_state.pop("faculty_username", None)
            st.session_state.pop("selected_cert_id", None)
            st.rerun()

    # ---------------- 1. KPI DASHBOARD METRIC CARDS ----------------
    stats = get_dashboard_stats(DB_PATH)

    st.markdown("""
        <div class="kpi-container">
            <div class="kpi-card kpi-total">
                <div class="kpi-title">Total Uploads</div>
                <div class="kpi-value">{total}</div>
            </div>
            <div class="kpi-card kpi-pending">
                <div class="kpi-title">Pending Review</div>
                <div class="kpi-value">{pending}</div>
            </div>
            <div class="kpi-card kpi-recommended">
                <div class="kpi-title">Recommended</div>
                <div class="kpi-value">{recommended}</div>
            </div>
            <div class="kpi-card kpi-manual">
                <div class="kpi-title">Manual Review</div>
                <div class="kpi-value">{manual}</div>
            </div>
            <div class="kpi-card kpi-flagged">
                <div class="kpi-title">Flagged / Duplicates</div>
                <div class="kpi-value">{flagged}</div>
            </div>
            <div class="kpi-card kpi-approved">
                <div class="kpi-title">Approved</div>
                <div class="kpi-value">{approved}</div>
            </div>
        </div>
    """.format(
        total=stats["total"],
        pending=stats["pending"],
        recommended=stats["recommended"],
        manual=stats["manual_verification"],
        flagged=stats["flagged"],
        approved=stats["approved"]
    ), unsafe_allow_html=True)

    # ---------------- 2. SEARCH & FILTER CONTROLS ----------------
    st.markdown("### 🗂️ Certificate Verification Queue")

    col_search, col_status_filter, col_cat_filter = st.columns([1.5, 1, 1])

    with col_search:
        search_query = st.text_input("🔍 Search by Register No, Student Name, or Keyword", placeholder="e.g. TVE21CS001 or Python or NPTEL")

    with col_status_filter:
        status_options = ["All Statuses", "Pending Review", "Recommended", "Manual Verification Required", "Flagged", "Approved", "Rejected"]
        selected_status_filter = st.selectbox("Filter by Status", status_options, index=0)

    with col_cat_filter:
        cat_options = ["All Categories"] + get_all_categories()
        selected_cat_filter = st.selectbox("Filter by Category", cat_options, index=0)

    # Map filter
    db_status_param = None
    if selected_status_filter == "Pending Review":
        # We will filter in pandas or query
        pass
    elif selected_status_filter != "All Statuses":
        db_status_param = selected_status_filter

    certificates_list = get_all_certificates(
        status=db_status_param,
        search=search_query if search_query else None,
        category=selected_cat_filter if selected_cat_filter != "All Categories" else None,
        db_path=DB_PATH
    )

    if selected_status_filter == "Pending Review":
        certificates_list = [c for c in certificates_list if c["status"] in ["Recommended", "Manual Verification Required", "Flagged"]]

    # ---------------- 3. BATCH ACTIONS & EXPORT TOOLBAR ----------------
    col_batch, col_exp_xlsx, col_exp_csv = st.columns([2, 1, 1])

    with col_batch:
        # Quick Batch Approval for all Recommended certificates
        rec_count = sum(1 for c in certificates_list if c["status"] == "Recommended")
        if rec_count > 0:
            if st.button(f"⚡ 1-Click Batch Approve All {rec_count} Recommended Certificate(s)", type="primary"):
                for c in certificates_list:
                    if c["status"] == "Recommended":
                        update_verification_status(
                            certificate_id=c["certificate_id"],
                            status="Approved",
                            awarded_points=c["suggested_points"],
                            faculty_remark="Batch approved by faculty (High OCR confidence).",
                            approved_by=faculty_user,
                            db_path=DB_PATH
                        )
                st.success(f"Successfully batch-approved {rec_count} recommended certificate(s)!")
                st.rerun()

    with col_exp_xlsx:
        excel_bytes = generate_excel_report(only_approved=False)
        st.download_button(
            label="📥 Export to Excel (.xlsx)",
            data=excel_bytes,
            file_name=f"KTU_Activity_Points_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col_exp_csv:
        csv_bytes = generate_csv_report(only_approved=False)
        st.download_button(
            label="📥 Export to CSV (.csv)",
            data=csv_bytes,
            file_name=f"KTU_Activity_Points_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.write("")

    # ---------------- 4. CERTIFICATES TABLE & DETAIL INSPECTION DRAWER ----------------
    if not certificates_list:
        st.info("No certificates found matching the selected filter criteria.")
        return

    # Table Display
    df_display = []
    for c in certificates_list:
        df_display.append({
            "ID": c["certificate_id"],
            "Register No": c["register_number"],
            "Student Name": c["student_name"] or "N/A",
            "Category": c["activity_category"],
            "Activity / Topic": c["extracted_activity"] or "N/A",
            "Organization": c["extracted_organization"] or "N/A",
            "Confidence": f"{c['confidence_score']:.1f}%",
            "Suggested Pts": c["suggested_points"],
            "Awarded Pts": c["awarded_points"],
            "Status": c["status"],
            "Uploaded": c["upload_date"][:10] if c["upload_date"] else "N/A"
        })

    table_df = pd.DataFrame(df_display)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # ---------------- 5. CERTIFICATE INSPECTION & APPROVAL STUDIO ----------------
    st.markdown("---")
    st.markdown("### 🔬 Certificate Inspection & Approval Studio")

    cert_ids = [c["certificate_id"] for c in certificates_list]
    current_selected = st.session_state.get("selected_cert_id", cert_ids[0] if cert_ids else None)
    
    selected_id_idx = cert_ids.index(current_selected) if current_selected in cert_ids else 0
    selected_cert_id = st.selectbox(
        "Select Certificate ID to Inspect & Verify:",
        cert_ids,
        index=selected_id_idx,
        format_func=lambda x: f"Cert #{x} — {next((c['register_number'] + ' (' + (c['student_name'] or 'Student') + ') - ' + c['activity_category'] for c in certificates_list if c['certificate_id'] == x), str(x))}"
    )
    st.session_state["selected_cert_id"] = selected_cert_id

    # Fetch full details
    cert_detail = get_certificate_by_id(selected_cert_id, DB_PATH)
    if not cert_detail:
        st.warning("Certificate details could not be loaded.")
        return

    # Split View Layout
    split_col_left, split_col_right = st.columns([1.1, 1.2], gap="large")

    # LEFT PANEL: DOCUMENT VIEWER
    with split_col_left:
        st.markdown(f"#### 📄 Certificate Document: `{cert_detail['file_name']}`")
        file_path = cert_detail.get("file_path", "")

        if os.path.exists(file_path):
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in [".png", ".jpg", ".jpeg", ".webp"]:
                try:
                    img = Image.open(file_path)
                    st.image(img, caption=f"ID #{selected_cert_id} - {cert_detail['file_name']}", use_container_width=True)
                except Exception as e:
                    st.error(f"Image load error: {e}")
            elif file_ext == ".pdf":
                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        if len(pdf.pages) > 0:
                            p_img = pdf.pages[0].to_image(resolution=200).original
                            st.image(p_img, caption=f"PDF Page 1 - {cert_detail['file_name']}", use_container_width=True)
                except Exception as e:
                    st.caption(f"📄 PDF Document: {cert_detail['file_name']}")
                    st.info("PDF document attached. Download or inspect text below.")

            with open(file_path, "rb") as f:
                btn_dl = st.download_button(
                    label=f"⬇️ Download Original {os.path.basename(file_path)}",
                    data=f.read(),
                    file_name=os.path.basename(file_path),
                    use_container_width=True
                )
        else:
            st.warning(f"File not found at `{file_path}`.")

        # Raw OCR Text expander
        with st.expander("📝 Extracted Raw Text Stream", expanded=False):
            st.code(cert_detail.get("raw_text") or "(No raw text stored)")

    # RIGHT PANEL: METADATA, VALIDATION, AND DECISION FORM
    with split_col_right:
        st.markdown("#### ⚙️ Validation Report & Verification Decision")

        curr_status = cert_detail.get("status", "Manual Verification Required")
        conf_val = cert_detail.get("confidence_score", 0.0)

        # Status badge indicator
        status_pill_class = "status-manual"
        if curr_status == "Approved":
            status_pill_class = "status-approved"
        elif curr_status == "Recommended":
            status_pill_class = "status-recommended"
        elif curr_status == "Flagged":
            status_pill_class = "status-flagged"
        elif curr_status == "Rejected":
            status_pill_class = "status-rejected"

        st.markdown(f"""
            <div style="display: flex; gap: 15px; align-items: center; margin-bottom: 15px;">
                <div class="status-pill {status_pill_class}">Current: {curr_status}</div>
                <div style="font-size: 14px; color: #475569;"><b>AI Confidence:</b> <b>{conf_val:.1f}%</b></div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("##### ✏️ Extracted Metadata (Faculty Editable)")

        with st.form(f"verify_form_{selected_cert_id}"):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                edit_reg = st.text_input("Register Number", value=cert_detail.get("register_number", ""), disabled=True)
                edit_name = st.text_input("Extracted Student Name", value=cert_detail.get("extracted_name") or cert_detail.get("student_name") or "")
                edit_cat = st.text_input("Activity Category", value=cert_detail.get("activity_category", ""), disabled=True)

            with f_col2:
                edit_date = st.text_input("Extracted Event Date", value=cert_detail.get("extracted_date") or "")
                edit_org = st.text_input("Issuing Organization", value=cert_detail.get("extracted_organization") or "")
                edit_cert_no = st.text_input("Certificate ID / Serial", value=cert_detail.get("certificate_number") or "")

            edit_act = st.text_input("Activity Title / Topic", value=cert_detail.get("extracted_activity") or "")

            st.markdown("##### 🎯 Activity Point Awarding")
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                sug_pts = cert_detail.get("suggested_points", 10)
                st.write(f"**AI Suggested Points:** `{sug_pts} Pts`")
            with p_col2:
                default_awarded = cert_detail.get("awarded_points") if cert_detail.get("awarded_points", 0) > 0 else sug_pts
                awarded_pts = st.number_input(
                    "Points to Award*",
                    min_value=0,
                    max_value=60,
                    value=int(default_awarded),
                    step=5,
                    help="Award points within KTU allowable category caps."
                )

            remarks_val = cert_detail.get("faculty_remark") or ""
            faculty_remark = st.text_area("Faculty Remarks / Notes", value=remarks_val, placeholder="e.g. Verified with portal. Authentic participation certificate.")

            st.markdown("##### 🏁 Verification Action")
            act_col1, act_col2, act_col3 = st.columns(3)

            btn_approve = act_col1.form_submit_button("✅ Approve Certificate", type="primary", use_container_width=True)
            btn_reject = act_col2.form_submit_button("❌ Reject Certificate", use_container_width=True)
            btn_save_edits = act_col3.form_submit_button("💾 Save Metadata Only", use_container_width=True)

            if btn_approve:
                # Validate awarded points against rules
                is_valid, msg = validate_awarded_points(cert_detail.get("activity_category", ""), awarded_pts)
                if not is_valid:
                    st.error(f"Cannot approve: {msg}")
                else:
                    # Update extraction edits
                    update_extraction(
                        certificate_id=selected_cert_id,
                        extracted_name=edit_name,
                        extracted_activity=edit_act,
                        extracted_date=edit_date,
                        extracted_organization=edit_org,
                        certificate_number=edit_cert_no,
                        db_path=DB_PATH
                    )
                    # Update status
                    update_verification_status(
                        certificate_id=selected_cert_id,
                        status="Approved",
                        awarded_points=awarded_pts,
                        faculty_remark=faculty_remark if faculty_remark else "Approved by faculty advisor.",
                        approved_by=faculty_user,
                        db_path=DB_PATH
                    )
                    st.success(f"Certificate #{selected_cert_id} APPROVED for {awarded_pts} points!")
                    st.rerun()

            elif btn_reject:
                update_verification_status(
                    certificate_id=selected_cert_id,
                    status="Rejected",
                    awarded_points=0,
                    faculty_remark=faculty_remark if faculty_remark else "Certificate rejected by faculty advisor.",
                    approved_by=faculty_user,
                    db_path=DB_PATH
                )
                st.warning(f"Certificate #{selected_cert_id} has been REJECTED.")
                st.rerun()

            elif btn_save_edits:
                update_extraction(
                    certificate_id=selected_cert_id,
                    extracted_name=edit_name,
                    extracted_activity=edit_act,
                    extracted_date=edit_date,
                    extracted_organization=edit_org,
                    certificate_number=edit_cert_no,
                    db_path=DB_PATH
                )
                st.success("Metadata edits saved successfully.")
                st.rerun()


if __name__ == "__main__":
    st.set_page_config(page_title="Faculty Dashboard - KTU Activity Points", page_icon="👨‍🏫", layout="wide")
    render_faculty_page()
