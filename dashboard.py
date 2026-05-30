"""경쟁사 마케팅 모니터링 대시보드.

Run with:
    streamlit run dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Make the package importable when the CWD is the project root (no install).
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from competitor_monitor.analysis.metrics import (
    build_analysis,
    datalab_trend,
    engagement_rates,
    share_of_voice,
    top_content,
    trend_deltas,
)
from competitor_monitor.branding import color_for
from competitor_monitor.fixtures import demo_records
from competitor_monitor.storage import Storage

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="경쟁사 마케팅 모니터링 대시보드",
    layout="wide",
)

_EMPTY_MSG = "데이터가 없습니다. 사이드바에서 '데모 데이터 사용'을 켜거나 먼저 수집을 실행하세요."

# ---------------------------------------------------------------------------
# Sidebar: DB path + demo toggle + competitor filter
# ---------------------------------------------------------------------------

def _default_db_path() -> str:
    """Try reading db_path from config.yaml; fall back to 'data/monitor.db'."""
    try:
        from competitor_monitor.config import load_settings
        return load_settings("config.yaml").db_path
    except Exception:
        return "data/monitor.db"


with st.sidebar:
    st.title("설정")

    use_demo = st.checkbox("데모 데이터 사용", value=False,
                           help="체크하면 API 키 없이 내장 샘플 데이터를 사용합니다.")

    db_path = st.text_input("SQLite DB 경로", value=_default_db_path(),
                            disabled=use_demo)

    st.divider()

# ---------------------------------------------------------------------------
# Storage — built once, then analytics are cached on the derived data.
# We cannot cache the Storage object itself (sqlite connections aren't
# serialisable), so we open it, pull every frame, and cache those.
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="데이터 로드 중…")
def _load_all(db_path_key: str, demo: bool) -> dict[str, Any]:
    """Open Storage, run all analytics, close, return plain-Python dicts."""
    if demo:
        storage = Storage(":memory:")
        storage.save(demo_records())
    else:
        storage = Storage(db_path_key)
    try:
        analysis = build_analysis(storage)
        # Also pull raw time-series rows for the line charts.
        ig_ts = storage.query(
            "SELECT competitor, snapshot_date, followers_count FROM ig_profile_snapshots ORDER BY snapshot_date"
        )
        yt_ts = storage.query(
            "SELECT competitor, snapshot_date, subscriber_count FROM yt_channel_snapshots ORDER BY snapshot_date"
        )
        # Convert sqlite3.Row → plain dicts so st.cache_data can serialise them.
        ig_ts_list = [dict(r) for r in ig_ts]
        yt_ts_list = [dict(r) for r in yt_ts]
    finally:
        storage.close()

    return {**analysis, "ig_ts": ig_ts_list, "yt_ts": yt_ts_list}


# Use the actual path or a sentinel string when in demo mode so the cache
# key changes correctly when the user toggles the checkbox.
_cache_key = ":memory:" if use_demo else db_path
data = _load_all(_cache_key, use_demo)

# ---------------------------------------------------------------------------
# Competitor filter (sidebar, populated from data)
# ---------------------------------------------------------------------------

def _all_competitors(data: dict) -> list[str]:
    competitors: set[str] = set()
    for item in data.get("engagement_rates", []):
        competitors.add(item["competitor"])
    for item in data.get("trend_deltas", {}).get("instagram", []):
        competitors.add(item["competitor"])
    for item in data.get("trend_deltas", {}).get("youtube", []):
        competitors.add(item["competitor"])
    return sorted(competitors)


all_competitors = _all_competitors(data)

with st.sidebar:
    selected_competitors: list[str] = st.multiselect(
        "경쟁사 필터",
        options=all_competitors,
        default=all_competitors,
        help="선택한 경쟁사만 차트와 표에 표시됩니다.",
    )

# Fall back to all if nothing selected (avoids a fully-empty dashboard).
if not selected_competitors:
    selected_competitors = all_competitors

# ---------------------------------------------------------------------------
# Helper: filter lists by competitor field
# ---------------------------------------------------------------------------

def _filter(items: list[dict], key: str = "competitor") -> list[dict]:
    if not selected_competitors:
        return items
    return [i for i in items if i.get(key) in selected_competitors]


# ---------------------------------------------------------------------------
# Main title
# ---------------------------------------------------------------------------
st.title("경쟁사 마케팅 모니터링 대시보드")

# ===========================================================================
# 1. KPI row
# ===========================================================================
st.subheader("주요 지표 (KPI)")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

# Total tracked competitors
total_comp = len(all_competitors)
kpi1.metric("추적 경쟁사 수", total_comp)

# Top IG follower gainer (largest delta)
ig_deltas: list[dict] = _filter(data.get("trend_deltas", {}).get("instagram", []))
if ig_deltas:
    top_gainer = max(ig_deltas, key=lambda x: x.get("delta", 0))
    kpi2.metric(
        "팔로워 최다 증가",
        top_gainer["competitor"],
        delta=f"+{top_gainer['delta']:,}  ({top_gainer['pct']}%)",
    )
else:
    kpi2.metric("팔로워 최다 증가", "-")

# Top share-of-voice keyword
sov: list[dict] = data.get("share_of_voice", [])
if sov:
    top_kw = sov[0]
    kpi3.metric(
        "검색 점유율 1위 키워드",
        top_kw["keyword"],
        delta=f"{top_kw['share_pct']}%",
    )
else:
    kpi3.metric("검색 점유율 1위 키워드", "-")

# Biggest DataLab mover (by absolute change_pct)
dl: list[dict] = data.get("datalab_trend", [])
if dl:
    top_dl = max(dl, key=lambda x: abs(x.get("change_pct", 0)))
    kpi4.metric(
        "검색량 최대 변화 키워드",
        top_dl["keyword_group"],
        delta=f"{top_dl['change_pct']:+.1f}%",
    )
else:
    kpi4.metric("검색량 최대 변화 키워드", "-")

st.divider()

# ===========================================================================
# 2. IG follower time-series (line chart)
# ===========================================================================
st.subheader("팔로워 추이 (Instagram)")

ig_ts_rows = [r for r in data.get("ig_ts", []) if r["competitor"] in selected_competitors]
if ig_ts_rows:
    ig_df = pd.DataFrame(ig_ts_rows)
    # Pivot: rows = snapshot_date, columns = competitor
    ig_pivot = ig_df.pivot_table(
        index="snapshot_date", columns="competitor", values="followers_count", aggfunc="last"
    )
    ig_pivot.index.name = "날짜"
    st.line_chart(ig_pivot, color=[color_for(c) for c in ig_pivot.columns])
else:
    st.info(_EMPTY_MSG)

st.divider()

# ===========================================================================
# 3. YT subscriber time-series (line chart)
# ===========================================================================
st.subheader("구독자 추이 (YouTube)")

yt_ts_rows = [r for r in data.get("yt_ts", []) if r["competitor"] in selected_competitors]
if yt_ts_rows:
    yt_df = pd.DataFrame(yt_ts_rows)
    yt_pivot = yt_df.pivot_table(
        index="snapshot_date", columns="competitor", values="subscriber_count", aggfunc="last"
    )
    yt_pivot.index.name = "날짜"
    st.line_chart(yt_pivot, color=[color_for(c) for c in yt_pivot.columns])
else:
    st.info(_EMPTY_MSG)

st.divider()

# ===========================================================================
# 4. Share of Voice (bar chart + table)
# ===========================================================================
st.subheader("검색 점유율 (Share of Voice)")

if sov:
    sov_df = pd.DataFrame(sov).set_index("keyword")
    col_bar, col_tbl = st.columns([2, 1])
    with col_bar:
        st.bar_chart(sov_df["share_pct"])
    with col_tbl:
        st.dataframe(
            sov_df[["total_mentions", "share_pct"]].rename(
                columns={"total_mentions": "언급 수", "share_pct": "점유율 (%)"}
            ),
            use_container_width=True,
        )
else:
    st.info(_EMPTY_MSG)

st.divider()

# ===========================================================================
# 5. DataLab trend (line chart per keyword_group)
# ===========================================================================
st.subheader("검색량 트렌드 (Naver DataLab)")

if dl:
    # Build a single wide DataFrame: index = period, columns = keyword_group
    dl_frames: list[pd.DataFrame] = []
    for entry in dl:
        if not entry.get("points"):
            continue
        frame = pd.DataFrame(entry["points"]).set_index("period")
        frame.columns = [entry["keyword_group"]]
        dl_frames.append(frame)

    if dl_frames:
        dl_df = pd.concat(dl_frames, axis=1).sort_index()
        dl_df.index.name = "날짜"
        st.line_chart(dl_df, color=[color_for(c) for c in dl_df.columns])
    else:
        st.info(_EMPTY_MSG)
else:
    st.info(_EMPTY_MSG)

st.divider()

# ===========================================================================
# 6. Engagement rates (table + bar chart)
# ===========================================================================
st.subheader("인게이지먼트 (Instagram)")

eng: list[dict] = _filter(data.get("engagement_rates", []))
if eng:
    eng_df = (
        pd.DataFrame(eng)
        .sort_values("engagement_rate_pct", ascending=False)
        .set_index("competitor")
    )
    col_eng_tbl, col_eng_bar = st.columns([2, 1])
    with col_eng_tbl:
        st.dataframe(
            eng_df.rename(columns={
                "followers": "팔로워",
                "avg_interactions": "평균 반응 수",
                "engagement_rate_pct": "인게이지먼트율 (%)",
                "sample_size": "샘플 수",
            }),
            use_container_width=True,
        )
    with col_eng_bar:
        st.bar_chart(eng_df["engagement_rate_pct"])
else:
    st.info(_EMPTY_MSG)

st.divider()

# ===========================================================================
# 7. Top content (IG + YT)
# ===========================================================================
st.subheader("주목 콘텐츠")

tc = data.get("top_content", {})
col_ig, col_yt = st.columns(2)

with col_ig:
    st.markdown("**Instagram 인기 게시물**")
    ig_posts: list[dict] = _filter(tc.get("instagram", []))
    if ig_posts:
        ig_posts_df = pd.DataFrame(ig_posts)
        # Make permalinks into HTML hyperlinks where Streamlit supports it
        if "permalink" in ig_posts_df.columns:
            ig_posts_df["permalink"] = ig_posts_df["permalink"].apply(
                lambda url: f'<a href="{url}" target="_blank">링크</a>' if url else ""
            )
        st.dataframe(
            ig_posts_df.rename(columns={
                "competitor": "경쟁사",
                "permalink": "링크",
                "like_count": "좋아요",
                "comments_count": "댓글",
                "caption_preview": "캡션 미리보기",
            }),
            use_container_width=True,
        )
    else:
        st.info(_EMPTY_MSG)

with col_yt:
    st.markdown("**YouTube 인기 동영상**")
    yt_videos: list[dict] = _filter(tc.get("youtube", []))
    if yt_videos:
        yt_videos_df = pd.DataFrame(yt_videos)
        # Build clickable URL from video_id
        if "video_id" in yt_videos_df.columns:
            yt_videos_df["url"] = yt_videos_df["video_id"].apply(
                lambda vid: f"https://www.youtube.com/watch?v={vid}" if vid else ""
            )
        st.dataframe(
            yt_videos_df[["competitor", "title", "view_count", "like_count", "url"]].rename(
                columns={
                    "competitor": "경쟁사",
                    "title": "제목",
                    "view_count": "조회수",
                    "like_count": "좋아요",
                    "url": "YouTube 링크",
                }
            ),
            use_container_width=True,
        )
    else:
        st.info(_EMPTY_MSG)
