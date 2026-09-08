"""Tests for the gloss-merging helpers in scripts/fetch_wordreference_translations.py.

The script is not an importable package module, so it is loaded by path.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / 'scripts'
    / 'fetch_wordreference_translations.py'
)


def _load_script():
    spec = importlib.util.spec_from_file_location(
        'fetch_wordreference_translations', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def script():
    return _load_script()


class TestUsableBlockLines:
    def test_keeps_a_headword_and_its_phrases(self, script):
        block = [
            'die Ahnung - idea, notion',
            'keine Ahnung haben - to have no idea',
        ]
        assert script._usable_block_lines(block) == block

    def test_drops_a_stale_row_a_correction_left_behind(self, script):
        """A corrected target orphans its old line, which lands in the block above."""
        block = [
            'die Ahnung - idea, notion',
            'due Mahnung - ***',
            'keine Ahnung haben - to have no idea',
        ]

        assert script._usable_block_lines(block) == [
            'die Ahnung - idea, notion',
            'keine Ahnung haben - to have no idea',
        ]

    def test_drops_lines_that_are_not_pairs(self, script):
        block = ['die Ahnung - idea, notion', '', 'a stray note']
        assert script._usable_block_lines(block) == ['die Ahnung - idea, notion']


class TestLoadPreviousBlocks:
    def test_groups_phrases_under_their_input_target(self, script, tmp_path):
        output = tmp_path / 'out.md'
        output.write_text(
            'die Stange - pole, rod\n'
            'von der Stange - off-the-peg\n'
            'die Pulle - bottle\n',
            encoding='utf-8',
        )

        blocks = script.load_previous_blocks(output, {'die stange', 'die pulle'})

        assert blocks['die stange'] == ['die Stange - pole, rod', 'von der Stange - off-the-peg']
        assert blocks['die pulle'] == ['die Pulle - bottle']

    def test_a_line_that_is_no_longer_a_target_joins_the_block_above(self, script, tmp_path):
        """Why _usable_block_lines is needed: absorption alone cannot tell them apart."""
        output = tmp_path / 'out.md'
        output.write_text(
            'die Ahnung - idea\n'
            'due Mahnung - ***\n',
            encoding='utf-8',
        )

        blocks = script.load_previous_blocks(output, {'die ahnung'})

        assert blocks['die ahnung'] == ['die Ahnung - idea', 'due Mahnung - ***']
        assert script._usable_block_lines(blocks['die ahnung']) == ['die Ahnung - idea']


class TestSplitGlosses:
    def test_splits_on_top_level_commas(self, script):
        assert script._split_glosses('scarcely, barely') == ['scarcely', 'barely']

    def test_keeps_a_parenthetical_intact(self, script):
        assert script._split_glosses('sole, bottom (river, valley), floor') == [
            'sole', 'bottom (river, valley)', 'floor']

    def test_drops_empty_parts(self, script):
        assert script._split_glosses('just, , barely,') == ['just', 'barely']


class TestMergeGlosses:
    def test_keeps_page_order(self, script):
        assert script._merge_glosses(['just', 'barely', 'hardly']) == [
            'just', 'barely', 'hardly']

    def test_deduplicates_a_gloss_carried_inside_a_longer_term(self, script):
        """"barely" is a term of its own and also rides inside "scarcely, barely"."""
        merged = script._merge_glosses(['just', 'barely', 'scarcely, barely', 'only just'])

        assert merged == ['just', 'barely', 'scarcely', 'only just']

    def test_deduplicates_case_insensitively(self, script):
        assert script._merge_glosses(['Barely', 'barely']) == ['Barely']

    def test_shared_seen_set_spans_several_entries(self, script):
        """Senses and editions repeat the same gloss; the caller merges across both."""
        seen = set()
        first = script._merge_glosses(['just', 'barely'], seen)
        second = script._merge_glosses(['hardly', 'barely'], seen)

        assert first == ['just', 'barely']
        assert second == ['hardly']

    def test_a_parenthetical_comma_is_not_a_duplicate_boundary(self, script):
        merged = script._merge_glosses(['bottom (river, valley)', 'floor'])
        assert merged == ['bottom (river, valley)', 'floor']
