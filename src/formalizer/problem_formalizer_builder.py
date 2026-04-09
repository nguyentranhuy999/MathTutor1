"""Builders for heuristic drafts and compact-skeleton reconstruction."""
from __future__ import annotations

from src.formalizer.problem_graph import build_problem_graph, build_problem_summary_graph
from src.formalizer.problem_formalizer_extractors import (
    _attach_target_quantity,
    _build_relation_candidates,
    _build_target_spec,
    _extract_entities,
    _extract_quantities,
    _extract_semantic_triples,
    _extract_target_text,
    _link_quantities_to_entities,
)
from src.formalizer.problem_formalizer_validation import (
    _apply_local_semantic_repairs,
    _coerce_list_of_strings,
    _compare_with_heuristic_notes,
    _sanitize_quantity_update,
    validate_formalized_problem,
)
from src.models import (
    FormalizedProblem,
    ProblemGraph,
    ProblemGraphEdge,
    ProblemGraphEdgeType,
    ProblemGraphNode,
    ProblemGraphNodeType,
    ProvenanceSource,
    QuantityAnnotation,
    RelationCandidate,
    RelationType,
    SemanticTriple,
    TargetSpec,
    TraceOperation,
)


def _build_compact_draft(heuristic_problem: FormalizedProblem) -> dict:
    return {
        "problem_text": heuristic_problem.problem_text,
        "quantities": [
            {
                "quantity_id": quantity.quantity_id,
                "surface_text": quantity.surface_text,
                "value": quantity.value,
                "unit": quantity.unit,
                "entity_id": quantity.entity_id,
                "semantic_role": quantity.semantic_role.value,
                "is_target_candidate": quantity.is_target_candidate,
            }
            for quantity in heuristic_problem.quantities
        ],
        "entities": [
            {
                "entity_id": entity.entity_id,
                "surface_text": entity.surface_text,
                "normalized_name": entity.normalized_name,
                "entity_type": entity.entity_type,
            }
            for entity in heuristic_problem.entities
        ],
        "target": (
            {
                "surface_text": heuristic_problem.target.surface_text,
                "normalized_question": heuristic_problem.target.normalized_question,
                "target_variable": heuristic_problem.target.target_variable,
                "target_quantity_id": heuristic_problem.target.target_quantity_id,
                "entity_id": heuristic_problem.target.entity_id,
                "unit": heuristic_problem.target.unit,
                "description": heuristic_problem.target.description,
            }
            if heuristic_problem.target is not None
            else None
        ),
        "relation_candidates": [
            {
                "relation_id": relation.relation_id,
                "relation_type": relation.relation_type.value,
                "operation_hint": relation.operation_hint.value,
                "source_quantity_ids": list(relation.source_quantity_ids),
                "target_variable": relation.target_variable,
                "expression": relation.expression,
                "rationale": relation.rationale,
            }
            for relation in heuristic_problem.relation_candidates
        ],
        "semantic_triples": [
            {
                "triple_id": triple.triple_id,
                "subject_text": triple.subject_text,
                "predicate_text": triple.predicate_text,
                "object_text": triple.object_text,
                "subject_node_id": triple.subject_node_id,
                "object_node_id": triple.object_node_id,
                "edge_type": triple.edge_type.value,
                "sentence_index": triple.sentence_index,
                "clause_index": triple.clause_index,
                "confidence": triple.confidence,
                "provenance": triple.provenance.value,
                "notes": list(triple.notes),
            }
            for triple in heuristic_problem.semantic_triples
        ],
        "graph_steps": [
            {
                "step_id": node.step_id,
                "step_index": node.step_index,
                "operation": node.operation.value if node.operation is not None else None,
                "expression": node.expression,
                "label": node.label,
                "input_refs": [
                    edge.source_node_id
                    for edge in sorted(
                        (
                            edge
                            for edge in (heuristic_problem.problem_graph.edges if heuristic_problem.problem_graph else [])
                            if edge.edge_type == ProblemGraphEdgeType.INPUT_TO_OPERATION
                            and edge.target_node_id == node.node_id
                        ),
                        key=lambda edge: edge.position if edge.position is not None else 0,
                    )
                ],
                "output_ref": next(
                    (
                        edge.target_node_id
                        for edge in (heuristic_problem.problem_graph.edges if heuristic_problem.problem_graph else [])
                        if edge.edge_type == ProblemGraphEdgeType.OUTPUT_FROM_OPERATION
                        and edge.source_node_id == node.node_id
                    ),
                    None,
                ),
            }
            for node in (heuristic_problem.problem_graph.nodes if heuristic_problem.problem_graph else [])
            if node.node_type == ProblemGraphNodeType.OPERATION
        ],
        "graph_target_node_id": (
            heuristic_problem.problem_graph.target_node_id if heuristic_problem.problem_graph is not None else None
        ),
    }


