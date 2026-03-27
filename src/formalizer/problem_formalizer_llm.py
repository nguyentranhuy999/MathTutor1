"""LLM prompt and retry loop for compact-skeleton problem formalization."""
from __future__ import annotations

import json

from pydantic import ValidationError

from src.formalizer.problem_formalizer_builder import (
    _build_compact_draft,
    _build_formalized_problem_from_skeleton,
)
from src.formalizer.problem_formalizer_validation import (
    _graph_feedback_payload,
    _missing_graph_validation_result,
    _schema_validation_result,
    _semantic_sanity_validation_result,
    validate_formalized_problem,
)
from src.llm import LLMClient
from src.models import (
    FormalizedProblem,
    GraphValidationIssue,
    GraphValidationResult,
    OperationType,
    QuantitySemanticRole,
    RelationType,
    TraceOperation,
)
from src.runtime.graph_validator import validate_problem_graph


def _build_llm_graph_prompt(
    problem_text: str,
    heuristic_problem: FormalizedProblem,
    feedback_issues: list[dict],
    attempt_index: int,
) -> tuple[str, str]:
    compact_draft = _build_compact_draft(heuristic_problem)
    system_prompt = (
        "You are a math problem formalizer. Return only a compact typed skeleton JSON object. "
        "Do not return the full FormalizedProblem. Use only the provided ids and allowed enum values. "
        "Your job is to correct semantics and propose an executable operation chain; local code will build the final object."
    )
    user_prompt = (
        f"Problem text:\n{problem_text}\n\n"
        "Return one JSON object with exactly these top-level fields:\n"
        "{\n"
        '  "quantity_updates": [\n'
        '    {"quantity_id": "...", "semantic_role": "...", "unit": "...", "entity_id": "...", "is_target_candidate": true}\n'
        "  ],\n"
        '  "target_update": {"surface_text": "...", "normalized_question": "...", "target_variable": "...", '
        '"target_quantity_id": "...", "entity_id": "...", "unit": "...", "description": "...", "confidence": 0.0},\n'
        '  "relation_updates": [\n'
        '    {"relation_id": "...", "relation_type": "...", "operation_hint": "...", '
        '"source_quantity_ids": ["..."], "target_variable": "...", "expression": "...", "rationale": "...", "confidence": 0.0}\n'
        "  ],\n"
        '  "graph_steps": [\n'
        '    {"step_id": "...", "step_index": 1, "operation": "...", "input_refs": ["..."], "output_ref": "...", '
        '"expression": "...", "label": "...", "output_unit": "...", "confidence": 0.0}\n'
        "  ],\n"
        '  "graph_target_node_id": "...",\n'
        '  "graph_confidence": 0.0,\n'
        '  "graph_notes": ["..."],\n'
        '  "assumptions": ["..."],\n'
        '  "confidence": 0.0,\n'
        '  "notes": ["..."]\n'
        "}\n\n"
        f"Allowed quantity semantic_role values: {[role.value for role in QuantitySemanticRole]}\n"
        f"Allowed relation_type values: {[relation.value for relation in RelationType]}\n"
        f"Allowed operation_hint values: {[operation.value for operation in OperationType]}\n"
        f"Allowed graph_steps operation values: {[operation.value for operation in TraceOperation]}\n\n"
        "Hard constraints:\n"
        "1. Reuse existing quantity_id and entity_id values from the draft. Do not invent new quantity ids.\n"
        "2. graph_target_node_id must match target_update.target_variable or the heuristic target variable.\n"
        "3. Each graph step must include step_id, step_index, operation, input_refs, output_ref, and expression.\n"
        "4. input_refs may reference only known quantity ids or outputs created by earlier steps.\n"
        "5. The final target must be reachable from the graph_steps sequence.\n"
        "6. Use only enum values exactly as listed above.\n"
        "7. Keep notes concise.\n\n"
        f"Attempt index: {attempt_index}\n\n"
        f"Structured feedback from the previous failed attempt:\n{json.dumps(feedback_issues, ensure_ascii=True)}\n\n"
        "Compact heuristic draft for reference only:\n"
        f"{json.dumps(compact_draft, ensure_ascii=True)}"
    )
    return system_prompt, user_prompt


def _llm_formalize_problem(
    problem_text: str,
    heuristic_problem: FormalizedProblem,
    llm_client: LLMClient,
) -> FormalizedProblem:
    feedback_issues: list[dict] = []
    last_validation_result = _missing_graph_validation_result()

    for attempt_index in range(1, 4):
        system_prompt, user_prompt = _build_llm_graph_prompt(
            problem_text,
            heuristic_problem,
            feedback_issues,
            attempt_index,
        )
        payload = llm_client.generate_json(
            task_name="problem_formalizer",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=50000,
        )
        payload["problem_text"] = problem_text.strip()
        notes = list(payload.get("notes", []))
        notes.append(f"llm_formalization_attempt:{attempt_index}")
        payload["notes"] = notes

        try:
            refined = _build_formalized_problem_from_skeleton(problem_text, heuristic_problem, payload)
        except ValidationError as exc:
            last_validation_result = _schema_validation_result(exc)
            feedback_issues = _graph_feedback_payload(last_validation_result)
            continue
        except (ValueError, TypeError) as exc:
            last_validation_result = GraphValidationResult(
                is_valid=False,
                issues=[
                    GraphValidationIssue(
                        code="skeleton_build_error",
                        message=str(exc),
                    )
                ],
                operation_node_count=0,
                notes=["skeleton_build_failed"],
            )
            feedback_issues = _graph_feedback_payload(last_validation_result)
            continue

        refined = validate_formalized_problem(refined)
        if refined.problem_graph is None:
            last_validation_result = _missing_graph_validation_result()
            feedback_issues = _graph_feedback_payload(last_validation_result)
            continue

        last_validation_result = validate_problem_graph(refined)
        if last_validation_result.is_valid:
            semantic_validation = _semantic_sanity_validation_result(refined)
            if not semantic_validation.is_valid:
                last_validation_result = semantic_validation
                feedback_issues = _graph_feedback_payload(last_validation_result)
                continue
            success_notes = list(refined.notes)
            success_notes.append("llm_formalization_used")
            success_notes.append("llm_compact_skeleton_used")
            if attempt_index > 1:
                success_notes.append(f"llm_formalization_repaired_after:{attempt_index}")
            return refined.model_copy(update={"notes": success_notes})

        feedback_issues = _graph_feedback_payload(last_validation_result)

    issue_notes = [f"graph_issue:{issue.code}" for issue in last_validation_result.issues]
    fallback_notes = list(heuristic_problem.notes) + issue_notes + ["llm_formalization_failed_fallback"]
    return heuristic_problem.model_copy(update={"notes": fallback_notes})
