"""Build and export problem/reference/student graph artifacts."""

from __future__ import annotations

import argparse
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
from src.shared_input import (
    ANSWER_INPUT_PATH,
    PROBLEM_INPUT_PATH,
)

DEBUG_DIR = Path(__file__).resolve().parent

PROBLEM_GRAPH_SCOPE = "debug_problem_graph"
REFERENCE_GRAPH_SCOPE = "debug_reference_graph"
STUDENT_GRAPH_SCOPE = "debug_student_graph"

ARTIFACT_DIR = DEBUG_DIR / "artifacts"
OUTPUT_DIR = DEBUG_DIR / "outputs"
PROBLEM_OUTPUT_PATH = ARTIFACT_DIR / "problem_graph.cypher"
REFERENCE_OUTPUT_PATH = ARTIFACT_DIR / "reference_graph.cypher"
STUDENT_OUTPUT_PATH = ARTIFACT_DIR / "student_graph.cypher"
STATUS_OUTPUT_PATH = OUTPUT_DIR / "debug_graph_export_status.txt"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export graph bai toan ra file .cypher")
    parser.add_argument("--problem-text", help="Noi dung de bai.")
    parser.add_argument(
        "--problem-file",
        default=str(PROBLEM_INPUT_PATH),
        help=f"Duong dan file txt chua de bai (mac dinh: {PROBLEM_INPUT_PATH}).",
    )
    parser.add_argument("--student-answer", help="Noi dung bai lam hoc sinh.")
    parser.add_argument(
        "--student-file",
        default=str(ANSWER_INPUT_PATH),
        help=f"Duong dan file txt chua bai lam hoc sinh (mac dinh: {ANSWER_INPUT_PATH}).",
    )
    return parser.parse_args(argv)


def _resolve_text(
    inline_text: str | None,
    file_path: str | None,
    field_name: str,
    inline_arg: str,
    file_arg: str,
) -> str:
    if inline_text is not None and inline_text.strip():
        return inline_text.strip()

    if not file_path:
        raise ValueError(f"Thieu {field_name}. Hay truyen {inline_arg} hoac {file_arg}.")

    candidate = Path(file_path)
    if not candidate.exists():
        raise FileNotFoundError(f"Khong tim thay {field_name}: {file_path}")

    text = candidate.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{field_name} trong file '{file_path}' dang rong.")
    return text


