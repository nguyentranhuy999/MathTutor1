from src.formalizer import formalize_problem
from src.models import RelationType, TraceOperation
from src.runtime import build_canonical_reference, compile_executable_plan, execute_plan, solve_problem, validate_problem_graph


def test_runtime_solves_rate_discount_problem_end_to_end():
    problem_text = (
        "A concert ticket costs $40. Mr. Benson bought 12 tickets and received a 5% discount "
        "for every ticket bought that exceeds 10. How much did Mr. Benson pay in all?"
    )

    reference = solve_problem(problem_text)

    assert reference.final_answer == 476.0
    assert reference.execution_trace.success is True
    assert len(reference.chosen_plan.steps) == 5
    assert "compiled_from_problem_graph" in reference.chosen_plan.notes
    assert reference.chosen_plan.steps[1].operation == TraceOperation.PERCENT_OF
    assert "#### 476" in (reference.rendered_solution_text or "")


def test_runtime_compiles_and_executes_additive_problem():
    formalized = formalize_problem(
        "Jan has 3 apples. She buys 5 more apples. How many apples does she have in total?"
    )

    plan = compile_executable_plan(formalized)
    trace = execute_plan(plan, formalized)

    assert formalized.relation_candidates[0].relation_type == RelationType.ADDITIVE_COMPOSITION
    assert "compiled_from_problem_graph" in plan.notes
    assert plan.steps[0].expression == "quantity_1 + quantity_2"
    assert trace.success is True
    assert trace.final_value == 8.0


def test_runtime_compiles_and_executes_subtractive_problem():
    formalized = formalize_problem("Tom had 10 marbles and gave away 4. How many marbles are left?")

    plan = compile_executable_plan(formalized)
    trace = execute_plan(plan, formalized)

    assert formalized.relation_candidates[0].relation_type == RelationType.SUBTRACTIVE_COMPARISON
    assert trace.success is True
    assert trace.final_value == 6.0


def test_runtime_uses_single_quantity_fallback_when_problem_is_explicit():
    reference = solve_problem("There are 8 apples. How many apples are there?")

    assert reference.final_answer == 8.0
    assert reference.execution_trace.success is True
    assert reference.chosen_plan.steps[0].output_ref == "how_many_apples_are_there"


def test_runtime_graph_validator_reports_missing_target_production():
    formalized = formalize_problem("There are 8 apples. How many apples are there?")
    assert formalized.problem_graph is not None

    broken_graph = formalized.problem_graph.model_copy(update={"edges": []})
    broken_problem = formalized.model_copy(update={"problem_graph": broken_graph})

    validation = validate_problem_graph(broken_problem)

    assert validation.is_valid is False
    assert any(issue.code == "target_not_produced" for issue in validation.issues)
