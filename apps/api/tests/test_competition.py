from __future__ import annotations

import sqlite3

from api import main


def test_competition_uses_only_serpapi_distinct_flight_numbers(tmp_path, monkeypatch):
    db_path = tmp_path / "competition.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE fare_quotes (
            source TEXT NOT NULL,
            origin TEXT NOT NULL,
            dest TEXT NOT NULL,
            carrier TEXT NOT NULL,
            flight_no TEXT,
            collected_at TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO fare_quotes VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("serpapi", "DEL", "BOM", "AI", "AI101", "2026-09-13T00:20:00+05:30"),
            ("serpapi", "DEL", "BOM", "AI", "AI102", "2026-09-13T00:20:00+05:30"),
            ("serpapi", "DEL", "BOM", "6E", "6E201", "2026-09-13T00:20:00+05:30"),
            # Direct-airline observations must not skew the common comparison panel.
            ("akasa", "DEL", "BOM", "QP", "QP301", "2026-09-20T00:20:00+05:30"),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(main, "lake_connect", lambda: sqlite3.connect(db_path))
    result = main.get_competition.__wrapped__(days=7)["data"][0]

    assert result["n_carriers"] == 2
    assert result["n_flights_observed"] == 3
    assert result["top_carrier"] == "AI"
    assert result["top_share_pct"] == 66.7
    assert result["hhi_observed"] == 5556
    assert "SerpAPI" in result["method"]
