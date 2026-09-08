#!/usr/bin/env python3
"""Resolve '***' placeholders in a needs-translations import file via WordReference.

``target - source`` entry per line (the same format ``utils.translation_import``
and the app's plain-text importer already use), where unresolved entries have
``***`` in place of the English source text.

One input row stands for a whole set of translations rather than a single
answer. A result page carries several dictionary editions, each with its own
senses, compound forms and example phrases, and a word thin in one edition is
often well covered by another. So every edition is read: glosses whose
headword matches the queried word are merged to fill the placeholder, and
every other entry on the page becomes a phrase pair written directly beneath
it. A single row routinely expands into a dozen or more pairs, all in one
file, so there is one thing to import and a phrase stays next to the
headword it came from.

Rate limiting: WordReference has no official API and no published rate limit,
so this script is deliberately conservative. It sleeps ``--delay`` seconds
after every live HTTP request (default 5s), but never after a hit against
``WordReference``'s own on-disk 24h cache (``cache/wordreference/lookups.json``),
so a re-run that mostly revisits already-fetched words stays fast.

Resumable: if ``--output`` already exists, entries it already resolved are
reused instead of re-fetched, so an interrupted run (or a deliberately capped
one via ``--limit``) can simply be re-invoked with the same arguments to pick
up where it left off.

Nothing here fabricates a translation. When no edition lists the word as a
headword the placeholder stays ``***`` and is reported for manual/LLM
follow-up -- any phrases the page did yield are still harvested. Answering
from an unrelated entry is what once resolved "Stange" to "a whole carton".

Usage:
    python scripts/fetch_wordreference_translations.py docs/Deutsch_import_needs_translations.md
    python scripts/fetch_wordreference_translations.py docs/Deutsch_import_needs_translations.md \\
        --delay 8 --limit 40 \\
        --known-targets docs/Deutsch_import.md docs/Deutsch_lernen.md
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extensions.wordreference import WordReference, WordReferenceError, WordReferenceResult  # noqa: E402
from utils import translation_import  # noqa: E402

PLACEHOLDER = '***'


def _lookup_word(target_text: str, target_language: str) -> str:
    """The single headword to query for a (possibly multi-form) target.

    A target like ``"der Stutzen, der Wadenstrumpf"`` or
    ``"klatschnass/klitschnass"`` names more than one form on one line; only
    the first is looked up. A leading article is dropped because
    WordReference indexes nouns under the bare headword: ``/deen/Reisepass``
    resolves, ``/deen/der%20Reisepass`` does not. The full original target
    text is kept as-is in the output -- only the source side is filled in.
    """
    first = target_text.split(',')[0].strip()
    first = first.split('/')[0].strip()
    _article, remainder = translation_import.extract_target_article(first, target_language)
    return remainder or first


class Row:
    """One line of the needs-translations file."""

    def __init__(self, line_no, raw_line, target=None, source=None):
        self.line_no = line_no
        self.raw_line = raw_line
        self.target = target
        self.source = source

    @property
    def parsed(self):
        return self.target is not None

    @property
    def is_malformed(self):
        """True when the placeholder ended up on the target side instead of the source side."""
        return self.parsed and self.target.strip() == PLACEHOLDER

    @property
    def needs_lookup(self):
        return self.parsed and not self.is_malformed and self.source.strip() == PLACEHOLDER


def parse_file(lines):
    rows = []
    for line_no, raw in enumerate(lines, start=1):
        split = translation_import.split_translation_line(raw)
        if split is None:
            rows.append(Row(line_no, raw))
            continue
        target, source = split
        rows.append(Row(line_no, raw, target, source))
    return rows


def load_known_targets(*paths: Path) -> Set[str]:
    """Casefolded target texts already present in the given import files.

    Used so harvested related phrases don't duplicate an entry the user
    already has elsewhere.
    """
    known = set()
    for path in paths:
        if not path or not path.exists():
            continue
        for raw in path.read_text(encoding='utf-8-sig').splitlines():
            split = translation_import.split_translation_line(raw)
            if split:
                known.add(split[0].strip().casefold())
    return known


def load_previous_blocks(output_path: Path, input_targets: Set[str]) -> Dict[str, List[str]]:
    """Casefolded input target -> the lines it produced last run.

    A resolved entry owns a block of output: its own line plus the phrase
    lines harvested with it, which run until the next line belonging to an
    input target. Reusing whole blocks is what makes a resumed run keep the
    phrases an earlier run already collected, instead of dropping everything
    that was not itself an input row.
    """
    blocks: Dict[str, List[str]] = {}
    if not output_path.exists():
        return blocks
    current = None
    for raw in output_path.read_text(encoding='utf-8-sig').splitlines():
        split = translation_import.split_translation_line(raw)
        key = split[0].casefold() if split else None
        if key is not None and key in input_targets:
            current = key
            blocks[current] = [raw]
        elif current is not None:
            blocks[current].append(raw)
    return blocks


def _block_is_resolved(block: List[str]) -> bool:
    split = translation_import.split_translation_line(block[0]) if block else None
    return bool(split and split[1].strip() and split[1].strip() != PLACEHOLDER)


def _usable_block_lines(block: List[str]) -> List[str]:
    """Keep only the translated pairs of a reused block.

    Whatever follows a headword is carried forward as its harvested phrases,
    and those always have a translation. A line still holding the
    placeholder belonged to an input row that has since been corrected or
    removed: it no longer matches any target, so it would be absorbed into
    the block above it and kept for good.
    """
    lines = []
    for raw in block:
        split = translation_import.split_translation_line(raw)
        if split is None or split[1].strip() == PLACEHOLDER:
            continue
        lines.append(raw)
    return lines


def _write_lines(path: Path, lines: List[str]) -> None:
    """Write LF-terminated lines, matching the import files rather than the platform."""
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(lines) + '\n')


def _will_hit_cache(wr: WordReference, word: str, from_language: str, to_language: str) -> bool:
    """Best-effort check of whether `wr.lookup` will use its on-disk cache (no HTTP call)."""
    try:
        query = WordReference._normalize_query_word(word)
    except WordReferenceError:
        return False
    key = WordReference._cache_key(query, from_language, to_language)
    cached = wr.results.get(key)
    return bool(cached and wr._is_cache_valid(cached))


def _split_glosses(text: str) -> List[str]:
    """Split on top-level commas, leaving a parenthetical's own commas alone."""
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    for ch in text:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    return [part.strip() for part in parts if part.strip()]


