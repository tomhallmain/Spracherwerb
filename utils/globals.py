from enum import Enum
import os

from utils.translations import _


class AppInfo:
    SERVICE_NAME = "MyPersonalApplicationsService"
    APP_IDENTIFIER = "Spracherwerb"
    #: Identifiers this app has used before. Key material is filed per
    #: identifier, so a rename orphans the old keys and everything encrypted
    #: under them -- an old name listed here keeps scripts/key_material.py
    #: reporting and backing it up.
    LEGACY_APP_IDENTIFIERS = ()


class Globals:
    HOME = os.path.expanduser("~")
    DELAY_TIME_SECONDS = 5
    DEFAULT_VOLUME_THRESHOLD = 60

    @classmethod
    def set_delay(cls, delay=5):
        cls.DELAY_TIME_SECONDS = int(delay)

    @classmethod
    def set_volume(cls, volume=60):
        cls.DEFAULT_VOLUME_THRESHOLD = int(volume)

class Language(Enum):
    """Supported languages with ISO 639-1 language codes as values."""
    ENGLISH = "en"
    GERMAN = "de"
    FRENCH = "fr"
    SPANISH = "es"
    ITALIAN = "it"
    LATIN = "la"
    
    @classmethod
    def get_all_codes(cls):
        """Get a list of all language codes."""
        return [lang.value for lang in cls]
    
    @classmethod
    def from_code(cls, code):
        """Get Language enum member from language code."""
        for lang in cls:
            if lang.value == code:
                return lang
        return None
    
    @classmethod
    def is_supported(cls, code):
        """Check if a language code is supported."""
        return cls.from_code(code) is not None
    
    @classmethod
    def get_language_name(cls, lang_code):
        """Convert a language code to its display name in the current locale."""
        # Map language codes to their display names
        lang_name_map = {
            cls.ENGLISH.value: _("English"),
            cls.GERMAN.value: _("German"),
            cls.FRENCH.value: _("French"),
            cls.SPANISH.value: _("Spanish"),
            cls.ITALIAN.value: _("Italian"),
            cls.LATIN.value: _("Latin"),
        }
        
        return lang_name_map.get(lang_code, lang_code)  # Return the code if no translation is available
    
    @classmethod
    def get_language_code(cls, lang_name):
        """Convert a language name to its language code."""
        # Create a mapping of translated names to codes
        lang_map = {
            _("English"): cls.ENGLISH.value,
            _("German"): cls.GERMAN.value,
            _("French"): cls.FRENCH.value,
            _("Spanish"): cls.SPANISH.value,
            _("Italian"): cls.ITALIAN.value,
            _("Latin"): cls.LATIN.value,
        }
        return lang_map.get(lang_name, lang_name)  # Return the code if found, otherwise return the input


class TranslationSortOrder(Enum):
    """Sort options for the translations listing window."""
    DATE_ADDED_NEWEST = "date_added_newest"
    DATE_ADDED_OLDEST = "date_added_oldest"
    SOURCE_TEXT = "source_text"
    TRANSLATED_TEXT = "translated_text"

    def label(self):
        if self == TranslationSortOrder.DATE_ADDED_NEWEST:
            return "Date Added (Newest)"
        if self == TranslationSortOrder.DATE_ADDED_OLDEST:
            return "Date Added (Oldest)"
        if self == TranslationSortOrder.SOURCE_TEXT:
            return "Source Text"
        if self == TranslationSortOrder.TRANSLATED_TEXT:
            return "Translated Text"
        raise ValueError(f"unhandled translation sort order: {self}")

    @classmethod
    def members_in_order(cls):
        return list(cls)

    @classmethod
    def default(cls):
        return cls.DATE_ADDED_NEWEST

    @classmethod
    def from_combo_index(cls, index):
        members = cls.members_in_order()
        if 0 <= index < len(members):
            return members[index]
        return cls.default()

    def combo_index(self):
        return self.members_in_order().index(self)

    @classmethod
    def from_cache(cls, value):
        """Restore from app_info_cache, accepting legacy int combo indices."""
        if value is None:
            return cls.default()
        if isinstance(value, int):
            return cls.from_combo_index(value)
        if isinstance(value, str):
            for member in cls:
                if member.value == value:
                    return member
        return cls.default()

    def apply_to(self, translations):
        if self == TranslationSortOrder.DATE_ADDED_NEWEST:
            translations.sort(key=lambda x: x['datetime'], reverse=True)
        elif self == TranslationSortOrder.DATE_ADDED_OLDEST:
            translations.sort(key=lambda x: x['datetime'])
        elif self == TranslationSortOrder.SOURCE_TEXT:
            translations.sort(key=lambda x: x['source_text'].lower())
        elif self == TranslationSortOrder.TRANSLATED_TEXT:
            translations.sort(key=lambda x: (
                x.get('target_article', '').lower(),
                x.get('translated_text', '').lower(),
            ))
        else:
            raise ValueError(f"unhandled translation sort order: {self}")


