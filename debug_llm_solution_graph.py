"""Debug helper: capture LLM formalizer response and export solution graph artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.formalizer import export_problem_graph_to_neo4j_cypher, formalize_problem
from src.llm import LLMClient, build_default_llm_client
from src.runtime import build_canonical_reference

PROBLEM_TEXT = (
    "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
    "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
)
GRAPH_SCOPE = "llm_solution_graph"
RAW_LLM_PATH = Path("debug_llm_solution_graph_llm_raw.json")
GRAPH_STEPS_PATH = Path("debug_llm_solution_graph_graph_steps.json")
SUMMARY_PATH = Path("debug_llm_solution_graph_output.txt")
CYPHER_PATH = Path("artifacts/llm_solution_graph.cypher")
GRAPH_STEPS_CYPHER_PATH = Path("artifacts/llm_graph_steps.cypher")


class RecordingLLMClient:
    def __init__(self, base_client: LLMClient):
        self._base_client = base_client
        self.records: list[dict[str, Any]] = []

    def generate_json(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        payload = self._base_client.generate_json(
            task_name=task_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.records.append(
            {
                "task_name": task_name,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response": payload,
            }
        )
        return payload


def _extract_graph_steps(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for record in reversed(records):
        if record.get("task_name") != "problem_formalizer":
            continue
        response = record.get("response")
        if not isinstance(response, dict):
            continue
        graph_steps = response.get("graph_steps")
        if isinstance(graph_steps, list):
            return [step for step in graph_steps if isinstance(step, dict)]
    return []


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _build_graph_steps_cypher(graph_steps: list[dict[str, Any]], *, graph_scope: str) -> str:
    lines: list[str] = [
        "// Auto-generated LLM graph_steps visualization",
        "CREATE CONSTRAINT llm_step_scope_id IF NOT EXISTS",
        "FOR (n:LLMStep) REQUIRE (n.graph_scope, n.step_id) IS UNIQUE;",
        f"MATCH (n:LLMStep {{graph_scope: '{_escape(graph_scope)}'}})",
        "DETACH DELETE n;",
        f"MATCH (n:LLMValue {{graph_scope: '{_escape(graph_scope)}'}})",
        "DETACH DELETE n;",
    ]
    for step in graph_steps:
        step_id = str(step.get("step_id") or "unknown_step")
        step_index = int(step.get("step_index") or 0)
        operation = str(step.get("operation") or "unknown")
        expression = str(step.get("expression") or "")
        output_ref = str(step.get("output_ref") or "")
        input_refs = [str(ref) for ref in step.get("input_refs", []) if ref is not None]

        lines.append(
            f"MERGE (s:LLMStep {{graph_scope: '{_escape(graph_scope)}', step_id: '{_escape(step_id)}'}})"
        )
        lines.append(
            f"SET s.step_index = {step_index}, s.operation = '{_escape(operation)}', s.expression = '{_escape(expression)}';"
        )

        lines.append(
            f"MERGE (out:LLMValue {{graph_scope: '{_escape(graph_scope)}', ref: '{_escape(output_ref)}'}})"
        )
        lines.append("MERGE (s)-[:PRODUCES]->(out);")

        for ref in input_refs:
            lines.append(f"MERGE (inp:LLMValue {{graph_scope: '{_escape(graph_scope)}', ref: '{_escape(ref)}'}})")
            lines.append("MERGE (inp)-[:INPUT_TO]->(s);")

    return "\n".join(lines) + "\n"


def main() -> None:
    base_llm = build_default_llm_client()
    if base_llm is None:
        raise RuntimeError("No LLM client configured. Please check your .env settings.")

    llm_client = RecordingLLMClient(base_llm)
    formalized = formalize_problem(PROBLEM_TEXT, llm_client=llm_client)
    if formalized.problem_graph is None:
        raise RuntimeError("formalize_problem did not produce problem_graph")

    reference = build_canonical_reference(formalized)
    cypher = export_problem_graph_to_neo4j_cypher(
        formalized.problem_graph,
        graph_scope=GRAPH_SCOPE,
        clear_scope=True,
    )

    RAW_LLM_PATH.write_text(json.dumps(llm_client.records, indent=2, ensure_ascii=False), encoding="utf-8")
    graph_steps = _extract_graph_steps(llm_client.records)
    GRAPH_STEPS_PATH.write_text(json.dumps(graph_steps, indent=2, ensure_ascii=False), encoding="utf-8")

    CYPHER_PATH.parent.mkdir(parents=True, exist_ok=True)
    CYPHER_PATH.write_text(cypher, encoding="utf-8")
    GRAPH_STEPS_CYPHER_PATH.write_text(
        _build_graph_steps_cypher(graph_steps, graph_scope=f"{GRAPH_SCOPE}_steps"),
        encoding="utf-8",
    )

    summary_lines = [
        "LLM Solution Graph Debug",
        f"problem: {PROBLEM_TEXT}",
        f"llm_calls: {len(llm_client.records)}",
        f"graph_steps_from_llm: {len(graph_steps)}",
        f"final_answer: {reference.final_answer}",
        "",
        "Plan steps:",
    ]
    for step in reference.chosen_plan.steps:
        summary_lines.append(f"- {step.step_id}: {step.expression} -> {step.output_ref}")

    summary_lines.extend(
        [
            "",
            f"Cypher file: {CYPHER_PATH}",
            f"LLM graph_steps Cypher file: {GRAPH_STEPS_CYPHER_PATH}",
            f"LLM raw file: {RAW_LLM_PATH}",
            f"LLM graph_steps JSON: {GRAPH_STEPS_PATH}",
            "Run inside Neo4j Browser:",
            f"MATCH (n:FormalizeNode {{graph_scope: '{GRAPH_SCOPE}'}}) RETURN n",
            f"MATCH (n:LLMStep {{graph_scope: '{GRAPH_SCOPE}_steps'}}) RETURN n",
        ]
    )
    SUMMARY_PATH.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("LLM solution graph artifacts exported")
    print(f"Cypher file: {CYPHER_PATH}")
    print(f"LLM graph_steps Cypher file: {GRAPH_STEPS_CYPHER_PATH}")
    print(f"LLM raw file: {RAW_LLM_PATH}")
    print(f"LLM graph_steps JSON: {GRAPH_STEPS_PATH}")
    print(f"Summary file: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
