"""
dashboard/pages/1_Users.py
──────────────────────────
Full CRUD for registered users and their landmarks.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import db as dashboard_db

st.set_page_config(page_title="Users — Farm AI Admin", page_icon="👤", layout="wide")

# ── Auth guard ────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.warning("Please log in from the Home page first.")
    st.stop()

# ── Sidebar logout ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🌱 Farm AI Admin")
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

# ── Constants ─────────────────────────────────────────────────────────────────
ENVS    = ["Open Field", "Polyhouse", "Controlled Env (CEA)"]
MEDIUMS = ["Soil", "Cocopeat", "Soil + Cocopeat", "Hydroponic", "Other"]

st.title("👤 Users & Landmarks")
users = dashboard_db.get_all_users()

if not users:
    st.info("No registered users in the database.")
    st.stop()

# ── User selector ─────────────────────────────────────────────────────────────
user_options = {f"{u['name']} ({u['farm']}) — ID {u['id']}": u for u in users}
selected_label = st.selectbox("Select a user to view / edit", list(user_options.keys()))
user = user_options[selected_label]

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════ #
# SECTION 1 — Edit Profile
# ════════════════════════════════════════════════════════════════════════════ #
with st.expander("✏️ Edit Profile & Schedule", expanded=True):
    with st.form("edit_profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_name  = st.text_input("Full Name",  value=user["name"])
            new_farm  = st.text_input("Farm Name",  value=user["farm"])
            new_lat   = st.number_input("Latitude",  value=float(user["lat"] or 0.0), format="%.6f")
            new_lon   = st.number_input("Longitude", value=float(user["lon"] or 0.0), format="%.6f")
        with col2:
            new_p = st.text_input("Morning Alert Time (HH:MM)", value=user["p_time"] or "")
            new_v = st.text_input("Evening Alert Time (HH:MM)", value=user["v_time"] or "")
            st.markdown("")  # spacer
            st.markdown(f"**Telegram ID:** `{user['id']}`")

        submitted = st.form_submit_button("💾 Save Profile Changes", use_container_width=True)
        if submitted:
            ok = dashboard_db.update_user_profile(
                user["id"], new_name, new_farm, new_lat, new_lon, new_p, new_v
            )
            if ok:
                st.success("✅ Profile updated. Changes take effect immediately.")
                st.rerun()
            else:
                st.error("❌ Update failed — check server logs.")

# ════════════════════════════════════════════════════════════════════════════ #
# SECTION 2 — Landmark Management
# ════════════════════════════════════════════════════════════════════════════ #
st.subheader("🪨 Landmarks")
landmarks = user.get("landmarks", [])

if landmarks:
    lm_df = pd.DataFrame([{
        "ID": lm["landmark_id"], "Label": lm["label"],
        "Environment": lm["env"], "Medium": lm["medium"]
    } for lm in landmarks])
    st.dataframe(lm_df, use_container_width=True, hide_index=True)
else:
    st.info("No landmarks registered for this user.")

# ── Edit existing landmark ─────────────────────────────────────────────────
if landmarks:
    with st.expander("✏️ Edit a Landmark"):
        lm_map = {f"[{lm['landmark_id']}] {lm['label']}": lm for lm in landmarks}
        lm_label = st.selectbox("Select landmark to edit", list(lm_map.keys()), key="edit_lm_sel")
        lm = lm_map[lm_label]
        with st.form("edit_lm_form"):
            new_label  = st.text_input("Label",       value=lm["label"])
            new_env    = st.selectbox("Environment",  ENVS,    index=ENVS.index(lm["env"]) if lm["env"] in ENVS else 0)
            new_medium = st.selectbox("Medium",       MEDIUMS, index=MEDIUMS.index(lm["medium"]) if lm["medium"] in MEDIUMS else 0)
            if st.form_submit_button("💾 Save Landmark Changes", use_container_width=True):
                ok = dashboard_db.update_landmark(user["id"], lm["landmark_id"], new_label, new_env, new_medium)
                if ok:
                    st.success(f"✅ Landmark [{lm['landmark_id']}] updated.")
                    st.rerun()
                else:
                    st.error("❌ Update failed.")

# ── Delete a landmark ──────────────────────────────────────────────────────
if landmarks:
    with st.expander("🗑️ Delete a Landmark"):
        lm_del_map = {f"[{lm['landmark_id']}] {lm['label']}": lm for lm in landmarks}
        del_label = st.selectbox("Select landmark to delete", list(lm_del_map.keys()), key="del_lm_sel")
        del_lm    = lm_del_map[del_label]
        st.warning(f"This will permanently remove **{del_lm['label']}** from this user's profile.")
        if st.checkbox(f"I confirm I want to delete [{del_lm['landmark_id']}] {del_lm['label']}", key="del_lm_chk"):
            if st.button("🗑️ Delete Landmark", type="primary"):
                ok = dashboard_db.delete_landmark(user["id"], del_lm["landmark_id"])
                if ok:
                    st.success("✅ Landmark deleted.")
                    st.rerun()
                else:
                    st.error("❌ Deletion failed.")

# ── Add new landmark ───────────────────────────────────────────────────────
with st.expander("➕ Add New Landmark"):
    with st.form("add_lm_form"):
        add_label  = st.text_input("Landmark Name (e.g. 'North Tunnel')")
        add_env    = st.selectbox("Environment", ENVS,    key="add_env")
        add_medium = st.selectbox("Medium",      MEDIUMS, key="add_med")
        if st.form_submit_button("➕ Add Landmark", use_container_width=True):
            if not add_label.strip():
                st.error("Label cannot be empty.")
            else:
                ok = dashboard_db.add_landmark(user["id"], add_label.strip(), add_env, add_medium)
                if ok:
                    st.success(f"✅ Landmark '{add_label}' added.")
                    st.rerun()
                else:
                    st.error("❌ Add failed.")

# ════════════════════════════════════════════════════════════════════════════ #
# SECTION 3 — Delete User
# ════════════════════════════════════════════════════════════════════════════ #
st.markdown("---")
with st.expander("☠️ Delete This User", expanded=False):
    st.error(
        f"This permanently removes **{user['name']}** ({user['farm']}) "
        f"and their **{len(landmarks)} landmark(s)** from the database. "
        f"**Logs are preserved.** This cannot be undone."
    )
    if st.checkbox(f"I confirm I want to delete user {user['name']} (ID: {user['id']})", key="del_user_chk"):
        if st.button("🗑️ Delete User", type="primary"):
            ok = dashboard_db.delete_user_and_landmarks(user["id"])
            if ok:
                st.success(f"✅ User {user['name']} has been removed.")
                st.rerun()
            else:
                st.error("❌ Deletion failed — check server logs.")
