"""
dashboard/db.py
───────────────
Standalone SQLite helpers for the Streamlit admin dashboard.
Intentionally has NO dependency on src/ so the dashboard process is
fully isolated from the bot. Uses WAL mode (same as the bot) so both
processes can coexist safely on the same DB file.
"""
import sqlite3
import json
import os
import uuid
from datetime import datetime

# Resolve DB path relative to the project root (one level up from dashboard/)
_DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT  = os.path.dirname(_DASHBOARD_DIR)
DB_PATH        = os.path.join(_PROJECT_ROOT, "data", "db", "farm.db")
JSON_LOGS_PATH = os.path.join(_PROJECT_ROOT, "data", "db", "logs.json")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


# ─── READ ────────────────────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    """Return every user with their landmark list."""
    conn = _get_conn()
    try:
        users = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
        result = []
        for u in users:
            lms = conn.execute(
                "SELECT * FROM landmarks WHERE user_id=? ORDER BY landmark_id",
                (u["id"],)
            ).fetchall()
            d = dict(u)
            d["landmarks"] = [dict(lm) for lm in lms]
            result.append(d)
        return result
    finally:
        conn.close()


def get_logs(user_id=None, category=None, start_date=None, end_date=None) -> list[dict]:
    """Return logs with optional filters, joined with user name and landmark label."""
    conn = _get_conn()
    try:
        query = """
            SELECT l.*, u.name as user_name,
                   lm.label as landmark_label
            FROM logs l
            LEFT JOIN users u ON l.user_id = u.id
            LEFT JOIN landmarks lm ON l.user_id = lm.user_id
                                   AND l.landmark_id = lm.landmark_id
            WHERE 1=1
        """
        params: list = []
        if user_id:
            query += " AND l.user_id = ?"
            params.append(user_id)
        if category:
            query += " AND l.category = ?"
            params.append(category)
        if start_date:
            query += " AND l.date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND l.date <= ?"
            params.append(end_date)
        query += " ORDER BY l.timestamp DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_ai_interactions(user_id=None) -> list[dict]:
    conn = _get_conn()
    try:
        if user_id:
            rows = conn.execute(
                "SELECT * FROM ai_interactions WHERE user_id=? ORDER BY timestamp DESC",
                (user_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT ai.*, u.name as user_name FROM ai_interactions ai "
                "LEFT JOIN users u ON ai.user_id = u.id "
                "ORDER BY ai.timestamp DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_table_counts() -> dict:
    conn = _get_conn()
    try:
        tables = ["users", "landmarks", "logs", "media", "ai_interactions"]
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in tables
        }
    finally:
        conn.close()


def get_table_rows(table: str, limit: int = 50) -> list[dict]:
    """Fetch the last `limit` rows from any table (for the raw inspector)."""
    allowed = {"users", "landmarks", "logs", "media", "ai_interactions"}
    if table not in allowed:
        return []
    conn = _get_conn()
    try:
        rows = conn.execute(f"SELECT * FROM {table} LIMIT {limit}").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_logs_json_raw() -> str:
    """Return the raw contents of logs.json shadow file."""
    if os.path.exists(JSON_LOGS_PATH):
        with open(JSON_LOGS_PATH, "r") as f:
            return f.read()
    return "[]"


def get_db_size_mb() -> float:
    try:
        return os.path.getsize(DB_PATH) / (1024 * 1024)
    except FileNotFoundError:
        return 0.0


# ─── WRITE ───────────────────────────────────────────────────────────────────

def update_user_profile(user_id: int, name: str, farm: str,
                        lat: float, lon: float,
                        p_time: str, v_time: str) -> bool:
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE users SET name=?, farm=?, lat=?, lon=?, p_time=?, v_time=? WHERE id=?",
            (name, farm, lat, lon, p_time, v_time, user_id)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def update_landmark(user_id: int, landmark_id: int,
                    label: str, env: str, medium: str) -> bool:
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE landmarks SET label=?, env=?, medium=? WHERE user_id=? AND landmark_id=?",
            (label, env, medium, user_id, landmark_id)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def add_landmark(user_id: int, label: str, env: str, medium: str) -> bool:
    """Assigns the next available landmark_id (max + 1) for this user."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(landmark_id) FROM landmarks WHERE user_id=?", (user_id,)
        ).fetchone()
        next_id = (row[0] or 0) + 1
        conn.execute(
            "INSERT INTO landmarks (user_id, landmark_id, label, env, medium) VALUES (?,?,?,?,?)",
            (user_id, next_id, label, env, medium)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def delete_landmark(user_id: int, landmark_id: int) -> bool:
    conn = _get_conn()
    try:
        conn.execute(
            "DELETE FROM landmarks WHERE user_id=? AND landmark_id=?",
            (user_id, landmark_id)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def delete_user_and_landmarks(user_id: int) -> bool:
    """Removes user + their landmarks. Logs are intentionally preserved."""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM landmarks WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()
