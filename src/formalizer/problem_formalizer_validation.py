"""Validation, repair, and acceptance policy helpers for problem formalization."""
from __future__ import annotations

from pydantic import ValidationError

from src.models import (
    FormalizedProblem,
    GraphValidationIssue,
    GraphValidationResult,
    OperationType,
    ProblemEntity,
    ProblemGraphNodeType,
    ProvenanceSource,
    QuantityAnnotation,
    QuantitySemanticRole,
    RelationCandidate,
    RelationType,
    TargetSpec,
)

from src.formalizer.problem_formalizer_extractors import _dedupe_quantities


def _sanitize_quantity_update(quantity_update: dict) -> tuple[dict, str | None]:
    sanitized = dict(quantity_update)
    invalid_note = None

    semantic_role = sanitized.get("semantic_role")
    if semantic_role is not None:
        allowed_roles = {role.value for role in QuantitySemanticRole}
        if semantic_role not in allowed_roles:
            invalid_note = f"ignored_invalid_semantic_role:{sanitized.get('quantity_id', 'unknown')}:{semantic_role}"
            sanitized.pop("semantic_role", None)

    return sanitized, invalid_note


def _coerce_list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _schema_validation_result(exc: ValidationError) -> GraphValidationResult:
    issues: list[GraphValidationIssue] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "unknown"
        issues.append(
            GraphValidationIssue(
                code="schema_validation_error",
                message=str(error.get("msg", "Schema validation failed")),
                details={
                    "location": location,
                    "error_type": error.get("type"),
                },
            )
        )
    return GraphValidationResult(
        is_valid=False,
        issues=issues,
        operation_node_count=0,
        notes=["schema_validation_failed"],
    )


def _missing_graph_validation_result() -> GraphValidationResult:
    return GraphValidationResult(
        is_valid=False,
        issues=[
            GraphValidationIssue(
                code="missing_problem_graph",
                message="LLM output must include a typed problem_graph",
            )
        ],
        operation_node_count=0,
        notes=["missing_problem_graph"],
    )


def _graph_feedback_payload(validation_result: GraphValidationResult) -> list[dict]:
    return [issue.model_dump(mode="json") for issue in validation_result.issues]


def validate_formalized_problem(problem: FormalizedProblem) -> FormalizedProblem:
    notes = list(problem.notes)

    deduped_entities: list[ProblemEntity] = []
    seen_entities: set[str] = set()
    for entity in problem.entities:
        key = (entity.normalized_name or entity.surface_text).strip().lower()
        if key in seen_entities:
            notes.append(f"deduped_entity:{key}")
            continue
        seen_entities.add(key)
        deduped_entities.append(entity)

    quantities, quantity_notes = _dedupe_quantities(list(problem.quantities))
    notes.extend(quantity_notes)
    if not quantities:
        notes.append("no_quantities_extracted")

    target = problem.target
    if target is None:
        target = TargetSpec(
            surface_text=problem.problem_text.strip(),
            normalized_question=problem.problem_text.strip(),
            target_variable="answer",
            provenance=ProvenanceSource.UNKNOWN,
            confidence=0.1,
        )
        notes.append("target_missing_fallback")

    relation_candidates = list(problem.relation_candidates)
    if not relation_candidates:
        problem = problem.model_copy(
            update={
                "relation_candidates": [
                    RelationCandidate(
                        relation_id="relation_fallback",
                        relation_type=RelationType.UNKNOWN,
                        operation_hint=OperationType.UNKNOWN,
                        source_quantity_ids=[q.quantity_id for q in quantities],
                        target_variable=target.target_variable,
                        confidence=0.1,
                        provenance=ProvenanceSource.UNKNOWN,
                        rationale="Fallback relation candidate due to missing inferred relation.",
                    )
                ]
            }
        )
        notes.append("relation_candidate_fallback")
        relation_candidates = list(problem.relation_candidates)

    for index, relation in enumerate(relation_candidates):
        expression = relation.expression
        if relation.target_variable == target.target_variable and not expression and quantities:
            expression = f"{target.target_variable} = unresolved_relation({', '.join(q.quantity_id for q in quantities)})"
            notes.append(f"filled_expression_for:{relation.relation_id}")
        relation_candidates[index] = relation.model_copy(update={"expression": expression})

    confidence = 0.15
    if quantities:
        confidence += 0.25
    if len(quantities) >= 2:
        confidence += 0.15
    if target and target.provenance != ProvenanceSource.UNKNOWN:
        confidence += 0.15
    if relation_candidates and relation_candidates[0].relation_type != RelationType.UNKNOWN:
        confidence += 0.2
    if any(q.semantic_role == QuantitySemanticRole.PERCENT for q in quantities):
        notes.append("contains_percent_quantity")
    if any(q.semantic_role == QuantitySemanticRole.THRESHOLD for q in quantities):
        notes.append("contains_threshold_quantity")

    return problem.model_copy(
        update={
            "entities": deduped_entities,
            "quantities": quantities,
            "target": target,
            "relation_candidates": relation_candidates,
            "confidence": max(problem.confidence, min(confidence, 0.92)),
            "notes": notes,
        }
    )


def _heuristic_graph_operation_steps(problem: FormalizedProblem):
    if problem.problem_graph is None:
        return []
    return [
        node
        for node in problem.problem_graph.nodes
        if node.node_type == ProblemGraphNodeType.OPERATION
    ]


