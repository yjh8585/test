"""Configuration loading.

Two sources of truth:
  * config.yaml  -> WHAT to monitor (competitors, keywords, sources, options).
  * .env         -> SECRETS (API keys). Never commit this file.

Load order for secrets: real OS environment first, then a .env file (so CI
secrets and local .env both work).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:  # python-dotenv is optional at import time
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


# --------------------------------------------------------------------------- #
# Typed config objects
# --------------------------------------------------------------------------- #
@dataclass
class CompetitorConfig:
    name: str
    instagram_username: str | None = None
    youtube_channel_id: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class Settings:
    competitors: list[CompetitorConfig]
    naver_search_sources: list[str]
    naver_datalab_keyword_groups: list[dict[str, Any]]
    ig_user_id: str | None
    enable_llm: bool
    llm_model: str
    db_path: str
    report_dir: str
    raw: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Secrets
# --------------------------------------------------------------------------- #
class Secrets:
    """Lazy accessor over environment variables.

    Missing keys return None rather than raising, so a partially-configured
    deployment can still run the collectors it *does* have keys for.
    """

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self._env = env if env is not None else dict(os.environ)

    def get(self, key: str) -> str | None:
        val = self._env.get(key)
        return val.strip() if val else None

    # Named accessors (documented in .env.example)
    @property
    def meta_access_token(self) -> str | None:
        return self.get("META_ACCESS_TOKEN")

    @property
    def youtube_api_key(self) -> str | None:
        return self.get("YOUTUBE_API_KEY")

    @property
    def naver_client_id(self) -> str | None:
        return self.get("NAVER_CLIENT_ID")

    @property
    def naver_client_secret(self) -> str | None:
        return self.get("NAVER_CLIENT_SECRET")

    @property
    def anthropic_api_key(self) -> str | None:
        return self.get("ANTHROPIC_API_KEY")


def load_secrets(env_file: str | os.PathLike[str] | None = ".env") -> Secrets:
    if load_dotenv and env_file and Path(env_file).exists():
        load_dotenv(env_file)
    return Secrets()


# --------------------------------------------------------------------------- #
# Settings loader
# --------------------------------------------------------------------------- #
def load_settings(path: str | os.PathLike[str] = "config.yaml") -> Settings:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    competitors = [
        CompetitorConfig(
            name=c["name"],
            instagram_username=c.get("instagram_username"),
            youtube_channel_id=c.get("youtube_channel_id"),
            keywords=list(c.get("keywords", [])),
        )
        for c in data.get("competitors", [])
    ]

    naver = data.get("naver", {})
    analysis = data.get("analysis", {})
    storage = data.get("storage", {})
    reporting = data.get("reporting", {})

    return Settings(
        competitors=competitors,
        naver_search_sources=list(naver.get("search_sources", ["blog", "cafearticle", "news"])),
        naver_datalab_keyword_groups=list(naver.get("datalab_keyword_groups", [])),
        ig_user_id=data.get("instagram", {}).get("ig_user_id"),
        enable_llm=bool(analysis.get("llm", {}).get("enabled", False)),
        llm_model=analysis.get("llm", {}).get("model", "claude-sonnet-4-6"),
        db_path=storage.get("db_path", "data/monitor.db"),
        report_dir=reporting.get("output_dir", "reports"),
        raw=data,
    )
