from src.diagnosis import diagnose
from src.evidence import build_diagnosis_evidence
from src.formalizer import formalize_problem, formalize_student_work
from src.models import DiagnosisLabel, HintLevel, TeacherMove
from src.pedagogy import build_hint_plan
from src.runtime import solve_problem


def _concert_context(student_answer: str):
    problem_text = (
        "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
        "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
    )
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work(student_answer, problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)
    diagnosis = diagnose(evidence)
    return problem, reference, diagnosis


def test_pedagogy_planner_refocuses_target_for_intermediate_selection():
    problem, reference, diagnosis = _concert_context("12 - 10 = 2\nAnswer is 2.")

    plan = build_hint_plan(problem, reference, diagnosis)

    assert diagnosis.diagnosis_label == DiagnosisLabel.TARGET_MISUNDERSTANDING
    assert plan.teacher_move == TeacherMove.REFOCUS_TARGET
    assert plan.hint_level == HintLevel.CONCEPTUAL
    assert "final answer" in plan.must_not_reveal
    assert "2" in plan.must_not_reveal


def test_pedagogy_planner_uses_next_step_for_arithmetic_error():
    problem_text = "Jan has 3 apples. She buys 5 more apples. How many apples does she have in total?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work("3 + 5 = 9\nAnswer is 9.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)
    diagnosis = diagnose(evidence)

    plan = build_hint_plan(problem, reference, diagnosis)

    assert diagnosis.diagnosis_label == DiagnosisLabel.ARITHMETIC_ERROR
    assert plan.teacher_move == TeacherMove.RECOMPUTE_STEP
    assert plan.hint_level == HintLevel.NEXT_STEP
    assert plan.disclosure_budget == 1


def test_pedagogy_planner_uses_metacognitive_prompt_for_unparseable():
    problem, reference, diagnosis = _concert_context("I do not know.")

    plan = build_hint_plan(problem, reference, diagnosis)

    assert diagnosis.diagnosis_label == DiagnosisLabel.UNPARSEABLE_ANSWER
    assert plan.teacher_move == TeacherMove.METACOGNITIVE_PROMPT
    assert plan.hint_level == HintLevel.CONCEPTUAL
    assert plan.disclosure_budget == 1


def test_pedagogy_planner_returns_zero_budget_for_correct_answer():
    problem_text = "Tom had 10 marbles and gave away 4. How many marbles are left?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work("Answer is 6.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)
    diagnosis = diagnose(evidence)

    plan = build_hint_plan(problem, reference, diagnosis)

    assert diagnosis.diagnosis_label == DiagnosisLabel.CORRECT_ANSWER
    assert plan.teacher_move == TeacherMove.RESTATE_RESULT
    assert plan.disclosure_budget == 0
    assert plan.focus_points == []
