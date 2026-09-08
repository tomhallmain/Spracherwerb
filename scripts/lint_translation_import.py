#!/usr/bin/env python3
"""Lint (and optionally normalize) a plain-text ``target - source`` import file.

Plain-text imports (``.txt``, one entry per line) go through
``utils.translation_import.lines_to_row_dicts``, which silently drops any line
``split_translation_line`` can't parse -- no dash, a multi-line dictionary
paste split across several dash-less lines, etc. Those lines simply never
reach the app's duplicate/merge handling (``merge_rows_by_target`` /
``index_existing_by_target`` in ``utils/translation_import.py``), so they are
lost with no warning in the "Import Complete" summary.

This script re-parses a file with the same helpers the app uses, so its
report matches what the real import would (and wouldn't) do, and surfaces
everything that needs a human/LLM look before import:

- lines that ``split_translation_line`` cannot parse at all (would be
  silently dropped)
- unresolved ``***`` placeholders
- entries whose source (right-hand) side still looks like German rather
  than a translation (heuristic; always worth a manual check)
- occurrences of "ibg", a common mobile-keyboard mistype of the "-ing"
  ending (n and b sit next to each other on a phone keyboard), e.g.
  "somethibg" for "something"
- duplicate targets within the file, via the project's own
  ``merge_rows_by_target`` -- this script does not reimplement dedup, but it
  does refuse to hand a merge to it when that would be unsafe (see below)

``merge_source_texts`` (used by ``merge_rows_by_target`` for every duplicate
target, in both this script and the app's real import path) naively does
``text.split(',')`` and rejoins the deduplicated parts. That is exactly right
for a short synonym list ("dog, canine, puppy") and exactly wrong for a
source text where a comma is doing something other than separating synonyms:
a comma nested inside parentheses ("cereal (e.g. oats, barley)" splits into
"cereal (e.g. oats" and "barley)", tearing the parenthetical in half and
losing the closing paren), or a genuine sentence that happens to contain one
("The dress was so tight, she could barely move."). This script checks each
in-file duplicate-target group for both patterns before merging: groups that
look safe are merged exactly as the app would; groups that don't are left
alone and reported separately, under "duplicate targets NOT merged", for a
human/LLM to resolve by hand.

Nothing here fabricates a translation. Entries that need one are reported,
not guessed.

Usage:
    python scripts/lint_translation_import.py docs/import.txt
    python scripts/lint_translation_import.py docs/import.txt --write-normalized docs/import.normalized.txt
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils import translation_import  # noqa: E402

# Heuristic only: flags candidates for manual review, not a verdict. Common
# German function words/diacritics turning up on the source side usually mean
# the "translation" is still German (see docs/import.txt history: entries
# like "Getreide - Hafer, Gerste, Weizen" had German glosses instead of an
# English translation).
_GERMAN_MARKER_RE = re.compile(
    r'[äöüßÄÖÜ]|(?:\b(?:und|oder|kleiner|größer|für|kein|nicht)\b)'
)

# A comma-separated word/phrase list is safe for merge_source_texts() to
# split on every comma. Anything ``translation_import.looks_like_prose`` flags
# is a sign that at least one comma in the text is doing something else, and
# the split would corrupt it -- the same check the app's import path now uses
# (see ``translation_import.protect_prose_commas``) to tag such commas before
# they ever reach a naive ``split(',')``.


def _merge_is_risky(source_texts):
    """Whether merge_source_texts() on these texts could corrupt one of them."""
    return any(translation_import.looks_like_prose(text) for text in source_texts)


class Entry:
    """One line of the import file, categorized for the report."""

    def __init__(self, line_no, raw_line):
        self.line_no = line_no
        self.raw_line = raw_line
        self.target = None
        self.source = None
        self.dropped_as_duplicate_of = None  # line_no of the entry it merged into

    @property
    def parsed(self):
        return self.target is not None

    @property
    def is_blank(self):
        return not self.raw_line.strip()

    @property
    def has_placeholder(self):
        return '***' in self.raw_line

    @property
    def has_ibg_typo(self):
        return 'ibg' in self.raw_line.lower()

    @property
    def looks_untranslated(self):
        if not self.parsed:
            return False
        return bool(_GERMAN_MARKER_RE.search(self.source))


def parse_file(lines):
    """Parse every line with the app's own splitter; nothing is skipped here."""
    entries = []
    for line_no, raw_line in enumerate(lines, start=1):
        entry = Entry(line_no, raw_line)
        split = translation_import.split_translation_line(raw_line)
        if split is not None:
            entry.target, entry.source = split
        entries.append(entry)
    return entries


def _group_parsed_by_target(entries):
    """Group parsed entries by casefolded target text, preserving file order."""
    groups = {}
    order = []
    for e in entries:
        if not e.parsed:
            continue
        key = translation_import.target_identity_key(e.target)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(e)
    return [groups[key] for key in order]


def find_in_file_duplicates(entries):
    """Merge safe duplicate-target groups; leave risky ones alone.

    Only calls ``translation_import.merge_rows_by_target`` -- the exact
    function the app runs on import -- on groups ``_merge_is_risky`` clears,
    so a merge that would happen here matches what the real import would do.
    Risky groups are left completely untouched (no entry gets
    ``dropped_as_duplicate_of`` set) and are returned for the report; nothing
    is merged or dropped on their behalf.

    Returns:
        list[list[Entry]]: the duplicate-target groups judged risky.
    """
    risky_groups = []
    for group in _group_parsed_by_target(entries):
        if len(group) < 2:
            continue
        if _merge_is_risky(e.source for e in group):
            risky_groups.append(group)
            continue

        rows = [{'translated_text': e.target, 'source_text': e.source} for e in group]
        merged_source = translation_import.merge_rows_by_target(rows)[0]['source_text']
        group[0].source = merged_source
        for e in group[1:]:
            e.dropped_as_duplicate_of = group[0].line_no

    return risky_groups


