"""Reporting layer: Markdown + HTML generation for weekly competitor reports.

render_markdown  -> pure-function dict -> str (no I/O)
render_html      -> minimal stdlib-only Markdown -> HTML conversion
write_report     -> persists both files under settings.report_dir
"""
from __future__ import annotations

import html as _html_mod
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _now_utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _safe(val: Any, fmt: str = "{}") -> str:
    """Format a value; return '-' when None."""
    if val is None:
        return "-"
    return fmt.format(val)


def _pct_str(val: Any) -> str:
    """Render a percentage with a leading + sign when positive."""
    if val is None:
        return "-"
    try:
        f = float(val)
        sign = "+" if f > 0 else ""
        return f"{sign}{f:.1f}%"
    except (TypeError, ValueError):
        return str(val)


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Return a GitHub-flavoured Markdown table string."""
    sep = ["-" * max(3, len(h)) for h in headers]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def _no_data() -> str:
    return "_데이터 없음_"


# --------------------------------------------------------------------------- #
# Executive-summary auto-generation
# --------------------------------------------------------------------------- #

def _build_summary(analysis: dict) -> str:
    """Derive a few Korean sentences that highlight the week's key numbers."""
    sentences: list[str] = []

    # ── Follower / subscriber movement ──────────────────────────────────────
    ig_deltas: list[dict] = (analysis.get("trend_deltas") or {}).get("instagram") or []
    yt_deltas: list[dict] = (analysis.get("trend_deltas") or {}).get("youtube") or []

    top_ig = max(
        (d for d in ig_deltas if d.get("delta") is not None),
        key=lambda d: d["delta"],
        default=None,
    )
    top_yt = max(
        (d for d in yt_deltas if d.get("delta") is not None),
        key=lambda d: d["delta"],
        default=None,
    )

    if top_ig:
        sentences.append(
            f"인스타그램에서 **{top_ig['competitor']}**가 전주 대비 "
            f"{_pct_str(top_ig.get('pct'))} 팔로워 변동으로 가장 큰 성장을 기록했습니다."
        )
    if top_yt:
        sentences.append(
            f"유튜브에서는 **{top_yt['competitor']}**가 "
            f"{_pct_str(top_yt.get('pct'))} 구독자 변동으로 주목됩니다."
        )

    # ── Share of voice ───────────────────────────────────────────────────────
    sov: list[dict] = analysis.get("share_of_voice") or []
    if sov:
        top_kw = max(sov, key=lambda d: float(d.get("share_pct") or 0), default=None)
        if top_kw:
            sentences.append(
                f"검색 점유율 최상위 키워드는 **{top_kw['keyword']}** "
                f"({_safe(top_kw.get('share_pct'), '{:.1f}%')})입니다."
            )

    # ── DataLab notable movement ─────────────────────────────────────────────
    dl: list[dict] = analysis.get("datalab_trend") or []
    notable = [d for d in dl if d.get("change_pct") is not None]
    if notable:
        mover = max(notable, key=lambda d: abs(float(d.get("change_pct") or 0)))
        sentences.append(
            f"네이버 DataLab 기준 **{mover['keyword_group']}** 검색량이 "
            f"{_pct_str(mover.get('change_pct'))} 변동해 이번 주 가장 눈에 띄는 트렌드입니다."
        )

    if not sentences:
        return "이번 주 집계된 데이터를 기반으로 작성된 자동 요약입니다. 세부 내용은 아래 섹션을 참고하세요."

    return "  \n".join(sentences)


# --------------------------------------------------------------------------- #
# render_markdown
# --------------------------------------------------------------------------- #

