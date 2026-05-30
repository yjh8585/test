"""Optional Claude-powered creative summary of competitor content.

The anthropic package is imported lazily inside the function so the module
loads successfully even when the package is not installed.  This keeps the
analysis layer usable in environments where only the free-tier analytics are
needed.
"""
from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Secrets, Settings
    from ..storage import Storage

logger = logging.getLogger(__name__)


def summarize_creative(
    storage: Storage,
    settings: Settings,
    secrets: Secrets,
) -> dict | None:
    """Ask Claude to identify main creative themes across all competitor content.

    Returns:
        None  – if LLM is disabled or the API key is missing.
        {"summary": <text>}  – on success; text is in Korean, 3-5 bullet insights.
        {"error": <message>} – if the API call fails for any reason.
    """
    # Respect the feature-flag and secrets guard so the function is safe to call
    # unconditionally from report generation without side effects.
    if not settings.enable_llm:
        return None
    if not secrets.anthropic_api_key:
        warnings.warn(
            "LLM summary requested (enable_llm=true) but ANTHROPIC_API_KEY is not set.",
            stacklevel=2,
        )
        return None

    # --- Gather recent content -------------------------------------------------
    ig_rows = storage.query(
        """
        SELECT competitor, caption
        FROM ig_media
        WHERE caption IS NOT NULL AND caption != ''
        ORDER BY timestamp DESC
        LIMIT 30
        """
    )

    yt_rows = storage.query(
        """
        SELECT competitor, title
        FROM yt_videos
        WHERE title IS NOT NULL AND title != ''
        ORDER BY published_at DESC
        LIMIT 30
        """
    )

    if not ig_rows and not yt_rows:
        logger.warning("summarize_creative: no content in DB yet, skipping LLM call.")
        return None

    # --- Build prompt ----------------------------------------------------------
    ig_lines = "\n".join(
        f"  [{r['competitor']} IG] {(r['caption'] or '')[:200]}"
        for r in ig_rows
    )
    yt_lines = "\n".join(
        f"  [{r['competitor']} YT] {r['title']}"
        for r in yt_rows
    )

    prompt = (
        "아래는 경쟁사들의 최근 소셜 미디어 콘텐츠 목록입니다.\n\n"
        "Instagram 캡션:\n"
        f"{ig_lines or '(데이터 없음)'}\n\n"
        "YouTube 동영상 제목:\n"
        f"{yt_lines or '(데이터 없음)'}\n\n"
        "위 콘텐츠를 분석하여 다음 항목을 한국어로 3~5개의 불릿 포인트로 정리해 주세요:\n"
        "1. 주요 크리에이티브 테마\n"
        "2. 전반적인 톤 앤 매너\n"
        "3. 눈에 띄는 캠페인 또는 프로모션\n"
        "간결하고 마케터가 바로 활용할 수 있는 인사이트 위주로 작성해 주세요."
    )

    # --- Call Claude (lazily imported) ----------------------------------------
    try:
        from anthropic import Anthropic  # noqa: PLC0415 — intentional lazy import

        client = Anthropic(api_key=secrets.anthropic_api_key)
        msg = client.messages.create(
            model=settings.llm_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text: str = msg.content[0].text
        return {"summary": text}

    except Exception as exc:  # noqa: BLE001 — intentional broad catch for robustness
        logger.warning("summarize_creative: API call failed — %s", exc)
        return {"error": str(exc)}
