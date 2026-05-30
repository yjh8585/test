"""Naver DataLab search-trend collector.

DataLab returns a *relative* search-volume index (0–100) for named keyword
groups over a time window. We always request the last 90 days at weekly
granularity so trending charts are consistent across runs.

A single POST request covers all keyword groups at once, which is more
efficient than the per-keyword approach used by NaverSearchCollector.
Keyword groups are defined in config.yaml under naver.datalab_keyword_groups.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from ..config import CompetitorConfig
from ..models import NaverDataLabPoint
from .base import Collector

log = logging.getLogger(__name__)

_URL = "https://openapi.naver.com/v1/datalab/search"
_TIMEOUT = 20
_TREND_DAYS = 90


class NaverDataLabCollector(Collector):
    name = "naver_datalab"

    def is_available(self) -> bool:
        # Reuses the same Naver credentials as NaverSearchCollector.
        return bool(self.secrets.naver_client_id and self.secrets.naver_client_secret)

    def collect(self, competitors: list[CompetitorConfig]) -> list[object]:
        keyword_groups = self.settings.naver_datalab_keyword_groups
        if not keyword_groups:
            log.debug("[naver_datalab] no keyword groups configured, nothing to collect")
            return []

        client_id = self.secrets.naver_client_id
        client_secret = self.secrets.naver_client_secret
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "Content-Type": "application/json",
        }

        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=_TREND_DAYS)
        payload = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": today.strftime("%Y-%m-%d"),
            "timeUnit": "week",
            "keywordGroups": keyword_groups,
        }

        records: list[object] = []
        try:
            resp = requests.post(
                _URL,
                headers=headers,  # type: ignore[arg-type]
                json=payload,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.warning("[naver_datalab] request failed: %s", exc)
            return records

        for group in data.get("results", []):
            group_name: str = group.get("title", "")
            for point in group.get("data", []):
                try:
                    records.append(
                        NaverDataLabPoint(
                            keyword_group=group_name,
                            period=point["period"],
                            ratio=float(point["ratio"]),
                        )
                    )
                except Exception as exc:
                    log.warning(
                        "[naver_datalab] skipping data point in group %r: %s",
                        group_name, exc,
                    )

        return records
