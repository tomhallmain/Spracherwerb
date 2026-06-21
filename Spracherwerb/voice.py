import datetime
import traceback

from utils.config import config
from utils.logging_setup import get_logger

logger = get_logger(__name__)

tts_runner_imported = False

try:
    from tts.tts_runner import TextToSpeechRunner, tts_available
    tts_runner_imported = True and tts_available and not config.disable_tts
except Exception as e:
    logger.error(str(e))
    logger.warning("Failed to import tts_runner.")

class Voice:
    MULTI_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self, coqui_named_voice="Royston Min", run_context=None):
        self.can_speak = tts_runner_imported and not config.disable_tts
        self._coqui_named_voice = coqui_named_voice
        self.model_args = (Voice.MULTI_MODEL, self._coqui_named_voice, "en")
        self.run_context = run_context
        if self.can_speak:
            self._tts = TextToSpeechRunner(self.model_args,
                                           filepath="muse_voice",
                                           delete_interim_files=False,
                                           auto_play=False,
                                           run_context=self.run_context)
        else:
            self._tts = None
            if config.disable_tts:
                logger.warning("TTS is disabled in config. Voice functionality will be limited.")
            else:
                logger.warning("TTS is not available. Voice functionality will be limited.")

    def say(self, text="", topic="", save_mp3=False, locale=None):
        # Say immediately
        if not self.can_speak or self._tts is None:
            logger.warning("Cannot speak.")
            return
        logger.info(f"Saying: {text}")
        temp_tts = TextToSpeechRunner(self.model_args, filepath="muse_voice", overwrite=True, run_context=self.run_context)
        current_time_str = str(datetime.datetime.now().timestamp())
        if "." in current_time_str:
            current_time_str = current_time_str.split(".")[0]
        self._tts.set_output_path(topic + "_" + current_time_str + "_")
        try:
            return temp_tts.speak(text, save_mp3=save_mp3, locale=locale)
        except Exception as e:
            logger.error(str(e))
            traceback.print_exc()

    def prepare_to_say(self, text="", topic="", save_mp3=False, save_for_last=False, locale=None):
        # Generate speech files from text, but don't play them yet
        if not self.can_speak or self._tts is None:
            logger.warning("Cannot speak.")
            return
        logger.info(f"Preparing to say: {text}")
        if save_for_last:
            self._tts.await_pending_speech_jobs(run_jobs=False)
        current_time_str = str(datetime.datetime.now().timestamp())
        if "." in current_time_str:
            current_time_str = current_time_str.split(".")[0]
        self._tts.set_output_path(topic + "_" + current_time_str + "_")
        try:
            return self._tts.speak(text, save_mp3=save_mp3, locale=locale)
        except Exception as e:
            logger.error(str(e))
            traceback.print_exc()

    def finish_speaking(self):
        if not self.can_speak or self._tts is None:
            logger.warning("Cannot speak.")
            return
        self._tts.await_pending_speech_jobs()

    def add_speech_file_to_queue(self, filepath):
        if not self.can_speak or self._tts is None:
            logger.warning("Cannot speak.")
            return
        self._tts.add_speech_file_to_queue(filepath)

    def set_language(self, language_code: str) -> None:
        self._language_code = language_code

    def set_speed(self, speed: float) -> None:
        self._speech_speed = speed

    def generate_speech(self, text: str, topic: str = "learning"):
        if not text or not self.can_speak:
            return None
        locale = getattr(self, "_language_code", None)
        return self.prepare_to_say(text, topic=topic, save_mp3=True, locale=locale)

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def cleanup(self) -> None:
        if self.can_speak and self._tts is not None:
            self.finish_speaking()


