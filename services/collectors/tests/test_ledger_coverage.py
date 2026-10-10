"""Ledger coverage is distinct from hash-chain integrity."""

from __future__ import annotations

from collectors import ledger


def test_status_reports_unsealed_raw_files(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    raw = repo / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "first.raw").write_text("first", encoding="utf-8")

    monkeypatch.setattr(ledger, "REPO_ROOT", repo)
    monkeypatch.setattr(ledger, "RAW_DIR", raw)
    monkeypatch.setattr(ledger, "LEDGER_PATH", repo / "data" / "ledger.jsonl")

    assert ledger.seal() == 1
    complete = ledger.status()
    assert complete["intact"] is True
    assert complete["coverage_complete"] is True
    assert complete["sealed_files"] == complete["raw_files"] == 1

    (raw / "second.raw").write_text("second", encoding="utf-8")
    incomplete = ledger.status()
    assert incomplete["intact"] is True
    assert incomplete["coverage_complete"] is False
    assert incomplete["unsealed_files"] == 1
