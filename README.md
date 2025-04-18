# Spracherwerb

Spracherwerb is an interactive language learning application that combines the power of large language models with text-to-speech technology and AI-generated imagery to create an immersive language learning experience. The application provides personalized language lessons, practice exercises, and real-time feedback through an intuitive interface, enhanced by visual learning aids.

NOTE: This project is a work in progress, and the features listed below may not be available at this time, as this is README is currently used as a planning document.

## Installation steps

- Download Coqui-TTS source from https://github.com/coqui-ai/TTS
- Install Coqui-TTS using `pip install -e.`
- Set `coqui_tts_location` in config.json in configs folder to the path of Coqui-TTS source.
- Download and install Ollama following the instructions at https://github.com/ollama/ollama
- Ensure Ollama is operational and serving with `ollama serve`
- In a virtual environment, run `pip install -r requirements.txt` on this directory.

## Configuration

- Set `LANGUAGE` environment variable to your target language code. If not supported, the language will default to English.
    - NOTE: Currently, Coqui-TTS has limited support for non-Roman characters. Support for additional writing systems will be added as better open-source TTS solutions become available.
- `muse_config`
    - `muse_language_learning_language` - Set your target language for learning
    - `muse_language_learning_language_level` - Set your current proficiency level (beginner, intermediate, advanced)
    - `llm_model_name` - The name of the LLM to use, exactly the same as Ollama model name
- `text_cleaner_ruleset` - Add rules to this list to edit text before it is spoken by the application
- `prompts_directory` - Directory containing prompts for different topics and languages. Supports:
  - System prompts in root directory
  - Language-specific prompts in subdirectories (e.g., 'en/', 'de/')
  - Automatic translation fallback when language-specific prompts aren't available

## Features

- Interactive language lessons with real-time feedback
- Text-to-speech pronunciation assistance
- AI-generated visual learning aids
- Customizable learning paths based on proficiency level
- Vocabulary building exercises with visual associations
- Grammar practice sessions
- Cultural context and usage examples
- Progress tracking
- Conversation practice with the AI tutor
- Writing exercises with corrections
- Listening comprehension exercises
- Visual vocabulary builder with AI-generated images
- Multi-language image generation support

## Visual Learning

The application integrates with AI image generation software to create visual learning aids:
- Automatic generation of images for vocabulary words
- Visual context for cultural concepts
- Scene generation for situational dialogues
- Multi-language support in image generation
- Real-time image display in the learning interface
- Customizable image generation parameters
- Visual memory aids for language concepts

## Usage

- In your virtual environment, run `python app.py` to start the application
- Select your target language and proficiency level
- Choose from various learning activities:
  - Vocabulary drills with visual aids
  - Grammar exercises
  - Conversation practice
  - Listening comprehension
  - Writing exercises
  - Cultural lessons with visual context
  - Visual vocabulary builder

## Learning Activities

The application offers various learning activities through prompts in the prompts folder:

- `vocabulary_builder` - Focused vocabulary learning with context, usage examples, and AI-generated images
- `grammar_practice` - Interactive grammar exercises with explanations
- `conversation_practice` - Simulated conversations with the AI tutor
- `listening_comprehension` - Audio-based exercises with follow-up questions
- `writing_practice` - Writing exercises with AI feedback
- `cultural_context` - Cultural insights and real-world language usage with visual aids
- `pronunciation_guide` - Detailed pronunciation assistance
- `idioms_and_expressions` - Learning common phrases and idioms with visual context
- `reading_comprehension` - Text-based exercises with comprehension questions
- `situational_dialogues` - Practice conversations for specific situations with scene visualization
- `visual_vocabulary` - Interactive vocabulary learning with AI-generated images

## Customization

The application can be customized to focus on specific aspects of language learning:
- Adjust difficulty levels
- Focus on particular language skills
- Customize learning pace
- Set specific learning goals
- Choose preferred learning methods
- Select topics of interest
- Configure image generation parameters
- Adjust visual learning preferences

## Note on Speech Recognition

While the application currently supports text-based input for exercises and practice, future versions will integrate speech recognition capabilities for pronunciation practice and speaking exercises. This will be implemented once reliable open-source speech recognition solutions become available for a wider range of languages.






