"""Air-Sankhyiki API — a prototype using api.mospi.gov.in-style envelopes.

MoSPI envelope (verified live 29 Aug 2026):
    {"data": [...], "meta_data": {page, totalRecords, totalPages, recordPerPage},
     "msg": "Data fetched successfully", "statusCode": true}

The live local MVP serves collected quotes, APIx, PRISM, nowcast, competition,
and ledger-health endpoints. Optional 15-minute demo authentication mirrors the
shape of the MoSPI flow; production government integration still requires
security, schema, and deployment review by the owning authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
import sqlite3
import threading
import time

from collectors.storage import DB_PATH, read_only_enabled
from collectors.storage import connect as lake_connect
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI(
    title="Air-Sankhyiki APIx",
    description="Real-time Airfare Price Index for India — MoSPI-mirror conventions",
    version="0.1.0",
)

# Dashboard (Next.js dev server / Vercel) reads these endpoints client-side.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("APIX_CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1_000)


# --------------------------------------------------------------------------- #
# Result cache. The index/PRISM/nowcast endpoints recompute pandas pipelines
# over the whole quote lake — seconds per call — but the lake only changes when
# a collection run writes (once nightly). So: memoize every computed payload
# keyed on the SQLite file's mtime; a new collection invalidates everything
# automatically, and repeat page loads serve in microseconds.
# --------------------------------------------------------------------------- #

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_LOCKS: dict[str, threading.Lock] = {}
_CACHE_LOCKS_GUARD = threading.Lock()
_SNAPSHOT_RESPONSES: dict[str, dict] | None = None


def _db_mtime() -> float:
    try:
        return os.path.getmtime(DB_PATH)
    except OSError:
        return 0.0


def _plain_cache_value(value):
    """Convert FastAPI Query defaults and ordinary values into stable JSON."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    default = getattr(value, "default", None)
    if default is None or isinstance(default, (str, int, float, bool)):
        return default
    return str(value)