def _compare_with_heuristic_notes(
    problem: FormalizedProblem,
    heuristic_problem: FormalizedProblem,
) -> list[str]:
    notes: list[str] = []
    heuristic_quantities = {quantity.quantity_id: quantity for quantity in heuristic_problem.quantities}

    for quantity in problem.quantities:
        heuristic_quantity = heuristic_quantities.get(quantity.quantity_id)
        if heuristic_quantity is None:
            continue
        if quantity.semantic_role != heuristic_quantity.semantic_role:
            notes.append(
                "heuristic_disagreement:quantity_role:"
                f"{quantity.quantity_id}:{heuristic_quantity.semantic_role.value}->{quantity.semantic_role.value}"
            )
        if quantity.unit != heuristic_quantity.unit:
            notes.append(
                f"heuristic_disagreement:quantity_unit:{quantity.quantity_id}:{heuristic_quantity.unit}->{quantity.unit}"
            )

    if problem.target is not None and heuristic_problem.target is not None:
        if problem.target.target_variable != heuristic_problem.target.target_variable:
            notes.append(
                "heuristic_disagreement:target_variable:"
                f"{heuristic_problem.target.target_variable}->{problem.target.target_variable}"
            )
        if problem.target.target_quantity_id != heuristic_problem.target.target_quantity_id:
            notes.append(
                "heuristic_disagreement:target_quantity_id:"
                f"{heuristic_problem.target.target_quantity_id}->{problem.target.target_quantity_id}"
            )

    if problem.relation_candidates and heuristic_problem.relation_candidates:
        current = problem.relation_candidates[0]
        heuristic = heuristic_problem.relation_candidates[0]
        if current.relation_type != heuristic.relation_type:
            notes.append(
                "heuristic_disagreement:relation_type:"
                f"{heuristic.relation_type.value}->{current.relation_type.value}"
            )
        if current.operation_hint != heuristic.operation_hint:
            notes.append(
                "heuristic_disagreement:operation_hint:"
                f"{heuristic.operation_hint.value}->{current.operation_hint.value}"
            )

    current_steps = len(_heuristic_graph_operation_steps(problem))
    heuristic_steps = len(_heuristic_graph_operation_steps(heuristic_problem))
    if current_steps != heuristic_steps:
        notes.append(f"heuristic_disagreement:graph_step_count:{heuristic_steps}->{current_steps}")

    return notes


def _apply_local_semantic_repairs(problem: FormalizedProblem) -> FormalizedProblem:
    if problem.target is None:
        return problem

    notes = list(problem.notes)
    graph_steps = _heuristic_graph_operation_steps(problem)
    target = problem.target
    quantities = list(problem.quantities)

    if graph_steps and len(graph_steps) > 1 and target.target_quantity_id is not None:
        target = target.model_copy(update={"target_quantity_id": None})
        notes.append("local_semantic_repair:cleared_target_quantity_for_derived_target")

    lowered_target_text = target.surface_text.lower()
    repaired_quantities: list[QuantityAnnotation] = []
    target_candidate_changed = False
    for quantity in quantities:
        should_be_candidate = quantity.surface_text.lower() in lowered_target_text
        if graph_steps and len(graph_steps) > 1 and quantity.is_target_candidate and not should_be_candidate:
            repaired_quantities.append(quantity.model_copy(update={"is_target_candidate": False}))
            target_candidate_changed = True
        else:
            repaired_quantities.append(quantity)

    if target_candidate_changed:
        notes.append("local_semantic_repair:cleared_input_target_candidates")

    return problem.model_copy(
        update={
            "target": target,
            "quantities": repaired_quantities,
            "notes": notes,
        }
    )


def _semantic_sanity_validation_result(problem: FormalizedProblem) -> GraphValidationResult:
    issues: list[GraphValidationIssue] = []
    graph_steps = _heuristic_graph_operation_steps(problem)
    quantities_by_role = {quantity.semantic_role for quantity in problem.quantities}

    if problem.target is None:
        issues.append(
            GraphValidationIssue(
                code="missing_target_spec",
                message="Formalized problem must include a target.",
            )
        )

    if len(graph_steps) > 1 and problem.target is not None and problem.target.target_quantity_id is not None:
        issues.append(
            GraphValidationIssue(
                code="derived_target_still_points_to_quantity",
                message="Derived multi-step targets must not point to a visible quantity id.",
                details={"target_quantity_id": problem.target.target_quantity_id},
            )
        )

    if problem.relation_candidates:
        relation = problem.relation_candidates[0]
        if relation.relation_type == RelationType.RATE_UNIT_RELATION:
            if QuantitySemanticRole.BASE not in quantities_by_role:
                issues.append(
                    GraphValidationIssue(
                        code="missing_base_quantity_for_rate_relation",
                        message="Rate/unit relations must include a base quantity.",
                    )
                )
            if QuantitySemanticRole.UNIT_RATE not in quantities_by_role:
                issues.append(
                    GraphValidationIssue(
                        code="missing_unit_rate_for_rate_relation",
                        message="Rate/unit relations must include a unit_rate quantity.",
                    )
                )
            if QuantitySemanticRole.PERCENT not in quantities_by_role:
                issues.append(
                    GraphValidationIssue(
                        code="missing_percent_for_rate_relation",
                        message="Rate/unit discount relations must include a percent quantity.",
                    )
                )
            if QuantitySemanticRole.THRESHOLD not in quantities_by_role:
                issues.append(
                    GraphValidationIssue(
                        code="missing_threshold_for_rate_relation",
                        message="Rate/unit discount relations must include a threshold quantity.",
                    )
                )

    return GraphValidationResult(
        is_valid=not issues,
        issues=issues,
        target_node_id=problem.problem_graph.target_node_id if problem.problem_graph is not None else None,
        operation_node_count=len(graph_steps),
        notes=["semantic_sanity_checked"],
    )

