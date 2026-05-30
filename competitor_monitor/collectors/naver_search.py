"""Naver Search Open API collector — buzz-volume counts per keyword × source.

The Naver Search API returns the *total* number of matching documents for a
query in a given vertical (blog, cafearticle, news, …). We use display=1 to
minimise payload size — we only need the total count, not the actual results.

One request is made per (keyword, source) pair. Competitors without keywords
are skipped; sources are configured globally in settings.naver_search_sources.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

import requests

from ..config import CompetitorConfig
from ..models import NaverSearchCount
from .base import Collector

log = logging.getLogger(__name__)

_BASE = "https://openapi.naver.com/v1/search/{source}.json"
_TIMEOUT = 20


class NaverSearchCollector(Collector):
    name = "naver_search"

    def is_available(self) -> bool:
        return bool(self.secrets.naver_client_id and self.secrets.naver_client_secret)

    def collect(self, competitors: list[CompetitorConfig]) -> list[object]:
        client_id = self.secrets.naver_client_id
        client_secret = self.secrets.naver_client_secret
        sources = self.settings.naver_search_sources
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        }
        records: list[object] = []

        for comp in competitors:
            for keyword in comp.keywords:
                for source in sources:
                    url = _BASE.format(source=source)
                    try:
                        resp = requests.get(
                            url,
                            params={"query": keyword, "display": 1},
                            headers=headers,  # type: ignore[arg-type]
                            timeout=_TIMEOUT,
                        )
                        resp.raise_for_status()
                        data = resp.json()
                    except Exception as exc:
                        log.warning(
                            "[naver_search] failed for keyword=%r source=%s: %s",
                            keyword, source, exc,
                        )
                        continue

                    try:
                        records.append(
                            NaverSearchCount(
                                keyword=keyword,
                                source=source,
                                total=int(data.get("total", 0)),
                            )
                        )
                    except Exception as exc:
                        log.warning(
                            "[naver_search] could not build NaverSearchCount "
                            "keyword=%r source=%s: %s",
                            keyword, source, exc,
                        )

        return records
