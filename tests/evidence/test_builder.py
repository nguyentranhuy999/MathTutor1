from src.evidence import build_diagnosis_evidence
from src.formalizer import formalize_problem, formalize_student_work
from src.runtime import solve_problem


def _concert_context():
    problem_text = (
        "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
        "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
    )
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    return problem, reference


def test_evidence_builder_detects_intermediate_target_selection():
    problem, reference = _concert_context()
    student = formalize_student_work("12 - 10 = 2\nAnswer is 2.", problem=problem, reference=reference)

    evidence = build_diagnosis_evidence(problem, reference, student)

    assert evidence.first_divergence_step_id == "step_1_excess_quantity"
    assert "selected_intermediate_target" in evidence.likely_error_mechanisms
    assert any(item.evidence_type == "selected_intermediate_reference" for item in evidence.evidence_items)


def test_evidence_builder_detects_visible_problem_quantity_selection():
    problem, reference = _concert_context()
    student = formalize_student_work("Answer is 40.", problem=problem, reference=reference)

    evidence = build_diagnosis_evidence(problem, reference, student)

    assert "selected_visible_quantity_as_answer" in evidence.likely_error_mechanisms
    assert any(item.evidence_type == "selected_visible_problem_quantity" for item in evidence.evidence_items)


def test_evidence_builder_detects_arithmetic_mismatch_on_step_alignment():
    problem_text = "Jan has 3 apples. She buys 5 more apples. How many apples does she have in total?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work("3 + 5 = 9\nAnswer is 9.", problem=problem, reference=reference)

    evidence = build_diagnosis_evidence(problem, reference, student)

    assert evidence.first_divergence_step_id == "step_1_add_all"
    assert "arithmetic_mismatch" in evidence.likely_error_mechanisms
    assert any(item.evidence_type == "step_value_mismatch" for item in evidence.evidence_items)


def test_evidence_builder_marks_unparseable_student_work():
    problem, reference = _concert_context()
    student = formalize_student_work("I do not know.", problem=problem, reference=reference)

    evidence = build_diagnosis_evidence(problem, reference, student)

    assert evidence.likely_error_mechanisms == ["unparseable_answer"]
    assert evidence.evidence_items[0].evidence_type == "unparseable_answer"


def test_evidence_builder_marks_correct_final_answer():
    problem_text = "Tom had 10 marbles and gave away 4. How many marbles are left?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work("Answer is 6.", problem=problem, reference=reference)

    evidence = build_diagnosis_evidence(problem, reference, student)

    assert any(item.evidence_type == "correct_final_answer" for item in evidence.evidence_items)
    assert evidence.first_divergence_step_id is None


def test_evidence_builder_accepts_reordered_but_consistent_process():
    problem, reference = _concert_context()
    student = formalize_student_work(
        "12 * 40 = 480\n12 - 10 = 2\n5% of 40 = 2\n2 * 2 = 4\n480 - 4 = 476\nAnswer is 476.",
        problem=problem,
        reference=reference,
    )

    evidence = build_diagnosis_evidence(problem, reference, student)

    assert any(item.evidence_type == "correct_final_answer" for item in evidence.evidence_items)
    assert any(item.evidence_type == "reordered_but_consistent_steps" for item in evidence.evidence_items)
    assert not any(item.evidence_type == "step_value_mismatch" for item in evidence.evidence_items)
    assert evidence.first_divergence_step_id is None
    assert evidence.alignment_map


def test_evidence_builder_detects_dependency_mismatch_and_graph_edit_distance():
    problem, reference = _concert_context()
    student = formalize_student_work(
        "12 * 40 = 480\n480 - 4 = 476\n5% of 40 = 2\n2 * 2 = 4\nAnswer is 476.",
        problem=problem,
        reference=reference,
    )

    evidence = build_diagnosis_evidence(problem, reference, student)

    assert any(item.evidence_type == "dependency_mismatch" for item in evidence.evidence_items)
    assert any(item.evidence_type == "edge_level_divergence" for item in evidence.evidence_items)
    graph_edit_item = next(item for item in evidence.evidence_items if item.evidence_type == "graph_edit_distance")
    assert graph_edit_item.metadata["total_cost"] > 0
    assert "dependency_mismatch" in evidence.likely_error_mechanisms
