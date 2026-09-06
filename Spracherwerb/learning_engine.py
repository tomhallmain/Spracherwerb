from typing import Optional, Dict, Any, List
import time
import logging

from extensions.gutenberg import Gutenberg
from extensions.languagetool import LanguageTool
from extensions.llm import LLM
from extensions.sd_runner_client import SDRunnerClient
from extensions.wordreference import WordReference
from utils.config import config
from utils.vocabulary_pool import VocabularyPool

from .activity_registry import ActivityRegistry
from .activity_results import ModuleServices
from .activity_types import ActivityType
from .media_generation import MediaGenerationService
from .voice import Voice
from .prompter import Prompter
from .session_context import SessionContext, UserAction
from .session_config import SessionConfig

logger = logging.getLogger(__name__)


class LearningEngine:
    """Routes learning activities to registered module implementations."""

    def __init__(
        self,
        session_config: SessionConfig,
        session_state: SessionContext,
        registry: ActivityRegistry | None = None,
        vocabulary_pool: VocabularyPool | None = None,
    ):
        self.config = session_config
        self.state = session_state
        self.registry = registry or ActivityRegistry
        self.vocabulary_pool = vocabulary_pool or VocabularyPool()
        self.voice = Voice()
        self.prompter = Prompter()
        self.sd_client = SDRunnerClient()
        # Owns the generation worker for this session. Modules hand it requests
        # rather than calling sd_client directly, so a slow picture holds up at
        # most the item being asked about.
        self.media = MediaGenerationService(sd_client=self.sd_client)
        self.llm = LLM.from_config()
        self.word_reference = WordReference()
        self.language_tool = LanguageTool(api_key=config.api_keys.get("languagetool"))
        self.gutenberg = Gutenberg()
        self.current_activity: Optional[str] = None
        self.current_module = None
        self.activity_results: Dict[str, Any] = {}
        self._setup_voice()

    def _setup_voice(self) -> None:
        self.voice.set_language(self.config.target_language)
        self.voice.set_speed(1.0)

    def _services(self) -> ModuleServices:
        return ModuleServices(
            prompter=self.prompter,
            voice=self.voice,
            session_config=self.config,
            session_context=self.state,
            vocabulary_pool=self.vocabulary_pool,
            sd_client=self.sd_client,
            media=self.media,
            llm=self.llm,
            word_reference=self.word_reference,
            language_tool=self.language_tool,
            gutenberg=self.gutenberg,
        )

    def _maybe_generate_voice(self, text: str) -> Optional[str]:
        if not text or not self.config.enable_pronunciation_practice:
            return None
        return self.voice.generate_speech(text, topic=self.current_activity or "learning")

    def start_activity(self, activity_type: str) -> Dict[str, Any]:
        if not self.state.is_active():
            raise Exception("Cannot start activity in inactive session")

        resolved_type = ActivityType.from_value(activity_type)
        module = self.registry.create(resolved_type)
        services = self._services()

        self.current_activity = activity_type
        self.current_module = module
        self.state.set_current_activity(activity_type)
        self.activity_results = {
            "start_time": time.time(),
            "activity_type": activity_type,
            "responses": [],
            "media_generated": [],
        }

        start_result = module.start(services)
        if start_result.voice_response is None:
            start_result.voice_response = self._maybe_generate_voice(start_result.text_response)

        payload = start_result.to_dict()
        payload["config"] = self.config.to_dict()
        return payload

    def process_user_response(self, response: str) -> Dict[str, Any]:
        if not self.current_activity or self.current_module is None:
            raise Exception("No active activity to process response for")

        services = self._services()
        turn_result = self.current_module.handle_response(response, services)
        if turn_result.voice_response is None:
            turn_result.voice_response = self._maybe_generate_voice(turn_result.text_response)

        self.activity_results["responses"].append(
            {
                "user_input": response,
                "system_response": turn_result.text_response,
                "timestamp": time.time(),
                "is_complete": turn_result.is_complete,
            }
        )
        if turn_result.media_path:
            self.activity_results["media_generated"].append(turn_result.media_path)

        return turn_result.to_dict()

    def generate_media(self, content: str) -> Optional[str]:
        if not self.config.enable_visual_learning:
            return None
        # Media generation will be centralized in a dedicated service (Phase 4 modules).
        return None

    def complete_activity(self) -> Dict[str, Any]:
        if not self.current_activity or self.current_module is None:
            raise Exception("No active activity to complete")

        services = self._services()
        module_results = self.current_module.complete(services)
        self.activity_results["module_results"] = module_results
        for key, value in module_results.items():
            if key not in self.activity_results:
                self.activity_results[key] = value

        self.activity_results["end_time"] = time.time()
        self.activity_results["duration"] = (
            self.activity_results["end_time"] - self.activity_results["start_time"]
        )

        self.state.complete_activity(self.current_activity, self.activity_results)

        self.current_activity = None
        self.current_module = None
        results = self.activity_results.copy()
        self.activity_results = {}
        return results

    def handle_user_action(self, action: UserAction) -> None:
        self.state.update_action(action)

        if action == UserAction.PAUSE:
            self.voice.pause()
        elif action == UserAction.RESUME:
            self.voice.resume()
        elif action == UserAction.SKIP_ACTIVITY:
            self.complete_activity()

    def cleanup(self) -> None:
        self.voice.cleanup()
        self.media.shutdown()
        self.current_activity = None
        self.current_module = None
        self.activity_results = {}
