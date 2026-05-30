"""YouTube collector via YouTube Data API v3.

Three sequential requests per competitor:
  1. channels  -> channel statistics + uploads playlist id.
  2. playlistItems -> most recent video ids (up to 10).
  3. videos    -> per-video snippet + statistics in one batch call.

The three-step design is required by the YouTube API — channel stats and
per-video stats are on different resources, and playlist paging gives us the
upload order without scanning all videos.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from ..config import CompetitorConfig
from ..models import YtChannelSnapshot, YtVideo
from .base import Collector

log = logging.getLogger(__name__)

_BASE = "https://www.googleapis.com/youtube/v3"
_TIMEOUT = 20
_RECENT_VIDEOS = 10


class YouTubeCollector(Collector):
    name = "youtube"

    def is_available(self) -> bool:
        return bool(self.secrets.youtube_api_key)

    def collect(self, competitors: list[CompetitorConfig]) -> list[object]:
        key = self.secrets.youtube_api_key
        records: list[object] = []

        for comp in competitors:
            if not comp.youtube_channel_id:
                continue
            channel_id = comp.youtube_channel_id

            # ------------------------------------------------------------------ #
            # Step 1: channel statistics + uploads playlist id
            # ------------------------------------------------------------------ #
            try:
                resp = requests.get(
                    f"{_BASE}/channels",
                    params={
                        "part": "statistics,contentDetails",
                        "id": channel_id,
                        "key": key,
                    },
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                ch_data: dict[str, Any] = resp.json()
            except Exception as exc:
                log.warning("[youtube] channels request failed for %s: %s", comp.name, exc)
                continue

            items = ch_data.get("items")
            if not items:
                log.warning("[youtube] no channel found for id=%s (%s)", channel_id, comp.name)
                continue

            ch_item = items[0]
            stats = ch_item.get("statistics", {})
            try:
                # subscriberCount is absent when the channel hides its count.
                records.append(
                    YtChannelSnapshot(
                        competitor=comp.name,
                        channel_id=channel_id,
                        subscriber_count=int(stats.get("subscriberCount", 0)),
                        view_count=int(stats.get("viewCount", 0)),
                        video_count=int(stats.get("videoCount", 0)),
                    )
                )
            except Exception as exc:
                log.warning("[youtube] could not build YtChannelSnapshot for %s: %s", comp.name, exc)

            try:
                uploads_playlist = (
                    ch_item["contentDetails"]["relatedPlaylists"]["uploads"]
                )
            except (KeyError, TypeError) as exc:
                log.warning("[youtube] uploads playlist missing for %s: %s", comp.name, exc)
                continue

            # ------------------------------------------------------------------ #
            # Step 2: most recent video ids from uploads playlist
            # ------------------------------------------------------------------ #
            try:
                resp = requests.get(
                    f"{_BASE}/playlistItems",
                    params={
                        "part": "contentDetails",
                        "playlistId": uploads_playlist,
                        "maxResults": _RECENT_VIDEOS,
                        "key": key,
                    },
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                pl_data: dict[str, Any] = resp.json()
            except Exception as exc:
                log.warning("[youtube] playlistItems request failed for %s: %s", comp.name, exc)
                continue

            video_ids = [
                item["contentDetails"]["videoId"]
                for item in pl_data.get("items", [])
                if item.get("contentDetails", {}).get("videoId")
            ]
            if not video_ids:
                continue

            # ------------------------------------------------------------------ #
            # Step 3: per-video snippet + statistics in one batched request
            # ------------------------------------------------------------------ #
            try:
                resp = requests.get(
                    f"{_BASE}/videos",
                    params={
                        "part": "snippet,statistics",
                        "id": ",".join(video_ids),
                        "key": key,
                    },
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                vid_data: dict[str, Any] = resp.json()
            except Exception as exc:
                log.warning("[youtube] videos request failed for %s: %s", comp.name, exc)
                continue

            for v in vid_data.get("items", []):
                try:
                    snippet = v.get("snippet", {})
                    vstats = v.get("statistics", {})
                    records.append(
                        YtVideo(
                            competitor=comp.name,
                            video_id=v["id"],
                            channel_id=channel_id,
                            title=snippet.get("title", ""),
                            published_at=snippet.get("publishedAt", ""),
                            view_count=int(vstats.get("viewCount", 0)),
                            like_count=int(vstats.get("likeCount", 0)),
                            comment_count=int(vstats.get("commentCount", 0)),
                        )
                    )
                except Exception as exc:
                    log.warning(
                        "[youtube] skipping video %s for %s: %s",
                        v.get("id"), comp.name, exc,
                    )

        return records
