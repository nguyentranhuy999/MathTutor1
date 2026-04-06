"""Build and export only problem graph artifacts (without running full tutoring pipeline)."""

from __future__ import annotations

from pathlib import Path

from src.formalizer import export_problem_graph_to_neo4j_cypher, formalize_problem

PROBLEM_TEXT = (
    "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
    "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
)
GRAPH_SCOPE = "debug_problem_graph"
OUTPUT_PATH = Path("artifacts/problem_graph.cypher")


def main() -> None:
    formalized = formalize_problem(PROBLEM_TEXT)
    if formalized.problem_graph is None:
        raise RuntimeError("formalize_problem did not produce problem_graph")

    cypher = export_problem_graph_to_neo4j_cypher(
        formalized.problem_graph,
        graph_scope=GRAPH_SCOPE,
        clear_scope=True,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(cypher, encoding="utf-8")

    print("Graph exported successfully")
    print(f"Cypher file: {OUTPUT_PATH}")
    print(f"graph_scope: {GRAPH_SCOPE}")
    print("Run inside Neo4j Browser:")
    print(f"MATCH (n:FormalizeNode {{graph_scope: '{GRAPH_SCOPE}'}}) RETURN n")


if __name__ == "__main__":
    main()
