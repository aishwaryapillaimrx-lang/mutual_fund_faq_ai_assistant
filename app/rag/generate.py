"""Claude call with Groq fallback: answer only from retrieved chunks."""

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


def _try_anthropic(question: str, chunks: Sequence[RetrievedChunk]) -> str | None:
    """Try to generate answer using Anthropic (Claude).
    
    Returns the answer text on success, or None if the API fails.
    Raises GenerationError only for unexpected errors.
    """
    if not config.ANTHROPIC_API_KEY:
        logger.debug("ANTHROPIC_API_KEY is not set, skipping Anthropic")
        return None
    
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
        logger.warning("Anthropic API call failed (%s), will try Groq fallback", type(exc).__name__)
        return None

    if response.stop_reason != "end_turn":
        logger.warning("Anthropic stopped early (%s), will try Groq fallback", response.stop_reason)
        return None
    
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        logger.warning("Anthropic returned empty output, will try Groq fallback")
        return None
    
    return text


def _try_groq(question: str, chunks: Sequence[RetrievedChunk]) -> str | None:
    """Try to generate answer using Groq as fallback.
    
    Returns the answer text on success, or None if the API fails.
    """
    if not config.GROQ_API_KEY:
        logger.debug("GROQ_API_KEY is not set, cannot use Groq fallback")
        return None
    
    try:
        from groq import Groq
    except ImportError:
        logger.error("groq library not installed, cannot use Groq fallback")
        return None
    
    client = Groq(
        api_key=config.GROQ_API_KEY,
        timeout=config.LLM_TIMEOUT_SECONDS,
    )
    try:
        response = client.chat.completions.create(
            model=config.GROQ_CHAT_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(question, chunks)}],
        )
    except Exception as exc:  # catch all Groq exceptions
        logger.error("Groq API call failed: %s", type(exc).__name__)
        return None

    if not response.choices:
        logger.error("Groq returned no choices")
        return None
    
    text = response.choices[0].message.content
    if isinstance(text, str):
        text = text.strip()
    
    if not text:
        logger.error("Groq returned empty output")
        return None
    
    return text


def generate_answer(question: str, chunks: Sequence[RetrievedChunk]) -> str:
    if config.ANTHROPIC_API_KEY:
        try:
            client = anthropic.Anthropic(
                api_key=config.ANTHROPIC_API_KEY,
                timeout=config.LLM_TIMEOUT_SECONDS,
                max_retries=1,
            )
            response = client.messages.create(
                model=config.CHAT_MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_message(question, chunks)}],
            )
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            if text:
                return text
        except Exception:
            pass

    if config.GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=config.GROQ_API_KEY, timeout=config.LLM_TIMEOUT_SECONDS)
            response = client.chat.completions.create(
                model=config.GROQ_CHAT_MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_message(question, chunks)}],
            )
            text = response.choices[0].message.content
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception:
            pass

    raise GenerationError("all providers exhausted")