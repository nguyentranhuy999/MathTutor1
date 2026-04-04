from debug_llm_solution_graph import _build_graph_steps_cypher, _extract_graph_steps


def test_extract_graph_steps_from_problem_formalizer_record():
    records = [
        {"task_name": "diagnosis", "response": {}},
        {
            "task_name": "problem_formalizer",
            "response": {
                "graph_steps": [
                    {
                        "step_id": "s1",
                        "step_index": 1,
                        "operation": "multiply",
                        "input_refs": ["q1", "q2"],
                        "output_ref": "out1",
                        "expression": "q1 * q2",
                    }
                ]
            },
        },
    ]

    steps = _extract_graph_steps(records)

    assert len(steps) == 1
    assert steps[0]["step_id"] == "s1"


def test_build_graph_steps_cypher_contains_expected_nodes_and_edges():
    cypher = _build_graph_steps_cypher(
        [
            {
                "step_id": "s1",
                "step_index": 1,
                "operation": "add",
                "input_refs": ["q1", "q2"],
                "output_ref": "out",
                "expression": "q1 + q2",
            }
        ],
        graph_scope="scope_1",
    )

    assert "CREATE CONSTRAINT llm_step_scope_id IF NOT EXISTS" in cypher
    assert "MERGE (s:LLMStep {graph_scope: 'scope_1', step_id: 's1'})" in cypher
    assert "MERGE (s)-[:PRODUCES]->(out);" in cypher
    assert "MERGE (inp)-[:INPUT_TO]->(s);" in cypher
