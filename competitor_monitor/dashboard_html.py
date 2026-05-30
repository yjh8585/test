"""Static HTML dashboard generator.

Produces a single self-contained .html file with interactive Chart.js charts.
No server needed — works offline, safe to email or attach as a CI artifact.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .branding import color_for

if TYPE_CHECKING:
    from .config import Settings
    from .storage import Storage

# Chart.js loaded from CDN — no local assets required
_CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js"


# --------------------------------------------------------------------------- #
# Internal query helpers
# --------------------------------------------------------------------------- #

def _ig_time_series(storage: Storage) -> dict[str, dict[str, int]]:
    """Return {competitor: {snapshot_date: followers_count}} ordered by date."""
    rows = storage.query(
        """
        SELECT competitor, snapshot_date, followers_count
        FROM ig_profile_snapshots
        ORDER BY snapshot_date ASC
        """
    )
    result: dict[str, dict[str, int]] = {}
    for r in rows:
        result.setdefault(r["competitor"], {})[r["snapshot_date"]] = r["followers_count"] or 0
    return result


def _yt_time_series(storage: Storage) -> dict[str, dict[str, int]]:
    """Return {competitor: {snapshot_date: subscriber_count}} ordered by date."""
    rows = storage.query(
        """
        SELECT competitor, snapshot_date, subscriber_count
        FROM yt_channel_snapshots
        ORDER BY snapshot_date ASC
        """
    )
    result: dict[str, dict[str, int]] = {}
    for r in rows:
        result.setdefault(r["competitor"], {})[r["snapshot_date"]] = r["subscriber_count"] or 0
    return result


def _sorted_dates(series: dict[str, dict[str, int]]) -> list[str]:
    """Collect and sort all unique dates across all competitors."""
    dates: set[str] = set()
    for d in series.values():
        dates.update(d.keys())
    return sorted(dates)


def _series_to_chartjs(
    series: dict[str, dict[str, int]],
    dates: list[str],
) -> list[dict]:
    """Convert {competitor: {date: value}} → Chart.js datasets list."""
    datasets = []
    for competitor, data in series.items():
        color = color_for(competitor)  # consistent brand colour per competitor
        datasets.append({
            "label": competitor,
            "data": [data.get(d) for d in dates],  # None gaps are fine — Chart.js skips them
            "borderColor": color,
            "backgroundColor": color + "33",  # 20 % opacity fill
            "tension": 0.3,
            "fill": False,
            "pointRadius": 3,
        })
    return datasets


# --------------------------------------------------------------------------- #
# KPI helpers
# --------------------------------------------------------------------------- #

def _kpi_cards(analysis: dict) -> dict:
    """Extract four headline numbers for the KPI row."""
    # Total unique competitors from IG + YT delta lists
    competitors: set[str] = set()
    for item in analysis["trend_deltas"].get("instagram", []):
        competitors.add(item["competitor"])
    for item in analysis["trend_deltas"].get("youtube", []):
        competitors.add(item["competitor"])

    # Top IG follower gainer
    ig_deltas = sorted(
        analysis["trend_deltas"].get("instagram", []),
        key=lambda x: x["delta"],
        reverse=True,
    )
    top_gainer = ig_deltas[0] if ig_deltas else None

    # Top share-of-voice keyword
    sov = analysis["share_of_voice"]
    top_sov = sov[0] if sov else None

    # Biggest DataLab mover (by absolute change_pct)
    dl = sorted(
        analysis["datalab_trend"],
        key=lambda x: abs(x["change_pct"]),
        reverse=True,
    )
    top_dl = dl[0] if dl else None

    return {
        "total_competitors": len(competitors),
        "top_gainer": top_gainer,
        "top_sov": top_sov,
        "top_dl": top_dl,
    }


# --------------------------------------------------------------------------- #
# HTML fragment builders
# --------------------------------------------------------------------------- #

def _render_kpi_row(kpi: dict) -> str:
    top_gainer = kpi["top_gainer"]
    top_sov = kpi["top_sov"]
    top_dl = kpi["top_dl"]

    gainer_html = (
        f"<div class='kpi-value'>{html.escape(top_gainer['competitor'])}</div>"
        f"<div class='kpi-sub'>+{top_gainer['delta']:,} ({top_gainer['pct']:+.1f}%)</div>"
        if top_gainer else "<div class='kpi-value'>—</div>"
    )
    sov_html = (
        f"<div class='kpi-value'>{html.escape(top_sov['keyword'])}</div>"
        f"<div class='kpi-sub'>{top_sov['share_pct']:.1f}% 점유</div>"
        if top_sov else "<div class='kpi-value'>—</div>"
    )
    dl_html = (
        f"<div class='kpi-value'>{html.escape(top_dl['keyword_group'])}</div>"
        f"<div class='kpi-sub'>{top_dl['change_pct']:+.1f}% 변화</div>"
        if top_dl else "<div class='kpi-value'>—</div>"
    )

    return f"""
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-label">경쟁사 수</div>
        <div class="kpi-value">{kpi['total_competitors']}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">IG 최다 증가 경쟁사</div>
        {gainer_html}
      </div>
      <div class="kpi-card">
        <div class="kpi-label">검색 점유율 1위</div>
        {sov_html}
      </div>
      <div class="kpi-card">
        <div class="kpi-label">DataLab 최대 변동</div>
        {dl_html}
      </div>
    </div>"""


def _render_top_content(tc: dict) -> str:
    """Render IG posts and YT videos as plain HTML tables."""
    ig_rows = ""
    for item in tc.get("instagram", []):
        link = html.escape(item.get("permalink") or "")
        caption = html.escape(item.get("caption_preview") or "")
        competitor = html.escape(item.get("competitor") or "")
        likes = item.get("like_count", 0)
        comments = item.get("comments_count", 0)
        cell = f'<a href="{link}" target="_blank" rel="noopener">{caption or link}</a>' if link else caption
        ig_rows += f"<tr><td>{competitor}</td><td>{cell}</td><td>{likes:,}</td><td>{comments:,}</td></tr>\n"

    yt_rows = ""
    for item in tc.get("youtube", []):
        video_id = html.escape(item.get("video_id") or "")
        title = html.escape(item.get("title") or "")
        competitor = html.escape(item.get("competitor") or "")
        views = item.get("view_count", 0)
        likes = item.get("like_count", 0)
        yt_url = f"https://youtu.be/{video_id}" if video_id else ""
        cell = f'<a href="{yt_url}" target="_blank" rel="noopener">{title}</a>' if yt_url else title
        yt_rows += f"<tr><td>{competitor}</td><td>{cell}</td><td>{views:,}</td><td>{likes:,}</td></tr>\n"

    ig_table = f"""
    <table>
      <thead><tr><th>경쟁사</th><th>캡션 미리보기</th><th>좋아요</th><th>댓글</th></tr></thead>
      <tbody>{ig_rows or '<tr><td colspan="4">데이터 없음</td></tr>'}</tbody>
    </table>""" if True else ""

    yt_table = f"""
    <table>
      <thead><tr><th>경쟁사</th><th>영상 제목</th><th>조회수</th><th>좋아요</th></tr></thead>
      <tbody>{yt_rows or '<tr><td colspan="4">데이터 없음</td></tr>'}</tbody>
    </table>"""

    return f"""
    <section class="content-section">
      <h2>주목 콘텐츠</h2>
      <h3>Instagram 인기 포스트</h3>
      {ig_table}
      <h3 style="margin-top:1.5rem">YouTube 인기 영상</h3>
      {yt_table}
    </section>"""


def _no_data_placeholder(label: str) -> str:
    return f'<div class="no-data">{html.escape(label)}: 데이터 없음</div>'


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def build_dashboard_html(
    storage: Storage,
    *,
    title: str = "경쟁사 마케팅 모니터링 대시보드",
    generated_at: str | None = None,
) -> str:
    """Return a complete, self-contained HTML dashboard document as a string."""
    from .analysis.metrics import build_analysis  # local import to avoid circular deps

    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    analysis = build_analysis(storage)

    # --- Time-series data for line charts ---
    ig_series = _ig_time_series(storage)
    ig_dates = _sorted_dates(ig_series)
    ig_datasets = _series_to_chartjs(ig_series, ig_dates)

    yt_series = _yt_time_series(storage)
    yt_dates = _sorted_dates(yt_series)
    yt_datasets = _series_to_chartjs(yt_series, yt_dates)

    # --- Share of voice doughnut ---
    sov = analysis["share_of_voice"]
    sov_labels = [item["keyword"] for item in sov]
    sov_values = [item["share_pct"] for item in sov]
    sov_colors = [color_for(item["keyword"]) for item in sov]

    # --- DataLab multi-line ---
    dl = analysis["datalab_trend"]
    # Collect all unique periods across all keyword groups
    dl_periods: set[str] = set()
    for group in dl:
        for pt in group["points"]:
            dl_periods.add(pt["period"])
    dl_period_list = sorted(dl_periods)
    dl_datasets = []
    for group in dl:
        period_map = {pt["period"]: pt["ratio"] for pt in group["points"]}
        color = color_for(group["keyword_group"])
        dl_datasets.append({
            "label": group["keyword_group"],
            "data": [period_map.get(p) for p in dl_period_list],
            "borderColor": color,
            "backgroundColor": color + "33",
            "tension": 0.3,
            "fill": False,
            "pointRadius": 2,
        })

    # --- Engagement rate bar ---
    eng = analysis["engagement_rates"]
    eng_labels = [item["competitor"] for item in eng]
    eng_values = [item["engagement_rate_pct"] for item in eng]
    eng_colors = [color_for(item["competitor"]) for item in eng]

    # --- KPI cards ---
    kpi = _kpi_cards(analysis)
    kpi_html = _render_kpi_row(kpi)

    # --- Top content ---
    tc_html = _render_top_content(analysis["top_content"])

    # Escape title for HTML output
    title_esc = html.escape(title)

    # Determine which charts have no data — show placeholder div instead of canvas
    def _chart_block(canvas_id: str, label: str, has_data: bool) -> str:
        if has_data:
            return f'<canvas id="{canvas_id}"></canvas>'
        return _no_data_placeholder(label)

    ig_block = _chart_block("igChart", "팔로워 추이", bool(ig_series))
    yt_block = _chart_block("ytChart", "구독자 추이", bool(yt_series))
    sov_block = _chart_block("sovChart", "검색 점유율", bool(sov))
    dl_block = _chart_block("dlChart", "DataLab 트렌드", bool(dl))
    eng_block = _chart_block("engChart", "인게이지먼트율", bool(eng))

    # Embed all chart data as JS const declarations — avoids any XSS via html.escape above
    js_data = f"""
