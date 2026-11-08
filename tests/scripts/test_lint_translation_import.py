"""Tests for linting several files at once in scripts/lint_translation_import.py.

The script is not an importable package module, so it is loaded by path.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / 'scripts'
    / 'lint_translation_import.py'
)


def _load_script():
    spec = importlib.util.spec_from_file_location(
        'lint_translation_import', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def script():
    return _load_script()


@pytest.fixture
def import_files(tmp_path):
    """Two files: the first has no final newline, the second starts with a BOM."""
    complete = tmp_path / 'complete.md'
    complete.write_text('der Hund - dog\ndie Katze - cat', encoding='utf-8')
    resolved = tmp_path / 'missing.resolved.md'
    resolved.write_text('﻿das Pferd - horse\nder Hund - hound\n', encoding='utf-8')
    return complete, resolved


class TestParseFiles:
    def test_reads_the_files_in_the_given_order(self, script, import_files):
        entries = script.parse_files(list(import_files))

        assert [e.raw_line for e in entries] == [
            'der Hund - dog',
            'die Katze - cat',
            'das Pferd - horse',
            'der Hund - hound',
        ]

    def test_each_entry_keeps_its_original_file_and_line(self, script, import_files):
        complete, resolved = import_files
        entries = script.parse_files([complete, resolved])

        assert [e.location for e in entries] == [
            f'{complete}:1', f'{complete}:2', f'{resolved}:1', f'{resolved}:2']

    def test_a_single_file_is_numbered_by_line_alone(self, script, import_files):
        entries = script.parse_files([import_files[0]])

        assert [e.location for e in entries] == ['1', '2']


class TestIdenticalDuplicates:
    def test_identical_sentences_are_merged_unchanged(self, script):
        sentence = 'Mir geht es um den Mann - I’m talking about the man, who told you'
        entries = script.parse_file([sentence, sentence])

        risky = script.find_in_file_duplicates(entries)

        assert risky == []
        assert entries[0].source == 'I’m talking about the man, who told you'
        assert entries[1].dropped_as_duplicate_of is entries[0]

    def test_identical_parenthesised_commas_are_merged_unchanged(self, script):
        line = 'erfahren - learn (of), be told (about, of)'
        entries = script.parse_file([line, line])

        assert script.find_in_file_duplicates(entries) == []
        assert entries[0].source == 'learn (of), be told (about, of)'

    def test_different_sentences_still_need_a_manual_merge(self, script):
        entries = script.parse_file([
            'was habe ich davon? - what do I get out of it?',
            'was habe ich davon? - why should I?',
        ])

        risky = script.find_in_file_duplicates(entries)

        assert len(risky) == 1
        assert all(e.dropped_as_duplicate_of is None for e in entries)


class TestMultipleSeparators:
    LINE = 'durchgehend von 9 - 18.30 geöffnet - open 9 a.m. - 6.30 p.m.'

    def test_gets_its_own_section_and_not_the_source_language_one(self, script):
        entries = script.parse_file([self.LINE])
        risky = script.find_in_file_duplicates(entries)

        report = script.build_report(entries, risky, 'de')

        assert "Lines with more than one ' - ' separator (1):" in report
        assert f"    1: {self.LINE}" in report
        assert 'still looks like' not in report

    def test_is_not_merged_with_a_target_its_wrong_split_matches(self, script):
        entries = script.parse_file([
            'durchgehend von 9 - open from 9',
            self.LINE,
        ])

        script.find_in_file_duplicates(entries)

        assert entries[0].source == 'open from 9'
        assert entries[1].dropped_as_duplicate_of is None

    def test_passes_through_normalization_unchanged(self, script):
        entries = script.parse_file([self.LINE])

        assert script.build_normalized_lines(entries) == [self.LINE]

    def test_a_hyphen_inside_a_word_is_not_a_separator(self, script):
        entries = script.parse_file(['die E-Mail - e-mail, email'])

        assert not entries[0].has_multiple_separators


class TestConsolidatedLint:
    def test_merges_a_duplicate_from_another_file(self, script, import_files):
        entries = script.parse_files(list(import_files))
        script.find_in_file_duplicates(entries)

        assert entries[0].source == 'dog, hound'
        assert entries[3].dropped_as_duplicate_of is entries[0]

    def test_report_names_the_original_file_of_each_duplicate(self, script, import_files):
        complete, resolved = import_files
        entries = script.parse_files([complete, resolved])
        risky = script.find_in_file_duplicates(entries)

        report = script.build_report(entries, risky, 'de')

        assert f"{resolved}:2: 'der Hund' duplicates {complete}:1" in report

    def test_writes_the_consolidated_normalized_file(self, script, import_files, tmp_path, monkeypatch):
        normalized = tmp_path / 'combined.md'
        monkeypatch.setattr(sys, 'argv', [
            'lint', *map(str, import_files), '--write-normalized', str(normalized)])

        script.main()

        assert normalized.read_text(encoding='utf-8') == (
            'der Hund - dog, hound\ndie Katze - cat\ndas Pferd - horse\n')

    def test_refuses_to_overwrite_an_input(self, script, import_files, monkeypatch):
        complete, resolved = import_files
        monkeypatch.setattr(sys, 'argv', [
            'lint', str(complete), str(resolved), '--write-normalized', str(complete)])

        with pytest.raises(SystemExit):
            script.main()
        assert complete.read_text(encoding='utf-8') == 'der Hund - dog\ndie Katze - cat'
