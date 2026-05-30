"""End-to-end and unit tests using the bundled synthetic fixtures.

These run fully offline (no API keys, no network).
"""
from __future__ import annotations

import sqlite3

import pytest

from competitor_monitor.analysis import build_analysis
from competitor_monitor.config import CompetitorConfig, Secrets, Settings
from competitor_monitor.fixtures import demo_records
from competitor_monitor.models import IgMedia, IgProfileSnapshot
from competitor_monitor.reporting import render_html, render_markdown
from competitor_monitor.storage import Storage


@pytest.fixture
def storage() -> Storage:
    s = Storage(":memory:")
    yield s
    s.close()


@pytest.fixture
def loaded(storage: Storage) -> Storage:
    storage.save(demo_records())
    return storage


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def test_save_returns_count(storage: Storage):
    n = storage.save(demo_records())
    assert n == len(demo_records())


def test_upsert_is_idempotent(storage: Storage):
    """Re-saving the same records must not duplicate rows."""
    storage.save(demo_records())
    before = storage.query("SELECT COUNT(*) AS c FROM ig_media")[0]["c"]
    storage.save(demo_records())
    after = storage.query("SELECT COUNT(*) AS c FROM ig_media")[0]["c"]
    assert before == after


def test_snapshot_upsert_updates_metrics(storage: Storage):
    today = "2026-05-30"
    storage.save([IgProfileSnapshot("X", "x", 100, 10, snapshot_date=today)])
    storage.save([IgProfileSnapshot("X", "x", 200, 12, snapshot_date=today)])
    rows = storage.query("SELECT followers_count FROM ig_profile_snapshots WHERE competitor='X'")
    assert len(rows) == 1 and rows[0]["followers_count"] == 200


def test_unknown_record_type_raises(storage: Storage):
    with pytest.raises(TypeError):
        storage.save([object()])


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def test_build_analysis_keys(loaded: Storage):
    a = build_analysis(loaded)
    assert set(a) >= {
        "engagement_rates", "share_of_voice", "trend_deltas",
        "datalab_trend", "top_content",
    }


def test_share_of_voice_sums_to_100(loaded: Storage):
    sov = build_analysis(loaded)["share_of_voice"]
    assert sov, "expected share-of-voice rows"
    assert abs(sum(r["share_pct"] for r in sov) - 100.0) < 0.01


def test_trend_deltas_detect_growth(loaded: Storage):
    ig = build_analysis(loaded)["trend_deltas"]["instagram"]
    nbk = next(r for r in ig if r["competitor"] == "New Balance Kids")
    assert nbk["delta"] > 0  # fixtures encode week-over-week growth


def test_engagement_rate_non_negative(loaded: Storage):
    for r in build_analysis(loaded)["engagement_rates"]:
        assert r["engagement_rate_pct"] >= 0


def test_analysis_on_empty_db(storage: Storage):
    """Cold start: empty DB must not crash the analysis layer."""
    a = build_analysis(storage)
    assert a["engagement_rates"] == []
    assert a["share_of_voice"] == []


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def test_render_markdown_has_sections(loaded: Storage):
    md = render_markdown(build_analysis(loaded))
    assert "# " in md
    assert "뉴발란스" in md or "New Balance" in md


def test_trend_table_shows_actual_counts(loaded: Storage):
    """Regression: the analysis/report key contract for follower/sub counts
    must line up so the 현재/이전 columns render real numbers, not '-'."""
    md = render_markdown(build_analysis(loaded))
    assert "154,900" in md   # NBK current followers from fixtures
    assert "41,850" in md    # NBK current subscribers from fixtures


def test_render_html_wraps_markdown(loaded: Storage):
    html = render_html(render_markdown(build_analysis(loaded)))
    assert html.strip().lower().startswith("<!doctype") or "<html" in html.lower()
    assert "<table" in html.lower()


def test_report_handles_empty_analysis(storage: Storage):
    md = render_markdown(build_analysis(storage))
    assert "데이터 없음" in md


def test_llm_summary_section_optional(loaded: Storage):
    a = build_analysis(loaded)
    assert "AI 크리에이티브" not in render_markdown(a, llm_summary=None)
    assert "AI 크리에이티브" in render_markdown(a, llm_summary={"summary": "테스트 요약"})
