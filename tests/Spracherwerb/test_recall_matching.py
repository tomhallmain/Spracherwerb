from Spracherwerb.recall_matching import check_recall_answer, resolve_recall_direction


class TestResolveRecallDirection:
    def test_beginner_recalls_source(self):
        assert resolve_recall_direction("beginner") == "recall_source"

    def test_beginner_is_case_insensitive(self):
        assert resolve_recall_direction("Beginner") == "recall_source"

    def test_intermediate_and_advanced_produce_target(self):
        assert resolve_recall_direction("intermediate") == "produce_target"
        assert resolve_recall_direction("advanced") == "produce_target"

    def test_unknown_level_defaults_to_produce_target(self):
        assert resolve_recall_direction("") == "produce_target"
        assert resolve_recall_direction(None) == "produce_target"


class TestCheckRecallAnswer:
    ENTRY = {"source_text": "dog", "translated_text": "Hund", "target_article": "der"}

    def test_produce_target_accepts_bare_word(self):
        is_correct, expected = check_recall_answer(self.ENTRY, "hund", "de", "produce_target")
        assert is_correct is True
        assert expected == "der Hund"

    def test_produce_target_accepts_articled_word(self):
        is_correct, _expected = check_recall_answer(self.ENTRY, "der Hund", "de", "produce_target")
        assert is_correct is True

    def test_produce_target_rejects_wrong_answer(self):
        is_correct, expected = check_recall_answer(self.ENTRY, "Katze", "de", "produce_target")
        assert is_correct is False
        assert expected == "der Hund"

    def test_recall_source_accepts_any_comma_separated_gloss(self):
        entry = {"source_text": "to go, to walk", "translated_text": "gehen"}
        is_correct, expected = check_recall_answer(entry, "to walk", "de", "recall_source")
        assert is_correct is True
        assert expected == "to go, to walk"

    def test_recall_source_rejects_wrong_answer(self):
        is_correct, _expected = check_recall_answer(self.ENTRY, "cat", "de", "recall_source")
        assert is_correct is False
