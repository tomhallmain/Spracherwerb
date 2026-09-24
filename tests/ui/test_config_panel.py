"""Config panel combo boxes show translated labels but store locale-independent values."""

import pytest

import ui.config_panel as config_panel_module
from ui.config_panel import ACTIVITY_MODES, PROFICIENCY_LEVELS, ConfigPanel


def fake_translate(msgid):
    """Stands in for a non-English locale, so a label is never its own msgid."""
    return f"<{msgid}>"


@pytest.fixture
def panel(qapp, monkeypatch):
    monkeypatch.setattr(config_panel_module, "_", fake_translate)
    widget = ConfigPanel()
    yield widget
    widget.deleteLater()


def combo_labels(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_proficiency_labels_are_translated_when_the_combo_is_filled(panel):
    assert combo_labels(panel.level_combo) == [
        fake_translate(label) for label, _level in PROFICIENCY_LEVELS
    ]


@pytest.mark.parametrize("level", ["beginner", "intermediate", "advanced"])
def test_selecting_a_level_stores_its_value_not_its_label(panel, level):
    target = panel.level_combo.findData(level)
    # Start elsewhere so the change signal fires even for the configured level.
    panel.level_combo.setCurrentIndex((target + 1) % panel.level_combo.count())
    panel.level_combo.setCurrentIndex(target)

    assert config_panel_module.config.proficiency_level == level


@pytest.mark.parametrize("level", ["beginner", "advanced"])
def test_the_configured_level_is_selected_on_open(qapp, monkeypatch, level):
    monkeypatch.setattr(config_panel_module, "_", fake_translate)
    monkeypatch.setattr(config_panel_module.config, "proficiency_level", level)
    widget = ConfigPanel()
    try:
        assert widget.level_combo.currentData() == level
    finally:
        widget.deleteLater()


def test_mode_labels_are_translated_and_carry_activity_type_values(panel):
    assert combo_labels(panel.mode_combo) == [
        fake_translate(label) for label, _activity_type in ACTIVITY_MODES
    ]
    assert [panel.mode_combo.itemData(i) for i in range(panel.mode_combo.count())] == [
        activity_type.value for _label, activity_type in ACTIVITY_MODES
    ]
