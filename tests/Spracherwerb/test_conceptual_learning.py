"""Tests for ConceptualLearning and its LLM-authored lesson format."""

import json
import random

import pytest

from Spracherwerb.activity_registry import ActivityRegistry
from Spracherwerb.activity_results import ModuleServices
from Spracherwerb.activity_types import ActivityType
from Spracherwerb.concept_questions import parse_concept_lesson
from Spracherwerb.conceptual_learning import (
    LESSON_ATTEMPTS,
    QUESTIONS_PER_SESSION,
    ConceptualLearning,
    _CONCEPTS_BY_LEVEL,
)
from Spracherwerb.learning_memory import LearningMemory
from Spracherwerb.session_config import SessionConfig
from utils.translations import _


@pytest.fixture(autouse=True)
def reset_registry():
    ActivityRegistry.reset_to_defaults()
    yield
    ActivityRegistry.reset_to_defaults()


@pytest.fixture(autouse=True)
def clean_learning_memory():
    before = dict(LearningMemory.grammar_points_covered)
    LearningMemory.grammar_points_covered = {}
    yield
    LearningMemory.grammar_points_covered = before


class FakeLLMResult:
    def __init__(self, response, context=None):
        self.response = response
        self.context = context


class FakeLLM:
    def __init__(self, responses=None, fail=False):
        self._responses = list(responses or [])
        self._fail = fail
        self.calls = []

    def generate_response(self, query, timeout=180, context=None, system_prompt=None, **kwargs):
        self.calls.append({'query': query, 'system_prompt': system_prompt})
        if self._fail:
            raise Exception("LLM unavailable")
        if not self._responses:
            raise Exception("No more fake responses queued")
        return FakeLLMResult(self._responses.pop(0))


class FakePrompter:
    def get_prompt(self, prompt_name, language_code="en", skip_fallback=False):
        return f"You are a tutor running a {prompt_name} activity."


class FakeVocabularyPool:
    def __init__(self, entries):
        self._entries = entries
        self.recorded = []

    def get_review_candidates(self, source_language, target_language, limit=5):
        return list(self._entries[:limit])

    def record_word_result(self, target_language, word, *, outcome="reviewed"):
        self.recorded.append((target_language, word, outcome))


def make_services(llm, proficiency_level="intermediate", vocabulary_pool=None):
    session_config = SessionConfig({
        "source_language": "en",
        "target_language": "de",
        "proficiency_level": proficiency_level,
    })
    return ModuleServices(
        prompter=FakePrompter(),
        voice=None,
        session_config=session_config,
        session_context=None,
        llm=llm,
        vocabulary_pool=vocabulary_pool,
    )


def make_lesson(**overrides):
    lesson = {
        "concept": "Nebensatz-Wortstellung",
        "explanation": "Im Nebensatz steht das konjugierte Verb am Ende.",
        "examples": [
            {"text": "Ich weiß, dass der Hund schläft.", "note": "Verb am Ende nach 'dass'."},
            {"text": "Er bleibt zu Hause, weil es regnet.", "note": "Verb am Ende nach 'weil'."},
        ],
        "questions": [
            {
                "prompt": "Welcher Satz folgt der Regel?",
                "options": ["..., weil ich müde bin.", "..., weil ich bin müde.", "..., weil bin ich müde."],
                "correct": "..., weil ich müde bin.",
                "explanation": "Das Verb 'bin' steht am Ende.",
            },
            {
                "prompt": "Welcher Satz verletzt die Regel?",
                "options": ["..., dass er kommt.", "..., dass kommt er.", "..., ob er kommt."],
                "correct": "..., dass kommt er.",
                "explanation": "Nach 'dass' muss 'kommt' am Ende stehen.",
            },
            {
                "prompt": "Ergänze: Ich hoffe, dass der Hund ...",
                "options": ["schnell läuft", "läuft schnell"],
                "correct": "schnell läuft",
                "explanation": "",
            },
        ],
    }
    lesson.update(overrides)
    return "```json\n" + json.dumps(lesson, ensure_ascii=False) + "\n```"


def answer_number(module, correct=True):
    question = module._questions[module._question_index]
    index = question.correct_index if correct else (question.correct_index + 1) % len(question.options)
    return str(index + 1)


