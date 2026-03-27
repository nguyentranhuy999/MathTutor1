from src.diagnosis import diagnose
from src.evidence import build_diagnosis_evidence
from src.formalizer import formalize_problem, formalize_student_work
from src.hint import build_hint_result, check_alignment, check_no_spoiler
from src.models import DiagnosisLabel, HintLevel, HintPlan, TeacherMove
from src.pedagogy import build_hint_plan
from src.runtime import solve_problem


def _concert_hint_context(student_answer: str):
    problem_text = (
        "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
        "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
    )
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work(student_answer, problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)
    diagnosis = diagnose(evidence)
    plan = build_hint_plan(problem, reference, diagnosis)
    return problem, reference, diagnosis, plan


def test_hint_controller_generates_verified_hint_for_target_misunderstanding():
    problem, reference, diagnosis, plan = _concert_hint_context("12 - 10 = 2\nAnswer is 2.")

    result = build_hint_result(problem, reference, diagnosis, plan)

    assert diagnosis.diagnosis_label == DiagnosisLabel.TARGET_MISUNDERSTANDING
    assert result.verification_passed is True
    assert not result.violated_rules
    assert "2" not in result.hint_text


def test_hint_verifier_blocks_hidden_numbers():
    _, _, _, plan = _concert_hint_context("12 - 10 = 2\nAnswer is 2.")

    violations = check_no_spoiler("The value 2 is not your final answer.", plan)

    assert any("reveals_hidden_number:2" == violation for violation in violations)


def test_hint_verifier_checks_alignment():
    _, _, _, plan = _concert_hint_context("12 - 10 = 2\nAnswer is 2.")

    violations = check_alignment("Compute it again carefully.", plan)

    assert "teacher_move_alignment_failed" in violations


class _FakeHintLLMClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def generate_json(
        self,
        task_name,
        system_prompt,
        user_prompt,
        temperature=0.0,
        max_tokens=1200,
    ):
        self.calls.append(task_name)
        return self.responses[task_name]


def test_hint_controller_repairs_generated_hint_before_fallback():
    problem, reference, diagnosis, plan = _concert_hint_context("12 - 10 = 2\nAnswer is 2.")
    client = _FakeHintLLMClient(
        {
            "hint_generator": {
                "hint_text": "The value 2 is not your final answer. Compute it again carefully."
            }
        }
    )

    result = build_hint_result(problem, reference, diagnosis, plan, llm_client=client)

    assert result.verification_passed is True
    assert "used_repaired_hint" in result.notes
    assert "used_fallback_hint" not in result.notes
    assert "2" not in result.hint_text
    assert client.calls == ["hint_generator"]


def test_hint_controller_can_use_llm_repair_when_deterministic_repair_still_fails():
    problem, reference, diagnosis, _ = _concert_hint_context("12 - 10 = 2\nAnswer is 2.")
    plan = HintPlan(
        diagnosis_label=diagnosis.diagnosis_label,
        hint_level=HintLevel.CONCEPTUAL,
        teacher_move=TeacherMove.REFOCUS_TARGET,
        target_step_id=diagnosis.target_step_id,
        disclosure_budget=1,
        focus_points=["what quantity the question is actually asking for"],
        must_not_reveal=["question", "quantity", "final", "intermediate"],
        rationale="Synthetic plan to force the LLM repair path.",
        confidence=0.8,
    )
    client = _FakeHintLLMClient(
        {
            "hint_generator": {"hint_text": "Question question question. Final intermediate quantity."},
            "hint_repair": {"hint_text": "Focus on what the problem is asking you to find."},
        }
    )

    result = build_hint_result(problem, reference, diagnosis, plan, llm_client=client)

    assert result.verification_passed is True
    assert "used_repaired_hint" in result.notes
    assert "hint_repair:llm_rewrite" in result.notes
    assert client.calls == ["hint_generator", "hint_repair"]
