from src.formalizer import export_problem_graph_to_neo4j_cypher, formalize_problem


def test_export_problem_graph_to_neo4j_cypher_contains_nodes_and_edges():
    formalized = formalize_problem("Jan has 3 apples. She buys 5 more apples. How many apples does she have in total?")
    assert formalized.problem_graph is not None

    cypher = export_problem_graph_to_neo4j_cypher(
        formalized.problem_graph,
        graph_scope="demo_scope",
        clear_scope=True,
    )

    assert "CREATE CONSTRAINT formalize_node_scope_id IF NOT EXISTS" in cypher
    assert "MATCH (n:FormalizeNode {graph_scope: 'demo_scope'})" in cypher
    assert "DETACH DELETE n;" in cypher
    assert "MERGE (n:FormalizeNode:QUANTITY" in cypher
    assert "MERGE (n:FormalizeNode:OPERATION" in cypher
    assert "MERGE (src)-[r:INPUT_TO_OPERATION" in cypher
    assert "MERGE (src)-[r:OUTPUT_FROM_OPERATION" in cypher
    assert "SET target.is_target = true" in cypher


def test_export_problem_graph_to_neo4j_cypher_escapes_strings():
    formalized = formalize_problem("Tom has 10 marbles and gives away 4. How many marbles are left?")
    assert formalized.problem_graph is not None

    mutated = formalized.problem_graph.model_copy(
        update={
            "nodes": [
                formalized.problem_graph.nodes[0].model_copy(update={"label": "Tom's total \\\\ stash"}),
                *formalized.problem_graph.nodes[1:],
            ]
        }
    )

    cypher = export_problem_graph_to_neo4j_cypher(mutated)

    assert "Tom\\'s total \\\\\\\\ stash" in cypher
