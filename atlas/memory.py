"""
memory.py — SQLite-backed persistence for Atlas.

Stores three things:
  1. users            — one row per Telegram user (profile facts, onboarding state)
  2. messages          — full conversation history, used to rebuild context each turn
  3. watchlist_items    — tickers a user has asked to be tracked

Kept deliberately dumb: no ORM, just sqlite3 + small helper functions.
"""

import sqlite3
import json
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = "finance_assistant.db"


def init_db(path: str = DB_PATH):
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                name          TEXT,
                onboarded     INTEGER DEFAULT 0,
                facts_json    TEXT DEFAULT '{}',
                created_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER,
                role          TEXT,       -- 'user' | 'assistant' | 'tool'
                content       TEXT,
                created_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS watchlist_items (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER,
                ticker        TEXT,
                added_at      TEXT,
                UNIQUE(user_id, ticker)
            );
            """
        )


@contextmanager
def _connect(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- users ----------

def get_or_create_user(user_id: int, name: str = "") -> sqlite3.Row:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return row
        conn.execute(
            "INSERT INTO users (user_id, name, onboarded, facts_json, created_at) VALUES (?, ?, 0, '{}', ?)",
            (user_id, name, _now()),
        )
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def mark_onboarded(user_id: int):
    with _connect() as conn:
        conn.execute("UPDATE users SET onboarded = 1 WHERE user_id = ?", (user_id,))


def save_fact(user_id: int, key: str, value: str):
    """Persist a small durable fact about the user, e.g. risk_tolerance: 'conservative'."""
    with _connect() as conn:
        row = conn.execute("SELECT facts_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        facts = json.loads(row["facts_json"]) if row else {}
        facts[key] = value
        conn.execute(
            "UPDATE users SET facts_json = ? WHERE user_id = ?",
            (json.dumps(facts), user_id),
        )


def get_facts(user_id: int) -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT facts_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return json.loads(row["facts_json"]) if row else {}


# ---------- conversation history ----------

def add_message(user_id: int, role: str, content: str):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, _now()),
        )


def get_recent_messages(user_id: int, limit: int = 20) -> list[dict]:
    """Returns the last `limit` messages, oldest first, ready to feed into the LLM."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


# ---------- watchlist ----------

def add_to_watchlist(user_id: int, ticker: str):
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist_items (user_id, ticker, added_at) VALUES (?, ?, ?)",
            (user_id, ticker.upper(), _now()),
        )


def remove_from_watchlist(user_id: int, ticker: str):
    with _connect() as conn:
        conn.execute(
            "DELETE FROM watchlist_items WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )


def get_watchlist(user_id: int) -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist_items WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        ).fetchall()
    return [r["ticker"] for r in rows]


def get_all_user_ids() -> list[int]:
    with _connect() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
    return [r["user_id"] for r in rows]