class TestConceptLessonParsing:
    def test_parses_fenced_json_and_keeps_the_correct_answer_after_shuffling(self):
        lesson = parse_concept_lesson(make_lesson(), rng=random.Random(3))

        assert lesson.concept == "Nebensatz-Wortstellung"
        assert len(lesson.examples) == 2
        assert len(lesson.questions) == 3
        assert lesson.questions[0].correct_option == "..., weil ich müde bin."

    def test_drops_only_the_invalid_questions(self):
        text = make_lesson(questions=[
            {"prompt": "Correct not in options", "options": ["a", "b"], "correct": "c"},
            {"prompt": "Duplicate options", "options": ["a", "A"], "correct": "a"},
            {"prompt": "Too few options", "options": ["a"], "correct": "a"},
            {"prompt": "Valid", "options": ["a", "b"], "correct": "b"},
        ])

        lesson = parse_concept_lesson(text)

        assert [q.prompt for q in lesson.questions] == ["Valid"]

    def test_accepts_plain_string_examples(self):
        lesson = parse_concept_lesson(make_lesson(examples=["Ich weiß, dass er kommt."]))

        assert lesson.examples[0].text == "Ich weiß, dass er kommt."
        assert lesson.examples[0].note == ""

    def test_non_json_response_is_rejected(self):
        assert parse_concept_lesson("Here is a lesson without any JSON.") is None
        assert parse_concept_lesson("{not valid json}") is None

    def test_answer_matching_accepts_numbers_and_option_text(self):
        question = parse_concept_lesson(make_lesson(), rng=random.Random(0)).questions[2]

        assert question.match_answer("1") == 0
        assert question.match_answer(" 2) ") == 1
        assert question.match_answer("SCHNELL LÄUFT") == question.options.index("schnell läuft")
        assert question.match_answer("9") is None
        assert question.match_answer("keine Ahnung") is None


class TestConceptualLearningRegistration:
    def test_is_registered_as_the_real_module(self):
        ActivityRegistry.register(ConceptualLearning)
        assert ActivityRegistry.is_implemented(ActivityType.CONCEPTUAL_LEARNING)
        assert isinstance(ActivityRegistry.create(ActivityType.CONCEPTUAL_LEARNING), ConceptualLearning)


class TestConceptualLearningStart:
    def test_shows_explanation_examples_and_only_the_first_question(self):
        module = ConceptualLearning(rng=random.Random(0))

        result = module.start(make_services(FakeLLM(responses=[make_lesson()])))

        assert result.expects_response is True
        assert _("Concept: {0}").format("Nebensatz-Wortstellung") in result.text_response
        assert "Im Nebensatz steht das konjugierte Verb am Ende." in result.text_response
        assert "Verb am Ende nach 'weil'." in result.text_response
        assert "Welcher Satz folgt der Regel?" in result.text_response
        assert "Welcher Satz verletzt die Regel?" not in result.text_response

    def test_seeds_the_first_uncovered_concept_for_the_level(self):
        LearningMemory.grammar_points_covered = {"de": [_CONCEPTS_BY_LEVEL["beginner"][0]]}
        llm = FakeLLM(responses=[make_lesson()])

        ConceptualLearning().start(make_services(llm, proficiency_level="beginner"))

        assert _CONCEPTS_BY_LEVEL["beginner"][1] in llm.calls[0]['query']

    def test_lets_the_llm_choose_once_every_seed_is_covered(self):
        LearningMemory.grammar_points_covered = {"de": list(_CONCEPTS_BY_LEVEL["advanced"])}
        llm = FakeLLM(responses=[make_lesson()])

        ConceptualLearning().start(make_services(llm, proficiency_level="advanced"))

        query = llm.calls[0]['query']
        assert "Avoid these, already covered" in query
        assert _CONCEPTS_BY_LEVEL["advanced"][0] in query

    def test_saved_translations_are_offered_and_marked_in_examples(self):
        pool = FakeVocabularyPool([{"source_text": "dog", "translated_text": "Hund"}])
        llm = FakeLLM(responses=[make_lesson()])
        module = ConceptualLearning(rng=random.Random(0))

        result = module.start(make_services(llm, vocabulary_pool=pool))

        assert "- Hund = dog" in llm.calls[0]['query']
        assert _("(uses your saved words: {0})").format("Hund") in result.text_response

    def test_unavailable_llm_does_not_expect_a_response(self):
        result = ConceptualLearning().start(make_services(FakeLLM(fail=True)))

        assert result.expects_response is False

    def test_unparseable_lesson_does_not_expect_a_response(self):
        llm = FakeLLM(responses=["no json here"] * LESSON_ATTEMPTS)

        result = ConceptualLearning().start(make_services(llm))

        assert result.expects_response is False
        assert len(llm.calls) == LESSON_ATTEMPTS

    def test_retries_once_after_an_unusable_reply(self):
        llm = FakeLLM(responses=["no json here", make_lesson()])

        result = ConceptualLearning(rng=random.Random(0)).start(make_services(llm))

        assert result.expects_response is True
        assert len(llm.calls) == 2

    def test_retries_a_lesson_without_questions_and_uses_the_one_with_them(self):
        llm = FakeLLM(responses=[make_lesson(questions=[]), make_lesson()])
        module = ConceptualLearning(rng=random.Random(0))

        result = module.start(make_services(llm))

        assert result.expects_response is True
        assert len(module._questions) == QUESTIONS_PER_SESSION

    def test_keeps_the_explanation_only_lesson_if_the_retry_is_unusable(self):
        llm = FakeLLM(responses=[make_lesson(questions=[]), "no json here"])

        result = ConceptualLearning().start(make_services(llm))

        assert result.expects_response is False
        assert "Im Nebensatz steht das konjugierte Verb am Ende." in result.text_response

    def test_unreachable_llm_is_not_retried(self):
        llm = FakeLLM(fail=True)

        ConceptualLearning().start(make_services(llm))

        assert len(llm.calls) == 1

    def test_lesson_without_valid_questions_still_shows_the_explanation(self):
        module = ConceptualLearning()
        llm = FakeLLM(responses=[make_lesson(questions=[])] * LESSON_ATTEMPTS)

        result = module.start(make_services(llm))

        assert result.expects_response is False
        assert "Im Nebensatz steht das konjugierte Verb am Ende." in result.text_response
        assert _("No practice questions could be prepared this time.") in result.text_response