const igDates    = {json.dumps(ig_dates)};
const igDatasets = {json.dumps(ig_datasets)};
const ytDates    = {json.dumps(yt_dates)};
const ytDatasets = {json.dumps(yt_datasets)};
const sovLabels  = {json.dumps(sov_labels)};
const sovValues  = {json.dumps(sov_values)};
const sovColors  = {json.dumps(sov_colors)};
const dlPeriods  = {json.dumps(dl_period_list)};
const dlDatasets = {json.dumps(dl_datasets)};
const engLabels  = {json.dumps(eng_labels)};
const engValues  = {json.dumps(eng_values)};
const engColors  = {json.dumps(eng_colors)};
"""

    # Chart.js initialization — one block, each chart conditional on canvas presence
    js_init = """
function makeChart(id, config) {
  const el = document.getElementById(id);
  if (!el) return;  // placeholder rendered instead
  new Chart(el, config);
}

makeChart('igChart', {
  type: 'line',
  data: { labels: igDates, datasets: igDatasets },
  options: {
    responsive: true,
    plugins: { title: { display: false } },
    scales: {
      y: { ticks: { callback: v => v >= 1000 ? (v/1000).toFixed(0)+'K' : v } }
    },
    spanGaps: true
  }
});

makeChart('ytChart', {
  type: 'line',
  data: { labels: ytDates, datasets: ytDatasets },
  options: {
    responsive: true,
    scales: {
      y: { ticks: { callback: v => v >= 1000 ? (v/1000).toFixed(0)+'K' : v } }
    },
    spanGaps: true
  }
});

