"""
KTU Activity Point Verification Assistant - Main Application Entry Point.
A comprehensive AI-assisted certificate screening, OCR data extraction,
activity point recommendation, duplicate detection, and faculty verification system.
"""

import os
import sys
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from utils.database import (
    init_db, get_dashboard_stats, get_all_certificates,
    get_all_students, get_rules, DB_PATH
)
from utils.ocr import is_tesseract_installed
from utils.rules import calculate_suggested_points, get_all_categories, DEFAULT_KTU_RULES
from utils.reports import generate_excel_report, generate_csv_report
from pages.student import render_student_page
from pages.faculty import render_faculty_page

# Set Page Config
st.set_page_config(
    page_title="KTU Activity Point Verification Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Database
init_db(DB_PATH)


def load_css():
    """Load application stylesheets."""
    css_path = os.path.join(BASE_DIR, "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_home_overview():
    """Render the central portal overview and analytics summary."""
    load_css()

    st.markdown("""
        <div class="ktu-header">
            <h1>🏛️ APJ Abdul Kalam Technological University</h1>
            <p>KTU Activity Point Verification Assistant — AI-Powered Certificate Screening & Faculty Approval System</p>
        </div>
    """, unsafe_allow_html=True)

    # ---------------- 1. TOP KPI METRICS ----------------
    stats = get_dashboard_stats(DB_PATH)

    st.markdown("""
        <div class="kpi-container">
            <div class="kpi-card kpi-total">
                <div class="kpi-title">Total Submissions</div>
                <div class="kpi-value">{total}</div>
            </div>
            <div class="kpi-card kpi-pending">
                <div class="kpi-title">Pending Verification</div>
                <div class="kpi-value">{pending}</div>
            </div>
            <div class="kpi-card kpi-recommended">
                <div class="kpi-title">AI Recommended</div>
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
                <div class="kpi-title">Approved Certificates</div>
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

    # ---------------- 2. QUICK PORTAL NAVIGATION CARDS ----------------
    st.markdown("### 🚀 Access Verification Modules")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="card-panel" style="border-left: 4px solid #2563EB;">
            <h3>🎓 Student Portal</h3>
            <p style="color: #64748B;">Upload activity point certificates (PDF, JPG, PNG) with instant OCR extraction preview, suggested activity points, duplicate screening, and tracking status.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Open Student Portal", type="primary", use_container_width=True):
            st.session_state["active_nav"] = "Student Portal"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="card-panel" style="border-left: 4px solid #059669;">
            <h3>👨‍🏫 Faculty Advisor Hub</h3>
            <p style="color: #64748B;">Secure faculty approval studio with split-screen document viewer, metadata editor, KTU point awarding, batch approval, and Excel/CSV reports export.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Open Faculty Hub", type="secondary", use_container_width=True):
            st.session_state["active_nav"] = "Faculty Hub"
            st.rerun()

    # ---------------- 3. ANALYTICS & CHARTS ----------------
    st.markdown("---")
    st.markdown("### 📈 Verification Analytics & Distribution")

    certs = get_all_certificates(db_path=DB_PATH)
    if certs:
        df_certs = pd.DataFrame(certs)
        c_chart1, c_chart2 = st.columns(2)

        with c_chart1:
            st.markdown("##### 🎯 Verification Status Breakdown")
            status_counts = df_certs["status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            
            color_map = {
                "Approved": "#2563EB",
                "Recommended": "#059669",
                "Manual Verification Required": "#D97706",
                "Flagged": "#DC2626",
                "Rejected": "#64748B"
            }
            
            fig_status = px.pie(
                status_counts,
                names="Status",
                values="Count",
                color="Status",
                color_discrete_map=color_map,
                hole=0.4
            )
            fig_status.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
            st.plotly_chart(fig_status, use_container_width=True)

        with c_chart2:
            st.markdown("##### 📂 Submissions by Category")
            cat_counts = df_certs["activity_category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            
            fig_cat = px.bar(
                cat_counts,
                x="Category",
                y="Count",
                color="Count",
                color_continuous_scale="Blues"
            )
            fig_cat.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
            st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("No certificate data recorded yet. Upload certificates to view distribution charts.")

    # ---------------- 4. INTERACTIVE POINT CALCULATOR WIDGET ----------------
    st.markdown("---")
    st.markdown("### 🧮 Interactive KTU Activity Point Calculator")
    st.caption("Estimate allowable activity points for various KTU events and certification levels.")

    calc_col1, calc_col2 = st.columns([1.2, 1])
    with calc_col1:
        calc_cat = st.selectbox("Select Activity Category", get_all_categories(), key="home_calc_cat")
        calc_notes = st.text_input("Keywords / Achievement (e.g. '1st Prize Winner', 'Elite+Gold', '4 weeks')", placeholder="e.g. 1st Prize Winner")
    
    with calc_col2:
        calc_pts, calc_exp = calculate_suggested_points(calc_cat, calc_notes)
        st.metric("Estimated Suggested Points", f"{calc_pts} Pts")
        st.caption(f"**Policy Breakdown:** {calc_exp}")


def render_analytics_page():
    """Detailed analytics and audit export reports."""
    load_css()
    st.markdown("### 📊 KTU Verification Reports & Auditing")

    certs = get_all_certificates(db_path=DB_PATH)
    if not certs:
        st.info("No submissions currently recorded in the database.")
        return

    df = pd.DataFrame(certs)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        excel_data = generate_excel_report(only_approved=False)
        st.download_button(
            "📥 Download Complete Audit Report (Excel .xlsx)",
            data=excel_data,
            file_name=f"KTU_Complete_Activity_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col_btn2:
        csv_data = generate_csv_report(only_approved=False)
        st.download_button(
            "📥 Download Complete Audit Report (CSV .csv)",
            data=csv_data,
            file_name=f"KTU_Complete_Activity_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.markdown("#### 📋 All Certificate Records")
    st.dataframe(df[[
        "certificate_id", "register_number", "student_name", "activity_category",
        "extracted_activity", "confidence_score", "suggested_points", "awarded_points", "status", "upload_date"
    ]], use_container_width=True, hide_index=True)


def render_system_status():
    """System diagnostic, OCR status, and sample data generator."""
    load_css()
    st.markdown("### ⚙️ System Settings & Diagnostics")

    tess_status = is_tesseract_installed()
    
    st.markdown(f"""
        <div class="card-panel">
            <h4>System Configuration</h4>
            <ul>
                <li><b>Database Engine:</b> SQLite 3 (<code>{DB_PATH}</code>)</li>
                <li><b>PDF Engine:</b> pdfplumber + pypdfium2 (Active ✅)</li>
                <li><b>Image Engine:</b> Pillow + OpenCV (cv2) (Active ✅)</li>
                <li><b>Tesseract OCR:</b> {'Detected & Active ✅' if tess_status else 'Optional Scanned OCR Mode (PDF native streams & fallbacks active) ⚠️'}</li>
                <li><b>Data & Excel Export:</b> Pandas + OpenPyXL (Active ✅)</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🔄 Sample Data Management")
    st.write("Reset or re-seed the SQLite database with realistic sample KTU students and test certificates.")

    if st.button("🌱 Re-Seed Sample Database & Certificates", type="primary"):
        from database.sample_data import seed_database_and_samples
        with st.spinner("Seeding database..."):
            seed_database_and_samples()
        st.success("Database seeded with sample students and test certificates!")
        st.rerun()


def main():
    """Main Application Controller."""
    load_css()

    # Sidebar Navigation
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/diploma.png", width=64)
        st.title("KTU CertiPoint")
        st.caption("v1.0.0 | KTU Activity Point Verification")

        st.markdown("---")
        nav_options = [
            "🏠 Overview Dashboard",
            "🎓 Student Portal",
            "👨‍🏫 Faculty Hub",
            "📊 Analytics & Reports",
            "⚙️ System Diagnostics"
        ]

        # Sync with session state
        default_index = 0
        if "active_nav" in st.session_state:
            if "Student" in st.session_state["active_nav"]:
                default_index = 1
            elif "Faculty" in st.session_state["active_nav"]:
                default_index = 2
            elif "Analytics" in st.session_state["active_nav"]:
                default_index = 3

        selected_page = st.radio("Navigation", nav_options, index=default_index)

        st.markdown("---")
        st.markdown("#### 💡 Quick Help")
        st.markdown("""
        - **Student:** Upload PDF/Image certificates.
        - **Faculty Login:** `faculty` / `admin123`.
        - **Export:** Excel (.xlsx) / CSV (.csv).
        """)

    # Routing
    if selected_page == "🏠 Overview Dashboard":
        render_home_overview()
    elif selected_page == "🎓 Student Portal":
        render_student_page()
    elif selected_page == "👨‍🏫 Faculty Hub":
        render_faculty_page()
    elif selected_page == "📊 Analytics & Reports":
        render_analytics_page()
    elif selected_page == "⚙️ System Diagnostics":
        render_system_status()


if __name__ == "__main__":
    main()
