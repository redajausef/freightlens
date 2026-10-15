"""Small SQLite repository. Parameterized queries and atomic review updates."""

import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from freightlens.models import Review


class Repository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS reviews "
                "(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, body TEXT NOT NULL)"
            )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, review_id: str) -> Review | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM reviews WHERE id=?", (review_id,)).fetchone()
        return Review.model_validate_json(row[0]) if row else None

    def find(self, fingerprint: str) -> Review | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM reviews WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
        return Review.model_validate_json(row[0]) if row else None

    def all(self) -> list[Review]:
        with self.connect() as db:
            rows = db.execute("SELECT body FROM reviews ORDER BY rowid DESC LIMIT 100").fetchall()
        return [Review.model_validate_json(row[0]) for row in rows]

    def insert(self, fingerprint: str, review: Review) -> tuple[Review, bool]:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO reviews VALUES (?, ?, ?)",
                (review.id, fingerprint, review.model_dump_json()),
            )
            created = cursor.rowcount == 1
            row = db.execute(
                "SELECT body FROM reviews WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
        return Review.model_validate_json(row[0]), created

    def update(self, review_id: str, change: Callable[[Review], None]) -> Review | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM reviews WHERE id=?", (review_id,)).fetchone()
            if not row:
                return None
            review = Review.model_validate_json(row[0])
            change(review)
            db.execute(
                "UPDATE reviews SET body=? WHERE id=?", (review.model_dump_json(), review_id)
            )
        return review
