from enum import Enum
import os

from utils.translations import I18N

_ = I18N._


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