class MediaFileType(Enum):
    MKV = '.MKV'
    MP4 = '.MP4'
    MOV = '.MOV'
    WEBM = '.WEBM'
    FLV = '.FLV'
    AVI = '.AVI'
    WMV = '.WMV'
    VOB = '.VOB'
    MPG = '.MPG'
    ASF = '.ASF'
    MP3 = '.MP3'
    OGG = '.OGG'
    AAC = '.AAC'
    FLAC = '.FLAC'
    ALAC = '.ALAC'
    WAV = '.WAV'
    AIFF = '.AIFF'
    TTA = '.TTA'
    M4A = '.M4A'
    MP2 = '.MP2'
    MP1 = '.MP1'
    AU = '.AU'
    S3M = '.S3M'
    IT = '.IT'
    XM = '.XM'
    MOD = '.MOD'
    MIDI = '.MIDI'
    MID = '.MID'
    WMA = '.WMA'
    OGG_OPUS = '.OGG_OPUS'
    WEBM_VP8 = '.WEBM_VP8'
    OPUS = '.OPUS'

    @classmethod
    def is_media_filetype(cls, filename):
        f = filename.upper()
        for e in cls:
            if f.endswith(e.value):
                return True
        return False



class Topic(Enum):
    WEATHER = "weather"
    NEWS = "news"
    HACKERNEWS = "hackernews"
    JOKE = "joke"
    FACT = "fact"
    FABLE = "fable"
    TRUTH_AND_LIE = "truth_and_lie"
    APHORISM = "aphorism"
    POEM = "poem"
    QUOTE = "quote"
    TONGUE_TWISTER = "tongue_twister"
    MOTIVATION = "motivation"
    CALENDAR = "calendar"
    RANDOM_WIKI_ARTICLE = "random_wiki_article"
    FUNNY_STORY = "funny_story"
    LANGUAGE_LEARNING = "language_learning"

    def translate(self):
        if self == Topic.WEATHER:
            return _("weather")
        elif self == Topic.NEWS:
            return _("news")
        elif self == Topic.HACKERNEWS:
            return "hacker news"
        elif self == Topic.JOKE:
            return _("joke")
        elif self == Topic.FACT:
            return _("fact")
        elif self == Topic.FABLE:
            return _("fable")
        elif self == Topic.TRUTH_AND_LIE:
            return _("truth and lie")
        elif self == Topic.APHORISM:
            return _("aphorism")
        elif self == Topic.POEM:
            return _("poem")
        elif self == Topic.QUOTE:
            return _("quote")
        elif self == Topic.TONGUE_TWISTER:
            return _("tongue twister")
        elif self == Topic.MOTIVATION:
            return _("motivation")
        elif self == Topic.CALENDAR:
            return _("calendar")
        elif self == Topic.RANDOM_WIKI_ARTICLE:
            return _("random wiki article")
        elif self == Topic.FUNNY_STORY:
            return _("funny story")
        elif self == Topic.LANGUAGE_LEARNING:
            return  _("language learning")
        else:
            raise Exception(f"unhandled topic: {self}")

    def get_prompt_topic_value(self):
        if self == Topic.HACKERNEWS:
            return "news"
        return str(self.value)


class ImageGenerationType(Enum):
    REDO_PROMPT = "redo_prompt"
    TAKE_PROMPT = "take_prompt"
    CONTROL_NET = "control_net"
    IP_ADAPTER = "ip_adapter"
    RENOISER = "renoiser"
    IMG2IMG = "img2img"
    IMAGE_EDIT = "image_edit"
    LAST_SETTINGS = "last_settings"
    CANCEL = "cancel"
    REVERT_TO_SIMPLE_GEN = "revert_to_simple_gen"

    def __str__(self):
        return self.value

    def get_text(self):
        if self == ImageGenerationType.REDO_PROMPT:
            return _("Redo Prompt")
        elif self == ImageGenerationType.TAKE_PROMPT:
            return _("Take Prompt")
        elif self == ImageGenerationType.CONTROL_NET:
            return _("Control Net")
        elif self == ImageGenerationType.IP_ADAPTER:
            return _("IP Adapter")
        elif self == ImageGenerationType.RENOISER:
            return _("Renoiser")
        elif self == ImageGenerationType.IMG2IMG:
            return _("Image to Image")
        elif self == ImageGenerationType.IMAGE_EDIT:
            return _("Image Edit")
        elif self == ImageGenerationType.LAST_SETTINGS:
            return _("Last Settings")
        elif self == ImageGenerationType.CANCEL:
            return _("Cancel")
        elif self == ImageGenerationType.REVERT_TO_SIMPLE_GEN:
            return _("Revert to Simple Generation")
        raise Exception("Unhandled image generation type text: " + str(self))

    @staticmethod
    def get(name):
        if isinstance(name, ImageGenerationType):
            return name

        for key, value in ImageGenerationType.__members__.items():
            if value.name == name or value.value == name or value.get_text() == name:
                return value
        raise Exception(f"Not a valid image generation mode: {name}")

    @staticmethod
    def members():
        return [value.name for key, value in ImageGenerationType.__members__.items()]


