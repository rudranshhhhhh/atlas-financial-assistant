"""
memory.py — Postgres-backed persistence for Atlas (hosted on Neon).

Stores three things:
  1. users            — one row per Telegram user (profile facts, onboarding state)
  2. messages          — full conversation history, used to rebuild context each turn
  3. watchlist_items    — tickers a user has asked to be tracked

Connects using the DATABASE_URL env var (your Neon connection string).
Every function name/signature below matches the old SQLite version exactly,
so nothing in ai_engine.py, tools.py, bot.py, or scheduler.py needs to change.
"""

import os
import json
from datetime import datetime, timezone
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ["DATABASE_URL"]


def init_db():
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id       BIGINT PRIMARY KEY,
                    name          TEXT,
                    onboarded     INTEGER DEFAULT 0,
                    facts_json    TEXT DEFAULT '{}',
                    created_at    TEXT
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id            SERIAL PRIMARY KEY,
                    user_id       BIGINT,
                    role          TEXT,
                    content       TEXT,
                    created_at    TEXT
                );

                CREATE TABLE IF NOT EXISTS watchlist_items (
                    id            SERIAL PRIMARY KEY,
                    user_id       BIGINT,
                    ticker        TEXT,
                    added_at      TEXT,
                    UNIQUE(user_id, ticker)
                );
                """
            )


@contextmanager
def _connect():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_or_create_user(user_id: int, name: str = "") -> dict:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                return row
            cur.execute(
                "INSERT INTO users (user_id, name, onboarded, facts_json, created_at) VALUES (%s, %s, 0, '{}', %s)",
                (user_id, name, _now()),
            )
            cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            return cur.fetchone()


def mark_onboarded(user_id: int):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET onboarded = 1 WHERE user_id = %s", (user_id,))


def save_fact(user_id: int, key: str, value: str):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT facts_json FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            facts = json.loads(row["facts_json"]) if row else {}
            facts[key] = value
            cur.execute(
                "UPDATE users SET facts_json = %s WHERE user_id = %s",
                (json.dumps(facts), user_id),
            )


def get_facts(user_id: int) -> dict:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT facts_json FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return json.loads(row["facts_json"]) if row else {}


def add_message(user_id: int, role: str, content: str):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (user_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                (user_id, role, content, _now()),
            )


def get_recent_messages(user_id: int, limit: int = 20) -> list[dict]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM messages WHERE user_id = %s ORDER BY id DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def add_to_watchlist(user_id: int, ticker: str):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO watchlist_items (user_id, ticker, added_at) VALUES (%s, %s, %s) ON CONFLICT (user_id, ticker) DO NOTHING",
                (user_id, ticker.upper(), _now()),
            )


def remove_from_watchlist(user_id: int, ticker: str):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM watchlist_items WHERE user_id = %s AND ticker = %s",
                (user_id, ticker.upper()),
            )


def get_watchlist(user_id: int) -> list[str]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ticker FROM watchlist_items WHERE user_id = %s ORDER BY added_at",
                (user_id,),
            )
            rows = cur.fetchall()
    return [r["ticker"] for r in rows]


def get_all_user_ids() -> list[int]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users")
            rows = cur.fetchall()
    return [r["user_id"] for r in rows]