def _append_section(lines, header, items, render_item, subtext=None):
    """Append a header + itemized list, but only when there's something to show."""
    if not items:
        return
    lines.append(header)
    if subtext:
        lines.append(subtext)
    for item in items:
        lines.append(render_item(item))
    lines.append("")


def build_report(entries, risky_groups):
    unparseable = [
        e for e in entries
        if not e.parsed and not e.is_blank and not e.has_placeholder
    ]
    placeholders = [e for e in entries if e.has_placeholder]
    untranslated_looking = [
        e for e in entries
        if e.parsed and not e.dropped_as_duplicate_of and e.looks_untranslated
    ]
    ibg_typos = [e for e in entries if e.has_ibg_typo]
    duplicates = [e for e in entries if e.dropped_as_duplicate_of]

    lines = []
    lines.append(f"Parsed {len(entries)} lines.")
    parsed_count = sum(1 for e in entries if e.parsed)
    lines.append(f"  {parsed_count} parsed as target/source entries")
    lines.append(f"  {len(duplicates)} of those duplicate an earlier target (would be merged)")
    lines.append("")

    _append_section(
        lines,
        f"Lines that would be SILENTLY DROPPED on import ({len(unparseable)}):",
        unparseable,
        lambda e: f"    {e.line_no}: {e.raw_line}",
        subtext=(
            "  split_translation_line() found no usable ' - ' separator; "
            "lines_to_row_dicts() skips these with no warning."
        ),
    )

    _append_section(
        lines,
        f"Unresolved '***' placeholders ({len(placeholders)}):",
        placeholders,
        lambda e: f"    {e.line_no}: {e.raw_line}",
    )

    _append_section(
        lines,
        f"Entries whose source side still looks German, needs a human/LLM check ({len(untranslated_looking)}):",
        untranslated_looking,
        lambda e: f"    {e.line_no}: {e.target} - {e.source}",
    )

    _append_section(
        lines,
        f"'ibg' typos (likely mistyped \"-ing\", n/b are keyboard neighbors) ({len(ibg_typos)}):",
        ibg_typos,
        lambda e: f"    {e.line_no}: {e.raw_line}",
    )

    _append_section(
        lines,
        f"In-file duplicate targets merged ({len(duplicates)}):",
        duplicates,
        lambda e: f"    {e.line_no}: {e.target!r} duplicates line {e.dropped_as_duplicate_of}",
    )

    if risky_groups:
        risky_entry_count = sum(len(g) for g in risky_groups)
        lines.append(
            f"Duplicate targets NOT merged -- unsafe to comma-split, needs manual "
            f"resolution ({len(risky_groups)} groups, {risky_entry_count} lines):"
        )
        lines.append(
            "  a source text has a comma nested in parens/brackets, reads as a "
            "sentence rather than a short gloss list, or contains a "
            "parenthetical aside (e.g. 'in fact'); merging would corrupt it"
        )
        for group in risky_groups:
            lines.append(f"    {group[0].target!r}:")
            for e in group:
                reason = []
                if translation_import.has_comma_inside_parens(e.source):
                    reason.append('comma inside parens')
                if translation_import.looks_like_sentence(e.source):
                    reason.append('looks like a sentence')
                if translation_import.has_discourse_marker_part(e.source):
                    reason.append('parenthetical aside')
                reason_str = f" [{', '.join(reason)}]" if reason else ""
                lines.append(f"      {e.line_no}: {e.target} - {e.source}{reason_str}")
        lines.append("")

    return '\n'.join(lines).rstrip('\n')


def build_normalized_lines(entries):
    """Rewrite parseable entries in canonical form; pass everything else through.

    Duplicate targets are dropped in favor of the earlier occurrence (which
    absorbed the merged source glosses). Everything that isn't a clean
    target/source entry -- blanks, '***' placeholders, unparseable lines,
    free-text notes -- is passed through unchanged rather than dropped, so a
    human/LLM review pass still has something to act on afterward.
    """
    out = []
    for e in entries:
        if e.dropped_as_duplicate_of:
            continue
        if e.parsed:
            out.append(f"{e.target} - {e.source}")
        else:
            out.append(e.raw_line)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help="plain-text import file to lint")
    parser.add_argument(
        '--write-normalized', type=Path, default=None,
        help="write a normalized copy (canonical spacing, in-file duplicates merged) to this path",
    )
    parser.add_argument(
        '--report-out', type=Path, default=None,
        help="also write the report to this path (in addition to stdout)",
    )
    args = parser.parse_args()

    text = args.input.read_text(encoding='utf-8-sig')
    lines = text.splitlines()

    entries = parse_file(lines)
    risky_groups = find_in_file_duplicates(entries)

    report = build_report(entries, risky_groups)
    print(report)
    if args.report_out:
        args.report_out.write_text(report + '\n', encoding='utf-8')

    if args.write_normalized:
        normalized = build_normalized_lines(entries)
        args.write_normalized.write_text('\n'.join(normalized) + '\n', encoding='utf-8')
        print(f"\nWrote normalized copy to {args.write_normalized}")


if __name__ == '__main__':
    main()
