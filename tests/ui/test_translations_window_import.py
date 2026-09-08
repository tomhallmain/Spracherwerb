"""Tests for TranslationsWindow's import-file parsing.

Kept apart from ``test_translations_import.py`` so that module's pure-helper
tests stay free of the Qt import chain.
"""

import pytest

from ui.translations_window import TranslationsWindow

SAMPLE = "die Stange - pole, rod, rail\nkaum - just, barely\n"


def parse(path):
    """Parse *path* without building a widget.

    ``_parse_import_file`` reads only class-level names -- the two extension
    tuples and two classmethods -- so the class stands in for the instance
    and no QApplication is needed.
    """
    return TranslationsWindow._parse_import_file(TranslationsWindow, str(path))


class TestParseImportFile:
    def test_markdown_is_read_the_same_way_as_plain_text(self, tmp_path):
        markdown = tmp_path / 'entries.md'
        plain = tmp_path / 'entries.txt'
        markdown.write_text(SAMPLE, encoding='utf-8')
        plain.write_text(SAMPLE, encoding='utf-8')

        assert parse(markdown) == parse(plain)

    def test_markdown_keeps_a_gloss_list_in_one_row(self, tmp_path):
        """The commas separate glosses, not columns."""
        path = tmp_path / 'entries.md'
        path.write_text(SAMPLE, encoding='utf-8')

        rows = parse(path)

        assert rows[0] == {
            'translated_text': 'die Stange',
            'source_text': 'pole, rod, rail',
        }

    def test_markdown_is_classified_as_line_based(self):
        """Pins the routing: the delimited path would read commas as columns."""
        assert '.md' in TranslationsWindow._LINE_IMPORT_EXTENSIONS
        assert '.md' not in TranslationsWindow._DELIMITED_IMPORT_EXTENSIONS

    def test_a_quote_in_markdown_is_not_treated_as_csv_quoting(self, tmp_path):
        path = tmp_path / 'entries.md'
        path.write_text('„Oh, es ist nichts" - "Oh, it\'s nothing"\n', encoding='utf-8')

        rows = parse(path)

        assert len(rows) == 1
        assert rows[0]['translated_text'] == '„Oh, es ist nichts"'

    def test_delimited_file_with_headers_still_parses_as_columns(self, tmp_path):
        path = tmp_path / 'entries.csv'
        path.write_text('source_text,translated_text\ndog,Hund\n', encoding='utf-8')

        rows = parse(path)

        assert rows == [{'source_text': 'dog', 'translated_text': 'Hund'}]

    def test_empty_markdown_yields_no_rows(self, tmp_path):
        path = tmp_path / 'entries.md'
        path.write_text('\n\n', encoding='utf-8')

        assert parse(path) == []

    @pytest.mark.parametrize('name', ['entries.pdf', 'entries.json', 'entries'])
    def test_unsupported_extension_raises(self, tmp_path, name):
        path = tmp_path / name
        path.write_text(SAMPLE, encoding='utf-8')

        with pytest.raises(ValueError):
            parse(path)
