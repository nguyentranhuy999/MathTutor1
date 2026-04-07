"""Debug helper: capture LLM formalizer response and export solution graph artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DEBUG_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DEBUG_DIR / "outputs"
ARTIFACT_DIR = DEBUG_DIR / "artifacts"

from src.formalizer import export_problem_graph_to_neo4j_cypher, formalize_problem
from src.llm import LLMClient, build_default_llm_client
from src.runtime import build_canonical_reference
from src.shared_input import read_problem_text

PROBLEM_TEXT = read_problem_text()
GRAPH_SCOPE = "llm_solution_graph"
RAW_LLM_PATH = OUTPUT_DIR / "debug_llm_solution_graph_llm_raw.json"
SUMMARY_PATH = OUTPUT_DIR / "debug_llm_solution_graph_output.txt"
CYPHER_PATH = ARTIFACT_DIR / "llm_solution_graph.cypher"


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

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_LLM_PATH.write_text(json.dumps(llm_client.records, indent=2, ensure_ascii=False), encoding="utf-8")

    CYPHER_PATH.parent.mkdir(parents=True, exist_ok=True)
    CYPHER_PATH.write_text(cypher, encoding="utf-8")

    summary_lines = [
        "LLM Solution Graph Debug",
        f"problem: {PROBLEM_TEXT}",
        f"llm_calls: {len(llm_client.records)}",
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
            f"LLM raw file: {RAW_LLM_PATH}",
            "Run inside Neo4j Browser:",
            f"MATCH (n:FormalizeNode {{graph_scope: '{GRAPH_SCOPE}'}}) RETURN n",
        ]
    )
    SUMMARY_PATH.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("LLM solution graph artifacts exported")
    print(f"Cypher file: {CYPHER_PATH}")
    print(f"LLM raw file: {RAW_LLM_PATH}")
    print(f"Summary file: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
