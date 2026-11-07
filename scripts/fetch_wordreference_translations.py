#!/usr/bin/env python3
"""Resolve '***' placeholders in a needs-translations import file via WordReference.

``target - source`` entry per line (the same format ``utils.translation_import``
and the app's plain-text importer already use), where unresolved entries have
``***`` in place of the source text.

Reverse rows work the same way in the other direction: ``*** - greed`` (or
``Volksangehöriger, *** - citizen``, keeping the forms already known) looks
the source side up in the source -> target dictionary and fills the ``***``
with the target-language glosses. Nouns get an article from the gender
WordReference lists, for target languages with an entry in
``_GENDER_ARTICLES_BY_LANGUAGE``. A file may mix both kinds.

The target and source languages default to ``target_language`` and
``source_language`` in the app config. WordReference only has dictionaries
with English on one side (en <-> de/fr/es/it).

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

Resumable: the output is written every ``--save-every`` live lookups and at
the end. If ``--output`` already exists, entries it already resolved are
reused instead of re-fetched, so an interrupted run (or a deliberately capped
one via ``--limit``) can simply be re-invoked with the same arguments to pick
up where it left off.

Nothing here fabricates a translation. When no edition lists the word as a
headword the placeholder stays ``***`` and is reported for manual/LLM
follow-up -- any phrases the page did yield are still harvested. Answering
from an unrelated entry is what once resolved "Stange" to "a whole carton".

Usage:
    python scripts/fetch_wordreference_translations.py path/to/needs_translations.md
    python scripts/fetch_wordreference_translations.py path/to/needs_translations.md \\
        --target-language fr --source-language en \\
        --delay 8 --limit 40 \\
        --known-targets path/to/import.md path/to/other_import.md
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extensions.wordreference import WordReference, WordReferenceError, WordReferenceResult  # noqa: E402
from utils import translation_import  # noqa: E402
from utils.config import config  # noqa: E402
from utils.logging_setup import get_logger  # noqa: E402

logger = get_logger('scripts.fetch_wordreference_translations')

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


# Infinitive markers dropped from a reverse query: WordReference indexes
# "belong", not "to belong".
_INFINITIVE_MARKERS_BY_LANGUAGE = {'en': 'to '}


def _reverse_lookup_word(source_text: str, source_language: str) -> str:
    """The single source-language headword to query for a reverse row.

    Only the first of several forms ("puny, sickly", "spit/spew") is looked
    up, without the source language's infinitive marker.
    """
    forms = _split_glosses(source_text)
    first = (forms[0] if forms else source_text).split('/')[0].strip()
    marker = _INFINITIVE_MARKERS_BY_LANGUAGE.get(
        translation_import.primary_language_tag(source_language))
    if marker and first.casefold().startswith(marker) and first[len(marker):].strip():
        first = first[len(marker):].strip()
    return first


# Letters of the target language that a reverse row's source side should not
# hold. When it does, the row has target-language text in the wrong column
# ("*** - Gießerei"), and WordReference can resolve such a query through the
# other edition and return glosses in the wrong language. Languages without
# an entry skip the check.
_TARGET_LETTERS_BY_LANGUAGE = {'de': 'äöüßÄÖÜ'}

# WordReference noun-gender POS -> article, per target language. Anything
# else (``Nm, Nf``, ``Nmf``, verbs, adjectives) gets no article, and so does
# every term in a language without an entry.
_GENDER_ARTICLES_BY_LANGUAGE = {
    'de': {'nm': 'der', 'nf': 'die', 'nn': 'das', 'npl': 'die'},
}


def _source_has_target_letters(source_text: str, target_language: str) -> bool:
    letters = _TARGET_LETTERS_BY_LANGUAGE.get(
        translation_import.primary_language_tag(target_language), '')
    return any(ch in letters for ch in source_text)


def _with_article(term: str, pos: Optional[str], target_language: str) -> str:
    """Prefix a noun with the article its POS implies, if it has none yet.

    A term holding a comma lists several forms under one POS, so no article
    is added to it.
    """
    articles = _GENDER_ARTICLES_BY_LANGUAGE.get(
        translation_import.primary_language_tag(target_language))
    if not articles or not pos or ',' in term:
        return term
    article = articles.get(pos.replace(' ', '').casefold())
    if not article:
        return term
    existing, _remainder = translation_import.extract_target_article(term, target_language)
    if existing:
        return term
    return f'{article} {term}'


def _fill_target(target_text: str, glosses: str) -> str:
    """Replace a reverse row's placeholder part with the glosses it lacks.

    ``"Volksangehöriger, ***"`` keeps its known form and gains the looked-up
    ones in its place; a gloss the row already lists is not repeated.
    """
    parts = _split_glosses(target_text)
    known = {part.casefold() for part in parts if part != PLACEHOLDER}
    new = [gloss for gloss in _split_glosses(glosses) if gloss.casefold() not in known]
    filled: List[str] = []
    for part in parts:
        if part == PLACEHOLDER:
            filled.extend(new)
        else:
            filled.append(part)
    return ', '.join(filled)


def _entry_terms(entry, article_language: Optional[str]) -> List[str]:
    """The entry's translations, with noun articles added when *article_language* is set."""
    if article_language is None:
        return list(entry.to_terms)
    positions = getattr(entry, 'to_term_pos', None) or []
    return [
        _with_article(term, positions[i] if i < len(positions) else None, article_language)
        for i, term in enumerate(entry.to_terms)
    ]


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
    def _target_has_placeholder(self):
        return PLACEHOLDER in _split_glosses(self.target)

    @property
    def is_malformed(self):
        """True when both sides hold the placeholder, leaving nothing to look up."""
        return (
            self.parsed
            and self.source.strip() == PLACEHOLDER
            and PLACEHOLDER in self.target
        )

    @property
    def needs_lookup(self):
        """Forward row: the source side is the placeholder."""
        return self.parsed and not self.is_malformed and self.source.strip() == PLACEHOLDER

    @property
    def needs_reverse_lookup(self):
        """Reverse row: one comma-separated part of the target is the placeholder."""
        return (
            self.parsed
            and not self.is_malformed
            and self.source.strip() != PLACEHOLDER
            and self._target_has_placeholder
        )

    @property
    def block_key(self):
        """Key that finds this row's block in a previous run's output.

        A forward row keeps its target when resolved and a reverse row keeps
        its source, so each is matched on the side it does not fill in.
        """
        if self.needs_reverse_lookup:
            return ('source', self.source.casefold())
        return ('target', self.target.casefold())


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


