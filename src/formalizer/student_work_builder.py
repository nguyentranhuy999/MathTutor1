"""Deterministic draft building and local reconstruction for student work."""
from __future__ import annotations

import re

from pydantic import ValidationError

from src.formalizer.reference_trace import build_student_partial_trace
from src.formalizer.student_work_graph import build_student_work_graph
from src.models import (
    CanonicalReference,
    FormalizedProblem,
    GraphValidationIssue,
    GraphValidationResult,
    ProvenanceSource,
    StudentStepAttempt,
    StudentWorkMode,
    StudentWorkState,
    TraceOperation,
)


_NUMBER_PATTERN = re.compile(r"-?\d[\d,]*\.?\d*")
_HASH_PATTERN = re.compile(r"####\s*(-?\d[\d,]*\.?\d*)")
_ANSWER_PATTERN = re.compile(
    r"(?:answer|final answer|result|total)\s*(?:is|=|:)?\s*(-?\d[\d,]*\.?\d*)",
    re.IGNORECASE,
)
_STEP_SPLIT_PATTERN = re.compile(r"(?:\r?\n)+")


def _parse_number(text: str) -> float | None:
    normalized = text.strip().replace(",", "")
    if normalized.endswith(".") and normalized[:-1].replace("-", "", 1).replace(".", "", 1).isdigit():
        normalized = normalized[:-1]
    try:
        return float(normalized)
    except ValueError:
        return None


def _extract_final_answer(raw_answer: str) -> tuple[float | None, list[str]]:
    notes: list[str] = []
    if not raw_answer.strip():
        return None, ["empty_answer"]

    hash_match = _HASH_PATTERN.search(raw_answer)
    if hash_match:
        parsed = _parse_number(hash_match.group(1))
        if parsed is not None:
            return parsed, ["hash_marker_match"]
        notes.append("hash_marker_unparseable")

    answer_match = _ANSWER_PATTERN.search(raw_answer)
    if answer_match:
        parsed = _parse_number(answer_match.group(1))
        if parsed is not None:
            return parsed, ["answer_cue_match"]
        notes.append("answer_cue_unparseable")

    all_numbers = _NUMBER_PATTERN.findall(raw_answer)
    if all_numbers:
        parsed = _parse_number(all_numbers[-1])
        if parsed is not None:
            label = "last_number_selected" if len(all_numbers) == 1 else f"multiple_numbers_found:{len(all_numbers)}"
            return parsed, [label]
        notes.append("last_number_unparseable")

    notes.append("no_numeric_candidate")
    return None, notes


def _split_student_steps(raw_answer: str) -> list[str]:
    if not raw_answer.strip():
        return []

    raw_lines = [segment.strip() for segment in _STEP_SPLIT_PATTERN.split(raw_answer) if segment.strip()]
    if len(raw_lines) > 1:
        return raw_lines

    sentence_lines = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", raw_answer) if segment.strip()]
    if len(sentence_lines) > 1:
        return sentence_lines

    return [raw_answer.strip()]


def _step_confidence(operation: TraceOperation | None, extracted_value: float | None, raw_text: str) -> float:
    if operation is not None and operation != TraceOperation.UNKNOWN and extracted_value is not None:
        return 0.82
    if extracted_value is not None and "=" in raw_text:
        return 0.72
    if extracted_value is not None:
        return 0.58
    return 0.25


def _referenced_problem_quantity_ids(line: str, problem: FormalizedProblem | None) -> list[str]:
    if problem is None:
        return []

    lowered_line = line.lower()
    referenced_ids: list[str] = []
    seen: set[str] = set()
    for quantity in problem.quantities:
        mentions_value = quantity.surface_text.lower() in lowered_line or f"{quantity.value:g}" in lowered_line
        if mentions_value and quantity.quantity_id not in seen:
            referenced_ids.append(quantity.quantity_id)
            seen.add(quantity.quantity_id)
    return referenced_ids


def _build_step_attempts(
    raw_answer: str,
    problem: FormalizedProblem | None,
) -> tuple[list[StudentStepAttempt], list[str]]:
    trace = build_student_partial_trace(raw_answer)
    lines = _split_student_steps(raw_answer)
    notes = list(trace.notes)
    attempts: list[StudentStepAttempt] = []

    for index, line in enumerate(lines, start=1):
        trace_step = trace.steps[index - 1] if index - 1 < len(trace.steps) else None
        extracted_value = trace_step.output_value if trace_step is not None else None
        operation = trace_step.operation if trace_step is not None else TraceOperation.UNKNOWN
        input_values = list(trace_step.input_values) if trace_step is not None else []
        referenced_ids = _referenced_problem_quantity_ids(line, problem)

        step_notes: list[str] = []
        if trace_step is not None and trace_step.provenance != ProvenanceSource.UNKNOWN:
            step_notes.append(f"trace_provenance={trace_step.provenance.value}")
        if "=" in line:
            step_notes.append("contains_equation")
        if referenced_ids:
            step_notes.append(f"referenced_ids={len(referenced_ids)}")

        attempts.append(
            StudentStepAttempt(
                step_id=f"student_step_{index}",
                raw_text=line,
                operation=operation,
                input_values=input_values,
                extracted_value=extracted_value,
                referenced_ids=referenced_ids,
                confidence=_step_confidence(operation, extracted_value, line),
                notes=step_notes,
            )
        )

    return attempts, notes


