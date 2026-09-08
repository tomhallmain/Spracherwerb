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


# A result page carries several dictionary editions. This one has no
# table.WRD content at all -- the word is only covered by an older edition,
# which is the shape that used to be reported as "no result".
OLD_EDITION_HTML = """
<div id="articleWRD"><!-- BEGIN ARTICLE WRD --><!-- END ARTICLE WRD --></div>
<div id="otherDicts">
  <div class="small1">W&ouml;rterbuch v1 Englisch-Deutsch &copy; WordReference.com 2012:</div>
  <div class="entry langenscheidt"><strong class="hw">Pulle</strong><span class="ital"> f</span><span class="roman">;</span><span class="usage"> umg</span><span class="roman"> bottle</span><span class="roman">;</span><div class="examplecontainer"><span class="example phrase ex"> ein Schluck aus der Pulle</span><span class="roman"> a swig from the bottle;</span></div></div>
</div>
"""

# An inline example container closes before its own translation, so the gloss
# trails after it and only ends at the <br>.
INLINE_EXAMPLE_HTML = """
<div id="otherDicts"><div class="entry langenscheidt"><strong class="hw">Stange</strong><ul class="arablist"><li class="arablist"><span class="arab headnumber">1.</span><span class="roman"> pole</span><span class="roman">;</span><div class="examplecontainer" style="display:inline;"><span class="example phrase ex"> von der Stange</span><span class="ital"> Kleidung</span><span class="roman">:</span></div><span class="ital"> attr</span><span class="roman"> off-the-peg &hellip;</span><span class="roman">,</span><span class="roman"> off the peg</span><br></li></ul></div></div>
"""

# A third layout: sense groups headed by span.lemma, translations in
# div.senseExample. Abbreviations nest their spelled-out form inside
# themselves and put the short form after it.
SENSE_GROUP_HTML = """
<div id="otherDicts">
  <div class="small1">W&ouml;rterbuch v2 Englisch-Deutsch &copy; WordReference.com 2019:</div>
  <div class="langenscheidt"><div class="entry">
    <div class="posGroupItems">
      <div class="lemGroup"><span class="lemma">draufsetzen</span></div>
      <ol class="arabiclist posGroup"><li class="senseGroup"><ul class="squarelist"><li>
        <div class="senseExample"><span class="lemmaCompGroup"><span class="ex">einen (<span class="meta"><span class="abbr tooltip"><span>oder | or</span>od</span></span> eins) draufsetzen</span> <span class="indGroup"><span class="ind">noch weiter gehen</span></span></span> &rarr; <span class="transCompGroup"><span class="trans">to put <span class="abbr tooltip"><span>jemand | somebody</span>sb</span> on</span></span></div>
      </li></ul></li></ol>
    </div>
  </div></div>
</div>
"""

# A page can carry a table running the other way, where the queried German
# word appears only among the translations of an English headword.
REVERSED_TABLE_HTML = """
<div id="articleWRD">
  <table class="WRD" data-dict="deen">
    <tr class="wrtopsection"><td colspan="3"><strong>Zusammengesetzte W&ouml;rter</strong></td></tr>
    <tr class="langHeader">
      <td class="FrWrd"><span class="ph" data-ph="sLang_en">Englisch</span></td>
      <td></td>
      <td class="ToWrd"><span class="ph" data-ph="sLang_de">Deutsch</span></td>
    </tr>
    <tr class="odd">
      <td class="FrWrd"><strong>saver</strong> <em class="POS2" data-abbr="n">n</em></td>
      <td>(person who saves money)</td>
      <td class="ToWrd">jdm, der spart <em class="POS2" data-abbr="Rdw">Rdw</em></td>
    </tr>
    <tr class="odd">
      <td>&nbsp;</td><td>&nbsp;</td>
      <td class="ToWrd">sparen <em class="POS2" data-abbr="Vi">Vi</em></td>
    </tr>
    <tr class="even">
      <td>&nbsp;</td><td>(selten)</td>
      <td class="ToWrd">Sparer <em class="POS2" data-abbr="Nm">Nm</em></td>
    </tr>
  </table>
</div>
"""

