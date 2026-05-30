"""Instagram collector via Meta Graph API Business Discovery.

Business Discovery lets us read a *competitor's* public IG profile through
*our own* IG Business account — no competitor cooperation needed. One request
per competitor fetches both the profile snapshot and the latest media in a
single round-trip by using field expansion.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from ..config import CompetitorConfig
from ..models import IgMedia, IgProfileSnapshot
from .base import Collector

log = logging.getLogger(__name__)

_GRAPH_URL = "https://graph.facebook.com/v18.0/{ig_user_id}"
_TIMEOUT = 20


class InstagramCollector(Collector):
    name = "instagram"

    def is_available(self) -> bool:
        # Both our IG user id (from settings) and the access token are required.
        return bool(self.secrets.meta_access_token and self.settings.ig_user_id)

    def collect(self, competitors: list[CompetitorConfig]) -> list[object]:
        token = self.secrets.meta_access_token
        ig_user_id = self.settings.ig_user_id
        url = _GRAPH_URL.format(ig_user_id=ig_user_id)
        records: list[object] = []

        for comp in competitors:
            if not comp.instagram_username:
                continue
            username = comp.instagram_username
            # Field expansion: fetch profile stats + latest media in one call.
            fields = (
                f"business_discovery.as(business_discovery)"
                f"{{followers_count,media_count,"
                f"media{{id,caption,like_count,comments_count,timestamp,permalink}}}}"
            )
            # Substitute the target username into the business_discovery field.
            fields = (
                f"business_discovery.as(business_discovery)"
                f".fields(username({username})"
                f"{{followers_count,media_count,"
                f"media{{id,caption,like_count,comments_count,timestamp,permalink}}}}"
                f")"
            )
            # The API uses a simpler dotted syntax for Business Discovery.
            fields = (
                f"business_discovery.username({username})"
                f"{{followers_count,media_count,"
                f"media{{id,caption,like_count,comments_count,timestamp,permalink}}}}"
            )
            params: dict[str, str] = {
                "access_token": token,  # type: ignore[assignment]
                "fields": fields,
            }
            try:
                resp = requests.get(url, params=params, timeout=_TIMEOUT)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
            except Exception as exc:
                log.warning("[instagram] failed to fetch @%s for %s: %s", username, comp.name, exc)
                continue

            bd = data.get("business_discovery")
            if not bd:
                log.warning("[instagram] no business_discovery in response for @%s", username)
                continue

            # Profile snapshot — one row per (competitor, day).
            try:
                records.append(
                    IgProfileSnapshot(
                        competitor=comp.name,
                        username=username,
                        followers_count=int(bd.get("followers_count", 0)),
                        media_count=int(bd.get("media_count", 0)),
                    )
                )
            except Exception as exc:
                log.warning("[instagram] could not build IgProfileSnapshot for %s: %s", comp.name, exc)

            # Individual media items — one row per stable media id.
            media_page: dict[str, Any] = bd.get("media", {})
            for item in media_page.get("data", []):
                try:
                    records.append(
                        IgMedia(
                            competitor=comp.name,
                            media_id=str(item["id"]),
                            # caption is absent on some media types (Reels without text).
                            caption=item.get("caption", ""),
                            like_count=int(item.get("like_count", 0)),
                            comments_count=int(item.get("comments_count", 0)),
                            timestamp=item.get("timestamp", ""),
                            permalink=item.get("permalink", ""),
                        )
                    )
                except Exception as exc:
                    log.warning(
                        "[instagram] skipping media item %s for %s: %s",
                        item.get("id"), comp.name, exc,
                    )

        return records
