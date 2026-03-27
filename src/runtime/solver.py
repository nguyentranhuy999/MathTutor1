"""Build canonical references from formalized problems."""
from __future__ import annotations

from src.formalizer import formalize_problem
from src.models import CanonicalReference, ExecutablePlan, ExecutionTrace, FormalizedProblem, SolverCandidate
from src.runtime.compiler import compile_executable_plan
from src.runtime.executor import execute_plan


def _render_solution_text(plan: ExecutablePlan, trace: ExecutionTrace) -> str:
    rendered_lines: list[str] = []
    outputs_by_step = {result.step_id: result for result in trace.step_results}

    for step in plan.steps:
        result = outputs_by_step.get(step.step_id)
        if result is None:
            continue
        if result.success and result.output_value is not None:
            rendered_lines.append(f"{step.expression} = {result.output_value:g}")
        else:
            rendered_lines.append(f"{step.expression} -> ERROR: {result.error_message}")

    if trace.success and trace.final_value is not None:
        rendered_lines.append(f"#### {trace.final_value:g}")
    return "\n".join(rendered_lines)


def build_solver_candidate(problem: FormalizedProblem) -> SolverCandidate:
    """Compile a single deterministic solver candidate from a formalized problem."""
    plan = compile_executable_plan(problem)
    return SolverCandidate(
        candidate_id=f"{plan.plan_id}_candidate",
        executable_plan=plan,
        rendered_reasoning=None,
        selection_score=plan.confidence,
        selection_notes=list(plan.notes),
    )


def build_canonical_reference(problem: FormalizedProblem) -> CanonicalReference:
    """Compile, execute, and package a canonical reference from a formalized problem."""
    candidate = build_solver_candidate(problem)
    plan = candidate.executable_plan
    trace = execute_plan(plan, problem)
    if not trace.success or trace.final_value is None:
        raise ValueError(f"Unable to build canonical reference: {trace.error_message or 'execution failed'}")

    rendered_solution_text = _render_solution_text(plan, trace)
    confidence = min((problem.confidence + plan.confidence + trace.confidence) / 3, 0.98)
    notes = list(problem.notes) + list(plan.notes) + list(trace.notes)
    notes.append("canonical_reference_built")

    return CanonicalReference(
        final_answer=trace.final_value,
        formalized_problem=problem,
        chosen_plan=plan,
        execution_trace=trace,
        rendered_solution_text=rendered_solution_text,
        source_model=None,
        confidence=confidence,
        notes=notes,
    )


def solve_problem(problem_text: str) -> CanonicalReference:
    """Formalize and solve a problem into a canonical executable reference."""
    formalized_problem = formalize_problem(problem_text)
    return build_canonical_reference(formalized_problem)

