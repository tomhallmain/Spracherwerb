import json
import os
import sys

from utils.utils import Utils

root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
configs_dir = os.path.join(root_dir, "configs")
library_data_dir = os.path.join(root_dir, "library_data", "data")


class Config:
    CONFIGS_DIR_LOC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs")

    def __init__(self):
        self.dict = {}
        self.foreground_color = "white"
        self.background_color = "#2596BE"
        
        # Language learning configuration
        self.target_language = "German"
        self.proficiency_level = "intermediate"  # beginner, intermediate, advanced
        self.learning_focus = ["vocabulary", "grammar", "conversation"]  # List of focus areas
        self.daily_goal_minutes = 30
        self.enable_visual_learning = True
        self.enable_pronunciation_practice = True
        self.save_tts_output_topics = []
        
        # LLM and TTS configuration
        self.llm_model_name = "deepseek-r1:14b"

        self.text_cleaner_ruleset = []
        self.coqui_tts_location = ""
        self.coqui_tts_model = ("tts_models/multilingual/multi-dataset/xtts_v2", "Royston Min", "en")
        self.max_chunk_tokens = 200
        
        # Learning content configuration
        self.prompts_directory = "prompts"
        self.text_cleaner_ruleset = []
        self.vocabulary_difficulty = "medium"  # easy, medium, hard
        self.grammar_difficulty = "medium"  # easy, medium, hard
        self.enable_cultural_context = True
        self.enable_situational_dialogues = True
        
        # UI and display settings
        self.show_videos_in_main_window = False
        self.play_videos_in_separate_window = False
        self.enable_dark_mode = True
        self.font_size = 12
        self.ui_language = "en"  # Interface language
        
        # Server configuration
        self.server_port = 6000
        self.server_password = "<PASSWORD>"
        self.server_host = "localhost"
        
        # Debug settings
        self.debug = False

        # Load configuration from file
        configs = [f.path for f in os.scandir(Config.CONFIGS_DIR_LOC) if f.is_file() and f.path.endswith(".json")]
        self.config_path = None

        for c in configs:
            if os.path.basename(c) == "config.json":
                self.config_path = c
                break
            elif os.path.basename(c) != "config_example.json":
                self.config_path = c

        if self.config_path is None:
            self.config_path = os.path.join(Config.CONFIGS_DIR_LOC, "config_example.json")

        try:
            self.dict = json.load(open(self.config_path, "r", encoding="utf-8"))
        except Exception as e:
            Utils.log_red(e)
            Utils.log_yellow("Unable to load config. Ensure config.json file settings are correct.")

        # Set values from config file
        self.set_values(str,
            "foreground_color",
            "background_color",
            "target_language",
            "proficiency_level",
            "llm_model_name",
            "vocabulary_difficulty",
            "grammar_difficulty",
            "ui_language",
        )
        
        self.set_values(int,
            "max_chunk_tokens",
            "daily_goal_minutes",
            "font_size",
            "server_port",
        )
        
        self.set_values(list,
            "learning_focus",
            "text_cleaner_ruleset",
            "coqui_tts_model",
            "save_tts_output_topics",
        )
        
        self.set_values(bool,
            "enable_visual_learning",
            "enable_pronunciation_practice",
            "enable_cultural_context",
            "enable_situational_dialogues",
            "show_videos_in_main_window",
            "play_videos_in_separate_window",
            "enable_dark_mode",
            "debug",
        )
        
        self.set_directories(
            "prompts_directory",
            "coqui_tts_location",
        )

        self.coqui_tts_model = tuple(self.coqui_tts_model)


    def validate_and_set_directory(self, key, override=False):
        loc = key if override else self.dict[key]
        if loc and loc.strip() != "":
            if "{HOME}" in loc:
                loc = loc.strip().replace("{HOME}", os.path.expanduser("~"))
            if not sys.platform == "win32" and "\\" in loc:
                loc = loc.replace("\\", "/")
            if not os.path.isdir(loc):
                raise Exception(f"Invalid location provided for {key}: {loc}")
            return loc
        return None

    def set_directories(self, *directories):
        for directory in directories:
            try:
                setattr(self, directory, self.validate_and_set_directory(directory))
            except Exception as e:
                Utils.log_yellow(e)
                Utils.log_yellow(f"Failed to set {directory} from config.json file. Ensure the key is set.")

    def set_values(self, type, *names):
        for name in names:
            if type:
                try:
                    setattr(self, name, type(self.dict[name]))
                except Exception as e:
                    Utils.log_red(e)
                    Utils.log_yellow(f"Failed to set {name} from config.json file. Ensure the value is set and of the correct type.")
            else:
                try:
                    setattr(self, name, self.dict[name])
                except Exception as e:
                    Utils.log_red(e)
                    Utils.log_yellow(f"Failed to set {name} from config.json file. Ensure the key is set.")


    def get_subdirectories(self):
        subdirectories = {}
        for directory in self.directories:
            try:
                this_dir_subdirs = [os.path.join(directory, d) for d in os.listdir(directory) if os .path.isdir(os.path.join(directory, d))]
                if len(this_dir_subdirs) == 0:
                    subdirectories[directory] = os.path.basename(directory)
                else:
                    for d in this_dir_subdirs:
                        subdirectories[d] = os.path.join(os.path.basename(directory), os.path.basename(d))
            except Exception:
                pass
        return subdirectories

    def get_all_directories(self):
        subdirectories_map = self.get_subdirectories()
        return list(subdirectories_map.keys())

    def matches_master_directory(self, directory):
        directory = os.path.normpath(os.path.realpath(directory))
        for d in self.directories:
            if d == directory:
                return True
        return False



config = Config()