def _infer_mode(raw_answer: str, steps: list[StudentStepAttempt], final_answer: float | None) -> StudentWorkMode:
    if not raw_answer.strip() or final_answer is None and not steps:
        return StudentWorkMode.UNPARSEABLE
    if len(steps) >= 2 or any("=" in step.raw_text for step in steps):
        return StudentWorkMode.PARTIAL_TRACE
    if len(steps) == 1 and "=" in steps[0].raw_text and final_answer is not None:
        return StudentWorkMode.PARTIAL_TRACE
    return StudentWorkMode.FINAL_ANSWER_ONLY if final_answer is not None else StudentWorkMode.UNPARSEABLE


def _infer_selected_target_ref(
    final_answer: float | None,
    problem: FormalizedProblem | None,
) -> str | None:
    if final_answer is None:
        return None

    if problem is not None:
        for quantity in problem.quantities:
            if abs(quantity.value - final_answer) < 1e-9:
                return quantity.quantity_id

    if problem is not None and problem.target is not None and problem.target.target_quantity_id is not None:
        target_quantity = next(
            (quantity for quantity in problem.quantities if quantity.quantity_id == problem.target.target_quantity_id),
            None,
        )
        if (
            target_quantity is not None
            and target_quantity.is_target_candidate
            and abs(target_quantity.value - final_answer) < 1e-9
        ):
            return problem.target.target_variable

    return None


def _attach_student_graph(
    student_state: StudentWorkState,
    problem: FormalizedProblem | None,
) -> StudentWorkState:
    student_graph = build_student_work_graph(student_state, problem=problem)
    if student_graph is None:
        return student_state
    return student_state.model_copy(update={"student_graph": student_graph})


def _heuristic_formalize_student_work(
    raw_answer: str,
    problem: FormalizedProblem | None = None,
    reference: CanonicalReference | None = None,
) -> StudentWorkState:
    cleaned_answer = (raw_answer or "").strip()
    final_answer, final_answer_notes = _extract_final_answer(cleaned_answer)
    steps, trace_notes = _build_step_attempts(cleaned_answer, problem)
    mode = _infer_mode(cleaned_answer, steps, final_answer)
    selected_target_ref = _infer_selected_target_ref(final_answer, problem)

    notes = list(final_answer_notes)
    notes.extend(trace_notes)
    if selected_target_ref is not None:
        notes.append(f"selected_target_ref={selected_target_ref}")
    if mode == StudentWorkMode.UNPARSEABLE:
        notes.append("student_work_unparseable")

    confidence = 0.0
    if final_answer is not None:
        confidence += 0.35
    if steps:
        confidence += min(0.4, 0.1 * len(steps))
    if selected_target_ref is not None:
        confidence += 0.15
    if mode == StudentWorkMode.PARTIAL_TRACE:
        confidence += 0.05

    return _attach_student_graph(
        StudentWorkState(
            raw_answer=cleaned_answer,
            normalized_final_answer=final_answer,
            mode=mode,
            steps=steps if mode != StudentWorkMode.FINAL_ANSWER_ONLY else [],
            student_graph=None,
            selected_target_ref=selected_target_ref,
            assumptions=[],
            confidence=min(confidence, 0.95),
            notes=notes,
        ),
        problem=problem,
    )


def _build_compact_student_draft(
    heuristic_state: StudentWorkState,
    problem: FormalizedProblem | None = None,
) -> dict:
    return {
        "raw_answer": heuristic_state.raw_answer,
        "normalized_final_answer": heuristic_state.normalized_final_answer,
        "mode": heuristic_state.mode.value,
        "selected_target_ref": heuristic_state.selected_target_ref,
        "steps": [
            {
                "step_id": step.step_id,
                "raw_text": step.raw_text,
                "operation": step.operation.value if step.operation is not None else None,
                "input_values": list(step.input_values),
                "extracted_value": step.extracted_value,
                "referenced_ids": list(step.referenced_ids),
            }
            for step in heuristic_state.steps
        ],
        "allowed_refs": _allowed_student_refs(problem),
    }


