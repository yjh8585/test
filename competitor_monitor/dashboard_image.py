"""PNG dashboard generator for the competitor monitoring system.

Renders all key analytics panels into a single PNG using matplotlib (headless,
no browser or display required). Suitable for emailing or embedding inline.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Must be set BEFORE importing pyplot to prevent display initialisation errors
# in headless / CI environments.
import matplotlib
matplotlib.use("Agg")  # non-interactive Agg backend — no display needed

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib import font_manager

# WenQuanYi Zen Hei ships with most Debian/Ubuntu systems and covers Hangul,
# CJK, and Latin characters.  We register it explicitly so Korean keyword
# labels render correctly instead of showing tofu boxes (□).
_FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
try:
    font_manager.fontManager.addfont(_FONT)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=_FONT).get_name()
except Exception:
    pass  # fall back to system default; may produce tofu for Korean text

# Prevent matplotlib from rendering the minus sign with the default font
# (which can break when a CJK font is active on some backends).
plt.rcParams["axes.unicode_minus"] = False

if TYPE_CHECKING:
    from .storage import Storage
    from .config import Settings

from .branding import color_for
from .analysis.metrics import (
    trend_deltas,
    share_of_voice,
    engagement_rates,
    datalab_trend,
)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _no_data(ax: plt.Axes, label: str = "데이터 없음") -> None:
    """Render a centred 'no data' message and hide all axes decorations."""
    ax.text(
        0.5, 0.5, label,
        ha="center", va="center",
        fontsize=13, color="#888888",
        transform=ax.transAxes,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def _rotate_xlabels(ax: plt.Axes, rotation: int = 45) -> None:
    """Rotate x-axis tick labels for readability (e.g. date strings)."""
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(rotation)
        lbl.set_ha("right")


# --------------------------------------------------------------------------- #
# Panel renderers
# --------------------------------------------------------------------------- #

def _panel_ig_followers(ax: plt.Axes, storage: Storage) -> None:
    """Panel 1 — Instagram follower count over time, one line per competitor."""
    rows = storage.query(
        "SELECT competitor, snapshot_date, followers_count "
        "FROM ig_profile_snapshots ORDER BY snapshot_date"
    )

    # Group rows by competitor while preserving chronological date order.
    by_comp: dict[str, dict[str, int]] = {}
    for r in rows:
        by_comp.setdefault(r["competitor"], {})[r["snapshot_date"]] = r["followers_count"] or 0

    if not by_comp:
        _no_data(ax)
        ax.set_title("팔로워 추이 (Instagram)")
        return

    for competitor, date_map in by_comp.items():
        dates = sorted(date_map.keys())
        values = [date_map[d] for d in dates]
        ax.plot(dates, values, marker="o", markersize=3,
                label=competitor, color=color_for(competitor), linewidth=1.8)

    ax.set_title("팔로워 추이 (Instagram)", fontsize=10, fontweight="bold")
    ax.set_ylabel("팔로워 수")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    _rotate_xlabels(ax)
    # Show only first, mid, last x-tick to avoid crowding
    xticks = ax.get_xticks()
    if len(xticks) > 4:
        ax.set_xticks([xticks[0], xticks[len(xticks) // 2], xticks[-1]])
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4)


def _panel_yt_subscribers(ax: plt.Axes, storage: Storage) -> None:
    """Panel 2 — YouTube subscriber count over time, one line per competitor."""
    rows = storage.query(
        "SELECT competitor, snapshot_date, subscriber_count "
        "FROM yt_channel_snapshots ORDER BY snapshot_date"
    )

    by_comp: dict[str, dict[str, int]] = {}
    for r in rows:
        by_comp.setdefault(r["competitor"], {})[r["snapshot_date"]] = r["subscriber_count"] or 0

    if not by_comp:
        _no_data(ax)
        ax.set_title("구독자 추이 (YouTube)")
        return

    for competitor, date_map in by_comp.items():
        dates = sorted(date_map.keys())
        values = [date_map[d] for d in dates]
        ax.plot(dates, values, marker="o", markersize=3,
                label=competitor, color=color_for(competitor), linewidth=1.8)

    ax.set_title("구독자 추이 (YouTube)", fontsize=10, fontweight="bold")
    ax.set_ylabel("구독자 수")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    _rotate_xlabels(ax)
    xticks = ax.get_xticks()
    if len(xticks) > 4:
        ax.set_xticks([xticks[0], xticks[len(xticks) // 2], xticks[-1]])
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4)


def _panel_share_of_voice(ax: plt.Axes, storage: Storage) -> None:
    """Panel 3 — Pie chart of Naver search share of voice per keyword."""
    sov = share_of_voice(storage)

    if not sov:
        _no_data(ax)
        ax.set_title("검색 점유율 (SoV)")
        return

    labels = [f"{r['keyword']}\n{r['share_pct']:.1f}%" for r in sov]
    sizes = [r["share_pct"] for r in sov]
    colors = [color_for(r["keyword"]) for r in sov]

    wedges, texts = ax.pie(
        sizes,
        labels=None,       # use legend instead to avoid overlapping text
        colors=colors,
        startangle=140,
        wedgeprops={"linewidth": 0.8, "edgecolor": "white"},
    )

    ax.legend(
        wedges, labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=7,
        frameon=False,
    )
    ax.set_title("검색 점유율 (SoV)", fontsize=10, fontweight="bold")


def _panel_datalab_trend(ax: plt.Axes, storage: Storage) -> None:
    """Panel 4 — Naver DataLab relative-search-volume trends per keyword group."""
    trends = datalab_trend(storage)

    if not trends:
        _no_data(ax)
        ax.set_title("검색량 트렌드 (DataLab)")
        return

    for entry in trends:
        kg = entry["keyword_group"]
        points = entry["points"]
        if not points:
            continue
        periods = [p["period"] for p in points]
        ratios = [p["ratio"] for p in points]
        ax.plot(periods, ratios, marker=".", markersize=4,
                label=kg, color=color_for(kg), linewidth=1.6)

    ax.set_title("검색량 트렌드 (DataLab)", fontsize=10, fontweight="bold")
    ax.set_ylabel("상대 검색량")
    _rotate_xlabels(ax)
    xticks = ax.get_xticks()
    if len(xticks) > 4:
        ax.set_xticks([xticks[0], xticks[len(xticks) // 2], xticks[-1]])
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4)


def _panel_engagement_rates(ax: plt.Axes, storage: Storage) -> None:
    """Panel 5 — Horizontal bar of IG engagement rate (%) per competitor, sorted desc."""
    eng = engagement_rates(storage)

    if not eng:
        _no_data(ax)
        ax.set_title("인게이지먼트율 (Instagram)")
        return

    # engagement_rates() already returns sorted desc; reverse for bottom-up bars.
    eng_sorted = list(reversed(eng))
    competitors = [r["competitor"] for r in eng_sorted]
    rates = [r["engagement_rate_pct"] for r in eng_sorted]
    colors = [color_for(c) for c in competitors]

    bars = ax.barh(competitors, rates, color=colors, edgecolor="white", linewidth=0.5)

    # Label bars with the rate value
    for bar, rate in zip(bars, rates):
        ax.text(
            bar.get_width() + max(rates) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{rate:.2f}%",
            va="center", fontsize=8,
        )

    ax.set_title("인게이지먼트율 (Instagram)", fontsize=10, fontweight="bold")
    ax.set_xlabel("인게이지먼트율 (%)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.1f}%"))
    ax.grid(axis="x", linestyle="--", alpha=0.4)


def _panel_follower_delta(ax: plt.Axes, storage: Storage) -> None:
    """Panel 6 — Bar chart of weekly Instagram follower change (delta) per competitor.

    Bars are green for positive deltas, red for negative/zero, annotated with
    the +/- value.
    """
    deltas_data = trend_deltas(storage)
    ig_deltas = deltas_data.get("instagram", [])

    if not ig_deltas:
        _no_data(ax)
        ax.set_title("팔로워 증감 (주간, Instagram)")
        return

    # Sort by delta descending so the biggest gainer is leftmost
    ig_deltas = sorted(ig_deltas, key=lambda r: r["delta"], reverse=True)
    competitors = [r["competitor"] for r in ig_deltas]
    deltas = [r["delta"] for r in ig_deltas]
    colors = ["#2ecc71" if d >= 0 else "#e74c3c" for d in deltas]

    bars = ax.bar(competitors, deltas, color=colors, edgecolor="white", linewidth=0.5)

    # Annotate bars with +/- formatted delta
    for bar, delta in zip(bars, deltas):
        sign = "+" if delta >= 0 else ""
        y_offset = max(abs(d) for d in deltas) * 0.02 if any(deltas) else 1
        y_pos = bar.get_height() + y_offset if delta >= 0 else bar.get_height() - y_offset
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y_pos,
            f"{sign}{delta:,}",
            ha="center", va="bottom" if delta >= 0 else "top",
            fontsize=8,
        )

    ax.axhline(0, color="#555555", linewidth=0.8, linestyle="--")
    ax.set_title("팔로워 증감 (주간, Instagram)", fontsize=10, fontweight="bold")
    ax.set_ylabel("증감 수")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    _rotate_xlabels(ax)
    ax.grid(axis="y", linestyle="--", alpha=0.4)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def build_dashboard_image(
    storage: Storage,
    *,
    path: str,
    title: str = "경쟁사 마케팅 모니터링 대시보드",
    generated_at: str | None = None,
) -> str:
    """Render all six monitoring panels into a single PNG at *path*.

    Returns the resolved path string so callers can display or email the file.
    """
    # Ensure the output directory exists before we try to write into it.
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    if generated_at is None:
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    fig, axes = plt.subplots(
        2, 3,
        figsize=(18, 12),
        constrained_layout=True,
    )

    # Flatten the 2x3 grid for indexed access
    ax_flat = axes.flatten()

    # Suptitle carries the dashboard title and generation timestamp.
    # No explicit y: constrained_layout reserves space for it automatically,
    # which keeps it clear of the top-row subplot titles.
    fig.suptitle(
        f"{title}\n생성: {generated_at}",
        fontsize=14,
        fontweight="bold",
    )

    # Render each panel; each function handles the empty-data case internally.
    _panel_ig_followers(ax_flat[0], storage)      # Panel 1
    _panel_yt_subscribers(ax_flat[1], storage)    # Panel 2
    _panel_share_of_voice(ax_flat[2], storage)    # Panel 3
    _panel_datalab_trend(ax_flat[3], storage)     # Panel 4
    _panel_engagement_rates(ax_flat[4], storage)  # Panel 5
    _panel_follower_delta(ax_flat[5], storage)    # Panel 6

    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)

    return path


def write_dashboard_image(
    storage: Storage,
    settings: Settings,
    *,
    basename: str | None = None,
) -> str:
    """Save the dashboard PNG to *settings.report_dir* and return the full path.

    Args:
        storage:  Populated Storage instance.
        settings: Settings object (supplies report_dir).
        basename: Filename stem, default "dashboard".
    """
    report_dir = Path(settings.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(report_dir / f"{basename or 'dashboard'}.png")
    return build_dashboard_image(storage, path=out_path)