def _compact_message(raw: str, *, limit: int = 240) -> str:
    compact = " ".join(raw.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _graph_stats(graph: ProblemGraph | None) -> str:
    if graph is None:
        return "missing"
    return f"nodes={len(graph.nodes)}, edges={len(graph.edges)}, target={graph.target_node_id}"


def _build_diagnostic_graph(
    *,
    base_graph: ProblemGraph | None,
    stage: str,
    error: Exception,
    problem_text: str,
    student_answer: str | None = None,
) -> ProblemGraph:
    nodes = list(base_graph.nodes) if base_graph is not None else []
    edges = list(base_graph.edges) if base_graph is not None else []
    target_node_id = base_graph.target_node_id if base_graph is not None else None

    if target_node_id is None:
        target_node_id = f"diagnostic_target_{stage}"
        nodes.append(
            ProblemGraphNode(
                node_id=target_node_id,
                node_type=ProblemGraphNodeType.TARGET,
                label=f"diagnostic_target_{stage}",
                target_variable=target_node_id,
                confidence=0.2,
                provenance=ProvenanceSource.UNKNOWN,
                notes=["target_missing_from_base_graph"],
            )
        )

    issue_node_id = f"diagnostic_{stage}_issue"
    if any(node.node_id == issue_node_id for node in nodes):
        issue_node_id = f"{issue_node_id}_{len(nodes)}"

    issue_notes = [
        f"stage={stage}",
        f"error_type={type(error).__name__}",
        f"error_message={_compact_message(str(error), limit=320)}",
        f"problem_preview={_compact_message(problem_text, limit=200)}",
    ]
    if student_answer is not None:
        issue_notes.append(f"student_preview={_compact_message(student_answer, limit=200)}")
    if base_graph is not None:
        issue_notes.append(f"base_graph={_graph_stats(base_graph)}")
    else:
        issue_notes.append("base_graph=missing")

    nodes.append(
        ProblemGraphNode(
            node_id=issue_node_id,
            node_type=ProblemGraphNodeType.INTERMEDIATE,
            label=f"{stage}_build_failed",
            confidence=0.2,
            provenance=ProvenanceSource.UNKNOWN,
            notes=issue_notes,
        )
    )

    issue_edge_id = f"edge_{issue_node_id}_to_{target_node_id}"
    if any(edge.edge_id == issue_edge_id for edge in edges):
        issue_edge_id = f"{issue_edge_id}_{len(edges)}"
    edges.append(
        ProblemGraphEdge(
            edge_id=issue_edge_id,
            source_node_id=issue_node_id,
            target_node_id=target_node_id,
            edge_type=ProblemGraphEdgeType.TARGETS_VALUE,
            confidence=0.2,
            provenance=ProvenanceSource.UNKNOWN,
            notes=["diagnostic_link"],
        )
    )

    return ProblemGraph(
        nodes=nodes,
        edges=edges,
        target_node_id=target_node_id,
        confidence=0.2,
        provenance=ProvenanceSource.UNKNOWN,
        notes=[f"diagnostic_graph_for_{stage}", f"error={type(error).__name__}"],
    )


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


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    problem_text = _resolve_text(
        inline_text=args.problem_text,
        file_path=args.problem_file,
        field_name="de bai",
        inline_arg="--problem-text",
        file_arg="--problem-file",
    )
    student_answer = _resolve_text(
        inline_text=args.student_answer,
        file_path=args.student_file,
        field_name="bai lam hoc sinh",
        inline_arg="--student-answer",
        file_arg="--student-file",
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    status_lines = [
        "Debug Graph Export Status",
        f"problem_text={_compact_message(problem_text, limit=200)}",
        f"student_answer={_compact_message(student_answer, limit=200)}",
    ]

    try:
        formalized = formalize_problem(problem_text)
    except Exception as exc:
        problem_graph = _build_diagnostic_graph(
            base_graph=None,
            stage="formalize_problem",
            error=exc,
            problem_text=problem_text,
            student_answer=student_answer,
        )
        reference_graph = _build_diagnostic_graph(
            base_graph=problem_graph,
            stage="reference",
            error=RuntimeError("reference_not_built_due_to_formalize_problem_failure"),
            problem_text=problem_text,
            student_answer=student_answer,
        )
        student_graph = _build_diagnostic_graph(
            base_graph=problem_graph,
            stage="student",
            error=RuntimeError("student_graph_not_built_due_to_formalize_problem_failure"),
            problem_text=problem_text,
            student_answer=student_answer,
        )
        status_lines.append(
            f"formalize_problem=failed: {type(exc).__name__}: {_compact_message(str(exc), limit=300)}"
        )
    else:
        if formalized.problem_graph is None:
            missing_problem_graph_error = RuntimeError("formalize_problem did not produce problem_graph")
            problem_graph = _build_diagnostic_graph(
                base_graph=None,
                stage="problem_graph_missing",
                error=missing_problem_graph_error,
                problem_text=problem_text,
                student_answer=student_answer,
            )
            status_lines.append(
                f"problem_graph=missing: {_compact_message(str(missing_problem_graph_error), limit=200)}"
            )
        else:
            problem_graph = formalized.problem_graph
            status_lines.append(f"problem_graph=ok ({_graph_stats(problem_graph)})")

        reference = None
        try:
            reference = build_canonical_reference(formalized)
            reference_graph = _build_reference_graph(reference)
            status_lines.append(
                f"reference_graph=ok ({_graph_stats(reference_graph)}), final_answer={reference.final_answer:g}"
            )
        except Exception as exc:
            reference_graph = _build_diagnostic_graph(
                base_graph=problem_graph,
                stage="reference",
                error=exc,
                problem_text=problem_text,
                student_answer=student_answer,
            )
            status_lines.append(
                f"reference_graph=failed: {type(exc).__name__}: {_compact_message(str(exc), limit=300)}"
            )

        try:
            student_work = formalize_student_work(
                student_answer,
                problem=formalized,
                reference=reference,
                llm_client=None,
            )
            if student_work.student_graph is None:
                raise RuntimeError("formalize_student_work did not produce student_graph")
            student_graph = student_work.student_graph
            status_lines.append(f"student_graph=ok ({_graph_stats(student_graph)})")
        except Exception as exc:
            student_graph = _build_diagnostic_graph(
                base_graph=problem_graph,
                stage="student",
                error=exc,
                problem_text=problem_text,
                student_answer=student_answer,
            )
            status_lines.append(
                f"student_graph=failed: {type(exc).__name__}: {_compact_message(str(exc), limit=300)}"
            )

    problem_cypher = export_problem_graph_to_neo4j_cypher(
        problem_graph,
        graph_scope=PROBLEM_GRAPH_SCOPE,
        clear_scope=True,
    )
    reference_cypher = export_problem_graph_to_neo4j_cypher(
        reference_graph,
        graph_scope=REFERENCE_GRAPH_SCOPE,
        clear_scope=True,
    )
    student_cypher = export_problem_graph_to_neo4j_cypher(
        student_graph,
        graph_scope=STUDENT_GRAPH_SCOPE,
        clear_scope=True,
    )

    PROBLEM_OUTPUT_PATH.write_text(problem_cypher, encoding="utf-8")
    REFERENCE_OUTPUT_PATH.write_text(reference_cypher, encoding="utf-8")
    STUDENT_OUTPUT_PATH.write_text(student_cypher, encoding="utf-8")
    STATUS_OUTPUT_PATH.write_text("\n".join(status_lines) + "\n", encoding="utf-8")

    print("Graphs exported (partial mode)")
    print(f"Problem graph:   {PROBLEM_OUTPUT_PATH}")
    print(f"Reference graph: {REFERENCE_OUTPUT_PATH}")
    print(f"Student graph:   {STUDENT_OUTPUT_PATH}")
    print(f"Status file:     {STATUS_OUTPUT_PATH}")
    print(f"Problem text:    {problem_text}")
    print(f"Student answer:  {student_answer}")
    for line in status_lines[3:]:
        print(f"- {line}")
    print("Run inside Neo4j Browser:")
    print(f"MATCH (n:FormalizeNode {{graph_scope: '{PROBLEM_GRAPH_SCOPE}'}}) RETURN n")
    print(f"MATCH (n:FormalizeNode {{graph_scope: '{REFERENCE_GRAPH_SCOPE}'}}) RETURN n")
    print(f"MATCH (n:FormalizeNode {{graph_scope: '{STUDENT_GRAPH_SCOPE}'}}) RETURN n")


if __name__ == "__main__":
    main(sys.argv[1:])
