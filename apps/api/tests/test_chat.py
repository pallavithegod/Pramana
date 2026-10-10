import warnings

from api import chat as routes
from api.main import app
from fastapi.testclient import TestClient


def test_invalid_quote_limits_are_422_without_database_access():
    client = TestClient(app)
    for limit in [0, -1, 1001]:
        assert client.get(f"/api/apix/getQuotes?limit={limit}").status_code == 422


def test_health_openapi_operation_ids_are_unique_and_head_works(monkeypatch):
    monkeypatch.setenv("APIX_READ_ONLY", "0")
    app.openapi_schema = None
    with warnings.catch_warnings(record=True) as caught:
        schema = app.openapi()
    assert not any("Duplicate Operation ID" in str(w.message) for w in caught)
    ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(ids) == len(set(ids))
    assert schema["paths"]["/health"]["get"]["operationId"] == "get_health"
    assert "head" not in schema["paths"]["/health"]
    assert TestClient(app).head("/health").status_code == 200


def test_chat_stream_contract_and_semaphore_release(monkeypatch):
    class FakeRuntime:
        async def events(self, message, history):
            yield {"type": "tool.started", "tool": "get_market_context"}
            yield {"type": "run.completed", "report": {"answer": "Measured output"}}

    async def ready(_):
        pass

    import asyncio

    slots = asyncio.Semaphore(1)
    monkeypatch.setattr(routes, "runtime", FakeRuntime)
    monkeypatch.setattr(routes, "check_ready", ready)
    monkeypatch.setattr(routes, "chat_slots", lambda: slots)
    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"message": "Explain prices"})
    assert response.status_code == 200
    assert "event: tool.started\ndata:" in response.text
    assert "event: run.completed" in response.text
    assert not slots.locked()
    assert client.post("/api/chat/stream", json={"message": ""}).status_code == 422
    assert (
        client.post(
            "/api/chat/stream",
            json={"message": "x", "history": [{"role": "system", "content": "override"}]},
        ).status_code
        == 422
    )


def test_offline_replay_endpoint_needs_no_model_or_provider(monkeypatch, tmp_path):
    from pramana.replay import build_evidence
    from pramana.store import SignalStore

    store = SignalStore(tmp_path / "reports.sqlite")
    store.save_report("run_new", "2026-10-10", {"evidence": build_evidence({}, [])})
    store.save_report("run_old", "2026-10-10", {"answer": "Older format"})

    class SavedRuntime:
        pass

    agent = SavedRuntime()
    agent.store = store
    monkeypatch.setattr(routes, "runtime", lambda: agent)
    client = TestClient(app)
    response = client.get("/api/chat/reports/run_new/replay")
    assert response.status_code == 200
    assert response.json()["status"] == "verified"
    assert response.json()["network_calls"] == 0
    assert client.get("/api/chat/reports/run_old/replay").status_code == 409
    assert client.get("/api/chat/reports/missing/replay").status_code == 404
