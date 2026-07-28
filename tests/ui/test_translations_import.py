import pytest

from utils import translation_import


class TestSplitTranslationLine:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("der Hund - the dog", ("der Hund", "the dog")),
            ("der Hund- the dog", ("der Hund", "the dog")),
            ("der Hund -the dog", ("der Hund", "the dog")),
            ("  die Katze  -  cat, feline  ", ("die Katze", "cat, feline")),
        ],
    )
    def test_splits_target_and_source(self, line, expected):
        assert translation_import.split_translation_line(line) == expected

    @pytest.mark.parametrize(
        "line",
        [
            "",
            "   ",
            "no separator here",
            "word-word",
        ],
    )
    def test_returns_none_for_unsplitable_lines(self, line):
        assert translation_import.split_translation_line(line) is None


class TestMergeSourceTexts:
    def test_merges_comma_parts_uniquely(self):
        merged = translation_import.merge_source_texts(
            "dog, canine",
            "canine, puppy",
        )
        assert merged == "dog, canine, puppy"

    def test_deduplicates_case_insensitively(self):
        merged = translation_import.merge_source_texts("Dog", "dog")
        assert merged == "Dog"

    def test_strips_extra_spaces(self):
        merged = translation_import.merge_source_texts(
            "dog ,  canine",
            " puppy ",
        )
        assert merged == "dog, canine, puppy"


class TestMergeRowsByTarget:
    def test_collapses_duplicate_targets_without_articles(self):
        rows = [
            {'source_text': 'to go', 'translated_text': 'gehen'},
            {'source_text': 'walk', 'translated_text': 'gehen'},
        ]

        merged = translation_import.merge_rows_by_target(rows)

        assert len(merged) == 1
        assert merged[0]['translated_text'] == 'gehen'
        assert 'target_article' not in merged[0]
        assert merged[0]['source_text'] == 'to go, walk'

    def test_collapses_duplicate_targets_in_import_batch(self):
        rows = [
            {
                'source_text': 'dog',
                'translated_text': 'Hund',
                'target_article': 'der',
                'notes': '',
            },
            {
                'source_text': 'canine, puppy',
                'translated_text': 'Hund',
                'target_article': 'der',
                'notes': 'note',
            },
        ]

        merged = translation_import.merge_rows_by_target(rows)

        assert len(merged) == 1
        assert merged[0]['translated_text'] == 'Hund'
        assert merged[0]['target_article'] == 'der'
        assert merged[0]['source_text'] == 'dog, canine, puppy'
        assert merged[0]['notes'] == 'note'

    def test_keeps_different_articles_separate(self):
        rows = [
            {
                'source_text': 'dog',
                'translated_text': 'Hund',
                'target_article': 'der',
            },
            {
                'source_text': 'cat',
                'translated_text': 'Hund',
                'target_article': 'die',
            },
        ]

        merged = translation_import.merge_rows_by_target(rows)

        assert len(merged) == 2


class TestTargetArticle:
    @pytest.mark.parametrize(
        ("text", "language", "expected"),
        [
            ("der Hund", "de", ("der", "Hund")),
            ("Die Katze", "de", ("Die", "Katze")),
            ("l'homme", "fr", ("l'", "homme")),
            ("the dog", "en", ("", "the dog")),
            ("Hund", "de", ("", "Hund")),
            ("gehen", "de", ("", "gehen")),
            ("schön", "de", ("", "schön")),
            ("rapidement", "fr", ("", "rapidement")),
            ("hablar", "es", ("", "hablar")),
            ("die", "de", ("", "die")),
        ],
    )
    def test_extract_target_article(self, text, language, expected):
        assert translation_import.extract_target_article(text, language) == expected

    def test_format_target_for_display_without_article(self):
        assert translation_import.format_target_for_display(
            "gehen", "", "de") == "gehen"

    def test_format_target_for_display(self):
        display = translation_import.format_target_for_display(
            "Hund", "der", "de")
        assert display == "der Hund"

    def test_normalize_splits_article_for_storage(self):
        t = {
            'translated_text': 'der Hund',
            'target_language': 'de',
        }
        translation_import.normalize_target_article_fields(t, 'de')
        assert t['target_article'] == 'der'
        assert t['translated_text'] == 'Hund'

    @pytest.mark.parametrize(
        "text",
        ["gehen", "schön", "schnell", "parler"],
    )
    def test_normalize_leaves_non_noun_entries_without_article(self, text):
        t = {
            'translated_text': text,
            'target_language': 'de',
        }
        translation_import.normalize_target_article_fields(t, 'de')
        assert 'target_article' not in t
        assert t['translated_text'] == text

    def test_normalize_clears_article_for_english_target(self):
        t = {
            'translated_text': 'the dog',
            'target_article': 'the',
            'target_language': 'en',
        }
        translation_import.normalize_target_article_fields(t, 'en')
        assert 'target_article' not in t
        assert t['translated_text'] == 'the dog'


class TestIndexBareNounFallback:
    def test_indexes_article_less_capitalized_row(self):
        existing = [{'translated_text': 'Hupe', 'source_text': 'horn'}]

        by_bare_noun = translation_import.index_bare_noun_fallback(existing, 'de')

        assert by_bare_noun == {'hupe': existing[0]}

    def test_ignores_row_that_already_has_an_article(self):
        existing = [
            {'translated_text': 'Hupe', 'source_text': 'horn', 'target_article': 'die'},
        ]

        by_bare_noun = translation_import.index_bare_noun_fallback(existing, 'de')

        assert by_bare_noun == {}

    def test_ignores_lowercase_entries(self):
        existing = [{'translated_text': 'gehen', 'source_text': 'to go'}]

        by_bare_noun = translation_import.index_bare_noun_fallback(existing, 'de')

        assert by_bare_noun == {}

    def test_empty_for_languages_without_target_articles(self):
        existing = [{'translated_text': 'Hupe', 'source_text': 'horn'}]

        by_bare_noun = translation_import.index_bare_noun_fallback(existing, 'en')

        assert by_bare_noun == {}

    def test_keeps_first_row_when_multiple_share_a_bare_noun(self):
        first = {'translated_text': 'Hupe', 'source_text': 'horn'}
        second = {'translated_text': 'Hupe', 'source_text': 'car horn'}

        by_bare_noun = translation_import.index_bare_noun_fallback([first, second], 'de')

        assert by_bare_noun == {'hupe': first}