def _build_problem_graph_from_skeleton(
    problem: FormalizedProblem,
    graph_steps: list[dict],
    graph_target_node_id: str | None,
    graph_confidence: float,
    graph_notes: list[str],
) -> ProblemGraph:
    nodes: list[ProblemGraphNode] = []
    edges: list[ProblemGraphEdge] = []

    for entity in problem.entities:
        nodes.append(
            ProblemGraphNode(
                node_id=entity.entity_id,
                node_type=ProblemGraphNodeType.ENTITY,
                label=entity.surface_text,
                entity_id=entity.entity_id,
                confidence=0.95,
                provenance=ProvenanceSource.PROBLEM_TEXT,
                notes=[],
            )
        )

    for quantity in problem.quantities:
        nodes.append(
            ProblemGraphNode(
                node_id=quantity.quantity_id,
                node_type=ProblemGraphNodeType.QUANTITY,
                label=quantity.surface_text,
                value=quantity.value,
                unit=quantity.unit,
                quantity_id=quantity.quantity_id,
                entity_id=quantity.entity_id,
                semantic_role=quantity.semantic_role,
                confidence=0.95,
                provenance=quantity.provenance,
                notes=list(quantity.notes),
            )
        )
        if quantity.entity_id is not None:
            edges.append(
                ProblemGraphEdge(
                    edge_id=f"edge_{quantity.entity_id}_owns_{quantity.quantity_id}",
                    source_node_id=quantity.entity_id,
                    target_node_id=quantity.quantity_id,
                    edge_type=ProblemGraphEdgeType.ENTITY_HAS_QUANTITY,
                    confidence=0.9,
                    provenance=ProvenanceSource.PROBLEM_TEXT,
                    notes=[],
                )
            )

    target_node_id = graph_target_node_id or (problem.target.target_variable if problem.target is not None else None)
    if problem.target is not None:
        nodes.append(
            ProblemGraphNode(
                node_id=problem.target.target_variable,
                node_type=ProblemGraphNodeType.TARGET,
                label=problem.target.surface_text,
                unit=problem.target.unit,
                entity_id=problem.target.entity_id,
                target_variable=problem.target.target_variable,
                confidence=problem.target.confidence,
                provenance=problem.target.provenance,
                notes=[],
            )
        )
        if problem.target.entity_id is not None:
            edges.append(
                ProblemGraphEdge(
                    edge_id=f"edge_{problem.target.target_variable}_describes_{problem.target.entity_id}",
                    source_node_id=problem.target.target_variable,
                    target_node_id=problem.target.entity_id,
                    edge_type=ProblemGraphEdgeType.DESCRIBES_ENTITY,
                    confidence=0.82,
                    provenance=ProvenanceSource.PROBLEM_TEXT,
                    notes=[],
                )
            )

    existing_node_ids = {node.node_id for node in nodes}
    existing_refs = set(existing_node_ids)

    for step in sorted(graph_steps, key=lambda item: int(item.get("step_index", 0) or 0)):
        step_id = str(step.get("step_id", "")).strip()
        operation_name = str(step.get("operation", TraceOperation.UNKNOWN.value)).strip()
        output_ref = str(step.get("output_ref", "")).strip()
        op_node_id = f"op_{step_id}"
        input_refs = [str(ref).strip() for ref in step.get("input_refs", []) if str(ref).strip()]
        label = str(step.get("label", step_id)).strip() or step_id
        expression = str(step.get("expression", "")).strip()

        nodes.append(
            ProblemGraphNode(
                node_id=op_node_id,
                node_type=ProblemGraphNodeType.OPERATION,
                label=label,
                operation=TraceOperation(operation_name),
                expression=expression,
                step_id=step_id,
                step_index=int(step.get("step_index", 1) or 1),
                confidence=float(step.get("confidence", 0.85) or 0.85),
                provenance=ProvenanceSource.LLM,
                notes=[],
            )
        )

        for position, input_ref in enumerate(input_refs):
            if input_ref not in existing_refs:
                continue
            edges.append(
                ProblemGraphEdge(
                    edge_id=f"edge_{input_ref}_to_{op_node_id}_{position}",
                    source_node_id=input_ref,
                    target_node_id=op_node_id,
                    edge_type=ProblemGraphEdgeType.INPUT_TO_OPERATION,
                    position=position,
                    confidence=0.9,
                    provenance=ProvenanceSource.LLM,
                    notes=[],
                )
            )

        if output_ref and output_ref not in existing_node_ids:
            node_type = (
                ProblemGraphNodeType.TARGET
                if problem.target is not None and output_ref == problem.target.target_variable
                else ProblemGraphNodeType.INTERMEDIATE
            )
            nodes.append(
                ProblemGraphNode(
                    node_id=output_ref,
                    node_type=node_type,
                    label=output_ref if node_type == ProblemGraphNodeType.INTERMEDIATE else problem.target.surface_text,
                    unit=step.get("output_unit") if isinstance(step.get("output_unit"), str) else None,
                    target_variable=output_ref if node_type == ProblemGraphNodeType.TARGET else None,
                    confidence=float(step.get("confidence", 0.85) or 0.85),
                    provenance=ProvenanceSource.LLM,
                    notes=[],
                )
            )
            existing_node_ids.add(output_ref)
            existing_refs.add(output_ref)

        if output_ref:
            edges.append(
                ProblemGraphEdge(
                    edge_id=f"edge_{op_node_id}_to_{output_ref}",
                    source_node_id=op_node_id,
                    target_node_id=output_ref,
                    edge_type=ProblemGraphEdgeType.OUTPUT_FROM_OPERATION,
                    confidence=0.9,
                    provenance=ProvenanceSource.LLM,
                    notes=[],
                )
            )
            existing_refs.add(output_ref)

        existing_refs.add(op_node_id)

    return ProblemGraph(
        nodes=nodes,
        edges=edges,
        target_node_id=target_node_id,
        confidence=graph_confidence,
        provenance=ProvenanceSource.LLM,
        notes=graph_notes,
    )


