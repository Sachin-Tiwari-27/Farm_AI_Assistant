"""
dashboard/pages/3_DB_Stats.py
──────────────────────────────
Live database statistics and raw table inspector.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import db as dashboard_db

st.set_page_config(page_title="DB Stats — Farm AI Admin", page_icon="🗄️", layout="wide")

# ── Auth guard ────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.warning("Please log in from the Home page first.")
    st.stop()

with st.sidebar:
    st.markdown("### 🌱 Farm AI Admin")
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

st.title("🗄️ Database Stats")

# ── Metrics ───────────────────────────────────────────────────────────────────
counts = dashboard_db.get_table_counts()
db_mb  = dashboard_db.get_db_size_mb()

st.subheader("Table Row Counts")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("users",            counts.get("users", 0))
c2.metric("landmarks",        counts.get("landmarks", 0))
c3.metric("logs",             counts.get("logs", 0))
c4.metric("media",            counts.get("media", 0))
c5.metric("ai_interactions",  counts.get("ai_interactions", 0))

st.markdown(f"**DB file size:** `{db_mb:.3f} MB`")

st.markdown("---")

# ── Raw table viewer ──────────────────────────────────────────────────────────
st.subheader("Raw Table Viewer")
st.caption("Shows the most recent rows (up to 50). Read-only.")

table = st.selectbox(
    "Choose a table",
    ["users", "landmarks", "logs", "media", "ai_interactions"]
)

rows = dashboard_db.get_table_rows(table, limit=50)
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(rows)} row(s) shown.")
else:
    st.info(f"Table `{table}` is empty.")
