"""Execute deterministic symbolic plans."""
from __future__ import annotations

import ast

from src.models import ExecutablePlan, ExecutionStepResult, ExecutionTrace, FormalizedProblem


_ALLOWED_FUNCTIONS = {
    "max": max,
    "min": min,
    "abs": abs,
}


def _build_environment(problem: FormalizedProblem) -> dict[str, float]:
    return {quantity.quantity_id: quantity.value for quantity in problem.quantities}


def _eval_ast(node: ast.AST, environment: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body, environment)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in environment:
            raise KeyError(f"Unknown reference '{node.id}'")
        return float(environment[node.id])
    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left, environment)
        right = _eval_ast(node.right, environment)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        raise ValueError(f"Unsupported operator '{type(node.op).__name__}'")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_ast(node.operand, environment)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id not in _ALLOWED_FUNCTIONS:
            raise ValueError(f"Unsupported function '{node.func.id}'")
        args = [_eval_ast(arg, environment) for arg in node.args]
        return float(_ALLOWED_FUNCTIONS[node.func.id](*args))
    raise ValueError(f"Unsupported expression node '{type(node).__name__}'")


def _evaluate_expression(expression: str, environment: dict[str, float]) -> float:
    parsed = ast.parse(expression, mode="eval")
    return float(_eval_ast(parsed, environment))


def execute_plan(plan: ExecutablePlan, problem: FormalizedProblem) -> ExecutionTrace:
    """Execute an executable plan against a formalized problem."""
    environment = _build_environment(problem)
    results: list[ExecutionStepResult] = []
    notes = [f"initial_bindings={len(environment)}"]

    if not plan.steps:
        return ExecutionTrace(
            plan_id=plan.plan_id,
            step_results=[],
            final_value=None,
            success=False,
            error_message="Executable plan has no steps",
            confidence=0.0,
            notes=notes + ["plan_has_no_steps"],
        )

    for step in plan.steps:
        resolved_inputs: list[float] = []
        missing_refs = [ref for ref in step.input_refs if ref not in environment]
        if missing_refs:
            error_message = f"Missing references for step '{step.step_id}': {missing_refs}"
            results.append(
                ExecutionStepResult(
                    step_id=step.step_id,
                    operation=step.operation,
                    resolved_inputs=resolved_inputs,
                    success=False,
                    error_message=error_message,
                    notes=["missing_input_refs"],
                )
            )
            return ExecutionTrace(
                plan_id=plan.plan_id,
                step_results=results,
                final_value=None,
                success=False,
                error_message=error_message,
                confidence=0.0,
                notes=notes + ["execution_stopped_missing_refs"],
            )

        for ref in step.input_refs:
            resolved_inputs.append(float(environment[ref]))

        try:
            output_value = _evaluate_expression(step.expression, environment)
        except Exception as exc:  # pragma: no cover
            results.append(
                ExecutionStepResult(
                    step_id=step.step_id,
                    operation=step.operation,
                    resolved_inputs=resolved_inputs,
                    success=False,
                    error_message=str(exc),
                    notes=["expression_evaluation_failed"],
                )
            )
            return ExecutionTrace(
                plan_id=plan.plan_id,
                step_results=results,
                final_value=None,
                success=False,
                error_message=str(exc),
                confidence=0.0,
                notes=notes + ["execution_stopped_exception"],
            )

        environment[step.output_ref] = output_value
        results.append(
            ExecutionStepResult(
                step_id=step.step_id,
                operation=step.operation,
                resolved_inputs=resolved_inputs,
                output_value=output_value,
                success=True,
                notes=[f"stored_as={step.output_ref}"],
            )
        )

    if plan.target_ref not in environment:
        error_message = f"Target ref '{plan.target_ref}' was not produced during execution"
        return ExecutionTrace(
            plan_id=plan.plan_id,
            step_results=results,
            final_value=None,
            success=False,
            error_message=error_message,
            confidence=0.0,
            notes=notes + ["target_ref_missing_after_execution"],
        )

    final_value = float(environment[plan.target_ref])
    success_ratio = sum(1 for result in results if result.success) / len(results)
    confidence = min(plan.confidence * success_ratio + 0.08, 1.0)

    return ExecutionTrace(
        plan_id=plan.plan_id,
        step_results=results,
        final_value=final_value,
        success=True,
        confidence=confidence,
        notes=notes + [f"target_ref={plan.target_ref}"],
    )

