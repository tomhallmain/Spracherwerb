"""Pure helpers for the translations window's search and pagination.

Kept free of any Qt dependency (unlike ``ui/translations_window.py``, which
imports PySide6 at module scope) so this logic can be unit tested without a
QApplication. ``ui/translations_window.py`` is the only caller.
"""

from utils.translation_import import coerce_str, format_target_for_display


def compute_search_matches(translations, search_text, target_language=None):
    """Indices into `translations` matching `search_text`.

    Case-insensitive substring match against source_text, the displayed
    target (article + translated_text), and notes. Matches against the
    underlying data rather than rendered table cells, so a search finds
    entries that aren't on the currently displayed page. Returns every
    index, in order, when `search_text` is blank.
    """
    search_text = coerce_str(search_text).lower()
    if not search_text:
        return list(range(len(translations)))

    matches = []
    for i, t in enumerate(translations):
        display_target = format_target_for_display(
            t.get('translated_text', ''),
            t.get('target_article', ''),
            t.get('target_language', target_language),
        )
        haystack = ' '.join([
            coerce_str(t.get('source_text', '')),
            display_target,
            coerce_str(t.get('notes', '')),
        ]).lower()
        if search_text in haystack:
            matches.append(i)
    return matches


def paginate(total, page, page_size):
    """Clamp `page` into range for `total` items of `page_size` each.

    Returns `(clamped_page, page_count, start, end)`; `start`/`end` are a
    0-indexed, end-exclusive slice range. `page_count` is always at least 1,
    even when `total` is 0, so a page label can always be rendered.
    """
    page_size = max(1, page_size)
    page_count = max(1, (total + page_size - 1) // page_size)
    clamped_page = max(0, min(page, page_count - 1))
    start = clamped_page * page_size
    end = min(start + page_size, total)
    return clamped_page, page_count, start, end