def render_markdown(
    analysis: dict,
    *,
    llm_summary: dict | None = None,
    generated_at: str | None = None,
    title: str = "경쟁사 마케팅 모니터링 주간 리포트",
) -> str:
    """Build a Korean-language weekly Markdown report from the analysis dict.

    Defensive: any sub-list may be empty or missing, any value may be None.
    """
    date_str = generated_at or _now_utc_date()
    sections: list[str] = []

    # ── Title ────────────────────────────────────────────────────────────────
    sections.append(f"# {title}")
    sections.append(f"_생성일: {date_str}_")

    # ── 요약 (Executive summary) ─────────────────────────────────────────────
    sections.append("## 요약")
    sections.append(_build_summary(analysis))

    # ── 인게이지먼트 ──────────────────────────────────────────────────────────
    sections.append("## 인게이지먼트")
    eng_rows: list[dict] = analysis.get("engagement_rates") or []
    if eng_rows:
        rows = [
            [
                _safe(r.get("competitor")),
                _safe(r.get("followers"), "{:,}"),
                _safe(r.get("avg_interactions"), "{:.1f}"),
                _safe(r.get("engagement_rate_pct"), "{:.2f}%"),
                _safe(r.get("sample_size")),
            ]
            for r in eng_rows
        ]
        sections.append(
            _md_table(
                ["경쟁사", "팔로워", "평균 상호작용", "인게이지먼트율", "샘플수"],
                rows,
            )
        )
    else:
        sections.append(_no_data())

    # ── 검색 점유율 / Share of Voice ─────────────────────────────────────────
    sections.append("## 검색 점유율 / Share of Voice")
    sov_rows: list[dict] = analysis.get("share_of_voice") or []
    if sov_rows:
        rows = [
            [
                _safe(r.get("keyword")),
                _safe(r.get("total_mentions"), "{:,}"),
                _safe(r.get("share_pct"), "{:.1f}%"),
            ]
            for r in sov_rows
        ]
        sections.append(_md_table(["키워드", "총 언급수", "점유율"], rows))
    else:
        sections.append(_no_data())

    # ── 팔로워·구독자 추이 ────────────────────────────────────────────────────
    sections.append("## 팔로워·구독자 추이")
    td: dict = analysis.get("trend_deltas") or {}

    ig_rows: list[dict] = td.get("instagram") or []
    sections.append("### Instagram")
    if ig_rows:
        rows = [
            [
                _safe(r.get("competitor")),
                _safe(r.get("followers_count_now"), "{:,}"),
                _safe(r.get("followers_count_prev"), "{:,}"),
                _safe(r.get("delta"), "{:+,}") if r.get("delta") is not None else "-",
                _pct_str(r.get("pct")),
            ]
            for r in ig_rows
        ]
        sections.append(
            _md_table(["경쟁사", "현재 팔로워", "이전 팔로워", "증감", "증감율"], rows)
        )
    else:
        sections.append(_no_data())

    yt_rows: list[dict] = td.get("youtube") or []
    sections.append("### YouTube")
    if yt_rows:
        rows = [
            [
                _safe(r.get("competitor")),
                _safe(r.get("subscriber_count_now"), "{:,}"),
                _safe(r.get("subscriber_count_prev"), "{:,}"),
                _safe(r.get("delta"), "{:+,}") if r.get("delta") is not None else "-",
                _pct_str(r.get("pct")),
            ]
            for r in yt_rows
        ]
        sections.append(
            _md_table(["경쟁사", "현재 구독자", "이전 구독자", "증감", "증감율"], rows)
        )
    else:
        sections.append(_no_data())

    # ── 검색량 트렌드 (DataLab) ───────────────────────────────────────────────
    sections.append("## 검색량 트렌드 (DataLab)")
    dl_rows: list[dict] = analysis.get("datalab_trend") or []
    if dl_rows:
        rows = [
            [
                _safe(r.get("keyword_group")),
                _safe(r.get("latest"), "{:.1f}"),
                _pct_str(r.get("change_pct")),
            ]
            for r in dl_rows
        ]
        sections.append(_md_table(["키워드 그룹", "최근 지수", "변동율"], rows))
    else:
        sections.append(_no_data())

    # ── 주목 콘텐츠 ───────────────────────────────────────────────────────────
    sections.append("## 주목 콘텐츠")
    tc: dict = analysis.get("top_content") or {}

    ig_content: list[dict] = tc.get("instagram") or []
    sections.append("### Instagram")
    if ig_content:
        rows = [
            [
                _safe(r.get("competitor")),
                _safe(r.get("like_count"), "{:,}"),
                _safe(r.get("comments_count"), "{:,}"),
                _safe(r.get("caption_preview")),
                f"[링크]({r['permalink']})" if r.get("permalink") else "-",
            ]
            for r in ig_content
        ]
        sections.append(
            _md_table(["경쟁사", "좋아요", "댓글", "캡션 미리보기", "링크"], rows)
        )
    else:
        sections.append(_no_data())

    yt_content: list[dict] = tc.get("youtube") or []
    sections.append("### YouTube")
    if yt_content:
        rows = [
            [
                _safe(r.get("competitor")),
                _safe(r.get("title")),
                _safe(r.get("view_count"), "{:,}"),
                _safe(r.get("like_count"), "{:,}"),
                f"[영상](https://youtu.be/{r['video_id']})"
                if r.get("video_id")
                else "-",
            ]
            for r in yt_content
        ]
        sections.append(
            _md_table(["경쟁사", "제목", "조회수", "좋아요", "링크"], rows)
        )
    else:
        sections.append(_no_data())

    # ── AI 크리에이티브 분석 ──────────────────────────────────────────────────
    # Only render when llm_summary is provided; distinguish success vs error.
    if llm_summary is not None:
        sections.append("## AI 크리에이티브 분석")
        if "summary" in llm_summary and llm_summary["summary"]:
            sections.append(llm_summary["summary"])
        elif "error" in llm_summary:
            sections.append(
                f"> ⚠️ AI 분석을 불러오지 못했습니다 (오류: {llm_summary['error']})"
            )
        else:
            sections.append("> AI 분석 결과가 없습니다.")

    return "\n\n".join(sections) + "\n"


