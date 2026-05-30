"""Resolve YouTube channel IDs for competitors via the YouTube Data API v3.

Because UC… channel IDs can't be reliably hardcoded (brands rename handles,
open new channels, etc.), this tool does a live API search and prints
copy-pasteable suggestions for config.yaml.

Usage:
    python -m competitor_monitor.tools.resolve_channels [--config config.yaml] [--env .env] [--max 3]
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

import requests

logger = logging.getLogger(__name__)

# A real YouTube channel ID is always exactly 24 chars, starts with 'UC'.
_PLACEHOLDER_MARKER = "x"  # placeholder IDs in config.example.yaml contain 'x'


# --------------------------------------------------------------------------- #
# API helpers
# --------------------------------------------------------------------------- #

def search_channels(api_key: str, query: str, max_results: int = 3) -> list[dict]:
    """Search YouTube for channels matching *query* and return slim result dicts.

    Each dict has: channel_id, title, description.
    Raises RuntimeError (with the API's own message when available) on HTTP error.
    """
    url = "https://www.googleapis.com/youtube/v3/search"
    params: dict[str, Any] = {
        "part": "snippet",
        "type": "channel",
        "q": query,
        "maxResults": max_results,
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=20)

    if not resp.ok:
        # Surface the API's own error message so the caller knows WHY it failed.
        try:
            api_msg = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            api_msg = resp.text
        raise RuntimeError(
            f"YouTube search API returned {resp.status_code}: {api_msg}"
        )

    items = resp.json().get("items", [])
    results = []
    for item in items:
        snippet = item.get("snippet", {})
        channel_id = item.get("id", {}).get("channelId", "")
        results.append(
            {
                "channel_id": channel_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
            }
        )
    return results


def resolve_handle(api_key: str, handle: str) -> dict | None:
    """Try to resolve a YouTube @handle (or plain username) to a channel ID.

    Returns {channel_id, title} for the first match, or None if not found.
    A leading '@' is stripped automatically.
    """
    # Strip leading '@' — the API's forHandle param doesn't want it.
    handle = handle.lstrip("@")

    url = "https://www.googleapis.com/youtube/v3/channels"
    params: dict[str, Any] = {
        "part": "snippet",
        "forHandle": handle,
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=20)

    if not resp.ok:
        try:
            api_msg = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            api_msg = resp.text
        logger.warning("resolve_handle(%s) HTTP %s: %s", handle, resp.status_code, api_msg)
        return None

    items = resp.json().get("items", [])
    if not items:
        return None

    first = items[0]
    return {
        "channel_id": first.get("id", ""),
        "title": first.get("snippet", {}).get("title", ""),
    }


# --------------------------------------------------------------------------- #
# Batch resolver
# --------------------------------------------------------------------------- #

def _is_placeholder(channel_id: str | None) -> bool:
    """Return True when the channel_id looks like a config placeholder.

    Real IDs start with 'UC' and are exactly 24 characters; any ID that
    fails those criteria (or contains placeholder 'x' chars mid-string) is
    treated as unresolved.
    """
    if not channel_id:
        return True
    if not (channel_id.startswith("UC") and len(channel_id) == 24):
        return True
    # config.example.yaml uses "UCxxxxxxxxxxxxxxxxxxxxxx" — if non-UC chars
    # are all the same placeholder char, it's clearly not real.
    if _PLACEHOLDER_MARKER in channel_id[2:]:
        return True
    return False


def resolve_for_competitors(settings, secrets, max_results: int = 3) -> dict:
    """Return search suggestions for every competitor that lacks a real channel ID.

    Returns {competitor_name: [suggestion_dicts]} where each suggestion_dict
    has channel_id, title, description.  Competitors that already have a valid
    UC… id are skipped (they don't need resolution).
    """
    api_key = secrets.youtube_api_key  # caller must check this is not None
    results: dict[str, list[dict]] = {}

    for competitor in settings.competitors:
        # Skip if we already have a real, non-placeholder channel ID.
        if not _is_placeholder(competitor.youtube_channel_id):
            logger.info(
                "Skipping %s — channel ID already set (%s)",
                competitor.name,
                competitor.youtube_channel_id,
            )
            continue

        query = competitor.name  # brand name is the most reliable search term
        try:
            suggestions = search_channels(api_key, query, max_results=max_results)
            results[competitor.name] = suggestions
        except Exception as exc:
            logger.warning(
                "Could not fetch suggestions for %r: %s", competitor.name, exc
            )
            results[competitor.name] = []  # include entry so report shows it

    return results


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    """Parse args, load config/secrets, run the resolver, print a readable report."""
    parser = argparse.ArgumentParser(
        prog="python -m competitor_monitor.tools.resolve_channels",
        description=(
            "Look up YouTube channel IDs for competitors via the YouTube Data API v3 "
            "and print suggestions to paste into config.yaml."
        ),
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        metavar="PATH",
        help="Path to the config YAML file (default: config.yaml).",
    )
    parser.add_argument(
        "--env",
        default=".env",
        metavar="PATH",
        help="Path to the .env secrets file (default: .env).",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=3,
        metavar="N",
        help="Maximum number of channel suggestions per competitor (default: 3).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    # Import here (not at module top) so the module can be imported cheaply in tests.
    from competitor_monitor.config import load_settings, load_secrets

    settings = load_settings(args.config)
    secrets = load_secrets(args.env)

    if not secrets.youtube_api_key:
        print(
            "ERROR: YOUTUBE_API_KEY is not set.\n"
            "\n"
            "Set it in your .env file or as an environment variable:\n"
            "    YOUTUBE_API_KEY=AIza...\n"
            "\n"
            "See docs/API_KEYS.md for instructions on obtaining a YouTube Data API v3 key.\n"
            "Once set, re-run:\n"
            f"    python -m competitor_monitor.tools.resolve_channels --config {args.config}",
            file=sys.stderr,
        )
        return 1

    suggestions = resolve_for_competitors(settings, secrets, max_results=args.max)

    if not suggestions:
        print("All competitors already have valid YouTube channel IDs. Nothing to resolve.")
        return 0

    print("\n=== YouTube Channel ID Suggestions ===\n")
    for name, candidates in suggestions.items():
        print(f"Competitor: {name}")
        if not candidates:
            print("  (no suggestions — check the API key or query manually on YouTube)")
        else:
            for i, c in enumerate(candidates, start=1):
                desc_preview = (c["description"] or "")[:100]
                print(
                    f"  [{i}] {c['title']}  ->  youtube_channel_id: \"{c['channel_id']}\"\n"
                    f"       {desc_preview}"
                )
        print()

    print(
        "Paste the chosen UC… id into config.yaml under the matching competitor,\n"
        "then re-run the pipeline:\n"
        "    python -m competitor_monitor.cli run"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