BlockKey = Tuple[str, str]


def load_previous_blocks(output_path: Path, input_keys: Set[BlockKey]) -> Dict[BlockKey, List[str]]:
    """Input row's ``block_key`` -> the lines it produced last run.

    A resolved entry owns a block of output: its own line plus the phrase
    lines harvested with it, which run until the next line belonging to an
    input row. Reusing whole blocks is what makes a resumed run keep the
    phrases an earlier run already collected, instead of dropping everything
    that was not itself an input row. A line is matched on its target first,
    then on its source.
    """
    blocks: Dict[BlockKey, List[str]] = {}
    if not output_path.exists():
        return blocks
    current = None
    for raw in output_path.read_text(encoding='utf-8-sig').splitlines():
        split = translation_import.split_translation_line(raw)
        key = None
        if split:
            for candidate in (('target', split[0].casefold()), ('source', split[1].casefold())):
                if candidate in input_keys:
                    key = candidate
                    break
        if key is not None:
            current = key
            blocks[current] = [raw]
        elif current is not None:
            blocks[current].append(raw)
    return blocks


def _block_is_resolved(block: List[str]) -> bool:
    split = translation_import.split_translation_line(block[0]) if block else None
    return bool(split and PLACEHOLDER not in block[0])


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
        if split is None or PLACEHOLDER in raw:
            continue
        lines.append(raw)
    return lines


def _write_lines(path: Path, lines: List[str]) -> None:
    """Write LF-terminated lines, matching the import files rather than the platform.

    Written to a temporary file and renamed over *path*, so an interrupted
    write cannot leave a truncated output for the next run to resume from.
    """
    temp_path = path.with_name(path.name + '.tmp')
    with open(temp_path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(lines) + '\n')
    os.replace(temp_path, path)


def _reusable_lines(row: 'Row', previous_blocks: Dict[BlockKey, List[str]]) -> Optional[List[str]]:
    """The lines a previous run resolved for *row*, or None if it needs a lookup."""
    block = previous_blocks.get(row.block_key)
    if block and _block_is_resolved(block):
        return _usable_block_lines(block)
    return None