def _merge_glosses(terms: List[str], seen: Optional[Set[str]] = None) -> List[str]:
    """Collect distinct glosses in page order.

    Uniqueness is judged per gloss, not per term: one term can already be a
    comma-separated list ("scarcely, barely"), and the same gloss recurs
    across senses and editions, so comparing whole terms would let a
    duplicate ride along inside a longer one.
    """
    if seen is None:
        seen = set()
    merged: List[str] = []
    for term in terms:
        for gloss in _split_glosses(term):
            key = gloss.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(gloss)
    return merged


def _collect_pairs(
    result: WordReferenceResult, headword: str
) -> Tuple[Optional[str], List[Tuple[str, str]]]:
    """Return (headword gloss, [(phrase, gloss), ...]) from every corpus on the page.

    A page is a whole set of translations, not one answer: the same word is
    covered by several dictionary editions, each with its own senses and
    example phrases. Glosses from every edition whose headword matches the
    queried word are merged (in page order, de-duplicated) to fill the
    placeholder; every other entry becomes a phrase pair of its own.

    Returns ``None`` for the gloss when no edition lists the word as a
    headword. The phrases are still returned in that case -- the page had
    usable content, just nothing that answers for the word itself, and
    guessing from an unrelated entry is how "Stange" once resolved to "a
    whole carton".
    """
    headword_folded = headword.casefold()
    glosses: List[str] = []
    seen_glosses = set()
    pairs: List[Tuple[str, str]] = []

    for section in result.sections:
        for entry in section.entries:
            if not entry.to_terms:
                continue
            from_term = entry.from_term.strip()
            if not from_term:
                continue
            if from_term.casefold() == headword_folded:
                glosses.extend(_merge_glosses(entry.to_terms, seen_glosses))
                continue
            if '…' in from_term or '...' in from_term:
                # A suffix/prefix template ("…stange"), not a word to look up.
                continue
            pairs.append((from_term, ', '.join(_merge_glosses(entry.to_terms))))

    return (', '.join(glosses) if glosses else None), pairs


