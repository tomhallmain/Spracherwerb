"""Structured lesson/question format the LLM authors for ConceptualLearning.

The LLM writes the whole lesson -- concept, explanation, examples, and its own
multiple-choice questions -- as one JSON object; this module is the contract
that output must satisfy. Anything malformed is dropped per item (a bad
question doesn't discard the good ones), so the module only ever grades
questions whose correct answer is unambiguous and machine-checkable.

Expected shape::

    {
      "concept": "verb-second word order",
      "explanation": "...",
      "examples": [{"text": "...", "note": "..."}],
      "questions": [{"prompt": "...", "options": ["...", "..."],
                     "correct": "<exact text of the correct option>",
                     "explanation": "..."}]
    }

`correct` is the option's text, not its index, so the order can be shuffled
here without trusting the model's numbering.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

MIN_OPTIONS = 2
MAX_OPTIONS = 6


@dataclass
class ConceptExample:
    text: str
    note: str = ""
    saved_phrases: List[str] = field(default_factory=list)


@dataclass
class ConceptQuestion:
    prompt: str
    options: List[str]
    correct_index: int
    explanation: str = ""
    saved_phrases: List[str] = field(default_factory=list)

    @property
    def correct_option(self) -> str:
        return self.options[self.correct_index]

    def match_answer(self, user_text: str) -> Optional[int]:
        """Resolve a reply to an option index: its 1-based number (optionally
        followed by ")" or "."), or the option's exact text. None if neither."""
        reply = (user_text or "").strip()
        number = reply.rstrip(").").strip()
        if number.isdigit():
            index = int(number) - 1
            return index if 0 <= index < len(self.options) else None
        folded = reply.casefold()
        for index, option in enumerate(self.options):
            if option.casefold() == folded:
                return index
        return None


@dataclass
class ConceptLesson:
    concept: str
    explanation: str
    examples: List[ConceptExample]
    questions: List[ConceptQuestion]


def parse_concept_lesson(
    text: str,
    rng: Optional[random.Random] = None,
) -> Optional[ConceptLesson]:
    """Parse and validate an LLM lesson response. None if there's no usable
    JSON object or it has neither an explanation nor any valid question."""
    data = _extract_json_object(text)
    if data is None:
        return None
    rng = rng or random.Random()

    explanation = _clean_str(data.get("explanation"))
    examples = [e for e in map(_parse_example, _as_list(data.get("examples"))) if e]
    questions = [q for q in (_parse_question(item, rng) for item in _as_list(data.get("questions"))) if q]
    if not explanation and not questions:
        return None
    return ConceptLesson(
        concept=_clean_str(data.get("concept")),
        explanation=explanation,
        examples=examples,
        questions=questions,
    )


def _extract_json_object(text: str) -> Optional[dict]:
    # Models can wrap JSON in code fences or add a sentence before/after it;
    # the outermost braces are taken as the object.
    text = text or ""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        logger.warning(f"Concept lesson was not valid JSON: {e}")
        return None
    return data if isinstance(data, dict) else None


def _parse_example(item: Any) -> Optional[ConceptExample]:
    if isinstance(item, str):
        item = {"text": item}
    if not isinstance(item, dict):
        return None
    text = _clean_str(item.get("text"))
    if not text:
        return None
    return ConceptExample(text=text, note=_clean_str(item.get("note")))


def _parse_question(item: Any, rng: random.Random) -> Optional[ConceptQuestion]:
    if not isinstance(item, dict):
        return None
    prompt = _clean_str(item.get("prompt"))
    options = [_clean_str(option) for option in _as_list(item.get("options"))]
    correct = _clean_str(item.get("correct"))
    if not prompt or not correct or any(not option for option in options):
        return None
    folded = [option.casefold() for option in options]
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS or len(set(folded)) != len(folded):
        return None
    if correct.casefold() not in folded:
        return None

    rng.shuffle(options)
    correct_index = [option.casefold() for option in options].index(correct.casefold())
    return ConceptQuestion(
        prompt=prompt,
        options=options,
        correct_index=correct_index,
        explanation=_clean_str(item.get("explanation")),
    )


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _clean_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
