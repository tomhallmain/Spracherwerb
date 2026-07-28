import pytest

from utils import translation_listing


class TestComputeSearchMatches:
    def test_returns_all_indices_in_order_when_search_text_is_blank(self):
        translations = [
            {'source_text': 'dog', 'translated_text': 'Hund'},
            {'source_text': 'cat', 'translated_text': 'Katze'},
        ]
        assert translation_listing.compute_search_matches(translations, '') == [0, 1]
        assert translation_listing.compute_search_matches(translations, '   ') == [0, 1]

    def test_matches_source_text(self):
        translations = [
            {'source_text': 'dog', 'translated_text': 'Hund'},
            {'source_text': 'cat', 'translated_text': 'Katze'},
        ]
        assert translation_listing.compute_search_matches(translations, 'cat') == [1]

    def test_matches_notes(self):
        translations = [
            {'source_text': 'dog', 'translated_text': 'Hund', 'notes': 'informal'},
            {'source_text': 'cat', 'translated_text': 'Katze', 'notes': ''},
        ]
        assert translation_listing.compute_search_matches(translations, 'informal') == [0]

    def test_matches_displayed_target_including_article(self):
        translations = [
            {
                'source_text': 'dog',
                'translated_text': 'Hund',
                'target_article': 'der',
                'target_language': 'de',
            },
        ]
        assert translation_listing.compute_search_matches(translations, 'der hund') == [0]
        # Substring of the noun alone still matches within the displayed phrase.
        assert translation_listing.compute_search_matches(translations, 'hund') == [0]

    def test_is_case_insensitive(self):
        translations = [{'source_text': 'Dog', 'translated_text': 'Hund'}]
        assert translation_listing.compute_search_matches(translations, 'DOG') == [0]

    def test_no_match_returns_empty_list(self):
        translations = [{'source_text': 'dog', 'translated_text': 'Hund'}]
        assert translation_listing.compute_search_matches(translations, 'bird') == []

    def test_falls_back_to_target_language_param_when_row_has_none(self):
        translations = [
            {'source_text': 'dog', 'translated_text': 'Hund', 'target_article': 'der'},
        ]
        assert translation_listing.compute_search_matches(
            translations, 'der hund', target_language='de') == [0]


class TestPaginate:
    def test_empty_list_yields_a_single_empty_page(self):
        page, page_count, start, end = translation_listing.paginate(0, 0, 200)
        assert (page, page_count, start, end) == (0, 1, 0, 0)

    def test_first_page_of_multiple(self):
        page, page_count, start, end = translation_listing.paginate(250, 0, 200)
        assert (page, page_count, start, end) == (0, 2, 0, 200)

    def test_second_page_of_multiple(self):
        page, page_count, start, end = translation_listing.paginate(250, 1, 200)
        assert (page, page_count, start, end) == (1, 2, 200, 250)

    def test_exact_multiple_of_page_size(self):
        _, page_count, _, _ = translation_listing.paginate(400, 0, 200)
        assert page_count == 2

    def test_page_beyond_last_is_clamped_to_last_page(self):
        page, page_count, start, end = translation_listing.paginate(250, 5, 200)
        assert (page, page_count, start, end) == (1, 2, 200, 250)

    def test_negative_page_is_clamped_to_first_page(self):
        page, page_count, start, end = translation_listing.paginate(250, -3, 200)
        assert (page, page_count, start, end) == (0, 2, 0, 200)

    def test_page_size_below_one_is_clamped_to_one(self):
        page, page_count, start, end = translation_listing.paginate(3, 0, 0)
        assert (page, page_count, start, end) == (0, 3, 0, 1)
