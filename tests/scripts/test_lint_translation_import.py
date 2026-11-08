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
