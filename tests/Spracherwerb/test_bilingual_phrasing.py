from Spracherwerb.bilingual_phrasing import bilingual_phrase

PHRASEBOOK = {
    'de': {'greet': 'Hallo, {name}!'},
}


class TestBilingualPhrase:
    def test_prefixes_the_target_language_template(self):
        result = bilingual_phrase('de', PHRASEBOOK, 'greet', 'Hello, Sam!', name='Sam')
        assert result == 'Hallo, Sam! (Hello, Sam!)'

    def test_falls_back_to_english_when_language_has_no_entry(self):
        result = bilingual_phrase('la', PHRASEBOOK, 'greet', 'Hello, Sam!', name='Sam')
        assert result == 'Hello, Sam!'

    def test_falls_back_to_english_when_key_has_no_entry(self):
        result = bilingual_phrase('de', PHRASEBOOK, 'farewell', 'Goodbye!')
        assert result == 'Goodbye!'

    def test_language_code_with_region_uses_primary_tag(self):
        result = bilingual_phrase('de-DE', PHRASEBOOK, 'greet', 'Hello, Sam!', name='Sam')
        assert result == 'Hallo, Sam! (Hello, Sam!)'