def _build_student_work_from_skeleton(
    raw_answer: str,
    heuristic_state: StudentWorkState,
    skeleton: dict,
    problem: FormalizedProblem | None = None,
) -> StudentWorkState:
    allowed_refs = set(_allowed_student_refs(problem))
    heuristic_steps_by_id = {step.step_id: step for step in heuristic_state.steps}

    steps = list(heuristic_state.steps)
    step_updates = skeleton.get("step_updates", [])
    if step_updates is not None:
        if not isinstance(step_updates, list):
            raise ValueError("step_updates must be a list when provided")
        merged_steps: list[StudentStepAttempt] = []
        seen_step_ids: set[str] = set()
        for step in heuristic_state.steps:
            update = next(
                (
                    candidate
                    for candidate in step_updates
                    if isinstance(candidate, dict) and candidate.get("step_id") == step.step_id
                ),
                None,
            )
            if update is None:
                merged_steps.append(step)
                seen_step_ids.add(step.step_id)
                continue

            sanitized_update = dict(update)
            sanitized_update.pop("raw_text", None)
            sanitized_update["step_id"] = step.step_id
            if "referenced_ids" in sanitized_update:
                referenced_ids = [
                    ref_id
                    for ref_id in sanitized_update["referenced_ids"]
                    if isinstance(ref_id, str) and ref_id in allowed_refs
                ]
                deduped_refs: list[str] = []
                seen_refs: set[str] = set()
                for ref_id in referenced_ids:
                    if ref_id not in seen_refs:
                        deduped_refs.append(ref_id)
                        seen_refs.add(ref_id)
                sanitized_update["referenced_ids"] = deduped_refs

            merged_steps.append(step.model_copy(update=sanitized_update))
            seen_step_ids.add(step.step_id)

        unknown_step_ids = [
            item.get("step_id")
            for item in step_updates
            if isinstance(item, dict)
            and item.get("step_id") is not None
            and item.get("step_id") not in heuristic_steps_by_id
        ]
        if unknown_step_ids:
            raise ValueError(f"step_updates contained unknown step_id values: {unknown_step_ids}")
        steps = merged_steps

    merged_payload = heuristic_state.model_dump(mode="json")
    merged_payload.update(
        {
            "raw_answer": (raw_answer or "").strip(),
            "normalized_final_answer": skeleton.get(
                "normalized_final_answer",
                heuristic_state.normalized_final_answer,
            ),
            "mode": skeleton.get("mode", heuristic_state.mode),
            "steps": [step.model_dump(mode="json") for step in steps],
            "selected_target_ref": skeleton.get("selected_target_ref", heuristic_state.selected_target_ref),
            "assumptions": list(skeleton.get("assumptions", heuristic_state.assumptions)),
            "confidence": float(skeleton.get("confidence", heuristic_state.confidence)),
            "notes": list(heuristic_state.notes) + list(skeleton.get("notes", [])),
            "student_graph": None,
        }
    )

    selected_target_ref = merged_payload.get("selected_target_ref")
    if selected_target_ref is not None and selected_target_ref not in allowed_refs:
        raise ValueError(f"selected_target_ref '{selected_target_ref}' is not in allowed_refs")

    try:
        merged_state = StudentWorkState.model_validate(merged_payload)
    except ValidationError as exc:
        raise exc

    return _attach_student_graph(merged_state, problem=problem)


def _allowed_student_refs(problem: FormalizedProblem | None) -> list[str]:
    refs: set[str] = set()
    if problem is not None:
        refs.update(quantity.quantity_id for quantity in problem.quantities)
        if problem.target is not None:
            refs.add(problem.target.target_variable)
    return sorted(refs)


def _compare_with_heuristic_student_notes(
    heuristic_state: StudentWorkState,
    refined_state: StudentWorkState,
) -> list[str]:
    notes: list[str] = []
    if heuristic_state.normalized_final_answer != refined_state.normalized_final_answer:
        notes.append("student_llm_diff:normalized_final_answer")
    if heuristic_state.mode != refined_state.mode:
        notes.append("student_llm_diff:mode")
    if heuristic_state.selected_target_ref != refined_state.selected_target_ref:
        notes.append("student_llm_diff:selected_target_ref")
    if len(heuristic_state.steps) != len(refined_state.steps):
        notes.append("student_llm_diff:step_count")
        return notes
    for heuristic_step, refined_step in zip(heuristic_state.steps, refined_state.steps):
        if heuristic_step.operation != refined_step.operation:
            notes.append(f"student_llm_diff:operation:{refined_step.step_id}")
        if heuristic_step.extracted_value != refined_step.extracted_value:
            notes.append(f"student_llm_diff:value:{refined_step.step_id}")
        if heuristic_step.referenced_ids != refined_step.referenced_ids:
            notes.append(f"student_llm_diff:refs:{refined_step.step_id}")
    return notes


def _schema_validation_result(exc: ValidationError | ValueError | TypeError) -> GraphValidationResult:
    if isinstance(exc, ValidationError):
        issues = [
            GraphValidationIssue(
                code="student_schema_validation_error",
                message=error["msg"],
                details={"loc": list(error["loc"])},
            )
            for error in exc.errors()
        ]
    else:
        issues = [GraphValidationIssue(code="student_schema_build_error", message=str(exc))]
    return GraphValidationResult(
        is_valid=False,
        issues=issues,
        operation_node_count=0,
        notes=["student_schema_validation_failed"],
    )
