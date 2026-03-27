from copy import deepcopy

from src.diagnosis import diagnose
from src.evidence import build_diagnosis_evidence
from src.formalizer import formalize_problem, formalize_student_work
from src.hint import build_hint_result
from src.models import DiagnosisLabel, QuantitySemanticRole
from src.pedagogy import build_hint_plan
from src.pipeline import run_tutoring_pipeline
from src.runtime import solve_problem


class FakeLLMClient:
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
        response = self.responses[task_name]
        if isinstance(response, list):
            if not response:
                raise AssertionError(f"No queued response left for task '{task_name}'")
            response = response.pop(0)
        if isinstance(response, Exception):
            raise response
        return deepcopy(response)


def _simple_problem_formalization():
    return {
        "quantity_updates": [
            {
                "quantity_id": "quantity_1",
                "semantic_role": "base",
                "unit": "apples",
                "is_target_candidate": True,
            }
        ],
        "target_update": {
            "surface_text": "How many apples are there?",
            "normalized_question": "How many apples are there?",
            "target_variable": "how_many_apples_are_there",
            "target_quantity_id": "quantity_1",
            "unit": "apples",
            "description": "How many apples are there",
            "confidence": 0.95,
        },
        "relation_updates": [
            {
                "relation_id": "relation_1",
                "relation_type": "unknown",
                "operation_hint": "unknown",
                "source_quantity_ids": ["quantity_1"],
                "target_variable": "how_many_apples_are_there",
                "expression": "quantity_1",
                "rationale": "Only one quantity is present, so it is also the answer.",
                "confidence": 0.8,
            }
        ],
        "graph_steps": [
            {
                "step_id": "step_1_single_quantity",
                "step_index": 1,
                "operation": "derive",
                "input_refs": ["quantity_1"],
                "output_ref": "how_many_apples_are_there",
                "expression": "quantity_1",
                "label": "Use the only quantity as the answer.",
                "output_unit": "apples",
                "confidence": 0.85,
            }
        ],
        "graph_target_node_id": "how_many_apples_are_there",
        "graph_confidence": 0.9,
        "graph_notes": ["llm_graph"],
        "assumptions": [],
        "confidence": 0.9,
        "notes": ["llm_refined"],
    }


def test_problem_formalizer_uses_llm_when_available():
    client = FakeLLMClient({"problem_formalizer": _simple_problem_formalization()})

    result = formalize_problem("There are 8 apples. How many apples are there?", llm_client=client)

    assert result.provenance.value == "llm"
    assert "llm_formalization_used" in result.notes
    assert "llm_compact_skeleton_used" in result.notes
    assert result.problem_graph is not None
    assert client.calls == ["problem_formalizer"]


def test_problem_formalizer_retries_after_invalid_graph_feedback():
    invalid_response = _simple_problem_formalization()
    invalid_response["graph_steps"] = [
        {
            "step_id": "step_1_single_quantity",
            "step_index": 1,
            "operation": "derive",
            "input_refs": ["missing_quantity_ref"],
            "output_ref": "how_many_apples_are_there",
            "expression": "missing_quantity_ref",
            "label": "Broken step",
            "output_unit": "apples",
            "confidence": 0.9,
        }
    ]
    client = FakeLLMClient(
        {
            "problem_formalizer": [invalid_response, _simple_problem_formalization()]
        }
    )

    result = formalize_problem("There are 8 apples. How many apples are there?", llm_client=client)

    assert result.provenance.value == "llm"
    assert "llm_formalization_used" in result.notes
    assert "llm_formalization_repaired_after:2" in result.notes
    assert client.calls == ["problem_formalizer", "problem_formalizer"]


def test_problem_formalizer_applies_local_semantic_repairs_to_derived_target():
    payload = _simple_problem_formalization()
    payload["quantity_updates"][0]["is_target_candidate"] = True
    payload["target_update"]["target_quantity_id"] = "quantity_1"
    payload["graph_steps"] = [
        {
            "step_id": "step_1_copy",
            "step_index": 1,
            "operation": "derive",
            "input_refs": ["quantity_1"],
            "output_ref": "intermediate_value",
            "expression": "quantity_1",
            "label": "Intermediate copy",
            "output_unit": "apples",
            "confidence": 0.85,
        },
        {
            "step_id": "step_2_answer",
            "step_index": 2,
            "operation": "derive",
            "input_refs": ["intermediate_value"],
            "output_ref": "how_many_apples_are_there",
            "expression": "intermediate_value",
            "label": "Final answer",
            "output_unit": "apples",
            "confidence": 0.85,
        },
    ]
    client = FakeLLMClient({"problem_formalizer": payload})

    result = formalize_problem("There are 8 apples. How many apples are there?", llm_client=client)

    assert result.target is not None
    assert result.target.target_quantity_id is None
    assert all(quantity.is_target_candidate is False for quantity in result.quantities)
    assert "local_semantic_repair:cleared_target_quantity_for_derived_target" in result.notes


