from enum import Enum
import os

from utils.translations import I18N

_ = I18N._


class AppInfo:
    SERVICE_NAME = "MyPersonalApplicationsService"
    APP_IDENTIFIER = "Spracherwerb"


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
        # Lazy import to avoid circular dependency
        from utils.translations import I18N
        
        # Map language codes to their display names
        lang_name_map = {
            cls.ENGLISH.value: I18N._("English"),
            cls.GERMAN.value: I18N._("German"),
            cls.FRENCH.value: I18N._("French"),
            cls.SPANISH.value: I18N._("Spanish"),
            cls.ITALIAN.value: I18N._("Italian"),
            cls.LATIN.value: I18N._("Latin"),
        }
        
        return lang_name_map.get(lang_code, lang_code)  # Return the code if no translation is available
    
    @classmethod
    def get_language_code(cls, lang_name):
        """Convert a language name to its language code."""
        # Lazy import to avoid circular dependency
        from utils.translations import I18N
        
        # Create a mapping of translated names to codes
        lang_map = {
            I18N._("English"): cls.ENGLISH.value,
            I18N._("German"): cls.GERMAN.value,
            I18N._("French"): cls.FRENCH.value,
            I18N._("Spanish"): cls.SPANISH.value,
            I18N._("Italian"): cls.ITALIAN.value,
            I18N._("Latin"): cls.LATIN.value,
        }
        return lang_map.get(lang_name, lang_name)  # Return the code if found, otherwise return the input


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
    TRACK_CONTEXT_PRIOR = "track_context_prior"
    TRACK_CONTEXT_POST = "track_context_post"
    PLAYLIST_CONTEXT = "playlist_context"
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
        elif self == Topic.TRACK_CONTEXT_PRIOR:
            return _("more about the next track")
        elif self == Topic.TRACK_CONTEXT_POST:
            return _("more about the last track")
        elif self == Topic.PLAYLIST_CONTEXT:
            return _("more about our playlist")
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
    CONTROL_NET = "control_net"
    IP_ADAPTER = "ip_adapter"
    RENOISER = "renoiser"
    LAST_SETTINGS = "last_settings"
    CANCEL = "cancel"
    REVERT_TO_SIMPLE_GEN = "revert_to_simple_gen"

    def __str__(self):
        return self.value

    @staticmethod
    def get(name):
        for key, value in ImageGenerationType.__members__.items():
            if str(value) == name:
                return value
        raise Exception(f"Not a valid prompt mode: {name}")

    @staticmethod
    def members():
        return [str(value) for key, value in ImageGenerationType.__members__.items()]

