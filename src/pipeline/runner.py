"""End-to-end tutoring pipeline runner."""
from __future__ import annotations

from src.diagnosis import diagnose
from src.evidence import build_diagnosis_evidence
from src.formalizer import formalize_problem, formalize_student_work
from src.hint import build_hint_result
from src.llm import LLMClient, build_default_llm_client
from src.models import HintMode, TutoringResult
from src.pedagogy import build_hint_plan
from src.runtime import build_canonical_reference


def run_tutoring_pipeline(
    problem_text: str,
    student_answer: str,
    hint_mode: HintMode = HintMode.NORMAL,
    llm_client: LLMClient | None = None,
    use_llm: bool = True,
) -> TutoringResult:
    """Run the full deterministic tutoring pipeline."""
    active_llm_client = llm_client
    if active_llm_client is None and use_llm:
        active_llm_client = build_default_llm_client()

    problem = formalize_problem(problem_text, llm_client=active_llm_client)
    reference = build_canonical_reference(problem)
    student_work = formalize_student_work(
        student_answer,
        problem=problem,
        reference=reference,
        llm_client=active_llm_client,
    )
    evidence = build_diagnosis_evidence(problem, reference, student_work)
    diagnosis = diagnose(evidence, llm_client=active_llm_client)
    hint_plan = build_hint_plan(problem, reference, diagnosis)
    hint_result = build_hint_result(
        problem,
        reference,
        diagnosis,
        hint_plan,
        hint_mode=hint_mode,
        llm_client=active_llm_client,
    )

    return TutoringResult(
        problem=problem,
        reference=reference,
        student_work=student_work,
        evidence=evidence,
        diagnosis=diagnosis,
        hint_plan=hint_plan,
        hint_result=hint_result,
    )
