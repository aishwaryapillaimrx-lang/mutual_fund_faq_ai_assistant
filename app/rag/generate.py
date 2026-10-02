"""Claude call: answer only from retrieved chunks."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import anthropic

from app import config
from app.rag.prompt import SYSTEM_PROMPT, build_user_message
from app.rag.retrieve import RetrievedChunk

logger = logging.getLogger(__name__)

MAX_TOKENS = 2000  # thinking tokens count toward this; answers are tiny


class GenerationError(Exception):
    """Timeout, API failure, refusal, or empty output. Caller shows the busy message."""


def generate_answer(question: str, chunks: Sequence[RetrievedChunk]) -> str:
    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set")
        raise GenerationError("no api key")
    client = anthropic.Anthropic(
        api_key=config.ANTHROPIC_API_KEY,
        timeout=config.LLM_TIMEOUT_SECONDS,
        max_retries=1,
    )
    try:
        response = client.messages.create(
            model=config.CHAT_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": build_user_message(question, chunks)}],
        )
    except anthropic.APIError as exc:  # timeouts, connection, status errors
        logger.error("LLM call failed: %s", type(exc).__name__)
        raise GenerationError(type(exc).__name__) from exc

    if response.stop_reason != "end_turn":
        logger.error("LLM stopped early: %s", response.stop_reason)
        raise GenerationError(str(response.stop_reason))
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise GenerationError("empty output")
    return text
