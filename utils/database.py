"""
utils/database.py
------------------
Multi-tenant SQLite data layer. Every table that holds company-specific
data carries a `workspace_id` foreign key, and every query in this module
filters by it. This is the core of "data isolation" between companies.

NOTE ON SCALE: SQLite is fine for a single-server MVP / early customers.
When you have real paying customers and concurrent writers, migrate this
class to Postgres (the method signatures below are written so that a
Postgres-backed subclass can drop in with minimal changes).
"""

import sqlite3
import os
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Optional


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", "./data/app.db")
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    industry TEXT,
                    linkedin_access_token TEXT,
                    linkedin_person_urn TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT,
                    score INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',   -- pending / approved / rejected
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    idea_id INTEGER REFERENCES ideas(id) ON DELETE SET NULL,
                    topic TEXT,
                    content TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',      -- draft / scheduled / published
                    scheduled_date TEXT,
                    linkedin_post_urn TEXT,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS competitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    profile_urn TEXT,          -- e.g. urn:li:person:XXXX or organization urn
                    profile_url TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    post_id INTEGER REFERENCES posts(id) ON DELETE SET NULL,
                    commenter_name TEXT,
                    comment_text TEXT,
                    matched_keyword TEXT,
                    status TEXT DEFAULT 'new',   -- new / contacted / converted / ignored
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ideas_ws ON ideas(workspace_id);
                CREATE INDEX IF NOT EXISTS idx_posts_ws ON posts(workspace_id);
                CREATE INDEX IF NOT EXISTS idx_competitors_ws ON competitors(workspace_id);
                CREATE INDEX IF NOT EXISTS idx_leads_ws ON leads(workspace_id);
                """
            )

    # ---------------- Workspaces ----------------
    def create_workspace(self, name: str, industry: str = "") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO workspaces (name, industry, created_at) VALUES (?, ?, ?)",
                (name, industry, datetime.utcnow().isoformat()),
            )
            return cur.lastrowid

    def get_workspaces(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM workspaces ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_workspace(self, workspace_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_workspace_linkedin_credentials(self, workspace_id: int, access_token: str, person_urn: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE workspaces SET linkedin_access_token = ?, linkedin_person_urn = ? WHERE id = ?",
                (access_token, person_urn, workspace_id),
            )

    # ---------------- Ideas ----------------
    def add_idea(self, workspace_id: int, title: str, description: str, score: int = 0) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO ideas (workspace_id, title, description, score, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (workspace_id, title, description, score, datetime.utcnow().isoformat()),
            )
            return cur.lastrowid

    def get_ideas(self, workspace_id: int, status: Optional[str] = None) -> list[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM ideas WHERE workspace_id = ? AND status = ? ORDER BY score DESC",
                    (workspace_id, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM ideas WHERE workspace_id = ? ORDER BY score DESC",
                    (workspace_id,),
                ).fetchall()
            return [dict(r) for r in rows]

    def update_idea_status(self, idea_id: int, workspace_id: int, status: str):
        # workspace_id passed explicitly and checked in the WHERE clause -- this is
        # what prevents workspace A from editing workspace B's rows even if an id leaks.
        with self._conn() as conn:
            conn.execute(
                "UPDATE ideas SET status = ? WHERE id = ? AND workspace_id = ?",
                (status, idea_id, workspace_id),
            )

    # ---------------- Posts ----------------
    def add_post(self, workspace_id: int, content: str, topic: str = "",
                 idea_id: Optional[int] = None, status: str = "draft",
                 scheduled_date: Optional[str] = None) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO posts (workspace_id, idea_id, topic, content, status,
                   scheduled_date, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (workspace_id, idea_id, topic, content, status, scheduled_date,
                 datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
            )
            return cur.lastrowid

    def get_posts(self, workspace_id: int, status: Optional[str] = None) -> list[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM posts WHERE workspace_id = ? AND status = ? ORDER BY created_at DESC",
                    (workspace_id, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM posts WHERE workspace_id = ? ORDER BY created_at DESC",
                    (workspace_id,),
                ).fetchall()
            return [dict(r) for r in rows]

    def update_post(self, post_id: int, workspace_id: int, **fields):
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [post_id, workspace_id]
        with self._conn() as conn:
            conn.execute(
                f"UPDATE posts SET {set_clause} WHERE id = ? AND workspace_id = ?",
                values,
            )

    def mark_published(self, post_id: int, workspace_id: int, linkedin_post_urn: str):
        self.update_post(post_id, workspace_id, status="published",
                          linkedin_post_urn=linkedin_post_urn)

    # ---------------- Competitors ----------------
    def add_competitor(self, workspace_id: int, name: str, profile_urn: str = "",
                        profile_url: str = "") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO competitors (workspace_id, name, profile_urn, profile_url, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (workspace_id, name, profile_urn, profile_url, datetime.utcnow().isoformat()),
            )
            return cur.lastrowid

    def get_competitors(self, workspace_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM competitors WHERE workspace_id = ?", (workspace_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ---------------- Leads ----------------
    def add_lead(self, workspace_id: int, comment_text: str, matched_keyword: str,
                 post_id: Optional[int] = None, commenter_name: str = "") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO leads (workspace_id, post_id, commenter_name, comment_text,
                   matched_keyword, created_at) VALUES (?, ?, ?, ?, ?, ?)""",
                (workspace_id, post_id, commenter_name, comment_text, matched_keyword,
                 datetime.utcnow().isoformat()),
            )
            return cur.lastrowid

    def get_leads(self, workspace_id: int, status: Optional[str] = None) -> list[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM leads WHERE workspace_id = ? AND status = ? ORDER BY created_at DESC",
                    (workspace_id, status),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM leads WHERE workspace_id = ? ORDER BY created_at DESC",
                    (workspace_id,),
                ).fetchall()
            return [dict(r) for r in rows]
