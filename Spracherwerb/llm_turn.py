"""Shared best-effort LLM call wrapper for activity modules.

Every call is wrapped so a failure (Ollama not running, timeout, malformed
response) degrades to None rather than raising -- callers treat None as
"LLM unavailable this turn" and fall back to a canned message, matching the
project's established pattern for optional external services (SD Runner,
TTS).
"""

import logging
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def ask_llm(
    llm: Any,
    query: str,
    system_prompt: Optional[str] = None,
    context: Any = None,
    timeout: float = 60.0,
) -> Optional[Tuple[str, Any]]:
    """Ask `llm` a question. Returns (response_text, new_context), or None on failure."""
    if llm is None:
        return None
    try:
        result = llm.generate_response(
            query, timeout=timeout, context=context, system_prompt=system_prompt)
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return None
    text = (result.response or "").strip()
    if not text:
        return None
    return text, result.context