# --------------------------------------------------------------------------- #
# Minimal Markdown → HTML converter (stdlib only)
# --------------------------------------------------------------------------- #

def _md_to_html(md: str) -> str:
    """Convert the subset of Markdown that render_markdown emits to HTML.

    Handles: headings (#/##/###), fenced tables, bold (**), inline links,
    blockquotes (>), italic (_), unordered/ordered lists, and paragraphs.
    No third-party deps; correctness is scoped to the output of render_markdown.
    """
    lines = md.split("\n")
    out: list[str] = []
    i = 0

    def escape(s: str) -> str:
        return _html_mod.escape(s, quote=False)

    def inline(s: str) -> str:
        """Apply inline formatting: bold, italic, links."""
        # Bold: **text**
        s = re.sub(r"\*\*(.+?)\*\*", lambda m: f"<strong>{escape(m.group(1))}</strong>", s)
        # Italic: _text_  (only whole-word boundaries to avoid false positives)
        s = re.sub(r"(?<!\w)_(.+?)_(?!\w)", lambda m: f"<em>{escape(m.group(1))}</em>", s)
        # Inline links: [text](url)
        s = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            lambda m: f'<a href="{escape(m.group(2))}">{escape(m.group(1))}</a>',
            s,
        )
        return s

    def parse_table(table_lines: list[str]) -> str:
        """Convert GFM table lines to an HTML <table>."""
        if len(table_lines) < 2:
            return ""
        header_cells = [c.strip() for c in table_lines[0].strip("|").split("|")]
        # table_lines[1] is the separator row — skip it
        body_lines = table_lines[2:]

        thead = "<thead><tr>" + "".join(f"<th>{inline(escape(h))}</th>" for h in header_cells) + "</tr></thead>"
        tbody_rows: list[str] = []
        for tl in body_lines:
            cells = [c.strip() for c in tl.strip("|").split("|")]
            # Pad / trim to match header width
            while len(cells) < len(header_cells):
                cells.append("")
            cells = cells[: len(header_cells)]
            tbody_rows.append(
                "<tr>" + "".join(f"<td>{inline(escape(c))}</td>" for c in cells) + "</tr>"
            )
        tbody = "<tbody>" + "".join(tbody_rows) + "</tbody>"
        return f"<table>{thead}{tbody}</table>"

    # ── Collect table blocks first (multi-line) ──────────────────────────────
    # We process line-by-line; when we detect a table (line starts with |)
    # accumulate lines until the block ends.

    while i < len(lines):
        line = lines[i]

        # Heading
        hm = re.match(r"^(#{1,6})\s+(.*)", line)
        if hm:
            level = len(hm.group(1))
            out.append(f"<h{level}>{inline(escape(hm.group(2)))}</h{level}>")
            i += 1
            continue

        # Blockquote
        if line.startswith(">"):
            content = line[1:].strip()
            out.append(f"<blockquote><p>{inline(escape(content))}</p></blockquote>")
            i += 1
            continue

        # Table (GFM): detect by leading pipe
        if re.match(r"^\s*\|", line):
            tbl: list[str] = []
            while i < len(lines) and re.match(r"^\s*\|", lines[i]):
                tbl.append(lines[i])
                i += 1
            out.append(parse_table(tbl))
            continue

        # Unordered list
        if re.match(r"^\s*[-*]\s+", line):
            items: list[str] = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                text = re.sub(r"^\s*[-*]\s+", "", lines[i])
                items.append(f"<li>{inline(escape(text))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Ordered list
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                text = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                items.append(f"<li>{inline(escape(text))}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Blank line → paragraph separator (skip)
        if line.strip() == "":
            i += 1
            continue

        # Paragraph / plain text
        out.append(f"<p>{inline(escape(line))}</p>")
        i += 1

    return "\n".join(out)


# --------------------------------------------------------------------------- #
# render_html
# --------------------------------------------------------------------------- #

_CSS = """
body {
    font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR', Arial, sans-serif;
    font-size: 15px;
    line-height: 1.7;
    max-width: 960px;
    margin: 40px auto;
    padding: 0 24px;
    color: #222;
    background: #fff;
}
h1 { font-size: 1.8em; border-bottom: 2px solid #333; padding-bottom: 6px; margin-bottom: 4px; }
h2 { font-size: 1.3em; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 32px; }
h3 { font-size: 1.1em; margin-top: 20px; color: #444; }
em  { color: #555; font-style: italic; }
blockquote {
    border-left: 4px solid #f0a020;
    margin: 12px 0;
    padding: 8px 16px;
    background: #fff8ee;
    color: #555;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 0.93em;
}
th {
    background: #2d5fad;
    color: #fff;
    padding: 8px 12px;
    text-align: left;
}
td {
    padding: 7px 12px;
    border-bottom: 1px solid #e0e0e0;
}
tr:nth-child(even) td { background: #f5f8ff; }
a { color: #2d5fad; text-decoration: none; }
a:hover { text-decoration: underline; }
p { margin: 8px 0; }
"""


def render_html(
    markdown_text: str,
    *,
    title: str = "경쟁사 마케팅 모니터링 주간 리포트",
) -> str:
    """Wrap converted Markdown in a minimal self-contained HTML document.

    Uses only stdlib; no third-party markdown or template libraries.
    """
    body = _md_to_html(markdown_text)
    escaped_title = _html_mod.escape(title)
    return (
        "<!DOCTYPE html>\n"
        "<html lang='ko'>\n"
        "<head>\n"
        f"  <meta charset='UTF-8'>\n"
        f"  <meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"  <title>{escaped_title}</title>\n"
        f"  <style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


# --------------------------------------------------------------------------- #
# write_report
# --------------------------------------------------------------------------- #

def write_report(
    analysis: dict,
    settings: Any,
    *,
    llm_summary: dict | None = None,
    basename: str | None = None,
) -> dict[str, str]:
    """Render and persist .md and .html reports to settings.report_dir.

    Returns {"markdown_path": ..., "html_path": ...} with absolute paths.
    """
    report_dir = Path(settings.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    base = basename or f"report_{_now_utc_date()}"

    md_text = render_markdown(analysis, llm_summary=llm_summary)
    html_text = render_html(md_text)

    md_path = report_dir / f"{base}.md"
    html_path = report_dir / f"{base}.html"

    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")

    return {
        "markdown_path": str(md_path.resolve()),
        "html_path": str(html_path.resolve()),
    }
