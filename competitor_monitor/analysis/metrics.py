"""Pure-Python analytics over the SQLite data.

All functions accept a Storage instance and return JSON-serialisable plain
dicts/lists so the reporting layer has no further transformation to do.

Why this module exists: separating analytics from collection lets us re-run
or back-test the analysis against any snapshot of the database without
triggering live API calls.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage import Storage


# --------------------------------------------------------------------------- #
# Instagram engagement
# --------------------------------------------------------------------------- #

def engagement_rates(storage: Storage) -> list[dict]:
    """Compute engagement rate per competitor from the latest IG profile snapshot.

    Rate = avg(like_count + comments_count) per media item / followers_count * 100.
    Only the most recent snapshot_date per competitor is used so that each run
    gives a current-state view rather than a historical average.
    """
    # Latest snapshot per competitor
    snapshots = storage.query(
        """
        SELECT competitor, followers_count
        FROM ig_profile_snapshots
        WHERE snapshot_date = (
            SELECT MAX(snapshot_date)
            FROM ig_profile_snapshots AS inner_s
            WHERE inner_s.competitor = ig_profile_snapshots.competitor
        )
        """
    )

    result: list[dict] = []
    for row in snapshots:
        competitor = row["competitor"]
        followers = row["followers_count"] or 0

        # Aggregate engagement across all stored media for this competitor
        media_rows = storage.query(
            """
            SELECT COALESCE(like_count, 0) + COALESCE(comments_count, 0) AS interactions
            FROM ig_media
            WHERE competitor = ?
            """,
            (competitor,),
        )

        sample_size = len(media_rows)
        if sample_size == 0 or followers == 0:
            # Guard: no media collected yet or zero followers
            result.append(
                {
                    "competitor": competitor,
                    "followers": followers,
                    "avg_interactions": 0.0,
                    "engagement_rate_pct": 0.0,
                    "sample_size": sample_size,
                }
            )
            continue

        avg_interactions = sum(r["interactions"] for r in media_rows) / sample_size
        engagement_rate_pct = round(avg_interactions / followers * 100, 4)

        result.append(
            {
                "competitor": competitor,
                "followers": followers,
                "avg_interactions": round(avg_interactions, 2),
                "engagement_rate_pct": engagement_rate_pct,
                "sample_size": sample_size,
            }
        )

    # Descending by engagement rate for easy scanning
    result.sort(key=lambda x: x["engagement_rate_pct"], reverse=True)
    return result


# --------------------------------------------------------------------------- #
# Share of voice (Naver search counts)
# --------------------------------------------------------------------------- #

def share_of_voice(storage: Storage) -> list[dict]:
    """Keyword share of total buzz on the latest snapshot date.

    Sums `total` across all sources per keyword for the most recent
    snapshot_date in naver_search_counts, then expresses each keyword's
    contribution as a percentage of the grand total.
    """
    # Find the single latest snapshot date across the whole table
    latest_rows = storage.query(
        "SELECT MAX(snapshot_date) AS latest FROM naver_search_counts"
    )
    if not latest_rows or latest_rows[0]["latest"] is None:
        return []

    latest_date = latest_rows[0]["latest"]

    rows = storage.query(
        """
        SELECT keyword, SUM(total) AS total_mentions
        FROM naver_search_counts
        WHERE snapshot_date = ?
        GROUP BY keyword
        ORDER BY total_mentions DESC
        """,
        (latest_date,),
    )

    grand_total = sum(r["total_mentions"] or 0 for r in rows)

    result: list[dict] = []
    for row in rows:
        mentions = row["total_mentions"] or 0
        share = round(mentions / grand_total * 100, 2) if grand_total else 0.0
        result.append(
            {
                "keyword": row["keyword"],
                "total_mentions": mentions,
                "share_pct": share,
            }
        )

    return result  # already sorted desc by total_mentions


# --------------------------------------------------------------------------- #
# Week-over-week follower / subscriber deltas
# --------------------------------------------------------------------------- #

def trend_deltas(storage: Storage) -> dict:
    """Week-over-week change for IG followers and YT subscribers per competitor.

    For each competitor, compares the latest snapshot to the one ~7 days prior
    (or the earliest available if history is shorter than 7 days).
    If only one snapshot exists, prev is returned as None and delta is 0.
    """

    def _wow(rows_by_competitor: dict[str, list], value_col: str) -> list[dict]:
        """Generic helper that works for any snapshot table."""
        out: list[dict] = []
        for competitor, rows in rows_by_competitor.items():
            # rows are ordered desc by snapshot_date (latest first)
            now_val = rows[0][value_col]

            if len(rows) == 1:
                out.append(
                    {
                        "competitor": competitor,
                        f"{value_col}_now": now_val,
                        f"{value_col}_prev": None,
                        "delta": 0,
                        "pct": 0.0,
                    }
                )
                continue

            # Use the snapshot closest to 7 days ago, falling back to earliest
            prev_row = rows[-1]  # earliest available (cold-start default)
            for r in rows[1:]:
                # snapshot_date is a YYYY-MM-DD string; lexicographic comparison works
                if rows[0]["snapshot_date"] >= r["snapshot_date"]:
                    from datetime import date
                    try:
                        d_now = date.fromisoformat(rows[0]["snapshot_date"])
                        d_cand = date.fromisoformat(r["snapshot_date"])
                        if (d_now - d_cand).days >= 7:
                            prev_row = r
                            break
                    except ValueError:
                        pass  # malformed date — keep scanning

            prev_val = prev_row[value_col]
            delta = (now_val or 0) - (prev_val or 0)
            pct = round(delta / prev_val * 100, 2) if prev_val else 0.0

            out.append(
                {
                    "competitor": competitor,
                    f"{value_col}_now": now_val,
                    f"{value_col}_prev": prev_val,
                    "delta": delta,
                    "pct": pct,
                }
            )
        return out

    # --- Instagram ---
    ig_rows = storage.query(
        """
        SELECT competitor, snapshot_date, followers_count
        FROM ig_profile_snapshots
        ORDER BY competitor, snapshot_date DESC
        """
    )
    ig_by_comp: dict[str, list] = {}
    for r in ig_rows:
        ig_by_comp.setdefault(r["competitor"], []).append(r)

    # --- YouTube ---
    yt_rows = storage.query(
        """
        SELECT competitor, snapshot_date, subscriber_count
        FROM yt_channel_snapshots
        ORDER BY competitor, snapshot_date DESC
        """
    )
    yt_by_comp: dict[str, list] = {}
    for r in yt_rows:
        yt_by_comp.setdefault(r["competitor"], []).append(r)

    return {
        "instagram": _wow(ig_by_comp, "followers_count"),
        "youtube": _wow(yt_by_comp, "subscriber_count"),
    }


# --------------------------------------------------------------------------- #
# Naver DataLab trend
# --------------------------------------------------------------------------- #

def datalab_trend(storage: Storage) -> list[dict]:
    """Time-series and direction read for each Naver DataLab keyword group.

    change_pct is the percentage change from the first data point in the
    stored window to the latest, giving a quick up/down signal.
    """
    rows = storage.query(
        """
        SELECT keyword_group, period, ratio
        FROM naver_datalab
        ORDER BY keyword_group, period ASC
        """
    )

    # Group by keyword_group preserving time order
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["keyword_group"], []).append(
            {"period": r["period"], "ratio": r["ratio"]}
        )

    result: list[dict] = []
    for kg, points in groups.items():
        first_ratio = points[0]["ratio"] if points else None
        latest_ratio = points[-1]["ratio"] if points else None

        if first_ratio and first_ratio != 0:
            change_pct = round((latest_ratio - first_ratio) / first_ratio * 100, 2)
        else:
            change_pct = 0.0

        result.append(
            {
                "keyword_group": kg,
                "points": points,
                "latest": latest_ratio,
                "change_pct": change_pct,
            }
        )

    return result


# --------------------------------------------------------------------------- #
# Top content
# --------------------------------------------------------------------------- #

def top_content(storage: Storage, limit: int = 5) -> dict:
    """Return the highest-engagement IG posts and YT videos across all competitors.

    Engagement proxy: like_count + comments_count for IG; view_count for YT.
    caption_preview is truncated to 80 characters.
    """
    ig_rows = storage.query(
        f"""
        SELECT competitor, permalink,
               COALESCE(like_count, 0)     AS like_count,
               COALESCE(comments_count, 0) AS comments_count,
               caption
        FROM ig_media
        ORDER BY (COALESCE(like_count, 0) + COALESCE(comments_count, 0)) DESC
        LIMIT {int(limit)}
        """
    )

    instagram = [
        {
            "competitor": r["competitor"],
            "permalink": r["permalink"],
            "like_count": r["like_count"],
            "comments_count": r["comments_count"],
            # First 80 chars of caption; handle NULL gracefully
            "caption_preview": (r["caption"] or "")[:80],
        }
        for r in ig_rows
    ]

    yt_rows = storage.query(
        f"""
        SELECT competitor, title,
               COALESCE(view_count, 0) AS view_count,
               COALESCE(like_count, 0) AS like_count,
               video_id
        FROM yt_videos
        ORDER BY COALESCE(view_count, 0) DESC
        LIMIT {int(limit)}
        """
    )

    youtube = [
        {
            "competitor": r["competitor"],
            "title": r["title"],
            "view_count": r["view_count"],
            "like_count": r["like_count"],
            "video_id": r["video_id"],
        }
        for r in yt_rows
    ]

    return {"instagram": instagram, "youtube": youtube}


# --------------------------------------------------------------------------- #
# Convenience aggregator
# --------------------------------------------------------------------------- #

def build_analysis(storage: Storage) -> dict:
    """Run all analytics in one call and return a single keyed result dict.

    Useful for report generation: call once, pass the dict to the formatter.
    """
    return {
        "engagement_rates": engagement_rates(storage),
        "share_of_voice": share_of_voice(storage),
        "trend_deltas": trend_deltas(storage),
        "datalab_trend": datalab_trend(storage),
        "top_content": top_content(storage),
    }
