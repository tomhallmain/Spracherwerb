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

        blocks = script.load_previous_blocks(
            output, {('target', 'die stange'), ('target', 'die pulle')})

        assert blocks[('target', 'die stange')] == [
            'die Stange - pole, rod', 'von der Stange - off-the-peg']
        assert blocks[('target', 'die pulle')] == ['die Pulle - bottle']

    def test_finds_a_reverse_rows_block_by_its_source(self, script, tmp_path):
        """A resolved reverse row has a new target, so only its source still matches."""
        output = tmp_path / 'out.md'
        output.write_text(
            'die Gier, die Habgier - greed\n'
            'die Geldgier - greed for money\n'
            'die Zahnseide - floss\n',
            encoding='utf-8',
        )

        blocks = script.load_previous_blocks(
            output, {('source', 'greed'), ('source', 'floss')})

        assert blocks[('source', 'greed')] == [
            'die Gier, die Habgier - greed', 'die Geldgier - greed for money']
        assert blocks[('source', 'floss')] == ['die Zahnseide - floss']

    def test_a_line_that_is_no_longer_a_target_joins_the_block_above(self, script, tmp_path):
        """Why _usable_block_lines is needed: absorption alone cannot tell them apart."""
        output = tmp_path / 'out.md'
        output.write_text(
            'die Ahnung - idea\n'
            'due Mahnung - ***\n',
            encoding='utf-8',
        )

        blocks = script.load_previous_blocks(output, {('target', 'die ahnung')})

        assert blocks[('target', 'die ahnung')] == ['die Ahnung - idea', 'due Mahnung - ***']
        assert script._usable_block_lines(blocks[('target', 'die ahnung')]) == [
            'die Ahnung - idea']


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


def _row(script, line):
    target, source = line.split(' - ', 1)
    return script.Row(1, line, target, source)


class TestRowDirection:
    def test_placeholder_on_the_right_is_a_forward_row(self, script):
        row = _row(script, 'holprig - ***')
        assert row.needs_lookup
        assert not row.needs_reverse_lookup
        assert row.block_key == ('target', 'holprig')

    def test_placeholder_on_the_left_is_a_reverse_row(self, script):
        row = _row(script, '*** - greed')
        assert row.needs_reverse_lookup
        assert not row.needs_lookup
        assert row.block_key == ('source', 'greed')

    def test_placeholder_beside_a_known_form_is_a_reverse_row(self, script):
        assert _row(script, 'Volksangehöriger, *** - citizen').needs_reverse_lookup

    def test_placeholder_on_both_sides_is_malformed(self, script):
        row = _row(script, '*** - ***')
        assert row.is_malformed
        assert not row.needs_lookup
        assert not row.needs_reverse_lookup


class TestReverseLookupWord:
    def test_queries_the_first_form_only(self, script):
        assert script._reverse_lookup_word('puny, sickly', 'en') == 'puny'
        assert script._reverse_lookup_word('spit/spew', 'en') == 'spit'

    def test_drops_the_source_languages_infinitive_marker(self, script):
        assert script._reverse_lookup_word('to belong', 'en') == 'belong'

    def test_keeps_a_to_that_is_not_an_infinitive_marker(self, script):
        assert script._reverse_lookup_word('to belong', 'fr') == 'to belong'

    def test_keeps_a_multi_word_phrase(self, script):
        assert script._reverse_lookup_word('for now', 'en') == 'for now'


class TestSourceHasTargetLetters:
    def test_flags_target_language_letters(self, script):
        assert script._source_has_target_letters('Gießerei', 'de')

    def test_passes_a_plain_source(self, script):
        assert not script._source_has_target_letters('foundry', 'de')

    def test_skips_a_language_without_a_letter_table(self, script):
        assert not script._source_has_target_letters('Gießerei', 'xx')


class TestWithArticle:
    @pytest.mark.parametrize(('term', 'pos', 'expected'), [
        ('Hund', 'Nm', 'der Hund'),
        ('Gier', 'Nf', 'die Gier'),
        ('Haus', 'Nn', 'das Haus'),
        ('Leute', 'Npl', 'die Leute'),
    ])
    def test_adds_the_article_for_a_noun_gender(self, script, term, pos, expected):
        assert script._with_article(term, pos, 'de') == expected

    @pytest.mark.parametrize('pos', [None, 'Vi', 'Adj', 'Nm, Nf'])
    def test_leaves_a_term_without_a_single_gender_alone(self, script, pos):
        assert script._with_article('sparen', pos, 'de') == 'sparen'

    def test_keeps_an_article_already_present(self, script):
        assert script._with_article('die Gier', 'Nf', 'de') == 'die Gier'

    def test_adds_none_to_a_list_of_forms(self, script):
        assert script._with_article('Gier, Habgier', 'Nf', 'de') == 'Gier, Habgier'

    def test_adds_none_outside_german(self, script):
        assert script._with_article('chien', 'Nm', 'fr') == 'chien'


class TestFillTarget:
    def test_replaces_a_bare_placeholder(self, script):
        assert script._fill_target('***', 'die Gier, die Habgier') == 'die Gier, die Habgier'

    def test_keeps_known_forms_and_skips_their_repeats(self, script):
        filled = script._fill_target(
            'Volksangehöriger, ***', 'der Bürger, Volksangehöriger, der Staatsbürger')

        assert filled == 'Volksangehöriger, der Bürger, der Staatsbürger'


class TestRemainingLines:
    def test_keeps_an_earlier_runs_block_and_the_input_line_otherwise(self, script):
        """A mid-run save must not replace rows resolved further down with their placeholders."""
        rows = script.parse_file(['die Stange - ***', 'die Pulle - ***', 'kaum - barely'])
        previous_blocks = {
            ('target', 'die stange'): ['die Stange - pole, rod', 'von der Stange - off-the-peg'],
        }

        assert script._remaining_lines(rows, previous_blocks) == [
            'die Stange - pole, rod',
            'von der Stange - off-the-peg',
            'die Pulle - ***',
            'kaum - barely',
        ]


class TestWriteLines:
    def test_replaces_the_file_and_leaves_no_temp_file(self, script, tmp_path):
        output = tmp_path / 'out.md'
        output.write_text('old\n', encoding='utf-8')

        script._write_lines(output, ['die Pulle - bottle'])

        assert output.read_text(encoding='utf-8') == 'die Pulle - bottle\n'
        assert list(tmp_path.iterdir()) == [output]
