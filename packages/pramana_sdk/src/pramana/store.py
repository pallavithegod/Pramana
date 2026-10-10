"""Mutable runtime history, isolated from the read-only analytical vault."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class SignalStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS observations (
                    product_id TEXT NOT NULL, observed_at TEXT NOT NULL,
                    currency TEXT NOT NULL, value REAL NOT NULL,
                    source TEXT NOT NULL, source_url TEXT,
                    PRIMARY KEY(product_id, observed_at)
                );
                CREATE TABLE IF NOT EXISTS reports (
                    run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                yield conn
        finally:
            conn.close()

    def record(self, items: list[dict], observed_at: str) -> None:
        with self.connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?)",
                [
                    (
                        i["product_id"],
                        observed_at,
                        i["currency"],
                        i["value"],
                        i["source"],
                        i.get("url"),
                    )
                    for i in items
                    if i.get("value") is not None
                ],
            )

    def history(self, product_id: str, limit: int = 90) -> list[dict]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT observed_at,value,currency,source,source_url FROM observations "
                "WHERE product_id=? ORDER BY observed_at DESC LIMIT ?",
                [product_id, limit],
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def save_report(self, run_id: str, created_at: str, payload: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reports VALUES (?,?,?)",
                [run_id, created_at, json.dumps(payload, allow_nan=False)],
            )

    def report(self, run_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM reports WHERE run_id=?", [run_id]).fetchone()
        return json.loads(row[0]) if row else None