def test_student_work_formalizer_uses_llm_to_parse_word_number_answer():
    problem_text = "There are 8 apples. How many apples are there?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    client = FakeLLMClient(
        {
            "student_work_formalizer": {
                "normalized_final_answer": 8.0,
                "mode": "final_answer_only",
                "selected_target_ref": "how_many_apples_are_there",
                "step_updates": [],
                "assumptions": [],
                "confidence": 0.9,
                "notes": ["llm_parsed_word_number"],
            }
        }
    )

    result = formalize_student_work("The answer is eight.", problem=problem, reference=reference, llm_client=client)

    assert result.normalized_final_answer == 8.0
    assert "llm_student_parse_used" in result.notes
    assert "llm_student_compact_skeleton_used" in result.notes
    assert client.calls == ["student_work_formalizer"]


def test_student_work_formalizer_retries_after_invalid_ref_feedback():
    problem_text = "There are 8 apples. How many apples are there?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    invalid_response = {
        "normalized_final_answer": 8.0,
        "mode": "final_answer_only",
        "selected_target_ref": "invented_ref",
        "step_updates": [],
        "confidence": 0.85,
        "notes": ["broken_selected_ref"],
    }
    repaired_response = {
        "normalized_final_answer": 8.0,
        "mode": "final_answer_only",
        "selected_target_ref": "how_many_apples_are_there",
        "step_updates": [],
        "confidence": 0.92,
        "notes": ["repaired_selected_ref"],
    }
    client = FakeLLMClient({"student_work_formalizer": [invalid_response, repaired_response]})

    result = formalize_student_work("The answer is eight.", problem=problem, reference=reference, llm_client=client)

    assert result.normalized_final_answer == 8.0
    assert result.selected_target_ref == "how_many_apples_are_there"
    assert "llm_student_parse_repaired_after:2" in result.notes
    assert client.calls == ["student_work_formalizer", "student_work_formalizer"]


def test_diagnosis_uses_llm_refinement():
    problem_text = "Jan has 3 apples. She buys 5 more apples. How many apples does she have in total?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work("3 + 5 = 9\nAnswer is 9.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)
    client = FakeLLMClient(
        {
            "diagnosis": {
                "diagnosis_label": "arithmetic_error",
                "subtype": "intermediate_calculation_error",
                "localization": "intermediate_step",
                "target_step_id": "step_1_add_all",
                "summary": "The student chooses the right setup but computes the sum incorrectly.",
                "supporting_evidence_types": ["final_answer_mismatch", "step_value_mismatch"],
                "confidence": 0.91,
                "notes": ["llm_refined_diagnosis"],
            }
        }
    )

    result = diagnose(evidence, llm_client=client)

    assert result.summary == "The student chooses the right setup but computes the sum incorrectly."
    assert "llm_diagnosis_used" in result.notes
    assert client.calls == ["diagnosis"]


def test_hint_generator_uses_llm_text_when_verification_passes():
    problem_text = "Tom had 10 marbles and gave away 4. How many marbles are left?"
    problem = formalize_problem(problem_text)
    reference = solve_problem(problem_text)
    student = formalize_student_work("Answer is 6.", problem=problem, reference=reference)
    evidence = build_diagnosis_evidence(problem, reference, student)
    diagnosis = diagnose(evidence)
    plan = build_hint_plan(problem, reference, diagnosis)
    client = FakeLLMClient({"hint_generator": {"hint_text": "Your answer is correct."}})

    result = build_hint_result(problem, reference, diagnosis, plan, llm_client=client)

    assert diagnosis.diagnosis_label == DiagnosisLabel.CORRECT_ANSWER
    assert result.hint_text == "Your answer is correct."
    assert result.verification_passed is True
    assert client.calls == ["hint_generator"]


def test_pipeline_uses_llm_across_all_target_modules():
    client = FakeLLMClient(
        {
            "problem_formalizer": _simple_problem_formalization(),
            "student_work_formalizer": {
                "normalized_final_answer": 8.0,
                "mode": "final_answer_only",
                "selected_target_ref": "how_many_apples_are_there",
                "step_updates": [],
                "assumptions": [],
                "confidence": 0.92,
                "notes": ["llm_pipeline_student_parse"],
            },
            "diagnosis": {
                "diagnosis_label": "correct_answer",
                "subtype": "matches_canonical_reference",
                "localization": "none",
                "target_step_id": None,
                "summary": "The student's answer matches the canonical reference.",
                "supporting_evidence_types": ["correct_final_answer"],
                "confidence": 0.93,
                "notes": ["llm_pipeline_diagnosis"],
            },
            "hint_generator": {"hint_text": "Your answer is correct."},
        }
    )

    result = run_tutoring_pipeline(
        "There are 8 apples. How many apples are there?",
        "The answer is eight.",
        llm_client=client,
        use_llm=True,
    )

    assert result.reference.final_answer == 8.0
    assert result.student_work.normalized_final_answer == 8.0
    assert result.diagnosis.diagnosis_label == DiagnosisLabel.CORRECT_ANSWER
    assert result.hint_result.hint_text == "Your answer is correct."
    assert client.calls == [
        "problem_formalizer",
        "student_work_formalizer",
        "diagnosis",
        "hint_generator",
    ]
