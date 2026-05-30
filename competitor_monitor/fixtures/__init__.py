"""Bundled sample data for offline demo and tests.

This is SYNTHETIC data — clearly fake numbers — so the whole pipeline
(collect -> store -> analyze -> report) can be exercised without any API keys.
It is NOT real competitor data. Use real API keys (docs/API_KEYS.md) to get
real numbers. Two snapshot dates a week apart are included so week-over-week
trend analysis has something to compute.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import (
    IgMedia,
    IgProfileSnapshot,
    NaverDataLabPoint,
    NaverSearchCount,
    YtChannelSnapshot,
    YtVideo,
)

_TODAY = datetime.now(timezone.utc).date()
_LAST_WEEK = _TODAY - timedelta(days=7)


def demo_records() -> list[object]:
    """Return a full set of synthetic records spanning two snapshot dates."""
    today = _TODAY.isoformat()
    prev = _LAST_WEEK.isoformat()
    recs: list[object] = []

    # --- Instagram: two profile snapshots (growth) + a few posts -----------
    recs += [
        IgProfileSnapshot("New Balance Kids", "newbalancekids", 152300, 412, snapshot_date=prev),
        IgProfileSnapshot("New Balance Kids", "newbalancekids", 154900, 418, snapshot_date=today),
        IgProfileSnapshot("Fila Kids", "filakids", 88100, 305, snapshot_date=prev),
        IgProfileSnapshot("Fila Kids", "filakids", 88650, 309, snapshot_date=today),
    ]
    recs += [
        IgMedia("New Balance Kids", "nbk_1", "봄 신상 키즈 스니커즈 출시 🌸 #뉴발란스키즈", 4820, 132,
                f"{today}T02:00:00+0000", "https://instagram.com/p/nbk_1"),
        IgMedia("New Balance Kids", "nbk_2", "가정의 달 패밀리룩 이벤트", 3110, 88,
                f"{prev}T05:00:00+0000", "https://instagram.com/p/nbk_2"),
        IgMedia("New Balance Kids", "nbk_3", "327 키즈 컬러 추가", 6740, 201,
                f"{today}T08:30:00+0000", "https://instagram.com/p/nbk_3"),
        IgMedia("Fila Kids", "fk_1", "디즈니 콜라보 키즈 컬렉션", 2980, 74,
                f"{today}T03:00:00+0000", "https://instagram.com/p/fk_1"),
    ]

    # --- YouTube: two channel snapshots + recent videos --------------------
    recs += [
        YtChannelSnapshot("New Balance Kids", "UCnbk", 41200, 5120000, 318, snapshot_date=prev),
        YtChannelSnapshot("New Balance Kids", "UCnbk", 41850, 5180000, 320, snapshot_date=today),
    ]
    recs += [
        YtVideo("New Balance Kids", "vid_nbk_1", "UCnbk", "327 키즈 봄 캠페인 필름",
                f"{today}T01:00:00Z", 128000, 3400, 210),
        YtVideo("New Balance Kids", "vid_nbk_2", "UCnbk", "키즈 풋스타일 가이드",
                f"{prev}T01:00:00Z", 54000, 1200, 65),
    ]

    # --- Naver Search buzz (latest date) -----------------------------------
    for src, total in (("blog", 1820), ("cafearticle", 4310), ("news", 240)):
        recs.append(NaverSearchCount("뉴발란스 키즈", src, total, snapshot_date=today))
    for src, total in (("blog", 760), ("cafearticle", 1990), ("news", 95)):
        recs.append(NaverSearchCount("휠라 키즈", src, total, snapshot_date=today))

    # --- Naver DataLab relative trend (weekly, rising) ---------------------
    base = _TODAY - timedelta(weeks=7)
    for i, ratio in enumerate([42.0, 48.5, 51.0, 55.2, 60.0, 58.3, 67.4, 72.1]):
        period = (base + timedelta(weeks=i)).isoformat()
        recs.append(NaverDataLabPoint("뉴발란스 키즈", period, ratio))

    return recs
