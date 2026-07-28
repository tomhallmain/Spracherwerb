"""Tests for the shared dictionary-hint helper (used by GrammarPractice and WritingPractice)."""

from Spracherwerb.dictionary_hint import pick_vocabulary_hint


class FakeEntry:
    def __init__(self, to_pos=None, from_pos=None):
        self.to_pos = to_pos
        self.from_pos = from_pos


class FakeSection:
    def __init__(self, entries):
        self.entries = entries


class FakeResult:
    def __init__(self, sections):
        self.sections = sections


class FakeVocabularyPool:
    def __init__(self, entries):
        self._entries = entries

    def get_review_candidates(self, source_language, target_language, limit=5):
        return list(self._entries[:limit])


class FakeWordReference:
    def __init__(self, results_by_word=None, fail_for=None):
        self._results_by_word = results_by_word or {}
        self._fail_for = fail_for or set()
        self.lookups = []

    def lookup(self, word, from_language, to_language):
        self.lookups.append(word)
        if word in self._fail_for:
            raise Exception("network error")
        return self._results_by_word.get(word)


class FakeServices:
    def __init__(self, vocabulary_pool, word_reference, source_language="en", target_language="de"):
        self.vocabulary_pool = vocabulary_pool
        self.word_reference = word_reference
        self._source_language = source_language
        self._target_language = target_language

    def language_pair(self):
        return self._source_language, self._target_language


class TestPickVocabularyHint:
    def test_returns_none_when_word_reference_is_unavailable(self):
        pool = FakeVocabularyPool([{"source_text": "dog", "translated_text": "Hund"}])
        services = FakeServices(pool, word_reference=None)

        assert pick_vocabulary_hint(services) is None

    def test_returns_none_when_pool_is_empty(self):
        pool = FakeVocabularyPool([])
        services = FakeServices(pool, word_reference=FakeWordReference())

        assert pick_vocabulary_hint(services) is None

    def test_skips_words_with_no_part_of_speech_and_uses_the_next_one(self):
        entries = [
            {"source_text": "quickly", "translated_text": "schnell"},
            {"source_text": "dog", "translated_text": "Hund"},
        ]
        pool = FakeVocabularyPool(entries)
        word_reference = FakeWordReference(results_by_word={
            "quickly": FakeResult([FakeSection([FakeEntry(to_pos=None, from_pos=None)])]),
            "dog": FakeResult([FakeSection([FakeEntry(to_pos="noun")])]),
        })
        services = FakeServices(pool, word_reference)

        hint = pick_vocabulary_hint(services)

        assert hint == "Hund (noun)"
        assert word_reference.lookups == ["quickly", "dog"]

    def test_falls_back_to_from_pos_when_to_pos_is_missing(self):
        pool = FakeVocabularyPool([{"source_text": "dog", "translated_text": "Hund"}])
        word_reference = FakeWordReference(results_by_word={
            "dog": FakeResult([FakeSection([FakeEntry(to_pos=None, from_pos="noun")])]),
        })
        services = FakeServices(pool, word_reference)

        assert pick_vocabulary_hint(services) == "Hund (noun)"

    def test_returns_none_when_no_word_has_a_part_of_speech(self):
        pool = FakeVocabularyPool([{"source_text": "dog", "translated_text": "Hund"}])
        word_reference = FakeWordReference(results_by_word={"dog": None})
        services = FakeServices(pool, word_reference)

        assert pick_vocabulary_hint(services) is None

    def test_lookup_failure_is_skipped_not_raised(self):
        entries = [
            {"source_text": "dog", "translated_text": "Hund"},
            {"source_text": "cat", "translated_text": "Katze"},
        ]
        pool = FakeVocabularyPool(entries)
        word_reference = FakeWordReference(
            fail_for={"dog"},
            results_by_word={"cat": FakeResult([FakeSection([FakeEntry(to_pos="noun")])])},
        )
        services = FakeServices(pool, word_reference)

        assert pick_vocabulary_hint(services) == "Katze (noun)"