def _remaining_lines(rows: List['Row'], previous_blocks: Dict[BlockKey, List[str]]) -> List[str]:
    """Output for rows not processed yet: a previous run's resolved block, else the input line.

    Saving mid-run appends these after the processed rows, so the saved file
    is complete and keeps what earlier runs resolved further down.
    """
    lines: List[str] = []
    for row in rows:
        if row.needs_lookup or row.needs_reverse_lookup:
            reused = _reusable_lines(row, previous_blocks)
            if reused is not None:
                lines.extend(reused)
                continue
        lines.append(row.raw_line)
    return lines


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
    result: WordReferenceResult, headword: str, article_language: Optional[str] = None
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

    *article_language* is set for reverse lookups, whose glosses are
    target-language nouns that should carry their article.
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
            terms = _entry_terms(entry, article_language)
            if from_term.casefold() == headword_folded:
                glosses.extend(_merge_glosses(terms, seen_glosses))
                continue
            if '…' in from_term or '...' in from_term:
                # A suffix/prefix template ("…stange"), not a word to look up.
                continue
            pairs.append((from_term, ', '.join(_merge_glosses(terms))))

    return (', '.join(glosses) if glosses else None), pairs


def resolve(
    rows: List[Row],
    *,
    from_language: str,
    to_language: str,
    delay: float,
    limit: Optional[int],
    refresh: bool,
    previous_blocks: Dict[BlockKey, List[str]],
    already_known_targets: Set[str],
    save: Optional[Callable[[List[str]], None]] = None,
    save_every: int = 10,
) -> Tuple[List[str], int, List[str]]:
    """Resolve placeholders. Returns (output_lines, harvested_count, report_lines).

    *from_language* is the target (left-hand) language and *to_language* the
    source; reverse rows are looked up from *to_language* into
    *from_language*. Each entry's harvested phrases are written directly
    beneath it, always as ``target - source``, so one import file carries
    both and a phrase stays next to the headword it came from.

    *save*, when given, is called with the whole output so far (processed
    rows, then ``_remaining_lines`` for the rest) after every *save_every*
    live lookups.
    """
    wr = WordReference()
    output_lines: List[str] = []
    harvested_count = 0
    harvested_seen: Set[str] = set(already_known_targets)
    report: List[str] = []
    live_lookups = 0
    pending = sum(1 for r in rows if r.needs_lookup or r.needs_reverse_lookup)
    position = 0
    limit_announced = False
    saved_at = 0
    print(
        f"{pending} row(s) need a lookup, {delay:g}s apart. Only live requests are "
        "listed; rows reused from the output or served from the cache are not.",
        flush=True,
    )

    for index, row in enumerate(rows):
        if save and save_every > 0 and live_lookups != saved_at and live_lookups % save_every == 0:
            save(output_lines + _remaining_lines(rows[index:], previous_blocks))
            saved_at = live_lookups

        if not row.parsed:
            output_lines.append(row.raw_line)
            continue

        if row.is_malformed:
            output_lines.append(row.raw_line)
            report.append(
                f"  line {row.line_no}: malformed row (placeholder on both sides) "
                f"-- {row.raw_line!r}; needs a manual fix, not a lookup"
            )
            continue

        reverse = row.needs_reverse_lookup
        if not reverse and not row.needs_lookup:
            output_lines.append(row.raw_line)
            continue
        position += 1

        reused = _reusable_lines(row, previous_blocks)
        if reused is not None:
            output_lines.extend(reused)
            continue

        known_side = row.source if reverse else row.target
        if reverse and _source_has_target_letters(row.source, from_language):
            output_lines.append(row.raw_line)
            report.append(
                f"  line {row.line_no}: source side looks like {from_language}, not "
                f"{to_language}; left as {PLACEHOLDER} -- {row.raw_line!r}"
            )
            logger.warning("[%d/%d] %s: source side looks like %s; not looked up",
                           position, pending, row.source, from_language)
            continue

        if limit is not None and live_lookups >= limit:
            if not limit_announced:
                print(f"[{position}/{pending}] --limit {limit} reached; no more lookups this run",
                      flush=True)
                limit_announced = True
            output_lines.append(row.raw_line)
            report.append(f"  line {row.line_no}: skipped ({PLACEHOLDER} left in place, --limit reached) -- {known_side}")
            continue

        if reverse:
            query = _reverse_lookup_word(row.source, to_language)
            lookup_from, lookup_to = to_language, from_language
        else:
            query = _lookup_word(row.target, from_language)
            lookup_from, lookup_to = from_language, to_language
        will_hit_cache = not refresh and _will_hit_cache(
            wr, query, lookup_from, lookup_to)

        try:
            result = wr.lookup(query, lookup_from, lookup_to, use_cache=not refresh)
        except WordReferenceError as exc:
            # Raised while normalizing the query, before any request goes out,
            # so there is no rate limit to respect here.
            output_lines.append(row.raw_line)
            report.append(f"  line {row.line_no}: lookup error for {query!r} -- {exc}")
            logger.warning("[%d/%d] %s: lookup error -- %s", position, pending, query, exc)
            continue

        def progress(status: str) -> None:
            """A plain line for a live request; unresolved outcomes call warn() instead."""
            if not will_hit_cache:
                print(f"[{position}/{pending}] {query}: {status}", flush=True)

        def warn(status: str) -> None:
            logger.warning("[%d/%d] %s: %s", position, pending, query, status)

        if not will_hit_cache:
            live_lookups += 1
            time.sleep(delay)

        if result is None:
            output_lines.append(row.raw_line)
            report.append(f"  line {row.line_no}: no WordReference result for {query!r}")
            warn("no result")
            continue

        headword_gloss, phrases = _collect_pairs(
            result, query, article_language=from_language if reverse else None)
        if reverse:
            # Harvested pairs come back as (source phrase, target glosses).
            phrases = [(gloss, phrase) for phrase, gloss in phrases]
        if headword_gloss is None:
            output_lines.append(row.raw_line)
            report.append(
                f"  line {row.line_no}: no edition lists {query!r} as a headword; left "
                f"as {PLACEHOLDER}"
                + (f", but harvested {len(phrases)} phrase(s)" if phrases else "")
                + f" -- check {result.url}"
            )
        elif reverse:
            output_lines.append(f"{_fill_target(row.target, headword_gloss)} - {row.source}")
        else:
            output_lines.append(f"{row.target} - {headword_gloss}")

        added = 0
        for target_text, source_text in phrases:
            key = target_text.casefold()
            if not target_text or not source_text or key in harvested_seen:
                continue
            harvested_seen.add(key)
            output_lines.append(f"{target_text} - {source_text}")
            added += 1
        harvested_count += added
        if headword_gloss is None:
            warn(f"no headword entry, left as {PLACEHOLDER}"
                 + (f", {added} phrase(s)" if added else ""))
        else:
            progress(f"resolved, {added} phrase(s)" if added else "resolved")

    return output_lines, harvested_count, report


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input', type=Path, help="needs-translations file: 'target - ***' rows, '*** - source' rows, or both")
    parser.add_argument(
        '--output', type=Path, default=None,
        help="where to write the resolved file (default: <input stem>.resolved.md next to input)")
    parser.add_argument(
        '--target-language', '--from-language', dest='from_language',
        default=translation_import.primary_language_tag(config.target_language),
        help="language of the left-hand (target) side (default: target_language "
             "from the app config)")
    parser.add_argument(
        '--source-language', '--to-language', dest='to_language',
        default=translation_import.primary_language_tag(config.source_language),
        help="language of the right-hand (source) side (default: source_language "
             "from the app config); '*** - source' rows are looked up from this language")
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
    parser.add_argument(
        '--save-every', type=int, default=10,
        help="write the output file after every N live lookups so an interrupted "
             "run can resume from it (default: 10; 0 writes only at the end)")
    parser.add_argument('--report-out', type=Path, default=None)
    args = parser.parse_args()
    if WordReference.dictionary_code(args.from_language, args.to_language) is None:
        parser.error(
            f"WordReference has no {args.from_language} <-> {args.to_language} dictionary; "
            "one side must be English and the other de/fr/es/it "
            "(set --target-language / --source-language)")

    output_path = args.output or args.input.with_name(args.input.stem + '.resolved' + args.input.suffix)

    text = args.input.read_text(encoding='utf-8-sig')
    rows = parse_file(text.splitlines())

    input_keys = {r.block_key for r in rows if r.parsed}
    previous_blocks = load_previous_blocks(output_path, input_keys)
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
        save=lambda lines: _write_lines(output_path, lines),
        save_every=args.save_every,
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
