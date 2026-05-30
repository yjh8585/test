"""SQLite storage layer.

Design goals:
  * Idempotent / re-run safe. Snapshots are keyed by (entity, day); items by
    their stable id. Re-collecting upserts instead of duplicating.
  * Type-dispatched. ``save()`` accepts any mix of record dataclasses and
    routes each to the right table.
  * Plain stdlib sqlite3 — no ORM, easy to inspect with any SQLite browser.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import (
    IgMedia,
    IgProfileSnapshot,
    NaverDataLabPoint,
    NaverSearchCount,
    YtChannelSnapshot,
    YtVideo,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS ig_profile_snapshots (
    competitor      TEXT NOT NULL,
    username        TEXT NOT NULL,
    followers_count INTEGER,
    media_count     INTEGER,
    snapshot_date   TEXT NOT NULL,
    collected_at    TEXT NOT NULL,
    PRIMARY KEY (competitor, snapshot_date)
);

CREATE TABLE IF NOT EXISTS ig_media (
    competitor     TEXT NOT NULL,
    media_id       TEXT PRIMARY KEY,
    caption        TEXT,
    like_count     INTEGER,
    comments_count INTEGER,
    timestamp      TEXT,
    permalink      TEXT,
    collected_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yt_channel_snapshots (
    competitor       TEXT NOT NULL,
    channel_id       TEXT NOT NULL,
    subscriber_count INTEGER,
    view_count       INTEGER,
    video_count      INTEGER,
    snapshot_date    TEXT NOT NULL,
    collected_at     TEXT NOT NULL,
    PRIMARY KEY (competitor, snapshot_date)
);

CREATE TABLE IF NOT EXISTS yt_videos (
    video_id      TEXT PRIMARY KEY,
    competitor    TEXT NOT NULL,
    channel_id    TEXT,
    title         TEXT,
    published_at  TEXT,
    view_count    INTEGER,
    like_count    INTEGER,
    comment_count INTEGER,
    collected_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS naver_search_counts (
    keyword       TEXT NOT NULL,
    source        TEXT NOT NULL,
    total         INTEGER,
    snapshot_date TEXT NOT NULL,
    collected_at  TEXT NOT NULL,
    PRIMARY KEY (keyword, source, snapshot_date)
);

CREATE TABLE IF NOT EXISTS naver_datalab (
    keyword_group TEXT NOT NULL,
    period        TEXT NOT NULL,
    ratio         REAL,
    collected_at  TEXT NOT NULL,
    PRIMARY KEY (keyword_group, period)
);
"""

# Per-record-type upsert spec: (table, columns, conflict_target)
_UPSERTS = {
    IgProfileSnapshot: (
        "ig_profile_snapshots",
        ("competitor", "username", "followers_count", "media_count", "snapshot_date", "collected_at"),
        ("competitor", "snapshot_date"),
    ),
    IgMedia: (
        "ig_media",
        ("competitor", "media_id", "caption", "like_count", "comments_count", "timestamp", "permalink", "collected_at"),
        ("media_id",),
    ),
    YtChannelSnapshot: (
        "yt_channel_snapshots",
        ("competitor", "channel_id", "subscriber_count", "view_count", "video_count", "snapshot_date", "collected_at"),
        ("competitor", "snapshot_date"),
    ),
    YtVideo: (
        "yt_videos",
        ("video_id", "competitor", "channel_id", "title", "published_at", "view_count", "like_count", "comment_count", "collected_at"),
        ("video_id",),
    ),
    NaverSearchCount: (
        "naver_search_counts",
        ("keyword", "source", "total", "snapshot_date", "collected_at"),
        ("keyword", "source", "snapshot_date"),
    ),
    NaverDataLabPoint: (
        "naver_datalab",
        ("keyword_group", "period", "ratio", "collected_at"),
        ("keyword_group", "period"),
    ),
}


class Storage:
    def __init__(self, db_path: str = "data/monitor.db") -> None:
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save(self, records: Iterable[object]) -> int:
        """Upsert a heterogeneous iterable of record dataclasses. Returns count."""
        n = 0
        for rec in records:
            spec = _UPSERTS.get(type(rec))
            if spec is None:
                raise TypeError(f"No storage mapping for record type {type(rec)!r}")
            table, columns, conflict = spec
            placeholders = ", ".join("?" for _ in columns)
            updates = ", ".join(f"{c}=excluded.{c}" for c in columns if c not in conflict)
            sql = (
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
                f"ON CONFLICT ({', '.join(conflict)}) DO UPDATE SET {updates}"
            )
            values = [getattr(rec, c) for c in columns]
            self.conn.execute(sql, values)
            n += 1
        self.conn.commit()
        return n

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
