"""The interaction log shows plain-text messages as written, never as markup."""

import pytest

from ui.interaction_panel import InteractionPanel


@pytest.fixture
def widget(qapp):
    panel = InteractionPanel()
    yield panel
    panel.deleteLater()


def test_angle_brackets_and_ampersands_are_shown_literally(widget):
    widget.append_message("Agent", "Stellung: <Verb> am Ende & <b>nicht</b> fett")

    assert "Stellung: <Verb> am Ende & <b>nicht</b> fett" in widget.log_area.toPlainText()


def test_newlines_still_become_line_breaks(widget):
    widget.append_message("Agent", "erste Zeile\nzweite Zeile")

    lines = widget.log_area.toPlainText().splitlines()
    assert "erste Zeile" in lines
    assert "zweite Zeile" in lines


def test_is_html_content_is_rendered_as_markup(widget):
    widget.append_message("Agent", "<i>kursiv</i>", is_html=True)

    assert "<i>" not in widget.log_area.toPlainText()
    assert "kursiv" in widget.log_area.toPlainText()
