"""Language tutor management for the Spracherwerb application."""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import time

from extensions.llm import LLMResult
from tts.speakers import speakers
from utils.config import config
from utils.utils import Utils
from utils.translations import I18N
from utils.logging_setup import get_logger

_ = I18N._

logger = get_logger(__name__)

@dataclass
class LanguageTutor:
    """Represents a language tutor with their characteristics and teaching style."""
    name: str
    voice_name: str
    gender: str
    teaching_style: str
    characteristics: List[str]
    system_prompt: str
    context: Optional[List[int]] = None
    native_language: str = "English"
    language_code: str = "en"
    last_greeting_time: Optional[float] = None
    last_farewell_time: Optional[float] = None
    avatar_paths: Optional[List[str]] = None
    is_mock: bool = False

    def __post_init__(self):
        if self.context is None:
            self.context = []
        if self.characteristics is None:
            self.characteristics = []
        if not hasattr(self, "is_mock"):
            self.is_mock = False
            
        # Validate language code
        valid_language_codes = ["en", "de", "es", "fr", "it", "ja", "ko", "zh"]
        if self.language_code not in valid_language_codes:
            raise ValueError(f"Invalid language code: {self.language_code}. Must be one of {valid_language_codes}")
        
        if self.voice_name not in speakers:
            try: 
                for speaker in speakers:
                    if Utils.is_similar_strings(speaker, self.voice_name):
                        logger.warning(f"Found similar voice name \"{self.voice_name}\", using valid speaker name \"{speaker}\" instead")
                        self.voice_name = speaker
                        break
            except Exception as e:
                logger.error(f"Error validating voice name: {e}")
                raise ValueError(f"Invalid voice name: {self.voice_name}. Must be one of {list(speakers.keys())}")
        
        if self.avatar_paths is not None:
            test_paths = list(self.avatar_paths)
            for path in test_paths:
                if not Path(path).exists():
                    test_paths.remove(path)
                    logger.warning(f"Avatar path \"{path}\" does not exist, removing it")
            if len(test_paths) == 0:
                logger.error(f"No valid avatar paths found for tutor \"{self.name}\", using default avatar")
                self.avatar_paths = None
            else:
                self.avatar_paths = test_paths

    def update_context(self, new_context: List[int]) -> None:
        """Update the context with a new list of integers."""
        old_context_len = len(self.context) if self.context else 0
        self.context = new_context
        # Update last farewell time whenever the tutor speaks
        self.set_last_farewell_time()
        logger.info(f"Updated context for {self.name}: {old_context_len} -> {len(new_context)} tokens")

    def set_last_farewell_time(self) -> None:
        """Set the last farewell time to the current time."""
        old_time = self.last_farewell_time
        self.last_farewell_time = time.time()
        if old_time:
            logger.info(f"Updated last farewell time for {self.name}: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(old_time))} -> {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_farewell_time))}")
        else:
            logger.info(f"Set initial farewell time for {self.name}: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_farewell_time))}")

    def get_context(self) -> List[int]:
        """Get the current context."""
        logger.info(f"Retrieved context for {self.name}: {len(self.context)} tokens")
        return self.context

    def get_gender(self) -> str:
        if self.gender is None or self.gender.upper() == "M":
            return _("a man")
        elif self.gender.upper() == "F" or self.gender.upper() == "W":
            return _("a woman")
        else:
            return self.gender

    def get_avatar_paths(self) -> Optional[List[str]]:
        return self.avatar_paths if hasattr(self, "avatar_paths") else None

    def update_from_dict(self, new_data: 'LanguageTutor', refresh_context=False) -> None:
        """Update the tutor from a new LanguageTutor object."""
        for key, value in new_data.__dict__.items():
            if key == "context" and not refresh_context:
                # Context needs to be preserved
                continue
            current_value = getattr(self, key)
            if current_value != value:
                setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the tutor to a dictionary for serialization."""
        logger.info(f"Serializing {self.name} tutor with {len(self.context)} tokens of context")
        return {
            "name": self.name,
            "voice_name": self.voice_name,
            "gender": self.gender,
            "teaching_style": self.teaching_style,
            "characteristics": self.characteristics,
            "system_prompt": self.system_prompt,
            "context": self.context,
            "native_language": self.native_language,
            "language_code": self.language_code,
            "last_greeting_time": self.last_greeting_time,
            "last_farewell_time": self.last_farewell_time
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LanguageTutor':
        """Create a tutor from a dictionary."""
        context_len = len(data.get("context", []))
        logger.info(f"Deserializing {data['name']} tutor with {context_len} tokens of context")
        return cls(
            name=data["name"],
            voice_name=data["voice_name"],
            gender=data["gender"],
            teaching_style=data["teaching_style"],
            characteristics=data["characteristics"],
            system_prompt=data["system_prompt"],
            context=data.get("context"),
            native_language=data.get("native_language", "English"),
            language_code=data.get("language_code", "en"),
            last_greeting_time=data.get("last_greeting_time"),
            last_farewell_time=data.get("last_farewell_time")
        )


class LanguageTutorManager:
    """Manages language tutors and their loading/saving."""
    
    def __init__(self):
        self.tutors: Dict[str, LanguageTutor] = {}
        self.current_tutor: Optional[LanguageTutor] = None
        self.allow_mock_tutors = False
        self._load_tutors()

    def _load_tutors(self):
        """Load tutors from the config JSON file."""
        try:
            print(f"Loading tutors from config, count = {len(config.language_tutors)}")
            for tutor_data in config.language_tutors:
                tutor = LanguageTutor.from_dict(tutor_data)
                if tutor.voice_name not in self.tutors:
                    self.tutors[tutor.voice_name] = tutor
                else:
                    logger.warning(f"Tutor already exists, skipping: {tutor.voice_name}")
        except Exception as e:
            logger.error(f"Error loading tutors: {e}")
        
        if len(self.tutors) == 0:
            self._create_default_tutors()
        
        self.current_tutor = self.tutors[list(self.tutors.keys())[0]]

    def reload_tutors(self):
        """Reload tutors from the config JSON file."""
        try:
            logger.info(f"Reloading tutors from config, count = {len(config.language_tutors)}")
            for tutor_data in config.language_tutors:
                tutor_new = LanguageTutor.from_dict(tutor_data)
                if tutor_new.voice_name not in self.tutors:
                    self.tutors[tutor_new.voice_name] = tutor_new
                else:
                    self.tutors[tutor_new.voice_name].update_from_dict(
                        tutor_new, refresh_context=config.language_tutor_refresh_context)
            # Remove mock tutors
            for name, tutor in self.tutors.items():
                if tutor.is_mock:
                    logger.warning(f"Removing mock tutor: {name}")
                    del self.tutors[name]
        except Exception as e:
            logger.error(f"Error reloading tutors: {e}")

    def _create_default_tutors(self):
        """Create default tutors if none exist."""
        default_tutors = [
            {
                "name": "Professor Schmidt",
                "voice_name": "Professor Schmidt",
                "gender": "M",
                "teaching_style": "structured and methodical",
                "characteristics": [
                    "expert in German language and culture",
                    "patient and encouraging",
                    "focuses on grammar and pronunciation",
                    "uses real-world examples"
                ],
                "system_prompt": "You are Professor Schmidt, a dedicated language teacher with expertise in German language and culture. Your teaching style is structured and methodical, with a focus on clear explanations and practical examples. You are patient and encouraging, always ready to help students understand complex concepts. You excel at breaking down grammar rules and pronunciation patterns, making them accessible to learners of all levels. Your lessons often incorporate cultural context and real-world usage examples.",
                "native_language": "German",
                "language_code": "de"
            },
            {
                "name": "Madame Dubois",
                "voice_name": "Madame Dubois",
                "gender": "F",
                "teaching_style": "engaging and conversational",
                "characteristics": [
                    "native French speaker",
                    "emphasizes conversation skills",
                    "uses cultural immersion techniques",
                    "adapts to student's learning style"
                ],
                "system_prompt": "You are Madame Dubois, a passionate French language teacher who believes in learning through conversation and cultural immersion. Your teaching style is engaging and conversational, focusing on practical communication skills. You adapt your approach to each student's learning style and needs. Your lessons often include cultural insights, idiomatic expressions, and real-life scenarios. You encourage students to think in French and express themselves naturally.",
                "native_language": "French",
                "language_code": "fr"
            },
            {
                "name": "Sensei Tanaka",
                "voice_name": "Sensei Tanaka",
                "gender": "M",
                "teaching_style": "traditional and precise",
                "characteristics": [
                    "expert in Japanese language and culture",
                    "emphasizes proper form and respect",
                    "uses mnemonics and visual aids",
                    "incorporates cultural context"
                ],
                "system_prompt": "You are Sensei Tanaka, a traditional Japanese language teacher who emphasizes proper form, respect, and cultural understanding. Your teaching style is precise and methodical, with a strong focus on correct pronunciation and writing. You use mnemonics and visual aids to help students remember complex characters and grammar patterns. Your lessons always include cultural context and proper etiquette. You believe that language learning is inseparable from cultural understanding.",
                "native_language": "Japanese",
                "language_code": "ja"
            }
        ]
        
        # Create the configs directory if it doesn't exist
        Path("configs").mkdir(exist_ok=True)

        # Load the default tutors
        for tutor_data in default_tutors:
            tutor = LanguageTutor.from_dict(tutor_data)
            self.tutors[tutor.voice_name] = tutor

    def get_tutor(self, voice_name: str) -> Optional[LanguageTutor]:
        """Get a tutor by voice name."""
        tutor = self.tutors.get(voice_name)
        if tutor:
            return tutor
        else:
            if hasattr(self, "allow_mock_tutors") and self.allow_mock_tutors:
                logger.warning(f"Mock tutor not found, creating new: {voice_name}")
                tutor = LanguageTutor(
                    name=voice_name,
                    voice_name=voice_name,
                    gender="M",
                    teaching_style="neutral",
                    characteristics=[],
                    system_prompt="",
                    native_language="English",
                    language_code="en"
                )
                self.tutors[voice_name] = tutor
                return tutor
            else:
                logger.error(f"Tutor not found: {voice_name}")
                return None

    def set_current_tutor(self, voice_name: str) -> Optional[LanguageTutor]:
        """Set the current tutor by voice name."""
        tutor = self.get_tutor(voice_name)
        if tutor:
            self.current_tutor = tutor
        return tutor

    def get_current_tutor(self) -> Optional[LanguageTutor]:
        """Get the current tutor."""
        return self.current_tutor

    def update_context(self, llm_result: Optional[LLMResult]):
        """Update the current tutor's context with new context from LLM response."""
        if self.current_tutor:
            if llm_result:
                if llm_result.context_provided:
                    self.current_tutor.update_context(llm_result.context)
                else:
                    # Update last farewell time whenever the tutor speaks
                    self.current_tutor.set_last_farewell_time()

    def get_context_and_system_prompt(self) -> Tuple[List[int], str]:
        """Get the current tutor's context and system prompt."""
        try:
            return (
                self.current_tutor.get_context() if self.current_tutor else [],
                self.current_tutor.system_prompt if self.current_tutor else None
            ) 
        except Exception as e:
            logger.error(f"Error getting context and system prompt: {e}")
            return ([], None) 