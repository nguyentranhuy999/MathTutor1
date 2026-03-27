"""Verification utilities for generated hints."""
from __future__ import annotations

import re

from src.models import HintPlan, TeacherMove


_NUMBER_PATTERN = re.compile(r"-?\d[\d,]*\.?\d*")


def _normalize(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def check_no_spoiler(hint_text: str, plan: HintPlan) -> list[str]:
    """Return spoiler violations found in the hint text."""
    violations: list[str] = []
    normalized_hint = _normalize(hint_text)
    hint_numbers = {match.replace(",", "") for match in _NUMBER_PATTERN.findall(hint_text)}

    for hidden in plan.must_not_reveal:
        normalized_hidden = _normalize(hidden)
        if not normalized_hidden:
            continue
        if _NUMBER_PATTERN.fullmatch(hidden.replace(",", "")):
            if hidden.replace(",", "") in hint_numbers:
                violations.append(f"reveals_hidden_number:{hidden}")
            continue
        if normalized_hidden in normalized_hint:
            violations.append(f"reveals_hidden_text:{hidden}")

    return violations


def check_alignment(hint_text: str, plan: HintPlan) -> list[str]:
    """Return alignment violations for the generated hint."""
    violations: list[str] = []
    normalized_hint = _normalize(hint_text)
    sentence_count = len([segment for segment in re.split(r"[.!?]+", hint_text) if segment.strip()])

    cue_map = {
        TeacherMove.REFOCUS_TARGET: ("question", "asking", "quantity", "intermediate", "final"),
        TeacherMove.CHECK_RELATIONSHIP: ("combine", "compare", "rate", "relationship", "step"),
        TeacherMove.RECOMPUTE_STEP: ("recheck", "calculation", "carefully", "step"),
        TeacherMove.CONTINUE_FROM_STEP: ("final", "step", "recompute", "setup"),
        TeacherMove.RESTATE_RESULT: ("correct",),
        TeacherMove.METACOGNITIVE_PROMPT: ("restate", "own words", "clear numeric answer"),
    }

    expected_cues = cue_map.get(plan.teacher_move, ())
    if expected_cues and not any(cue in normalized_hint for cue in expected_cues):
        violations.append("teacher_move_alignment_failed")

    if plan.hint_level.value == "conceptual" and "calculate" in normalized_hint and plan.disclosure_budget <= 1:
        violations.append("conceptual_hint_too_computational")

    if sentence_count > 2:
        violations.append("hint_too_long")

    return violations


def verify_hint_text(hint_text: str, plan: HintPlan) -> list[str]:
    """Return the combined verification violations for a hint."""
    return check_no_spoiler(hint_text, plan) + check_alignment(hint_text, plan)
