from src.diagnosis import diagnose
from src.evidence import build_diagnosis_evidence
from src.formalizer import formalize_problem, formalize_student_work
from src.models import DiagnosisLabel, ErrorLocalization
from src.runtime import solve_problem


def _concert_context():
    problem_text = (
        "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
        "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
    )
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    return problem, reference


def test_diagnosis_marks_correct_answer():
    problem_text = "Tom had 10 marbles and gave away 4. How many marbles are left?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work("Answer is 6.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)

    result = diagnose(evidence)

    assert result.diagnosis_label == DiagnosisLabel.CORRECT_ANSWER
    assert result.localization == ErrorLocalization.NONE


def test_diagnosis_marks_unparseable_answer():
    problem, reference = _concert_context()
    student = formalize_student_work("I do not know.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)

    result = diagnose(evidence)

    assert result.diagnosis_label == DiagnosisLabel.UNPARSEABLE_ANSWER
    assert result.localization == ErrorLocalization.UNKNOWN


def test_diagnosis_marks_intermediate_target_selection():
    problem, reference = _concert_context()
    student = formalize_student_work("12 - 10 = 2\nAnswer is 2.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)

    result = diagnose(evidence)

    assert result.diagnosis_label == DiagnosisLabel.TARGET_MISUNDERSTANDING
    assert result.subtype == "selected_intermediate_quantity"
    assert result.localization == ErrorLocalization.TARGET_SELECTION


def test_diagnosis_marks_visible_problem_quantity_selection():
    problem, reference = _concert_context()
    student = formalize_student_work("Answer is 40.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)

    result = diagnose(evidence)

    assert result.diagnosis_label == DiagnosisLabel.TARGET_MISUNDERSTANDING
    assert result.subtype == "selected_visible_problem_quantity"


def test_diagnosis_marks_arithmetic_error():
    problem_text = "Jan has 3 apples. She buys 5 more apples. How many apples does she have in total?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work("3 + 5 = 9\nAnswer is 9.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)

    result = diagnose(evidence)

    assert result.diagnosis_label == DiagnosisLabel.ARITHMETIC_ERROR
    assert result.localization == ErrorLocalization.INTERMEDIATE_STEP


def test_diagnosis_keeps_correct_answer_when_steps_are_reordered():
    problem, reference = _concert_context()
    student = formalize_student_work(
        "12 * 40 = 480\n5% of 40 = 2\n2 * 2 = 4\n480 - 4 = 476\nAnswer is 476.",
        problem=problem,
        reference=reference,
    )
    evidence = build_diagnosis_evidence(problem, reference, student)

    result = diagnose(evidence)

    assert result.diagnosis_label == DiagnosisLabel.CORRECT_ANSWER
    assert result.localization == ErrorLocalization.NONE
