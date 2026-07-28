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


class TestCoerceStr:
    def test_none_becomes_empty_string(self):
        assert translation_import.coerce_str(None) == ''

    def test_strips_surrounding_whitespace(self):
        assert translation_import.coerce_str('  gehen  ') == 'gehen'

    def test_non_string_is_stringified(self):
        assert translation_import.coerce_str(5) == '5'


class TestPrimaryLanguageTag:
    @pytest.mark.parametrize(
        ("language_code", "expected"),
        [
            (None, ''),
            ('', ''),
            ('en', 'en'),
            ('en-US', 'en'),
            ('DE_de', 'de'),
            ('fr', 'fr'),
        ],
    )
    def test_extracts_primary_subtag(self, language_code, expected):
        assert translation_import.primary_language_tag(language_code) == expected


class TestLanguageUsesTargetArticles:
    @pytest.mark.parametrize(
        ("language_code", "expected"),
        [
            ('en', False),
            ('en-US', False),
            ('de', True),
            ('fr', True),
            ('es', True),
        ],
    )
    def test_only_english_is_excluded(self, language_code, expected):
        assert translation_import.language_uses_target_articles(language_code) == expected


class TestLinesToRowDicts:
    def test_converts_splitable_lines_and_skips_the_rest(self):
        lines = [
            'der Hund - the dog',
            'no separator here',
            '',
            'die Katze - cat, feline',
        ]

        rows = translation_import.lines_to_row_dicts(lines)

        assert rows == [
            {'translated_text': 'der Hund', 'source_text': 'the dog'},
            {'translated_text': 'die Katze', 'source_text': 'cat, feline'},
        ]

    def test_empty_input_yields_no_rows(self):
        assert translation_import.lines_to_row_dicts([]) == []


class TestExtractLineFromRow:
    def test_returns_the_single_non_empty_value(self):
        row = {'col1': 'gehen', 'col2': ''}
        assert translation_import.extract_line_from_row(row) == 'gehen'

    def test_returns_none_when_multiple_values_are_non_empty(self):
        row = {'col1': 'gehen', 'col2': 'walk'}
        assert translation_import.extract_line_from_row(row) is None

    def test_returns_none_for_non_dict_rows(self):
        assert translation_import.extract_line_from_row(['gehen']) is None
        assert translation_import.extract_line_from_row('gehen') is None

    def test_flattens_list_values(self):
        row = {'col1': ['', 'gehen', '']}
        assert translation_import.extract_line_from_row(row) == 'gehen'

    def test_returns_none_when_all_values_are_blank(self):
        row = {'col1': '', 'col2': '   '}
        assert translation_import.extract_line_from_row(row) is None


class TestRowsHaveTranslationFields:
    def test_true_when_a_row_has_source_or_translated_text(self):
        rows = [{'foo': 'bar'}, {'source_text': 'dog'}]
        assert translation_import.rows_have_translation_fields(
            rows, row_is_blank=lambda r: False) is True

    def test_false_when_no_row_has_translation_fields(self):
        rows = [{'foo': 'bar'}, {'baz': 'qux'}]
        assert translation_import.rows_have_translation_fields(
            rows, row_is_blank=lambda r: False) is False

    def test_blank_rows_are_skipped(self):
        rows = [{'source_text': 'dog'}]
        assert translation_import.rows_have_translation_fields(
            rows, row_is_blank=lambda r: True) is False

    def test_non_dict_rows_are_skipped(self):
        rows = ['not a row']
        assert translation_import.rows_have_translation_fields(
            rows, row_is_blank=lambda r: False) is False


class TestIndexExistingByTarget:
    def test_indexes_by_casefolded_article_and_text(self):
        existing = [
            {'translated_text': 'Hund', 'target_article': 'der', 'source_text': 'dog'},
        ]

        by_target = translation_import.index_existing_by_target(existing)

        assert by_target[('der', 'hund')] is existing[0]

    def test_merges_duplicate_targets_case_insensitively(self):
        first = {'translated_text': 'Hund', 'target_article': 'der', 'source_text': 'dog'}
        second = {'translated_text': 'hund', 'target_article': 'Der', 'source_text': 'canine'}

        by_target = translation_import.index_existing_by_target([first, second])

        assert len(by_target) == 1
        assert by_target[('der', 'hund')] is first
        assert first['source_text'] == 'dog, canine'

    def test_skips_rows_with_no_translated_text(self):
        existing = [{'translated_text': '', 'source_text': 'x'}]
        assert translation_import.index_existing_by_target(existing) == {}