class TestConceptualLearningQuestions:
    def test_runs_all_questions_and_completes(self):
        module = ConceptualLearning(rng=random.Random(0))
        services = make_services(FakeLLM(responses=[make_lesson()]))
        module.start(services)

        results = [module.handle_response(answer_number(module), services)
                   for _i in range(QUESTIONS_PER_SESSION)]

        assert [r.is_complete for r in results] == [False, False, True]
        assert _("Session complete: {0} of {1} correct.").format(3, 3) in results[-1].text_response

    def test_wrong_answer_reveals_the_correct_option_and_records_an_error(self):
        module = ConceptualLearning(rng=random.Random(0))
        services = make_services(FakeLLM(responses=[make_lesson()]))
        module.start(services)
        question = module._questions[0]

        result = module.handle_response(answer_number(module, correct=False), services)

        expected = _("Not quite -- the answer was {0}) {1}").format(
            question.correct_index + 1, question.correct_option)
        assert expected in result.text_response
        assert module._errors == [question.prompt]

    def test_unrecognized_reply_repeats_the_question_without_advancing(self):
        module = ConceptualLearning(rng=random.Random(0))
        services = make_services(FakeLLM(responses=[make_lesson()]))
        module.start(services)

        result = module.handle_response("keine Ahnung", services)

        assert module._question_index == 0
        assert result.is_complete is False
        assert "Welcher Satz folgt der Regel?" in result.text_response

    def test_handle_response_after_finished_is_safe(self):
        module = ConceptualLearning(rng=random.Random(0))
        services = make_services(FakeLLM(responses=[make_lesson()]))
        module.start(services)
        for _i in range(QUESTIONS_PER_SESSION):
            module.handle_response(answer_number(module), services)

        result = module.handle_response("1", services)

        assert result.is_complete is True
        assert _("This activity has already finished.") in result.text_response


class TestConceptualLearningVoiceText:
    def test_start_speaks_only_the_example_sentences(self):
        result = ConceptualLearning(rng=random.Random(0)).start(
            make_services(FakeLLM(responses=[make_lesson()])))

        assert result.voice_text == (
            "Ich weiß, dass der Hund schläft.\nEr bleibt zu Hause, weil es regnet.")

    def test_start_speaks_the_explanation_when_there_are_no_examples(self):
        result = ConceptualLearning(rng=random.Random(0)).start(
            make_services(FakeLLM(responses=[make_lesson(examples=[])])))

        assert result.voice_text == "Im Nebensatz steht das konjugierte Verb am Ende."

    def test_answer_speaks_the_explanation_and_a_reprompt_speaks_nothing(self):
        module = ConceptualLearning(rng=random.Random(0))
        services = make_services(FakeLLM(responses=[make_lesson()]))
        module.start(services)
        explanation = module._questions[0].explanation

        reprompt = module.handle_response("keine Ahnung", services)
        answered = module.handle_response(answer_number(module), services)

        assert reprompt.voice_text == ""
        assert answered.voice_text == explanation


class TestConceptualLearningResults:
    def test_complete_reports_reviewed_saved_words_and_updates_memory(self):
        pool = FakeVocabularyPool([{"source_text": "dog", "translated_text": "Hund"}])
        module = ConceptualLearning(rng=random.Random(0))
        services = make_services(FakeLLM(responses=[make_lesson()]), vocabulary_pool=pool)
        module.start(services)
        module.handle_response(answer_number(module), services)
        module.handle_response(answer_number(module, correct=False), services)
        module.handle_response(answer_number(module), services)

        results = module.complete(services)

        assert results["grammar_points"] == [_CONCEPTS_BY_LEVEL["intermediate"][0]]
        assert results["questions_answered"] == 3
        assert results["correct_answers"] == 2
        assert results["reviewed_words"] == ["Hund"]
        assert pool.recorded == [("de", "Hund", "reviewed")]
        assert _CONCEPTS_BY_LEVEL["intermediate"][0] in LearningMemory.grammar_points_covered["de"]

    def test_seed_is_recorded_as_covered_even_when_the_llm_renames_it(self):
        module = ConceptualLearning(rng=random.Random(0))
        services = make_services(FakeLLM(responses=[make_lesson(), make_lesson()]))
        seed = _CONCEPTS_BY_LEVEL["intermediate"][0]
        module.start(services)

        results = module.complete(services)
        second = ConceptualLearning(rng=random.Random(0))
        second.start(services)

        assert results["grammar_points"] == [seed]
        assert LearningMemory.grammar_points_covered["de"] == [seed]
        assert second._seed_concept == _CONCEPTS_BY_LEVEL["intermediate"][1]
