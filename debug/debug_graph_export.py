"""Build and export problem/reference/student graph artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.formalizer import (
    export_problem_graph_to_neo4j_cypher,
    formalize_problem,
    formalize_student_work,
)
from src.models import (
    CanonicalReference,
    ProblemGraph,
    ProblemGraphEdge,
    ProblemGraphEdgeType,
    ProblemGraphNode,
    ProblemGraphNodeType,
    ProvenanceSource,
    QuantitySemanticRole,
)
from src.runtime import build_canonical_reference

PROBLEM_TEXT = (
    "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
    "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
)
STUDENT_ANSWER = "12 * 40 = 480\n12 - 10 = 2\n5% of 40 = 2\n2 * 2 = 4\n480 - 4 = 474\nAnswer is 474."

PROBLEM_GRAPH_SCOPE = "debug_problem_graph"
REFERENCE_GRAPH_SCOPE = "debug_reference_graph"
STUDENT_GRAPH_SCOPE = "debug_student_graph"

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
PROBLEM_OUTPUT_PATH = ARTIFACT_DIR / "problem_graph.cypher"
REFERENCE_OUTPUT_PATH = ARTIFACT_DIR / "reference_graph.cypher"
STUDENT_OUTPUT_PATH = ARTIFACT_DIR / "student_graph.cypher"


def _build_reference_graph(reference: CanonicalReference) -> ProblemGraph:
    problem = reference.formalized_problem
    plan = reference.chosen_plan
    trace = reference.execution_trace
    trace_by_step_id = {step_result.step_id: step_result for step_result in trace.step_results}

    nodes: dict[str, ProblemGraphNode] = {}
    edges: list[ProblemGraphEdge] = []
    edge_ids: set[str] = set()

    def add_node(node: ProblemGraphNode) -> None:
        nodes.setdefault(node.node_id, node)

    def add_edge(edge: ProblemGraphEdge) -> None:
        if edge.edge_id in edge_ids:
            return
        edges.append(edge)
        edge_ids.add(edge.edge_id)

    for quantity in problem.quantities:
        add_node(
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

    def ensure_input_node(ref_id: str) -> None:
        if ref_id in nodes:
            return
        node_type = ProblemGraphNodeType.TARGET if ref_id == plan.target_ref else ProblemGraphNodeType.INTERMEDIATE
        add_node(
            ProblemGraphNode(
                node_id=ref_id,
                node_type=node_type,
                label=ref_id,
                target_variable=ref_id if node_type == ProblemGraphNodeType.TARGET else None,
                semantic_role=(
                    None if node_type == ProblemGraphNodeType.TARGET else QuantitySemanticRole.INTERMEDIATE
                ),
                confidence=0.55,
                provenance=ProvenanceSource.SOLVER_REFERENCE,
                notes=["reference_placeholder_ref"],
            )
        )

    for step_index, step in enumerate(plan.steps, start=1):
        op_node_id = f"reference_op_{step.step_id}"
        step_result = trace_by_step_id.get(step.step_id)
        output_value = step_result.output_value if step_result is not None and step_result.success else None
        output_node_type = (
            ProblemGraphNodeType.TARGET if step.output_ref == plan.target_ref else ProblemGraphNodeType.INTERMEDIATE
        )

        add_node(
            ProblemGraphNode(
                node_id=op_node_id,
                node_type=ProblemGraphNodeType.OPERATION,
                label=step.explanation or step.expression,
                operation=step.operation,
                expression=step.expression,
                step_id=step.step_id,
                step_index=step_index,
                confidence=step.confidence,
                provenance=ProvenanceSource.SOLVER_REFERENCE,
                notes=[],
            )
        )
        add_node(
            ProblemGraphNode(
                node_id=step.output_ref,
                node_type=output_node_type,
                label=step.output_ref,
                value=output_value,
                target_variable=step.output_ref if output_node_type == ProblemGraphNodeType.TARGET else None,
                semantic_role=(
                    None if output_node_type == ProblemGraphNodeType.TARGET else QuantitySemanticRole.INTERMEDIATE
                ),
                confidence=step.confidence,
                provenance=ProvenanceSource.SOLVER_REFERENCE,
                notes=(list(step_result.notes) if step_result is not None else []),
            )
        )

        for position, input_ref in enumerate(step.input_refs):
            ensure_input_node(input_ref)
            add_edge(
                ProblemGraphEdge(
                    edge_id=f"edge_{input_ref}_to_{op_node_id}_{position}",
                    source_node_id=input_ref,
                    target_node_id=op_node_id,
                    edge_type=ProblemGraphEdgeType.INPUT_TO_OPERATION,
                    position=position,
                    confidence=step.confidence,
                    provenance=ProvenanceSource.SOLVER_REFERENCE,
                    notes=[],
                )
            )

        add_edge(
            ProblemGraphEdge(
                edge_id=f"edge_{op_node_id}_to_{step.output_ref}",
                source_node_id=op_node_id,
                target_node_id=step.output_ref,
                edge_type=ProblemGraphEdgeType.OUTPUT_FROM_OPERATION,
                confidence=step.confidence,
                provenance=ProvenanceSource.SOLVER_REFERENCE,
                notes=[],
            )
        )

    return ProblemGraph(
        nodes=list(nodes.values()),
        edges=edges,
        target_node_id=plan.target_ref,
        confidence=min(max(reference.confidence, 0.4), 0.98),
        provenance=ProvenanceSource.SOLVER_REFERENCE,
        notes=[
            "reference_graph_built_from_executable_plan",
            f"reference_steps={len(plan.steps)}",
            f"trace_success={trace.success}",
        ],
    )


def main() -> None:
    formalized = formalize_problem(PROBLEM_TEXT)
    if formalized.problem_graph is None:
        raise RuntimeError("formalize_problem did not produce problem_graph")

    reference = build_canonical_reference(formalized)
    reference_graph = _build_reference_graph(reference)

    student_work = formalize_student_work(
        STUDENT_ANSWER,
        problem=formalized,
        reference=reference,
        llm_client=None,
    )
    if student_work.student_graph is None:
        raise RuntimeError("formalize_student_work did not produce student_graph")

    problem_cypher = export_problem_graph_to_neo4j_cypher(
        formalized.problem_graph,
        graph_scope=PROBLEM_GRAPH_SCOPE,
        clear_scope=True,
    )
    reference_cypher = export_problem_graph_to_neo4j_cypher(
        reference_graph,
        graph_scope=REFERENCE_GRAPH_SCOPE,
        clear_scope=True,
    )
    student_cypher = export_problem_graph_to_neo4j_cypher(
        student_work.student_graph,
        graph_scope=STUDENT_GRAPH_SCOPE,
        clear_scope=True,
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    PROBLEM_OUTPUT_PATH.write_text(problem_cypher, encoding="utf-8")
    REFERENCE_OUTPUT_PATH.write_text(reference_cypher, encoding="utf-8")
    STUDENT_OUTPUT_PATH.write_text(student_cypher, encoding="utf-8")

    print("Graphs exported successfully")
    print(f"Problem graph:   {PROBLEM_OUTPUT_PATH}")
    print(f"Reference graph: {REFERENCE_OUTPUT_PATH}")
    print(f"Student graph:   {STUDENT_OUTPUT_PATH}")
    print("Run inside Neo4j Browser:")
    print(f"MATCH (n:FormalizeNode {{graph_scope: '{PROBLEM_GRAPH_SCOPE}'}}) RETURN n")
    print(f"MATCH (n:FormalizeNode {{graph_scope: '{REFERENCE_GRAPH_SCOPE}'}}) RETURN n")
    print(f"MATCH (n:FormalizeNode {{graph_scope: '{STUDENT_GRAPH_SCOPE}'}}) RETURN n")


if __name__ == "__main__":
    main()
