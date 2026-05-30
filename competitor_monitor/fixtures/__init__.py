"""Bundled sample data for offline demo and tests.

This is SYNTHETIC data — clearly fake numbers — so the whole pipeline
(collect -> store -> analyze -> report -> dashboard) can be exercised without
any API keys. It is NOT real competitor data; use real API keys
(docs/API_KEYS.md) to get real numbers.

The generator emits 8 WEEKLY snapshots per competitor so the dashboard time
series and week-over-week trend analysis both have real history to chart.
"""
from __future__ import annotations

from dataclasses import dataclass
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
_WEEKS = 8  # weeks of synthetic history


@dataclass(frozen=True)
class _Spec:
    name: str
    ig_username: str
    yt_channel_id: str
    keyword: str
    ig_followers0: int        # followers at the oldest week
    ig_weekly_growth: int
    yt_subs0: int
    yt_weekly_growth: int
    search: dict              # {source: total} at the latest date
    datalab0: float           # datalab ratio at the oldest week
    datalab_weekly: float     # weekly ratio change
    top_like: int             # like count of the headline IG post
    top_views: int            # views of the headline YT video


# Synthetic competitor set. Numbers are illustrative, not real.
_SPECS = [
    _Spec("New Balance Kids", "newbalancekids", "UCnbk", "뉴발란스 키즈",
          150000, 700, 40800, 130, {"blog": 1820, "cafearticle": 4310, "news": 240}, 42.0, 4.3, 6740, 128000),
    _Spec("Fila Kids", "filakids", "UCfila", "휠라 키즈",
          87000, 230, 22500, 60, {"blog": 760, "cafearticle": 1990, "news": 95}, 30.0, 2.1, 2980, 54000),
    _Spec("Adidas Kids", "adidaskids", "UCadidas", "아디다스 키즈",
          205000, 1200, 95000, 400, {"blog": 2450, "cafearticle": 5120, "news": 410}, 55.0, 3.8, 8900, 240000),
    _Spec("Nike Kids", "nikekids", "UCnike", "나이키 키즈",
          340000, 1500, 130000, 600, {"blog": 3010, "cafearticle": 6740, "news": 520}, 61.0, 4.9, 11200, 360000),
    _Spec("Play Kids", "playkids_official", "UCplay", "플레이 키즈",
          29000, 320, 8400, 90, {"blog": 540, "cafearticle": 1230, "news": 60}, 22.0, 5.5, 1840, 31000),
]


def _date(weeks_ago: int) -> str:
    return (_TODAY - timedelta(weeks=weeks_ago)).isoformat()


def demo_records() -> list[object]:
    """Return synthetic records for all competitors across 8 weekly snapshots."""
    recs: list[object] = []
    today = _date(0)

    for s in _SPECS:
        # --- weekly IG / YT snapshots (oldest -> newest) -------------------
        for i in range(_WEEKS):
            weeks_ago = _WEEKS - 1 - i
            d = _date(weeks_ago)
            recs.append(IgProfileSnapshot(
                s.name, s.ig_username,
                followers_count=s.ig_followers0 + s.ig_weekly_growth * i,
                media_count=300 + i,
                snapshot_date=d,
            ))
            recs.append(YtChannelSnapshot(
                s.name, s.yt_channel_id,
                subscriber_count=s.yt_subs0 + s.yt_weekly_growth * i,
                view_count=5_000_000 + i * 60_000,
                video_count=300 + i,
                snapshot_date=d,
            ))
            # weekly DataLab relative-trend point
            recs.append(NaverDataLabPoint(
                s.keyword, d, round(s.datalab0 + s.datalab_weekly * i, 1),
            ))

        # --- a few recent IG posts (engagement + top content) --------------
        recs += [
            IgMedia(s.name, f"{s.ig_username}_1", f"{s.keyword} 봄 신상 출시 🌸",
                    s.top_like, s.top_like // 30, f"{today}T02:00:00+0000",
                    f"https://instagram.com/p/{s.ig_username}_1"),
            IgMedia(s.name, f"{s.ig_username}_2", f"{s.keyword} 가정의 달 이벤트",
                    int(s.top_like * 0.6), s.top_like // 45, f"{_date(1)}T05:00:00+0000",
                    f"https://instagram.com/p/{s.ig_username}_2"),
        ]

        # --- recent YT videos ----------------------------------------------
        recs += [
            YtVideo(s.name, f"{s.yt_channel_id}_v1", s.yt_channel_id,
                    f"{s.keyword} 봄 캠페인 필름", f"{today}T01:00:00Z",
                    s.top_views, s.top_views // 40, s.top_views // 600),
            YtVideo(s.name, f"{s.yt_channel_id}_v2", s.yt_channel_id,
                    f"{s.keyword} 풋스타일 가이드", f"{_date(1)}T01:00:00Z",
                    int(s.top_views * 0.4), s.top_views // 90, s.top_views // 1200),
        ]

        # --- Naver search buzz (latest date) -------------------------------
        for src, total in s.search.items():
            recs.append(NaverSearchCount(s.keyword, src, total, snapshot_date=today))

    return recs
