import sqlite3

from fastapi.testclient import TestClient


def test_snapshot_response_table_loads_after_manifest_validation(tmp_path, monkeypatch):
    from api import main, snapshot

    db_path = tmp_path / "snapshot.sqlite"
    key = main.snapshot_cache_key("sample")
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE api_response_cache (cache_key TEXT PRIMARY KEY, payload TEXT)")
        conn.execute(
            "INSERT INTO api_response_cache VALUES (?, ?)",
            (key, '{"data":[{"ready":true}]}'),
        )

    monkeypatch.setattr(main, "read_only_enabled", lambda: True)
    monkeypatch.setattr(main, "lake_connect", lambda: sqlite3.connect(db_path))
    monkeypatch.setattr(snapshot, "validated_manifest", lambda: {"verified": True})
    monkeypatch.setattr(main, "_SNAPSHOT_RESPONSES", None)

    assert main._snapshot_responses()[key]["data"][0]["ready"] is True


def test_cached_endpoint_prefers_published_snapshot_payload(monkeypatch):
    from api import main

    expected = {"data": [{"value": "published"}]}
    key = main.snapshot_cache_key("sample", kwargs={"value": 1})
    monkeypatch.setattr(main, "_SNAPSHOT_RESPONSES", {key: expected})
    monkeypatch.setattr(main, "read_only_enabled", lambda: True)

    calls = 0

    @main.cached
    def sample(value):
        nonlocal calls
        calls += 1
        return {"data": [{"value": value}]}

    assert sample(value=1) == expected
    assert calls == 0


def test_fastapi_query_arguments_match_publish_time_cache_key(monkeypatch):
    from api import main

    expected = {
        "data": [{"route": "DEL-BOM", "hhi_observed": 2500}],
        "meta_data": {"page": 1, "totalRecords": 1, "totalPages": 1, "recordPerPage": 1},
        "msg": "Data fetched successfully",
        "statusCode": True,
    }
    key = main.snapshot_cache_key("get_competition", kwargs={"days": 14})
    monkeypatch.setattr(main, "_SNAPSHOT_RESPONSES", {key: expected})
    monkeypatch.setattr(main, "read_only_enabled", lambda: True)

    response = TestClient(main.app).get("/api/apix/getCompetition?days=14")

    assert response.status_code == 200
    assert response.json() == expected


def test_fair_fare_panel_returns_complete_latest_route_day(tmp_path, monkeypatch):
    from api import main

    db_path = tmp_path / "quotes.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE fare_quotes (
                carrier TEXT, flight_no TEXT, origin TEXT, dest TEXT,
                departure_date TEXT, collected_at TEXT, lead_days INTEGER,
                rbd TEXT, total_fare REAL, base_fare REAL, taxes_fees REAL,
                seats_available INTEGER, source TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO fare_quotes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    "QP",
                    "QP1",
                    "DEL",
                    "BOM",
                    "2026-09-20",
                    "2026-09-18T00:20:00",
                    2,
                    "Y",
                    5000,
                    4000,
                    1000,
                    5,
                    "akasa",
                ),
                (
                    "QP",
                    "QP2",
                    "DEL",
                    "BOM",
                    "2026-09-21",
                    "2026-09-19T00:20:00",
                    2,
                    "Y",
                    5500,
                    4400,
                    1100,
                    4,
                    "akasa",
                ),
                (
                    "AI",
                    "AI1",
                    "DEL",
                    "BOM",
                    "2026-09-21",
                    "2026-09-19T00:21:00",
                    2,
                    None,
                    5300,
                    None,
                    None,
                    None,
                    "serpapi",
                ),
                (
                    "QP",
                    "QP3",
                    "BLR",
                    "BOM",
                    "2026-09-21",
                    "2026-09-19T00:22:00",
                    2,
                    "Y",
                    5100,
                    4100,
                    1000,
                    3,
                    "akasa",
                ),
            ],
        )

    monkeypatch.setattr(main, "lake_connect", lambda: sqlite3.connect(db_path))
    result = main.get_fair_fare_panel.__wrapped__(route_code="DEL-BOM")

    assert result["meta_data"]["totalRecords"] == 2
    assert {row["flight_no"] for row in result["data"]} == {"QP2", "AI1"}
    assert all(row["collected_at"].startswith("2026-09-19") for row in result["data"])