def resolve(
    rows: List[Row],
    *,
    from_language: str,
    to_language: str,
    delay: float,
    limit: Optional[int],
    refresh: bool,
    previous_blocks: Dict[str, List[str]],
    already_known_targets: Set[str],
) -> Tuple[List[str], int, List[str]]:
    """Resolve placeholders. Returns (output_lines, harvested_count, report_lines).

    Each entry's harvested phrases are written directly beneath it, so one
    import file carries both and a phrase stays next to the headword it came
    from.
    """
    wr = WordReference()
    output_lines: List[str] = []
    harvested_count = 0
    harvested_seen: Set[str] = set(already_known_targets)
    report: List[str] = []
    live_lookups = 0

    for row in rows:
        if not row.parsed:
            output_lines.append(row.raw_line)
            continue

        if row.is_malformed:
            output_lines.append(row.raw_line)
            report.append(
                f"  line {row.line_no}: malformed row (placeholder is on the target "
                f"side) -- {row.raw_line!r}; needs a manual fix, not a lookup"
            )
            continue

        if not row.needs_lookup:
            output_lines.append(row.raw_line)
            continue

        prior_block = previous_blocks.get(row.target.casefold())
        if prior_block and _block_is_resolved(prior_block):
            output_lines.extend(_usable_block_lines(prior_block))
            continue

        if limit is not None and live_lookups >= limit:
            output_lines.append(row.raw_line)
            report.append(f"  line {row.line_no}: skipped ({PLACEHOLDER} left in place, --limit reached) -- {row.target}")
            continue

        query = _lookup_word(row.target, from_language)
        will_hit_cache = not refresh and _will_hit_cache(
            wr, query, from_language, to_language)

        try:
            result = wr.lookup(query, from_language, to_language, use_cache=not refresh)
        except WordReferenceError as exc:
            # Raised while normalizing the query, before any request goes out,
            # so there is no rate limit to respect here.
            output_lines.append(row.raw_line)
            report.append(f"  line {row.line_no}: lookup error for {query!r} -- {exc}")
            continue

        if not will_hit_cache:
            live_lookups += 1
            time.sleep(delay)

        if result is None:
            output_lines.append(row.raw_line)
            report.append(f"  line {row.line_no}: no WordReference result for {query!r}")
            continue

        headword_gloss, phrases = _collect_pairs(result, query)
        if headword_gloss is None:
            output_lines.append(row.raw_line)
            report.append(
                f"  line {row.line_no}: no edition lists {query!r} as a headword; left "
                f"as {PLACEHOLDER}"
                + (f", but harvested {len(phrases)} phrase(s)" if phrases else "")
                + f" -- check {result.url}"
            )
        else:
            output_lines.append(f"{row.target} - {headword_gloss}")

        for phrase, gloss in phrases:
            key = phrase.casefold()
            if key in harvested_seen:
                continue
            harvested_seen.add(key)
            output_lines.append(f"{phrase} - {gloss}")
            harvested_count += 1

    return output_lines, harvested_count, report


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input', type=Path, help="needs-translations file, one 'target - ***' entry per line")
    parser.add_argument(
        '--output', type=Path, default=None,
        help="where to write the resolved file (default: <input stem>.resolved.md next to input)")
    parser.add_argument('--from-language', default='de')
    parser.add_argument('--to-language', default='en')
    parser.add_argument(
        '--delay', type=float, default=5.0,
        help="seconds to wait after each live WordReference request (default: 5.0)")
    parser.add_argument(
        '--limit', type=int, default=None,
        help="stop after this many live lookups in this run (default: no limit); "
             "re-run with the same --output to resume")
    parser.add_argument(
        '--refresh', action='store_true',
        help="ignore the on-disk lookup cache and re-fetch. The cache stores parsed "
             "results, so a word cached before a parser change keeps returning the "
             "old parse until its 24h entry expires")
    parser.add_argument(
        '--known-targets', type=Path, nargs='*', default=[],
        help="other import files to check so harvested phrases don't duplicate existing entries")
    parser.add_argument('--report-out', type=Path, default=None)
    args = parser.parse_args()

    output_path = args.output or args.input.with_name(args.input.stem + '.resolved' + args.input.suffix)

    text = args.input.read_text(encoding='utf-8-sig')
    rows = parse_file(text.splitlines())

    input_targets = {r.target.casefold() for r in rows if r.parsed}
    previous_blocks = load_previous_blocks(output_path, input_targets)
    known_targets = load_known_targets(args.input, output_path, *args.known_targets)

    output_lines, harvested_count, report = resolve(
        rows,
        from_language=args.from_language,
        to_language=args.to_language,
        delay=args.delay,
        limit=args.limit,
        refresh=args.refresh,
        previous_blocks=previous_blocks,
        already_known_targets=known_targets,
    )

    _write_lines(output_path, output_lines)
    print(
        f"Wrote {len(output_lines)} lines to {output_path} "
        f"({harvested_count} harvested phrase(s) placed under their headwords)"
    )

    remaining = sum(1 for line in output_lines if PLACEHOLDER in line)
    report_lines = [
        f"Processed {len(rows)} lines from {args.input}.",
        f"{remaining} entries still contain '{PLACEHOLDER}' and need another pass or a manual fix.",
        "",
    ]
    if report:
        report_lines.append("Notes:")
        report_lines.extend(report)
    report_text = '\n'.join(report_lines).rstrip('\n')
    print(report_text)
    if args.report_out:
        _write_lines(args.report_out, report_text.splitlines())


if __name__ == '__main__':
    main()
