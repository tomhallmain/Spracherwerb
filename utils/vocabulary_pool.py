"""Shared vocabulary access for learning modules."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from utils.config import config
from utils.logging_setup import get_logger

from Spracherwerb.learning_memory import LearningMemory

logger = get_logger(__name__)


class VocabularyPool:
    """Read and update candidate words from translations storage and memory."""

    def __init__(self, data_manager=None):
        if data_manager is None:
            from utils.translation_data_manager import TranslationDataManager

            data_manager = TranslationDataManager()
        self.data_manager = data_manager

    def get_entries(
        self,
        source_language: str,
        target_language: str,
    ) -> List[Dict[str, Any]]:
        entries = self.data_manager.get_language_pair(source_language, target_language)
        return list(entries or [])

    def get_review_candidates(
        self,
        source_language: str,
        target_language: str,
        limit: int = 20,
        exclude: Optional[List[str]] = None,
        shuffle: bool = True,
    ) -> List[Dict[str, Any]]:
        """Return translation rows suitable for review activities."""
        exclude_set = {value.lower() for value in (exclude or [])}
        entries = self.get_entries(source_language, target_language)
        candidates = []
        for entry in entries:
            source_text = str(entry.get("source_text", "")).strip()
            translated_text = str(entry.get("translated_text", "")).strip()
            if not source_text or not translated_text:
                continue
            if source_text.lower() in exclude_set or translated_text.lower() in exclude_set:
                continue
            candidates.append(entry)
        if shuffle:
            random.shuffle(candidates)
        return candidates[:limit]

    def record_word_result(
        self,
        target_language: str,
        word: str,
        *,
        outcome: str = "reviewed",
    ) -> None:
        """Persist a lightweight outcome to learning memory."""
        normalized = word.strip()
        if not normalized:
            return
        if outcome in ("learned", "reviewed", "correct"):
            LearningMemory.update_vocabulary(target_language, normalized)
        logger.debug(
            "Recorded vocabulary outcome %s for %r (%s)",
            outcome,
            normalized,
            target_language,
        )

    def default_session_limit(self) -> int:
        return int(
            config.learning_config.get(
                "max_new_words_per_session",
                20,
            )
        )