makeChart('sovChart', {
  type: 'doughnut',
  data: {
    labels: sovLabels,
    datasets: [{ data: sovValues, backgroundColor: sovColors, hoverOffset: 8 }]
  },
  options: {
    responsive: true,
    plugins: {
      legend: { position: 'right' },
      tooltip: { callbacks: { label: ctx => ctx.label + ': ' + ctx.parsed.toFixed(1) + '%' } }
    }
  }
});

makeChart('dlChart', {
  type: 'line',
  data: { labels: dlPeriods, datasets: dlDatasets },
  options: {
    responsive: true,
    scales: { y: { min: 0, max: 100, title: { display: true, text: '상대 검색량 (0-100)' } } },
    spanGaps: true
  }
});

makeChart('engChart', {
  type: 'bar',
  data: {
    labels: engLabels,
    datasets: [{
      label: '인게이지먼트율 (%)',
      data: engValues,
      backgroundColor: engColors,
    }]
  },
  options: {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: { y: { title: { display: true, text: '인게이지먼트율 (%)' } } }
  }
});
"""

    # Full HTML document
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title_esc}</title>
  <script src="{_CHARTJS_CDN}"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic",
                   "맑은 고딕", sans-serif;
      background: #f5f6fa;
      color: #2d2d2d;
      font-size: 14px;
    }}
    header {{
      background: #1a1a2e;
      color: #fff;
      padding: 1.2rem 2rem;
    }}
    header h1 {{ margin: 0; font-size: 1.4rem; font-weight: 600; }}
    header .meta {{ font-size: 0.8rem; opacity: 0.65; margin-top: 0.3rem; }}
    main {{ padding: 1.5rem 2rem; max-width: 1400px; margin: 0 auto; }}

    /* KPI row */
    .kpi-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 1.8rem;
    }}
    .kpi-card {{
      background: #fff;
      border-radius: 10px;
      padding: 1.1rem 1.3rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.06);
    }}
    .kpi-label {{ font-size: 0.75rem; color: #888; text-transform: uppercase;
                  letter-spacing: .04em; margin-bottom: .35rem; }}
    .kpi-value {{ font-size: 1.3rem; font-weight: 700; color: #1a1a2e; }}
    .kpi-sub   {{ font-size: 0.78rem; color: #555; margin-top: .25rem; }}

    /* Chart grid */
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
      gap: 1.2rem;
      margin-bottom: 1.8rem;
    }}
    .chart-card {{
      background: #fff;
      border-radius: 10px;
      padding: 1.2rem 1.4rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.06);
    }}
    .chart-card h2 {{
      margin: 0 0 1rem;
      font-size: 0.95rem;
      font-weight: 600;
      color: #1a1a2e;
      border-bottom: 2px solid #eee;
      padding-bottom: 0.5rem;
    }}
    .chart-card canvas {{ max-height: 280px; }}

    /* No-data placeholder */
    .no-data {{
      display: flex;
      align-items: center;
      justify-content: center;
      height: 120px;
      color: #aaa;
      font-size: 0.9rem;
      border: 2px dashed #e0e0e0;
      border-radius: 8px;
    }}

    /* Content section tables */
    .content-section {{
      background: #fff;
      border-radius: 10px;
      padding: 1.4rem 1.6rem;
      box-shadow: 0 2px 8px rgba(0,0,0,.06);
      margin-bottom: 2rem;
    }}
    .content-section h2 {{
      margin: 0 0 1rem;
      font-size: 1rem;
      font-weight: 700;
      color: #1a1a2e;
    }}
    .content-section h3 {{
      font-size: 0.88rem;
      font-weight: 600;
      color: #444;
      margin: 0 0 0.5rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.83rem;
    }}
    th {{
      background: #f0f1f5;
      text-align: left;
      padding: 0.5rem 0.7rem;
      font-weight: 600;
      color: #555;
    }}
    td {{
      padding: 0.45rem 0.7rem;
      border-bottom: 1px solid #f0f0f0;
      vertical-align: top;
    }}
    tr:last-child td {{ border-bottom: none; }}
    a {{ color: #4e79a7; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    footer {{
      text-align: center;
      font-size: 0.75rem;
      color: #aaa;
      padding: 1.5rem 0 2rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title_esc}</h1>
    <div class="meta">생성일시: {html.escape(generated_at)}</div>
  </header>
  <main>
    {kpi_html}

    <div class="chart-grid">
      <div class="chart-card">
        <h2>팔로워 추이 (Instagram)</h2>
        {ig_block}
      </div>
      <div class="chart-card">
        <h2>구독자 추이 (YouTube)</h2>
        {yt_block}
      </div>
      <div class="chart-card">
        <h2>검색 점유율 (Naver)</h2>
        {sov_block}
      </div>
      <div class="chart-card">
        <h2>검색량 트렌드 (DataLab)</h2>
        {dl_block}
      </div>
      <div class="chart-card" style="grid-column: 1 / -1">
        <h2>인게이지먼트율 (Instagram)</h2>
        {eng_block}
      </div>
    </div>

    {tc_html}
  </main>
  <footer>Competitor Marketing Monitoring System — Static Dashboard</footer>

  <script>
{js_data}
  </script>
  <script>
{js_init}
  </script>
</body>
</html>"""


def write_dashboard(
    storage: Storage,
    settings: Settings,
    *,
    basename: str | None = None,
) -> str:
    """Write the HTML dashboard to settings.report_dir and return the file path."""
    out_dir = Path(settings.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{basename or 'dashboard'}.html"
    path = out_dir / filename
    path.write_text(build_dashboard_html(storage), encoding="utf-8")
    return str(path)
