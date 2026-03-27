"""Deterministic pedagogy planner built on diagnosis results."""
from __future__ import annotations

from src.models import (
    CanonicalReference,
    DiagnosisLabel,
    DiagnosisResult,
    ErrorLocalization,
    FormalizedProblem,
    HintLevel,
    HintPlan,
    TeacherMove,
)


def _find_reference_step(reference: CanonicalReference, step_id: str | None):
    if step_id is None:
        return None
    return next((step for step in reference.chosen_plan.steps if step.step_id == step_id), None)


def _base_must_not_reveal(reference: CanonicalReference) -> list[str]:
    items = ["final answer", f"{reference.final_answer:g}"]
    return items


def _step_specific_must_not_reveal(reference: CanonicalReference, step_id: str | None) -> list[str]:
    if step_id is None:
        return []

    hidden: list[str] = []
    for step, result in zip(reference.chosen_plan.steps, reference.execution_trace.step_results):
        if step.step_id == step_id and result.success and result.output_value is not None:
            hidden.extend([step.output_ref, f"{result.output_value:g}"])
            break
    return hidden


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _plan_for_correct_answer(
    problem: FormalizedProblem,
    reference: CanonicalReference,
    diagnosis: DiagnosisResult,
) -> HintPlan:
    return HintPlan(
        diagnosis_label=diagnosis.diagnosis_label,
        hint_level=HintLevel.CONCEPTUAL,
        teacher_move=TeacherMove.RESTATE_RESULT,
        target_step_id=diagnosis.target_step_id,
        disclosure_budget=0,
        focus_points=[],
        must_not_reveal=[],
        rationale="The student is already correct, so no instructional hint is needed.",
        confidence=min(diagnosis.confidence, 0.95),
    )


def _plan_for_unparseable(
    problem: FormalizedProblem,
    reference: CanonicalReference,
    diagnosis: DiagnosisResult,
) -> HintPlan:
    target_prompt = (
        f"what quantity the question asks for: {problem.target.surface_text}"
        if problem.target is not None
        else "state the answer as a single numeric result"
    )
    return HintPlan(
        diagnosis_label=diagnosis.diagnosis_label,
        hint_level=HintLevel.CONCEPTUAL,
        teacher_move=TeacherMove.METACOGNITIVE_PROMPT,
        target_step_id=None,
        disclosure_budget=1,
        focus_points=[target_prompt, "state the final answer clearly as one number"],
        must_not_reveal=_base_must_not_reveal(reference),
        rationale="The student first needs help formatting or restating an answer before deeper tutoring is useful.",
        confidence=min(diagnosis.confidence + 0.02, 0.96),
    )


def _plan_for_target_misunderstanding(
    problem: FormalizedProblem,
    reference: CanonicalReference,
    diagnosis: DiagnosisResult,
) -> HintPlan:
    focus_points = ["what quantity the question is actually asking for"]
    if problem.target is not None:
        focus_points.append(problem.target.surface_text)

    step = _find_reference_step(reference, diagnosis.target_step_id)
    if step is not None and step.explanation:
        focus_points.append(f"why {step.output_ref} is only an intermediate result")

    must_not_reveal = _base_must_not_reveal(reference) + _step_specific_must_not_reveal(
        reference,
        diagnosis.target_step_id,
    )
    return HintPlan(
        diagnosis_label=diagnosis.diagnosis_label,
        hint_level=HintLevel.CONCEPTUAL,
        teacher_move=TeacherMove.REFOCUS_TARGET,
        target_step_id=diagnosis.target_step_id,
        disclosure_budget=1,
        focus_points=_dedupe(focus_points),
        must_not_reveal=_dedupe(must_not_reveal),
        rationale="The diagnosis indicates the student solved for the wrong target quantity and should be redirected to the question goal.",
        confidence=min(diagnosis.confidence + 0.03, 0.97),
    )


