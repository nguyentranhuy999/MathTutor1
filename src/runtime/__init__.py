"""Executable runtime package."""

from src.runtime.compiler import compile_executable_plan
from src.runtime.executor import execute_plan
from src.runtime.graph_validator import validate_problem_graph


def build_canonical_reference(*args, **kwargs):
    from src.runtime.solver import build_canonical_reference as _build_canonical_reference

    return _build_canonical_reference(*args, **kwargs)


def build_solver_candidate(*args, **kwargs):
    from src.runtime.solver import build_solver_candidate as _build_solver_candidate

    return _build_solver_candidate(*args, **kwargs)


def solve_problem(*args, **kwargs):
    from src.runtime.solver import solve_problem as _solve_problem

    return _solve_problem(*args, **kwargs)

__all__ = [
    "build_canonical_reference",
    "build_solver_candidate",
    "compile_executable_plan",
    "execute_plan",
    "solve_problem",
    "validate_problem_graph",
]
