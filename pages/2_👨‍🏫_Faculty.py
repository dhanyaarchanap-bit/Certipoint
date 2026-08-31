"""
Faculty Dashboard Page Wrapper for Streamlit multi-page routing.
"""

import streamlit as st
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from pages.faculty import render_faculty_page

st.set_page_config(
    page_title="Faculty Dashboard - KTU Activity Points",
    page_icon="👨‍🏫",
    layout="wide"
)

render_faculty_page()