def _build_formalized_problem_from_skeleton(
    problem_text: str,
    heuristic_problem: FormalizedProblem,
    payload: dict,
) -> FormalizedProblem:
    notes = list(heuristic_problem.notes)
    notes.extend(_coerce_list_of_strings(payload.get("notes")))

    quantity_updates_by_id: dict[str, dict] = {}
    for raw_update in payload.get("quantity_updates", []):
        if not isinstance(raw_update, dict):
            continue
        quantity_id = str(raw_update.get("quantity_id", "")).strip()
        if not quantity_id:
            continue
        sanitized, invalid_note = _sanitize_quantity_update(raw_update)
        if invalid_note:
            notes.append(invalid_note)
        quantity_updates_by_id[quantity_id] = sanitized

    quantities: list[QuantityAnnotation] = []
    for quantity in heuristic_problem.quantities:
        update = quantity_updates_by_id.get(quantity.quantity_id, {})
        quantity_payload = quantity.model_dump(mode="json")
        quantity_payload.update(
            {
                key: value
                for key, value in update.items()
                if key in {"unit", "entity_id", "semantic_role", "is_target_candidate"}
            }
        )
        quantities.append(QuantityAnnotation.model_validate(quantity_payload))
        if update.get("semantic_role") and update.get("semantic_role") != quantity.semantic_role.value:
            notes.append(
                f"llm_quantity_role_update:{quantity.quantity_id}:{quantity.semantic_role.value}->{update.get('semantic_role')}"
            )

    entities = list(heuristic_problem.entities)

    target_payload = heuristic_problem.target.model_dump(mode="json") if heuristic_problem.target is not None else {}
    target_update = payload.get("target_update")
    if isinstance(target_update, dict):
        target_payload.update(
            {
                key: value
                for key, value in target_update.items()
                if key
                in {
                    "surface_text",
                    "normalized_question",
                    "target_variable",
                    "target_quantity_id",
                    "entity_id",
                    "unit",
                    "description",
                    "confidence",
                }
            }
        )
    target_payload["provenance"] = ProvenanceSource.LLM.value
    target = TargetSpec.model_validate(target_payload) if target_payload else None

    relation_candidates: list[RelationCandidate] = []
    raw_relations = payload.get("relation_updates")
    if isinstance(raw_relations, list) and raw_relations:
        for index, raw_relation in enumerate(raw_relations, start=1):
            if not isinstance(raw_relation, dict):
                continue
            relation_payload = {
                "relation_id": raw_relation.get("relation_id") or f"relation_{index}",
                "relation_type": raw_relation.get("relation_type", RelationType.UNKNOWN.value),
                "operation_hint": raw_relation.get("operation_hint", "unknown"),
                "source_quantity_ids": raw_relation.get("source_quantity_ids")
                or [quantity.quantity_id for quantity in quantities],
                "target_variable": raw_relation.get("target_variable")
                or (target.target_variable if target is not None else None),
                "expression": raw_relation.get("expression"),
                "rationale": raw_relation.get("rationale"),
                "confidence": raw_relation.get("confidence", 0.75),
                "provenance": ProvenanceSource.LLM.value,
            }
            relation_candidates.append(RelationCandidate.model_validate(relation_payload))
    else:
        relation_candidates = list(heuristic_problem.relation_candidates)

    semantic_triples: list[SemanticTriple] = list(heuristic_problem.semantic_triples)
    raw_triples = payload.get("semantic_triples")
    if isinstance(raw_triples, list) and raw_triples:
        rebuilt_triples: list[SemanticTriple] = []
        for index, raw_triple in enumerate(raw_triples, start=1):
            if not isinstance(raw_triple, dict):
                continue
            triple_payload = {
                "triple_id": raw_triple.get("triple_id") or f"triple_{index}",
                "subject_text": raw_triple.get("subject_text") or "",
                "predicate_text": raw_triple.get("predicate_text") or "",
                "object_text": raw_triple.get("object_text"),
                "subject_node_id": raw_triple.get("subject_node_id"),
                "object_node_id": raw_triple.get("object_node_id"),
                "edge_type": raw_triple.get("edge_type", ProblemGraphEdgeType.VERB_RELATION.value),
                "sentence_index": raw_triple.get("sentence_index"),
                "clause_index": raw_triple.get("clause_index"),
                "confidence": raw_triple.get("confidence", 0.68),
                "provenance": raw_triple.get("provenance", ProvenanceSource.LLM.value),
                "notes": _coerce_list_of_strings(raw_triple.get("notes")),
            }
            try:
                rebuilt_triples.append(SemanticTriple.model_validate(triple_payload))
            except ValueError as exc:
                notes.append(f"llm_semantic_triple_invalid:{index}:{exc}")
        if rebuilt_triples:
            semantic_triples = rebuilt_triples
            notes.append(f"llm_semantic_triples_applied={len(semantic_triples)}")

    graph_steps = payload.get("graph_steps", [])
    if not isinstance(graph_steps, list):
        graph_steps = []
    problem = FormalizedProblem(
        problem_text=problem_text.strip(),
        quantities=quantities,
        entities=entities,
        target=target,
        relation_candidates=relation_candidates,
        semantic_triples=semantic_triples,
        assumptions=_coerce_list_of_strings(payload.get("assumptions")),
        confidence=float(payload.get("confidence", heuristic_problem.confidence) or heuristic_problem.confidence),
        provenance=ProvenanceSource.LLM,
        notes=notes,
    )
    problem = validate_formalized_problem(problem)
    graph = _build_problem_graph_from_skeleton(
        problem=problem,
        graph_steps=[step for step in graph_steps if isinstance(step, dict)],
        graph_target_node_id=payload.get("graph_target_node_id"),
        graph_confidence=float(payload.get("graph_confidence", problem.confidence) or problem.confidence),
        graph_notes=_coerce_list_of_strings(payload.get("graph_notes")) or ["llm_graph_skeleton"],
    )
    problem = problem.model_copy(update={"problem_graph": graph})
    problem = _apply_local_semantic_repairs(problem)
    comparison_notes = _compare_with_heuristic_notes(problem, heuristic_problem)
    if comparison_notes:
        problem = problem.model_copy(update={"notes": list(problem.notes) + comparison_notes})
    summary_graph = build_problem_summary_graph(problem)
    problem = problem.model_copy(update={"problem_summary_graph": summary_graph})
    return problem


