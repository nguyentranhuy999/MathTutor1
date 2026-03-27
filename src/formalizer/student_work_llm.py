"""LLM prompt and retry loop for compact student-work formalization."""
from __future__ import annotations

import json

from src.formalizer.student_work_builder import (
    _allowed_student_refs,
    _build_compact_student_draft,
    _build_student_work_from_skeleton,
    _compare_with_heuristic_student_notes,
    _schema_validation_result,
)
from src.formalizer.student_work_validation import (
    _student_feedback_payload,
    _student_sanity_validation_result,
)
from src.llm import LLMClient
from src.models import (
    CanonicalReference,
    FormalizedProblem,
    GraphValidationIssue,
    GraphValidationResult,
    StudentStepAttempt,
    StudentWorkMode,
    StudentWorkState,
    TraceOperation,
)


def _build_llm_student_prompt(
    raw_answer: str,
    heuristic_state: StudentWorkState,
    problem: FormalizedProblem | None,
    feedback_issues: list[dict],
    attempt_index: int,
) -> tuple[str, str]:
    compact_draft = _build_compact_student_draft(heuristic_state, problem=problem)
    allowed_refs = _allowed_student_refs(problem)
    allowed_step_ids = [step.step_id for step in heuristic_state.steps]
    system_prompt = (
        "You are a student-work formalizer for math tutoring. Return only a compact typed skeleton JSON object. "
        "Do not invent new steps. Do not rewrite the student's text. Keep everything strictly grounded in the "
        "student answer and the provided draft ids. Local code will build the final StudentWorkState and graph."
    )
    user_prompt = (
        f"Student answer:\n{raw_answer}\n\n"
        "Return one JSON object with only these top-level fields:\n"
        "{\n"
        '  "normalized_final_answer": 0.0,\n'
        '  "mode": "final_answer_only|partial_trace|full_trace|unparseable",\n'
        '  "selected_target_ref": "...",\n'
        '  "step_updates": [\n'
        '    {"step_id": "...", "operation": "...", "input_values": [0.0], "extracted_value": 0.0, "referenced_ids": ["..."], "confidence": 0.0, "notes": ["..."]}\n'
        "  ],\n"
        '  "assumptions": ["..."],\n'
        '  "confidence": 0.0,\n'
        '  "notes": ["..."]\n'
        "}\n\n"
        f"Allowed mode values: {[mode.value for mode in StudentWorkMode]}\n"
        f"Allowed step operation values: {[operation.value for operation in TraceOperation]}\n"
        f"Allowed selected_target_ref and referenced_ids values: {allowed_refs}\n"
        f"Allowed step_id values: {allowed_step_ids}\n\n"
        "Hard constraints:\n"
        "1. Do not invent new step_id values; reuse only the step ids from the draft.\n"
        "2. Do not include raw_text in step_updates; local code preserves the original student text.\n"
        "3. referenced_ids may contain only values from the allowed refs list.\n"
        "4. If the student's text does not support a field confidently, omit it instead of guessing.\n"
        "5. Do not add steps that are not visible in the student's answer.\n"
        "6. Notes must be short and factual.\n\n"
        f"Attempt index: {attempt_index}\n\n"
        f"Structured feedback from the previous failed attempt:\n{json.dumps(feedback_issues, ensure_ascii=True)}\n\n"
        "Compact heuristic draft for reference only:\n"
        f"{json.dumps(compact_draft, ensure_ascii=True)}"
    )
    return system_prompt, user_prompt


def _student_missing_validation_result() -> GraphValidationResult:
    return GraphValidationResult(
        is_valid=False,
        issues=[
            GraphValidationIssue(
                code="student_missing_graph",
                message="Student work graph was not built from the compact skeleton",
            )
        ],
        operation_node_count=0,
        notes=["student_graph_missing"],
    )


def _llm_formalize_student_work(
    raw_answer: str,
    heuristic_state: StudentWorkState,
    problem: FormalizedProblem | None,
    reference: CanonicalReference | None,
    llm_client: LLMClient,
) -> StudentWorkState:
    feedback_issues: list[dict] = []
    last_validation_result = _student_missing_validation_result()

    for attempt_index in range(1, 4):
        system_prompt, user_prompt = _build_llm_student_prompt(
            raw_answer,
            heuristic_state,
            problem,
            feedback_issues,
            attempt_index,
        )
        payload = llm_client.generate_json(
            task_name="student_work_formalizer",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=10000,
        )
        payload["notes"] = list(payload.get("notes", [])) + [f"llm_student_parse_attempt:{attempt_index}"]

        try:
            refined = _build_student_work_from_skeleton(
                raw_answer,
                heuristic_state,
                payload,
                problem=problem,
            )
        except (ValueError, TypeError) as exc:
            last_validation_result = _schema_validation_result(exc)
            feedback_issues = _student_feedback_payload(last_validation_result)
            continue

        last_validation_result = _student_sanity_validation_result(refined, problem=problem, reference=reference)
        if last_validation_result.is_valid:
            success_notes = list(refined.notes)
            success_notes.extend(_compare_with_heuristic_student_notes(heuristic_state, refined))
            success_notes.append("llm_student_parse_used")
            success_notes.append("llm_student_compact_skeleton_used")
            if attempt_index > 1:
                success_notes.append(f"llm_student_parse_repaired_after:{attempt_index}")
            return refined.model_copy(update={"notes": success_notes})

        feedback_issues = _student_feedback_payload(last_validation_result)

    fallback_notes = list(heuristic_state.notes)
    fallback_notes.extend(f"student_graph_issue:{issue.code}" for issue in last_validation_result.issues)
    fallback_notes.append("llm_student_parse_failed_fallback")
    return heuristic_state.model_copy(update={"notes": fallback_notes})
