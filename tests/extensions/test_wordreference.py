"""Unit tests for the WordReference extension."""

from pathlib import Path
import shutil
from unittest.mock import MagicMock, patch

import pytest

from extensions.wordreference import (
    WordReference,
    WordReferenceError,
    WordReferenceResult,
    WordReferenceSection,
    WordReferenceTranslation,
)


SAMPLE_HTML = """
<div id="articleWRD">
  <table class="WRD" data-dict="ende">
    <tr class="wrtopsection"><td colspan="3"><strong>Principal Translations</strong></td></tr>
    <tr class="odd">
      <td class="FrWrd"><strong>dog</strong> <em class="POS2" data-abbr="n">n</em></td>
      <td>(pet: canine)</td>
      <td class="ToWrd">Hund <em class="POS2" data-abbr="Nm">Nm</em></td>
    </tr>
    <tr class="odd">
      <td>&nbsp;</td>
      <td>(pejorative)</td>
      <td class="ToWrd">Köter <em class="POS2" data-abbr="Nm">Nm</em></td>
    </tr>
  </table>
</div>
"""


@pytest.fixture
def wordreference_client():
    with patch.object(WordReference, '_load_cache'):
        client = WordReference()
    yield client


class TestWordReference:
    def setup_method(self):
        cache_dir = Path('cache/wordreference')
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

    def test_initialization(self, wordreference_client):
        assert isinstance(wordreference_client, WordReference)

    @pytest.mark.parametrize(
        ('from_lang', 'to_lang', 'expected'),
        [
            ('en', 'de', 'ende'),
            ('de', 'en', 'deen'),
            ('en', 'fr', 'enfr'),
            ('fr', 'en', 'fren'),
            ('de', 'fr', None),
            ('la', 'en', None),
        ],
    )
    def test_dictionary_code(self, from_lang, to_lang, expected):
        assert WordReference.dictionary_code(from_lang, to_lang) == expected

    def test_build_lookup_url(self):
        url = WordReference.build_lookup_url('dog', 'en', 'de')
        assert url == 'https://www.wordreference.com/ende/dog'

    def test_lookup_uses_local_html_response(self, wordreference_client):
        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            wordreference_client.session,
            'get',
            return_value=mock_response,
        ) as mock_get:
            result = wordreference_client.lookup('dog', 'en', 'de', use_cache=False)

        mock_get.assert_called_once_with(
            'https://www.wordreference.com/ende/dog',
            timeout=20,
        )
        assert isinstance(result, WordReferenceResult)
        assert result.word == 'dog'
        assert result.dictionary_code == 'ende'
        assert result.sections
        assert any(
            'Hund' in term
            for section in result.sections
            for entry in section.entries
            for term in entry.to_terms
        )

    def test_parse_html(self, wordreference_client):
        sections = wordreference_client._parse_html(SAMPLE_HTML, 'ende')
        assert len(sections) == 1
        assert sections[0].title == 'Principal Translations'
        assert sections[0].entries[0].from_term == 'dog'
        assert sections[0].entries[0].to_terms == ['Hund', 'Köter']

    def test_unsupported_language_pair_returns_none(self, wordreference_client):
        with patch.object(wordreference_client.session, 'get') as mock_get:
            result = wordreference_client.lookup('lupus', 'la', 'en')
        assert result is None
        mock_get.assert_not_called()

    def test_empty_word_raises(self):
        with pytest.raises(WordReferenceError):
            WordReference.build_lookup_url('   ', 'en', 'de')

    def test_format_result_summary(self):
        result = WordReferenceResult(
            word='dog',
            dictionary_code='ende',
            from_language='en',
            to_language='de',
            url='https://www.wordreference.com/ende/dog',
            sections=[
                WordReferenceSection(
                    title='Principal Translations',
                    entries=[
                        WordReferenceTranslation(
                            from_term='dog',
                            to_terms=['Hund'],
                            context='(pet: canine)',
                            from_pos='n',
                            to_pos='Nm',
                        )
                    ],
                )
            ],
        )
        summary = WordReference.format_result_summary(result)
        assert 'dog' in summary
        assert 'Hund' in summary
        assert 'wordreference.com/ende/dog' in summary

    def test_open_lookup_in_browser(self):
        with patch('extensions.wordreference.webbrowser.open') as mock_open:
            url = WordReference.open_lookup_in_browser('dog', 'en', 'de')
        assert url == 'https://www.wordreference.com/ende/dog'
        mock_open.assert_called_once_with(url)

    def test_open_in_browser_delegates_to_class_method(self, wordreference_client):
        with patch.object(
            WordReference,
            'open_lookup_in_browser',
            return_value='https://www.wordreference.com/ende/dog',
        ) as mock_open:
            url = wordreference_client.open_in_browser('dog', 'en', 'de')
        assert url == 'https://www.wordreference.com/ende/dog'
        mock_open.assert_called_once_with('dog', 'en', 'de')