def snapshot_cache_key(fn_name: str, args: tuple = (), kwargs: dict | None = None) -> str:
    """Canonical key shared by publish-time materialization and live requests."""
    return json.dumps(
        {
            "function": fn_name,
            "args": [_plain_cache_value(value) for value in args],
            "kwargs": {
                key: _plain_cache_value(value) for key, value in sorted((kwargs or {}).items())
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _snapshot_responses() -> dict[str, dict]:
    """Load verified, publish-time API payloads from an immutable snapshot.

    Older snapshots do not contain this table and safely fall back to runtime
    computation. New snapshots serve analytical pages without running pandas
    on Render's request path.
    """
    global _SNAPSHOT_RESPONSES
    if not read_only_enabled():
        return {}
    if _SNAPSHOT_RESPONSES is not None:
        return _SNAPSHOT_RESPONSES

    from api.snapshot import validated_manifest

    validated_manifest()
    conn = lake_connect()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='api_response_cache'"
        ).fetchone()
        if not exists:
            _SNAPSHOT_RESPONSES = {}
        else:
            _SNAPSHOT_RESPONSES = {
                key: json.loads(payload)
                for key, payload in conn.execute(
                    "SELECT cache_key, payload FROM api_response_cache"
                )
            }
    finally:
        conn.close()
    return _SNAPSHOT_RESPONSES


def cached(fn):
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = snapshot_cache_key(fn.__name__, args, kwargs)
        published = _snapshot_responses().get(key)
        if published is not None:
            return published
        mtime = _db_mtime()
        hit = _CACHE.get(key)
        if hit and hit[0] == mtime:
            return hit[1]

        # A cold Render instance can receive the dashboard request while its
        # background cache warmer is still computing the same pandas payload.
        # Coalesce those calls so the free-tier CPU performs the calculation
        # once instead of running two copies in contention.
        with _CACHE_LOCKS_GUARD:
            key_lock = _CACHE_LOCKS.setdefault(key, threading.Lock())
        with key_lock:
            mtime = _db_mtime()
            hit = _CACHE.get(key)
            if hit and hit[0] == mtime:
                return hit[1]
            result = fn(*args, **kwargs)
            _CACHE[key] = (mtime, result)
            return result

    return wrapper


# --------------------------------------------------------------------------- #
# Auth — mirrors api.mospi.gov.in: signup → login → 15-minute bearer token.
# Enforcement is off by default (APIX_REQUIRE_AUTH=1 turns it on) so the public
# dashboard works while the MoSPI-parity flow stays demo-able.
# --------------------------------------------------------------------------- #

TOKEN_TTL_S = 15 * 60
_JWT_SECRET = os.environ.get("APIX_JWT_SECRET", "dev-secret-change-in-prod")
_REQUIRE_AUTH = os.environ.get("APIX_REQUIRE_AUTH", "0") == "1"


def _b64url(b: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _jwt_encode(payload: dict) -> str:
    import base64

    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"


def _jwt_decode(token: str) -> dict | None:
    import base64

    try:
        header, body, sig = token.split(".")
        expected = hmac.new(
            _JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256
        ).digest()
        got = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
        if not hmac.compare_digest(expected, got):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:  # noqa: BLE001 — any malformed token is just unauthorized
        return None


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """MoSPI-parity enforcement: when APIX_REQUIRE_AUTH=1, every /api/apix/*
    call needs a live bearer token from /api/auth/login (15-min expiry)."""
    if _REQUIRE_AUTH and request.url.path.startswith("/api/apix/"):
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not token or _jwt_decode(token) is None:
            return JSONResponse(
                status_code=401,
                content={"data": [], "msg": "Invalid or expired token", "statusCode": False},
            )
    return await call_next(request)


def _users_db() -> sqlite3.Connection:
    if read_only_enabled():
        raise HTTPException(
            status_code=503,
            detail="Demo account storage is disabled on the read-only hosted snapshot",
        )
    conn = lake_connect()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_users ("
        "email TEXT PRIMARY KEY, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    return conn


def _hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


class Credentials(BaseModel):
    email: str
    password: str


@app.post("/api/auth/signup")
def signup(body: Credentials) -> dict:
    conn = _users_db()
    salt = secrets.token_hex(16)
    try:
        with conn:
            conn.execute(
                "INSERT INTO api_users VALUES (?,?,?,datetime('now'))",
                [body.email.lower(), salt, _hash_pw(body.password, salt)],
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="User already exists") from None
    finally:
        conn.close()
    return {"data": {"email": body.email}, "msg": "Signup successful", "statusCode": True}


@app.post("/api/auth/login")
def login(body: Credentials) -> dict:
    conn = _users_db()
    row = conn.execute(
        "SELECT salt, pw_hash FROM api_users WHERE email=?", [body.email.lower()]
    ).fetchone()
    conn.close()
    if not row or not hmac.compare_digest(row[1], _hash_pw(body.password, row[0])):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _jwt_encode({"sub": body.email.lower(), "exp": int(time.time()) + TOKEN_TTL_S})
    return {
        "data": {"token": token, "tokenType": "Bearer", "expiresInSeconds": TOKEN_TTL_S},
        "msg": "Login successful",
        "statusCode": True,
    }


def envelope(rows: list[dict], page: int, per_page: int, total: int) -> dict:
    return {
        "data": rows,
        "meta_data": {
            "page": page,
            "totalRecords": total,
            "totalPages": max(1, math.ceil(total / per_page)),
            "recordPerPage": per_page,
        },
        "msg": "Data fetched successfully" if rows else "No Data Found",
        "statusCode": bool(rows),
    }


@app.get("/api/apix/getQuotes")
def get_quotes(
    route_code: str | None = Query(default=None, description="e.g. DEL-BOM"),
    carrier_code: str | None = Query(default=None, description="IATA code, e.g. QP"),
    leadtime_code: int | None = Query(default=None, description="advance window: 1|7|15|30|45"),
    limit: int = Query(default=100, le=1000),
    page: int = Query(default=1, ge=1),
) -> dict:
    where, params = ["1=1"], []
    if route_code:
        o, _, d = route_code.partition("-")
        where.append("origin=? AND dest=?")
        params += [o.upper(), d.upper()]
    if carrier_code:
        where.append("carrier=?")
        params.append(carrier_code.upper())
    if leadtime_code is not None:
        where.append("lead_days BETWEEN ? AND ?")
        params += [leadtime_code - 2, leadtime_code + 2]

    conn = lake_connect()
    conn.row_factory = sqlite3.Row
    clause = " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) FROM fare_quotes WHERE {clause}", params).fetchone()[0]
    rows = [
        dict(r)
        for r in conn.execute(
            f"SELECT * FROM fare_quotes WHERE {clause} ORDER BY collected_at DESC LIMIT ? OFFSET ?",
            params + [limit, (page - 1) * limit],
        )
    ]
    conn.close()
    return envelope(rows, page, limit, total)


@app.get("/api/apix/getFairFarePanel")
@cached
def get_fair_fare_panel(route_code: str = Query(description="e.g. DEL-BOM")) -> dict:
    """Latest complete route panel for the Fair Fare comparison.

    Unlike the paginated audit endpoint, this returns only the newest observed
    collection day for one route. The browser therefore receives the complete
    comparison set without downloading historical rows or guessing whether the
    first page covered the full day.
    """
    origin, _, dest = route_code.upper().partition("-")
    conn = lake_connect()
    conn.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT carrier, flight_no, origin, dest, departure_date, collected_at,
                   lead_days, rbd, total_fare, base_fare, taxes_fees,
                   seats_available, source
            FROM fare_quotes
            WHERE origin=? AND dest=?
              AND substr(collected_at,1,10) = (
                  SELECT MAX(substr(collected_at,1,10))
                  FROM fare_quotes WHERE origin=? AND dest=?
              )
            ORDER BY total_fare, carrier, flight_no
            """,
            [origin, dest, origin, dest],
        )
    ]
    conn.close()
    return envelope(rows, 1, max(len(rows), 1), len(rows))


@app.get("/api/apix/getAPIxIndex")
@cached
def get_apix_index(
    limit: int = Query(default=100, le=1000),
    page: int = Query(default=1, ge=1),
    leadtime_code: int | None = Query(
        default=None, description="restrict to one advance window: 1|7|15|30|45"
    ),
) -> dict:
    """Daily headline APIx — v2 engine (2 Sep 2026): quality gates → rolling
    GEKS-Törnqvist per cell (product-churn-proof, drift-free) → BCWFI weights
    (DGCA route share × booking-density). Same response shape as v1.
    leadtime_code restricts the aggregate to a single booking window."""
    import pandas as pd
    import yaml
    from apix_index.aggregate import compute_apix_v2, lead_bucket

    conn = lake_connect()
    quotes = pd.read_sql_query(
        "SELECT origin, dest, carrier, flight_no, lead_days, total_fare, collected_at "
        "FROM fare_quotes",
        conn,
    )
    conn.close()
    # isinstance guard: when called internally (nowcast, cache warmer) without
    # kwargs, FastAPI's Query default object arrives instead of None — treating
    # it as a real filter silently empties the index (bug found 6 Sep).
    if isinstance(leadtime_code, int) and not quotes.empty:
        quotes = quotes[lead_bucket(quotes["lead_days"]) == leadtime_code]

    basket_path = DB_PATH.parents[1] / "route_basket.yaml"
    weights = None
    if basket_path.exists():
        with open(basket_path, encoding="utf-8") as f:
            basket = yaml.safe_load(f)
        weights = {f"{r['origin']}-{r['dest']}": r["weight"] for r in basket["routes"]}

    daily = compute_apix_v2(quotes, weights)
    rows = [
        {
            "date": str(r["day"]),
            "index": round(r["apix"], 2),
            "inflation": r["inflation_dod"],
            "status": "P",  # provisional daily, matching NSO release discipline
            "n_cells": r["n_cells"],
            "n_matched_products": r["n_matched"],
        }
        for r in daily.to_dict("records")
    ]
    total = len(rows)
    rows = rows[(page - 1) * limit : page * limit]
    return envelope(rows, page, limit, total)


def _quotes_df(route_code: str | None = None):
    import pandas as pd

    conn = lake_connect()
    where = ""
    params: list[str] = []
    if route_code:
        origin, _, dest = route_code.upper().partition("-")
        where = " WHERE origin=? AND dest=?"
        params = [origin, dest]
    df = pd.read_sql_query(
        "SELECT origin, dest, carrier, flight_no, lead_days, total_fare, base_fare, "
        "rbd, seats_available, source, collected_at FROM fare_quotes" + where,
        conn,
        params=params,
    )
    conn.close()
    return df


@app.get("/api/apix/getRouteHeatmap")
@cached
def get_route_heatmap() -> dict:
    """Signature visual feed: per (route × lead bucket) — latest cell index vs its
    base day, latest cheapest fare, product count. One row per cell."""
    from apix_index.aggregate import cell_indices, prepare

    df = _quotes_df()
    prices = prepare(df)
    cells = cell_indices(prices)
    latest_fare = (
        prices.sort_values("day")
        .groupby(["route", "bucket"], as_index=False)
        .last()[["route", "bucket", "price"]]
    )
    rows = []
    if not cells.empty:
        latest = cells.sort_values("day").groupby(["route", "bucket"], as_index=False).last()
        merged = latest.merge(latest_fare, on=["route", "bucket"], how="left")
        rows = [
            {
                "route": r["route"],
                "leadtime_code": int(r["bucket"]),
                "index": round(float(r["index"]), 2),
                "change_pct": round(float(r["index"]) - 100.0, 2),
                "latest_fare": round(float(r["price"]), 0) if r["price"] == r["price"] else None,
                "n_matched_products": int(r["n_matched"]),
                "as_of": str(r["day"]),
            }
            for r in merged.to_dict("records")
        ]
    return envelope(rows, 1, max(len(rows), 1), len(rows))


@app.get("/api/apix/getRouteSeries")
@cached
def get_route_series(route_code: str = Query(description="e.g. DEL-BOM")) -> dict:
    """Daily cell indices plus the observed booking curve for one route.

    Index values remain matched-product measures. Fare levels are preserved for
    every observed day/window even when product churn leaves that cell without
    a fixed-base index match.
    """
    from apix_index.aggregate import cell_indices, prepare

    df = _quotes_df(route_code)
    rows = []
    if not df.empty:
        prices = prepare(df)
        cells = cell_indices(prices)
        fares = prices.groupby(["day", "bucket"], as_index=False)["price"].min()
        # The booking curve is a current cross-window price view, not an index
        # relative. Keep every observed fare and attach matched-index metadata
        # where it exists. Using cells as the left side silently discarded
        # current T+ windows after flight-number churn.
        merged = (
            fares.merge(
                cells[["day", "bucket", "index", "n_matched"]],
                on=["day", "bucket"],
                how="left",
            )
            if not cells.empty
            else fares
        )
        for r in merged.to_dict("records"):
            index_value = r.get("index")
            matched_value = r.get("n_matched")
            rows.append(
                {
                    "date": str(r["day"]),
                    "leadtime_code": int(r["bucket"]),
                    "index": (
                        round(float(index_value), 2)
                        if index_value is not None and math.isfinite(float(index_value))
                        else None
                    ),
                    "cheapest_fare": round(float(r["price"]), 0),
                    "n_matched_products": (
                        int(matched_value)
                        if matched_value is not None and math.isfinite(float(matched_value))
                        else 0
                    ),
                }
            )
    return envelope(rows, 1, max(len(rows), 1), len(rows))


@app.get("/api/apix/getFareLadder")
@cached
def get_fare_ladder(route_code: str = Query(description="e.g. DEL-BOM")) -> dict:
    """PRISM raw material: latest observed RBD price rungs for a route (Akasa rich
    schema) — rung = booking class, price = cheapest total for that rung, seats =
    availability behind it."""
    o, _, d = route_code.upper().partition("-")
    conn = lake_connect()
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT rbd, flight_no, departure_date,
                   MIN(total_fare) AS total_fare,
                   MIN(base_fare)  AS base_fare,
                   MAX(seats_available) AS seats_available,
                   MAX(substr(collected_at,1,10)) AS as_of
            FROM fare_quotes
            WHERE origin=? AND dest=? AND rbd IS NOT NULL
              AND substr(collected_at,1,10) = (
                  SELECT MAX(substr(collected_at,1,10)) FROM fare_quotes
                  WHERE origin=? AND dest=? AND rbd IS NOT NULL)
            GROUP BY rbd, flight_no, departure_date
            ORDER BY total_fare
            """,
            [o, d, o, d],
        )
    ]
    conn.close()
    return envelope(rows, 1, max(len(rows), 1), len(rows))


@app.get("/api/apix/getSourceHealth")
@cached
def get_source_health() -> dict:
    """Trust-page feed: per source per collection day — quote count, route count,
    last collection timestamp."""
    conn = lake_connect()
    conn.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT source, substr(collected_at,1,10) AS date,
                   COUNT(*) AS quotes,
                   COUNT(DISTINCT origin||'-'||dest) AS routes,
                   MAX(collected_at) AS last_collected_at
            FROM fare_quotes GROUP BY source, date ORDER BY date, source
            """
        )
    ]
    conn.close()
    return envelope(rows, 1, max(len(rows), 1), len(rows))


def _rbd_quotes_df():
    import pandas as pd

    conn = lake_connect()
    df = pd.read_sql_query(
        "SELECT carrier, flight_no, origin, dest, departure_date, rbd, base_fare, "
        "total_fare, components, seats_available, collected_at "
        "FROM fare_quotes WHERE rbd IS NOT NULL",
        conn,
    )
    conn.close()
    return df


@app.get("/api/apix/getPrismEvents")
@cached
def get_prism_events(route_code: str | None = Query(default=None)) -> dict:
    """PRISM event log: FILING, availability-pressure rung heuristic, or
    EXTERNAL_FEE_CHANGE statutory/airport fee guard."""
    from apix_index.prism import classify_days

    df = _rbd_quotes_df()
    if route_code:
        o, _, d = route_code.upper().partition("-")
        df = df[(df["origin"] == o) & (df["dest"] == d)]
    events = classify_days(df) if not df.empty else None
    rows = [] if events is None or events.empty else json.loads(events.to_json(orient="records"))
    return envelope(rows, 1, max(len(rows), 1), len(rows))


@app.get("/api/apix/getPrismDecomposition")
@cached
def get_prism_decomposition() -> dict:
    """Daily filing, market, and availability-pressure indices (base 100)."""
    from apix_index.prism import decompose

    df = _rbd_quotes_df()
    dec = decompose(df) if not df.empty else None
    rows = [] if dec is None or dec.empty else dec.to_dict("records")
    return envelope(rows, 1, max(len(rows), 1), len(rows))


@app.get("/api/apix/getNowcast")
@cached
def get_nowcast() -> dict:
    """Kalman local-level nowcast of the current month's average APIx.
    Honest by design: returns explicit insufficient-panel status until enough
    daily observations exist — never a synthetic curve."""
    from apix_index.nowcast import MIN_DAYS, nowcast_month

    idx = get_apix_index(limit=1000, page=1, leadtime_code=None)["data"]
    import pandas as pd

    daily = pd.DataFrame([{"date": r["date"], "index": r["index"]} for r in idx])
    nc = nowcast_month(daily) if len(daily) else None
    if nc is None:
        rows = [
            {
                "status": "INSUFFICIENT_PANEL",
                "days_observed": len(daily),
                "days_required": MIN_DAYS,
            }
        ]
    else:
        rows = [{**nc, "status": "OK"}]
    return envelope(rows, 1, 1, 1)


@app.get("/api/apix/getCompetition")
@cached
def get_competition(days: int = Query(default=7, ge=1, le=30)) -> dict:
    # default 7: the multi-carrier source sweeps weekly (SerpApi quota), so a
    # 7-day window always contains one full sweep
    """Observed-frequency concentration per route.

    Carrier shares use distinct flight numbers from the SerpAPI-covered panel
    over the last N collection days; HHI = Σ share² × 10000. This is neither
    scheduled capacity nor DGCA seat share. Single-carrier routes are retained
    but explicitly identified as a source-coverage limitation.
    """
    conn = lake_connect()
    conn.row_factory = sqlite3.Row
    raw = conn.execute(
        """
        SELECT origin||'-'||dest AS route, carrier, COUNT(DISTINCT flight_no) AS flights
        FROM fare_quotes
        WHERE source = ?
          AND flight_no IS NOT NULL
          AND substr(collected_at,1,10) >= date((SELECT MAX(substr(collected_at,1,10))
                                                 FROM fare_quotes
                                                 WHERE source = ?), ?)
        GROUP BY route, carrier
        """,
        ["serpapi", "serpapi", f"-{days - 1} days"],
    ).fetchall()
    conn.close()

    by_route: dict[str, list] = {}
    for r in raw:
        by_route.setdefault(r["route"], []).append((r["carrier"], r["flights"]))
    rows = []
    for route, carriers in sorted(by_route.items()):
        total = sum(f for _, f in carriers)
        shares = {c: f / total for c, f in carriers}
        hhi = round(sum(s * s for s in shares.values()) * 10000)
        top = max(shares, key=lambda c: shares[c])
        rows.append(
            {
                "route": route,
                "hhi_observed": hhi,
                "n_carriers": len(carriers),
                "top_carrier": top,
                "top_share_pct": round(shares[top] * 100, 1),
                "n_flights_observed": total,
                "method": "SerpAPI distinct-flight-number share, last "
                f"{days} collection days; frequency proxy only, not scheduled "
                "capacity or proof of pricing power; single-carrier routes may "
                "reflect source coverage",
            }
        )
    return envelope(rows, 1, max(len(rows), 1), len(rows))


@app.get("/api/apix/getLedgerStatus")
def get_ledger_status() -> dict:
    """Evidence-ledger health: entry count, chain head, full verification result."""
    if read_only_enabled():
        from api.snapshot import hosted_ledger_status

        s = hosted_ledger_status()
    else:
        from collectors.ledger import status

        s = status()
    return envelope([s], 1, 1, 1)


@app.on_event("startup")
def warm_cache() -> None:
    """Precompute every heavy payload in the background so the first dashboard
    load after a restart (or nightly data refresh) never waits on pandas."""
    import threading

    def go() -> None:
        for call in (
            # Keep the kwargs identical to FastAPI's default request so the
            # warmer and GET /getAPIxIndex share one cache entry.
            lambda: get_apix_index(limit=100, page=1, leadtime_code=None),
            get_route_heatmap,
            get_nowcast,
            get_source_health,
            lambda: get_competition(days=7),
            get_prism_decomposition,
            lambda: get_prism_events(route_code=None),
        ):
            try:
                call()
            except Exception as e:  # noqa: BLE001 — warming must never block startup
                print(f"cache warm skipped one payload: {e}")

    threading.Thread(target=go, daemon=True).start()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict:
    if read_only_enabled():
        from api.snapshot import validated_manifest

        manifest = validated_manifest()
        return {
            "status": "ok",
            "mode": "read-only-snapshot",
            "snapshot_generated_at": manifest["generated_at"],
            "snapshot_sha256": manifest["database"]["sha256"],
            "api_cache_entries": manifest["database"].get("api_cache_entries", 0),
        }
    return {"status": "ok", "mode": "local-writable"}