def _attach_problem_graphs(problem: FormalizedProblem) -> FormalizedProblem:
    summary_graph = build_problem_summary_graph(problem)
    graph = build_problem_graph(problem)
    return problem.model_copy(update={"problem_summary_graph": summary_graph, "problem_graph": graph})


def _heuristic_formalize_problem(problem_text: str) -> FormalizedProblem:
    cleaned_text = (problem_text or "").strip()
    target_text = _extract_target_text(cleaned_text)
    quantities = _extract_quantities(cleaned_text, target_text)
    entities = _extract_entities(cleaned_text)
    quantities = _link_quantities_to_entities(quantities, entities)
    target = _build_target_spec(cleaned_text, target_text)
    target = _attach_target_quantity(target, quantities)
    relation_candidates, relation_notes = _build_relation_candidates(cleaned_text, target, quantities)
    semantic_triples = _extract_semantic_triples(cleaned_text, target, entities, quantities)

    notes = [f"quantities_extracted={len(quantities)}"]
    if entities:
        notes.append(f"entities_extracted={len(entities)}")
    if target_text:
        notes.append("target_extracted")
    notes.append(f"semantic_triples_extracted={len(semantic_triples)}")
    notes.append("hybrid_layer1_structured_extraction_done")
    notes.append("hybrid_layer2_semantic_triples_done")
    notes.append("hybrid_layer3_llm_refinement_skipped")
    notes.extend(relation_notes)

    problem = FormalizedProblem(
        problem_text=cleaned_text,
        quantities=quantities,
        entities=entities,
        target=target,
        relation_candidates=relation_candidates,
        semantic_triples=semantic_triples,
        assumptions=[],
        confidence=0.0,
        provenance=ProvenanceSource.HEURISTIC,
        notes=notes,
    )
    formalized = _attach_problem_graphs(validate_formalized_problem(problem))
    return formalized.model_copy(update={"notes": list(formalized.notes) + ["hybrid_layer4_graph_projection_done"]})
