"""
dashboard/app.py
────────────────
Entry point for the Farm AI Assistant admin dashboard.
Run with: streamlit run dashboard/app.py
"""
import os
import sys
import streamlit as st
from dotenv import load_dotenv

# ── Resolve paths ─────────────────────────────────────────────────────────────
_DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT  = os.path.dirname(_DASHBOARD_DIR)
sys.path.insert(0, _DASHBOARD_DIR)   # so pages can import db

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Farm AI — Admin",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Password gate ─────────────────────────────────────────────────────────────
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🌱 Farm AI — Admin Dashboard")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔒 Login Required")
        pwd = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Login", use_container_width=True):
            if pwd == DASHBOARD_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

# ── Authenticated — Home / Overview ───────────────────────────────────────────
import db as dashboard_db   # noqa: E402  (imported after path setup)

st.title("🌱 Farm AI — Admin Dashboard")
st.caption("Overview · Use the sidebar to navigate to Users, Logs, or DB Stats.")

# Logout button in sidebar
with st.sidebar:
    st.markdown("### 🌱 Farm AI Admin")
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

# ── Metrics row ───────────────────────────────────────────────────────────────
counts = dashboard_db.get_table_counts()
db_mb  = dashboard_db.get_db_size_mb()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("👤 Users",         counts.get("users", 0))
c2.metric("🪨 Landmarks",     counts.get("landmarks", 0))
c3.metric("📋 Log Entries",   counts.get("logs", 0))
c4.metric("🤖 AI Chats",      counts.get("ai_interactions", 0))
c5.metric("💾 DB Size",       f"{db_mb:.2f} MB")

st.markdown("---")

# ── Quick user summary table ──────────────────────────────────────────────────
st.subheader("Registered Users")
users = dashboard_db.get_all_users()
if users:
    import pandas as pd
    rows = [{
        "ID":          u["id"],
        "Name":        u["name"],
        "Farm":        u["farm"],
        "Morning":     u["p_time"],
        "Evening":     u["v_time"],
        "Landmarks":   len(u["landmarks"]),
        "Lat":         u["lat"],
        "Lon":         u["lon"],
    } for u in users]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No registered users yet.")