def _plan_for_quantity_relation_error(
    problem: FormalizedProblem,
    reference: CanonicalReference,
    diagnosis: DiagnosisResult,
) -> HintPlan:
    focus_points = ["how the problem quantities should be combined"]
    relation = problem.relation_candidates[0] if problem.relation_candidates else None
    if relation is not None and relation.rationale:
        focus_points.append(relation.rationale)
    if problem.target is not None:
        focus_points.append(f"target: {problem.target.surface_text}")

    step = _find_reference_step(reference, diagnosis.target_step_id)
    if step is not None and step.explanation:
        focus_points.append(step.explanation)

    return HintPlan(
        diagnosis_label=diagnosis.diagnosis_label,
        hint_level=HintLevel.RELATIONAL,
        teacher_move=TeacherMove.CHECK_RELATIONSHIP,
        target_step_id=diagnosis.target_step_id,
        disclosure_budget=2,
        focus_points=_dedupe(focus_points),
        must_not_reveal=_dedupe(_base_must_not_reveal(reference) + _step_specific_must_not_reveal(reference, diagnosis.target_step_id)),
        rationale="The student likely needs help reasoning about the relationship between quantities before recomputing anything.",
        confidence=min(diagnosis.confidence + 0.02, 0.97),
    )


def _plan_for_arithmetic_error(
    problem: FormalizedProblem,
    reference: CanonicalReference,
    diagnosis: DiagnosisResult,
) -> HintPlan:
    step = _find_reference_step(reference, diagnosis.target_step_id)
    focus_points = ["recompute the arithmetic carefully"]
    teacher_move = TeacherMove.RECOMPUTE_STEP
    disclosure_budget = 1

    if diagnosis.localization == ErrorLocalization.INTERMEDIATE_STEP and step is not None:
        focus_points.append(f"check the calculation around {step.output_ref}")
        if step.explanation:
            focus_points.append(step.explanation)
    elif diagnosis.localization == ErrorLocalization.FINAL_COMPUTATION:
        teacher_move = TeacherMove.CONTINUE_FROM_STEP
        focus_points.append("revisit the final computation after setting up the right quantities")

    if problem.target is not None:
        focus_points.append(f"target: {problem.target.surface_text}")

    return HintPlan(
        diagnosis_label=diagnosis.diagnosis_label,
        hint_level=HintLevel.NEXT_STEP,
        teacher_move=teacher_move,
        target_step_id=diagnosis.target_step_id,
        disclosure_budget=disclosure_budget,
        focus_points=_dedupe(focus_points),
        must_not_reveal=_dedupe(_base_must_not_reveal(reference) + _step_specific_must_not_reveal(reference, diagnosis.target_step_id)),
        rationale="The student appears to be aiming at the right quantity and mainly needs support checking the computation.",
        confidence=min(diagnosis.confidence + 0.03, 0.97),
    )


def _plan_for_unknown(
    problem: FormalizedProblem,
    reference: CanonicalReference,
    diagnosis: DiagnosisResult,
) -> HintPlan:
    focus_points = ["restate the question in your own words"]
    if problem.target is not None:
        focus_points.append(problem.target.surface_text)

    return HintPlan(
        diagnosis_label=diagnosis.diagnosis_label,
        hint_level=HintLevel.CONCEPTUAL,
        teacher_move=TeacherMove.METACOGNITIVE_PROMPT,
        target_step_id=diagnosis.target_step_id,
        disclosure_budget=1,
        focus_points=_dedupe(focus_points),
        must_not_reveal=_base_must_not_reveal(reference),
        rationale="The diagnosis is not specific enough, so the safest next move is to prompt the student to re-orient to the task.",
        confidence=min(diagnosis.confidence, 0.9),
    )


def build_hint_plan(
    problem: FormalizedProblem,
    reference: CanonicalReference,
    diagnosis: DiagnosisResult,
) -> HintPlan:
    """Build a deterministic pedagogy plan from diagnosis and task context."""
    if diagnosis.diagnosis_label == DiagnosisLabel.CORRECT_ANSWER:
        return _plan_for_correct_answer(problem, reference, diagnosis)
    if diagnosis.diagnosis_label == DiagnosisLabel.UNPARSEABLE_ANSWER:
        return _plan_for_unparseable(problem, reference, diagnosis)
    if diagnosis.diagnosis_label == DiagnosisLabel.TARGET_MISUNDERSTANDING:
        return _plan_for_target_misunderstanding(problem, reference, diagnosis)
    if diagnosis.diagnosis_label == DiagnosisLabel.QUANTITY_RELATION_ERROR:
        return _plan_for_quantity_relation_error(problem, reference, diagnosis)
    if diagnosis.diagnosis_label == DiagnosisLabel.ARITHMETIC_ERROR:
        return _plan_for_arithmetic_error(problem, reference, diagnosis)
    return _plan_for_unknown(problem, reference, diagnosis)

