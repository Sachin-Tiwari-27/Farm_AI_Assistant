"""
dashboard/pages/2_Logs.py
─────────────────────────
Log viewer with filters, CSV/JSON download, and AI interaction explorer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import json
import streamlit as st
import pandas as pd
import db as dashboard_db
from datetime import date, timedelta

st.set_page_config(page_title="Logs — Farm AI Admin", page_icon="📋", layout="wide")

# ── Auth guard ────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.warning("Please log in from the Home page first.")
    st.stop()

with st.sidebar:
    st.markdown("### 🌱 Farm AI Admin")
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

st.title("📋 Logs & Downloads")

# ── Filters ───────────────────────────────────────────────────────────────────
users = dashboard_db.get_all_users()
user_options = {"All Users": None} | {f"{u['name']} ({u['farm']})": u["id"] for u in users}

col1, col2, col3, col4 = st.columns(4)
with col1:
    start_d = st.date_input("From date", value=date.today() - timedelta(days=30))
with col2:
    end_d   = st.date_input("To date",   value=date.today())
with col3:
    sel_user_label = st.selectbox("User", list(user_options.keys()))
    sel_user_id    = user_options[sel_user_label]
with col4:
    sel_cat = st.selectbox("Category", ["All", "morning", "evening", "adhoc"])
    cat_filter = None if sel_cat == "All" else sel_cat

# ── Fetch & display ───────────────────────────────────────────────────────────
logs = dashboard_db.get_logs(
    user_id    = sel_user_id,
    category   = cat_filter,
    start_date = start_d.isoformat(),
    end_date   = end_d.isoformat(),
)

st.markdown(f"**{len(logs)} log(s)** matching filters.")

if logs:
    display_cols = ["date", "user_name", "landmark_label", "category", "status", "transcription"]
    df = pd.DataFrame(logs)

    # Truncate transcription for table display
    if "transcription" in df.columns:
        df["transcription"] = df["transcription"].fillna("").str[:120]

    # Only show columns that exist
    available_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available_cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("⬇️ Downloads")
    dl1, dl2 = st.columns(2)

    with dl1:
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False)
        st.download_button(
            label    = "📥 Download Filtered Logs (.csv)",
            data     = csv_buf.getvalue(),
            file_name= f"farm_logs_{start_d}_{end_d}.csv",
            mime     = "text/csv",
            use_container_width=True,
        )

    with dl2:
        raw_json = dashboard_db.get_logs_json_raw()
        st.download_button(
            label    = "📥 Download Full logs.json",
            data     = raw_json,
            file_name= "logs.json",
            mime     = "application/json",
            use_container_width=True,
        )
else:
    st.info("No logs found for selected filters.")
    _, dl_col, _ = st.columns([1, 2, 1])
    with dl_col:
        raw_json = dashboard_db.get_logs_json_raw()
        st.download_button(
            label    = "📥 Download Full logs.json",
            data     = raw_json,
            file_name= "logs.json",
            mime     = "application/json",
            use_container_width=True,
        )

# ── AI Interactions ───────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("🤖 AI Interactions / Chat Log"):
    ai_logs = dashboard_db.get_ai_interactions(user_id=sel_user_id)
    if ai_logs:
        ai_df = pd.DataFrame(ai_logs)
        ai_display = [c for c in ["timestamp", "user_name", "model_used", "rating",
                                   "feedback_status", "prompt", "response"] if c in ai_df.columns]
        # Truncate long columns for display
        for col in ["prompt", "response"]:
            if col in ai_df.columns:
                ai_df[col] = ai_df[col].fillna("").str[:200]
        st.dataframe(ai_df[ai_display], use_container_width=True, hide_index=True)

        ai_csv = io.StringIO()
        pd.DataFrame(ai_logs).to_csv(ai_csv, index=False)
        st.download_button(
            "📥 Download AI Interactions (.csv)",
            data=ai_csv.getvalue(),
            file_name="ai_interactions.csv",
            mime="text/csv",
        )
    else:
        st.info("No AI interactions found.")