ALTERNATING_ROWS_HTML = """
<div id="articleWRD">
  <table class="WRD" data-dict="deen">
    <tr class="odd">
      <td class="FrWrd"><strong>eine ganze Stange</strong></td>
      <td>(Zigarettenbox)</td>
      <td class="ToWrd">a whole carton</td>
    </tr>
    <tr class="even">
      <td class="FrWrd"><strong>eine Stange Geld</strong></td>
      <td></td>
      <td class="ToWrd">a tidy sum</td>
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

    def test_parses_both_alternating_row_classes(self, wordreference_client):
        """Translation rows alternate odd/even; reading only one drops half the table."""
        sections = wordreference_client._parse_html(ALTERNATING_ROWS_HTML, 'deen')

        from_terms = [e.from_term for s in sections for e in s.entries]
        assert from_terms == ['eine ganze Stange', 'eine Stange Geld']

    def test_parses_an_older_edition_when_the_current_one_is_empty(
        self, wordreference_client
    ):
        sections = wordreference_client._parse_html(OLD_EDITION_HTML, 'deen')

        assert len(sections) == 1
        assert '2012' in sections[0].title
        entries = sections[0].entries
        assert entries[0].from_term == 'Pulle'
        assert entries[0].to_terms == ['bottle']
        assert entries[1].from_term == 'ein Schluck aus der Pulle'
        assert entries[1].to_terms == ['a swig from the bottle']

    def test_drops_register_labels_from_an_older_edition(self, wordreference_client):
        sections = wordreference_client._parse_html(OLD_EDITION_HTML, 'deen')

        rendered = ' '.join(
            term for s in sections for e in s.entries for term in e.to_terms)
        assert 'umg' not in rendered

    def test_reorients_a_reverse_direction_table(self, wordreference_client):
        """One English headword spreads its German translations down the continuation rows."""
        sections = wordreference_client._parse_html(REVERSED_TABLE_HTML, 'deen')

        pairs = [(e.from_term, e.to_terms) for s in sections for e in s.entries]
        assert pairs == [
            ('jdm, der spart', ['saver']),
            ('sparen', ['saver']),
            ('Sparer', ['saver']),
        ]

    def test_keeps_a_same_direction_table_as_is(self, wordreference_client):
        """The language header decides; a normal table must not be flipped."""
        sections = wordreference_client._parse_html(ALTERNATING_ROWS_HTML, 'deen')

        assert [e.from_term for s in sections for e in s.entries] == [
            'eine ganze Stange', 'eine Stange Geld']

    def test_uses_the_body_of_an_error_response(self, wordreference_client):
        """A word with no entry of its own is served with a 404 and a usable body."""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.status_code = 404

        with patch.object(
            wordreference_client.session, 'get', return_value=mock_response
        ):
            result = wordreference_client.lookup('dog', 'en', 'de', use_cache=False)

        assert result is not None
        assert result.sections

    def test_parses_a_sense_group_edition(self, wordreference_client):
        sections = wordreference_client._parse_html(SENSE_GROUP_HTML, 'deen')

        assert len(sections) == 1
        assert '2019' in sections[0].title
        entries = sections[0].entries
        assert [e.from_term for e in entries] == ['einen (od eins) draufsetzen']
        assert entries[0].to_terms == ['to put sb on']

    def test_drops_the_spelled_out_form_of_an_abbreviation(self, wordreference_client):
        """The expansion is nested inside the abbreviation, so plain text reads "somebodysb"."""
        sections = wordreference_client._parse_html(SENSE_GROUP_HTML, 'deen')

        rendered = ' '.join(
            [e.from_term for s in sections for e in s.entries]
            + [t for s in sections for e in s.entries for t in e.to_terms]
        )
        assert 'somebody' not in rendered
        assert 'oder | or' not in rendered
        assert 'sb' in rendered

    def test_leaves_out_the_german_sense_indicator(self, wordreference_client):
        sections = wordreference_client._parse_html(SENSE_GROUP_HTML, 'deen')

        rendered = ' '.join(t for s in sections for e in s.entries for t in e.to_terms)
        assert 'noch weiter gehen' not in rendered

    def test_keeps_a_trailing_gloss_with_its_inline_example(self, wordreference_client):
        sections = wordreference_client._parse_html(INLINE_EXAMPLE_HTML, 'deen')

        entries = {e.from_term: e.to_terms for s in sections for e in s.entries}
        assert entries['Stange'] == ['pole']
        assert entries['von der Stange'] == ['off-the-peg, off the peg']

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
