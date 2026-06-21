"""Pure helpers for parsing and normalizing imported translation rows.

Target entries may optionally include a leading article prefix (e.g. ``der`` in
``der Hund``). Many entries will not have one: verbs, adjectives, adverbs,
phrases, and nouns imported without an article all store only ``translated_text``.
The ``target_article`` field is omitted unless a prefix is detected.
"""

# Leading prefixes that *may* be split off when present. Detection is
# best-effort only; absence of a match leaves the full text in translated_text.
_ARTICLE_PREFIXES_BY_LANGUAGE = {
    'de': (
        'eines', 'einer', 'einem', 'einen', 'eine', 'ein',
        'der', 'die', 'das', 'den', 'dem', 'des',
    ),
    'fr': (
        'des', 'les', 'une', 'le', 'la', 'un', "l'",
    ),
    'es': (
        'unos', 'unas', 'los', 'las', 'una', 'el', 'la', 'un',
    ),
    'it': (
        'gli', 'uno', 'una', "un'", 'un', 'il', 'lo', 'la', 'i', 'le', "l'",
    ),
}


def coerce_str(value):
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def primary_language_tag(language_code):
    """BCP 47 primary language subtag (e.g. en-US -> en), lowercased."""
    if not language_code:
        return ''
    return str(language_code).strip().lower().replace('_', '-').split('-')[0]


def language_uses_target_articles(language_code):
    """Whether this target language may store an optional ``target_article`` field.

    Returns False for English (articles are never split or stored). For all
    other languages, extraction is attempted but most entries will still have
    no article when the text is not a prefixed noun phrase.
    """
    return primary_language_tag(language_code) != 'en'


def extract_target_article(translated_text, target_language):
    """Optionally split a leading article prefix from target text.

    Returns:
        tuple[str, str]: (target_article, remainder). ``target_article`` is
        empty when the language does not support the field, no recognizable
        prefix was found, or the entry is not a prefixed noun phrase (e.g. a
        verb or adjective).
    """
    if not language_uses_target_articles(target_language):
        return '', coerce_str(translated_text)

    text = coerce_str(translated_text)
    if not text:
        return '', text

    primary = primary_language_tag(target_language)
    prefixes = _ARTICLE_PREFIXES_BY_LANGUAGE.get(primary, ())
    text_folded = text.casefold()

    for prefix in prefixes:
        prefix_folded = prefix.casefold()
        if prefix.endswith("'") or prefix.endswith('\u2019'):
            if text_folded.startswith(prefix_folded):
                remainder = text[len(prefix):].lstrip()
                if remainder:
                    return text[:len(prefix)], remainder
            continue

        prefix_with_space = prefix_folded + ' '
        if text_folded.startswith(prefix_with_space):
            return text[:len(prefix)], text[len(prefix):].lstrip()

    return '', text


def format_target_for_display(translated_text, target_article='', target_language=None):
    """Rebuild the user-facing target phrase; omits prefix when no article stored."""
    text = coerce_str(translated_text)
    article = coerce_str(target_article)
    if not article:
        return text
    if target_language is not None and not language_uses_target_articles(target_language):
        return text
    if article.endswith("'") or article.endswith('\u2019'):
        return article + text
    return f'{article} {text}'


def target_identity_key(translated_text, target_article=''):
    """Case-insensitive key for the same target text and optional article."""
    return (
        coerce_str(target_article).casefold(),
        coerce_str(translated_text).casefold(),
    )


def normalize_target_article_fields(t, target_language=None):
    """Optionally split a leading article into ``target_article`` when detected.

    Entries without a detectable prefix keep the full text in ``translated_text``
    and do not receive a ``target_article`` key.
    """
    lang = target_language or t.get('target_language', '')
    if not language_uses_target_articles(lang):
        t.pop('target_article', None)
        return t

    article = coerce_str(t.get('target_article'))
    text = coerce_str(t.get('translated_text'))
    if article:
        combined = format_target_for_display(text, article, lang)
        article, text = extract_target_article(combined, lang)
    elif text:
        article, text = extract_target_article(text, lang)

    if article:
        t['target_article'] = article
    else:
        t.pop('target_article', None)
    t['translated_text'] = text
    return t


def split_translation_line(line):
    """Split a line into (translated_text, source_text).

    Plain-text imports use target-on-the-left, source-on-the-right. Tries
    `` - `` first, then hyphen separators missing a space on one side.
    """
    text = coerce_str(line)
    if not text:
        return None

    if ' - ' in text:
        left, right = text.split(' - ', 1)
    else:
        separator = None
        for candidate in (' -', '- '):
            if candidate in text:
                separator = candidate
                break
        if separator is None:
            return None
        left, right = text.split(separator, 1)

    translated_text = left.strip()
    source_text = right.strip()
    if translated_text and source_text:
        return translated_text, source_text
    return None


def lines_to_row_dicts(lines):
    """Convert plain ``target - source`` lines into import row dicts."""
    rows = []
    for line in lines:
        split = split_translation_line(line)
        if split is None:
            continue
        translated_text, source_text = split
        rows.append({
            'translated_text': translated_text,
            'source_text': source_text,
        })
    return rows


def extract_line_from_row(row):
    """Return a single combined value from a CSV row lacking explicit fields."""
    if not isinstance(row, dict):
        return None
    values = []
    for value in row.values():
        if isinstance(value, list):
            values.extend(coerce_str(v) for v in value)
        else:
            values.append(coerce_str(value))
    non_empty = [value for value in values if value]
    if len(non_empty) == 1:
        return non_empty[0]
    return None


def rows_have_translation_fields(rows, row_is_blank):
    """True when parsed CSV/TSV rows include explicit source/target columns."""
    for row in rows:
        if not isinstance(row, dict) or row_is_blank(row):
            continue
        if coerce_str(row.get('source_text')) or coerce_str(row.get('translated_text')):
            return True
    return False


def merge_source_texts(*source_texts):
    """Join comma-separated source glosses, keeping each part once."""
    seen = set()
    parts = []
    for text in source_texts:
        for part in coerce_str(text).split(','):
            part = part.strip()
            if not part:
                continue
            key = part.casefold()
            if key in seen:
                continue
            seen.add(key)
            parts.append(part)
    return ', '.join(parts)


def merge_rows_by_target(rows):
    """Collapse rows that share a target by merging their source glosses."""
    merged = {}
    order = []
    for row in rows:
        target_key = target_identity_key(
            row.get('translated_text', ''), row.get('target_article', ''))
        if not target_key[1]:
            continue
        if target_key not in merged:
            merged[target_key] = row.copy()
            order.append(target_key)
            continue
        existing = merged[target_key]
        existing['source_text'] = merge_source_texts(
            existing.get('source_text', ''), row.get('source_text', ''))
        if not coerce_str(existing.get('notes')) and coerce_str(row.get('notes')):
            existing['notes'] = row['notes']
    return [merged[key] for key in order]


def index_existing_by_target(existing):
    """Map casefolded target text to an existing row, merging duplicate targets."""
    by_target = {}
    for row in existing:
        target_key = target_identity_key(
            row.get('translated_text', ''), row.get('target_article', ''))
        if not target_key[1]:
            continue
        if target_key in by_target:
            by_target[target_key]['source_text'] = merge_source_texts(
                by_target[target_key].get('source_text', ''),
                row.get('source_text', ''),
            )
        else:
            by_target[target_key] = row
    return by_target
