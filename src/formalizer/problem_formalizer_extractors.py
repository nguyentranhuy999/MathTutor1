"""Low-level parsing and heuristic extraction helpers for problem formalization."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from src.models import (
    OperationType,
    ProblemEntity,
    ProvenanceSource,
    QuantityAnnotation,
    QuantitySemanticRole,
    RelationCandidate,
    RelationType,
    TargetSpec,
)


_NUMBER_PATTERN = re.compile(r"-?\$?\d[\d,]*\.?\d*%?")
_TARGET_QUESTION_PATTERN = re.compile(
    r"((?:if\b.*?,\s*)?(?:how many|how much|what|which|who|where|when|why)[^?]*\?)",
    re.IGNORECASE,
)
_ENTITY_PATTERN = re.compile(
    r"\b(?:(Mr|Mrs|Ms|Dr)\.\s+[A-Z][a-z]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
)

_ADDITIVE_CUES = (
    "total",
    "altogether",
    "in all",
    "sum",
    "more",
    "added",
    "combined",
    "together",
    "buys",
)
_SUBTRACTIVE_CUES = (
    "left",
    "remain",
    "remaining",
    "still available",
    "difference",
    "less",
    "fewer",
    "exceeds",
    "exceed",
    "beyond",
    "over",
    "spent",
    "lost",
    "after",
)
_MULTIPLICATIVE_CUES = (
    "times",
    "twice",
    "double",
    "triple",
    "half",
    "quarter",
)
_PARTITION_CUES = (
    "split equally",
    "share equally",
    "group",
    "groups",
    "divide equally",
)
_RATE_CUES = (
    "each",
    "per",
    "%",
    "percent",
    "every",
    "costs",
    "price",
)
_THRESHOLD_CUES = (
    "exceeds",
    "exceed",
    "over",
    "beyond",
    "after",
    "first",
    "at least",
    "at most",
)

_UNIT_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "if",
    "in",
    "is",
    "it",
    "much",
    "many",
    "of",
    "or",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "to",
    "was",
    "were",
    "what",
    "which",
    "who",
    "why",
    "with",
}


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    sentences: list[tuple[str, int, int]] = []
    if not text:
        return sentences
    for match in re.finditer(r"[^.!?]+[.!?]?", text):
        sentence = match.group().strip()
        if sentence:
            sentences.append((sentence, match.start(), match.end()))
    return sentences


def _extract_target_text(problem_text: str) -> str:
    text = (problem_text or "").strip()
    if not text:
        return ""

    question_match = _TARGET_QUESTION_PATTERN.search(text)
    if question_match:
        return question_match.group(1).strip()

    question_index = text.rfind("?")
    if question_index != -1:
        prefix = text[:question_index]
        sentence_start = 0
        for marker in (". ", "! ", "? ", "; ", ": "):
            marker_index = prefix.rfind(marker)
            if marker_index != -1:
                sentence_start = max(sentence_start, marker_index + len(marker))
        candidate = text[sentence_start:question_index + 1].strip()
        if candidate:
            return candidate
        return text[:question_index + 1].strip()

    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    return parts[-1] if parts else text


def _slugify(text: str, fallback: str = "target") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug or fallback


def _matching_cues(text: str, cues: Iterable[str]) -> list[str]:
    lowered = text.lower()
    return [cue for cue in cues if cue in lowered]


def _infer_relation_and_operation(problem_text: str, target_text: str = "") -> tuple[RelationType, OperationType, list[str]]:
    combined_text = f"{problem_text} {target_text}".strip().lower()
    add_matches = _matching_cues(combined_text, _ADDITIVE_CUES)
    sub_matches = _matching_cues(combined_text, _SUBTRACTIVE_CUES)
    mult_matches = _matching_cues(combined_text, _MULTIPLICATIVE_CUES)
    partition_matches = _matching_cues(combined_text, _PARTITION_CUES)
    rate_matches = _matching_cues(combined_text, _RATE_CUES)

    notes: list[str] = []
    if add_matches:
        notes.append("additive_cues=" + ",".join(add_matches))
    if sub_matches:
        notes.append("subtractive_cues=" + ",".join(sub_matches))
    if mult_matches:
        notes.append("multiplicative_cues=" + ",".join(mult_matches))
    if partition_matches:
        notes.append("partition_cues=" + ",".join(partition_matches))
    if rate_matches:
        notes.append("rate_cues=" + ",".join(rate_matches))

    expected_operation = OperationType.UNKNOWN
    if len(add_matches) > len(sub_matches):
        expected_operation = OperationType.ADDITIVE
    elif len(sub_matches) > len(add_matches):
        expected_operation = OperationType.SUBTRACTIVE

    if rate_matches:
        return RelationType.RATE_UNIT_RELATION, expected_operation, notes
    if partition_matches:
        return RelationType.PARTITION_GROUPING, expected_operation, notes
    if mult_matches:
        return RelationType.MULTIPLICATIVE_SCALING, expected_operation, notes
    if expected_operation == OperationType.ADDITIVE:
        return RelationType.ADDITIVE_COMPOSITION, expected_operation, notes
    if expected_operation == OperationType.SUBTRACTIVE:
        return RelationType.SUBTRACTIVE_COMPARISON, expected_operation, notes
    return RelationType.UNKNOWN, expected_operation, notes


def _extract_entities(problem_text: str) -> list[ProblemEntity]:
    seen: set[str] = set()
    entities: list[ProblemEntity] = []
    for idx, match in enumerate(_ENTITY_PATTERN.finditer(problem_text or ""), start=1):
        surface = match.group(0).strip()
        key = surface.lower()
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            ProblemEntity(
                entity_id=f"entity_{idx}",
                surface_text=surface,
                normalized_name=surface,
                entity_type="person" if surface.startswith(("Mr.", "Mrs.", "Ms.", "Dr.")) else "named_entity",
                metadata={"char_start": match.start(), "char_end": match.end()},
            )
        )
    return entities


def _link_quantities_to_entities(
    quantities: list[QuantityAnnotation],
    entities: list[ProblemEntity],
) -> list[QuantityAnnotation]:
    if not quantities or not entities:
        return quantities

    linked: list[QuantityAnnotation] = []
    for quantity in quantities:
        if quantity.entity_id is not None or quantity.char_start is None:
            linked.append(quantity)
            continue

        best_entity: ProblemEntity | None = None
        best_distance: int | None = None
        for entity in entities:
            char_start = entity.metadata.get("char_start")
            if not isinstance(char_start, int):
                continue
            distance = abs(char_start - quantity.char_start)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_entity = entity

        if best_entity is None:
            linked.append(quantity)
            continue

        linked.append(quantity.model_copy(update={"entity_id": best_entity.entity_id}))

    return linked


def _infer_unit(surface: str, right_context: str) -> Optional[str]:
    if "$" in surface:
        return "dollars"
    if "%" in surface:
        return "percent"
    words = re.findall(r"[A-Za-z]+", right_context)
    collected: list[str] = []
    for word in words:
        lowered = word.lower()
        if lowered in _UNIT_STOPWORDS:
            if collected:
                break
            continue
        collected.append(lowered)
        if len(collected) >= 2:
            break
    return " ".join(collected) if collected else None


def _infer_semantic_role(surface: str, context: str, target_text: str) -> tuple[QuantitySemanticRole, bool]:
    lowered_context = context.lower()
    if "%" in surface or "percent" in lowered_context:
        return QuantitySemanticRole.PERCENT, False
    if any(cue in lowered_context for cue in _THRESHOLD_CUES):
        return QuantitySemanticRole.THRESHOLD, False
    if any(cue in lowered_context for cue in _RATE_CUES):
        return QuantitySemanticRole.UNIT_RATE, False
    if target_text and surface in target_text:
        return QuantitySemanticRole.TARGET_CANDIDATE, True
    return QuantitySemanticRole.BASE, False


def _extract_quantities(problem_text: str, target_text: str) -> list[QuantityAnnotation]:
    quantities: list[QuantityAnnotation] = []
    sentences = _split_sentences(problem_text)

    for idx, match in enumerate(_NUMBER_PATTERN.finditer(problem_text or ""), start=1):
        surface = match.group(0)
        normalized = surface.replace("$", "").replace("%", "").replace(",", "")
        try:
            value = float(normalized)
        except ValueError:
            continue

        sentence_index = None
        sentence_text = ""
        for s_idx, (sentence, start, end) in enumerate(sentences):
            if start <= match.start() < end:
                sentence_index = s_idx
                sentence_text = sentence
                break

        right_context = (problem_text[match.end():match.end() + 30] or "").strip()
        local_context = problem_text[max(0, match.start() - 25):match.end() + 35]
        semantic_role, is_target_candidate = _infer_semantic_role(surface, local_context, target_text)
        quantities.append(
            QuantityAnnotation(
                quantity_id=f"quantity_{idx}",
                surface_text=surface,
                value=value,
                unit=_infer_unit(surface, right_context),
                semantic_role=semantic_role,
                sentence_index=sentence_index,
                char_start=match.start(),
                char_end=match.end(),
                is_target_candidate=is_target_candidate,
                provenance=ProvenanceSource.PROBLEM_TEXT,
                notes=[f"context={local_context.strip()}"] if sentence_text else [],
            )
        )

    return quantities


def _build_target_spec(problem_text: str, target_text: str) -> Optional[TargetSpec]:
    if not target_text:
        return None
    unit = None
    lowered = target_text.lower()
    if "how much" in lowered:
        unit = "dollars"
    elif "how many" in lowered:
        words = re.findall(r"[A-Za-z]+", target_text)
        for idx, word in enumerate(words):
            if word.lower() == "many" and idx + 1 < len(words):
                unit = words[idx + 1].lower()
                break

    return TargetSpec(
        surface_text=target_text,
        normalized_question=target_text.strip(),
        target_variable=_slugify(target_text, fallback="answer"),
        unit=unit,
        description=target_text.strip("?"),
        provenance=ProvenanceSource.PROBLEM_TEXT,
        confidence=0.85,
    )


def _attach_target_quantity(
    target: Optional[TargetSpec],
    quantities: list[QuantityAnnotation],
) -> Optional[TargetSpec]:
    if target is None:
        return None

    lowered_target = target.surface_text.lower()
    target_quantity = next(
        (
            quantity
            for quantity in quantities
            if quantity.is_target_candidate and quantity.surface_text.lower() in lowered_target
        ),
        None,
    )
    if target_quantity is None and target.unit is not None:
        target_quantity = next(
            (
                quantity
                for quantity in quantities
                if quantity.unit is not None and target.unit in quantity.unit
            ),
            None,
        )
    if target_quantity is None:
        return target

    return target.model_copy(
        update={
            "target_quantity_id": target_quantity.quantity_id,
            "entity_id": target_quantity.entity_id,
        }
    )


def _candidate_expression(
    relation_type: RelationType,
    operation: OperationType,
    quantities: list[QuantityAnnotation],
    target_ref: str,
) -> Optional[str]:
    refs = [q.quantity_id for q in quantities]
    if not refs:
        return None
    if relation_type == RelationType.RATE_UNIT_RELATION:
        unit_rate = next((q for q in quantities if q.semantic_role == QuantitySemanticRole.UNIT_RATE), None)
        percent = next((q for q in quantities if q.semantic_role == QuantitySemanticRole.PERCENT), None)
        threshold = next((q for q in quantities if q.semantic_role == QuantitySemanticRole.THRESHOLD), None)
        base = next((q for q in quantities if q.semantic_role == QuantitySemanticRole.BASE), None)
        if unit_rate and percent and threshold and base:
            return (
                f"{target_ref} = ({base.quantity_id} * {unit_rate.quantity_id}) - "
                f"(max({base.quantity_id} - {threshold.quantity_id}, 0) * "
                f"({percent.quantity_id}/100) * {unit_rate.quantity_id})"
            )
        return f"{target_ref} = rate_or_percent_relation({', '.join(refs)})"
    if relation_type == RelationType.ADDITIVE_COMPOSITION and len(refs) >= 2:
        return f"{target_ref} = " + " + ".join(refs)
    if relation_type == RelationType.SUBTRACTIVE_COMPARISON and len(refs) >= 2:
        return f"{target_ref} = {refs[0]} - " + " - ".join(refs[1:])
    if relation_type == RelationType.MULTIPLICATIVE_SCALING and len(refs) >= 2:
        return f"{target_ref} = {refs[0]} * {refs[1]}"
    return None


def _build_relation_candidates(
    problem_text: str,
    target: Optional[TargetSpec],
    quantities: list[QuantityAnnotation],
) -> tuple[list[RelationCandidate], list[str]]:
    target_text = target.surface_text if target is not None else ""
    relation_type, operation_hint, notes = _infer_relation_and_operation(problem_text, target_text)
    target_variable = target.target_variable if target is not None else "answer"
    relation = RelationCandidate(
        relation_id="relation_1",
        relation_type=relation_type,
        operation_hint=operation_hint,
        source_quantity_ids=[q.quantity_id for q in quantities],
        target_variable=target_variable,
        expression=_candidate_expression(relation_type, operation_hint, quantities, target_variable),
        rationale="Heuristic relation candidate built from problem cues and extracted quantities.",
        confidence=0.72 if relation_type != RelationType.UNKNOWN else 0.35,
        provenance=ProvenanceSource.HEURISTIC if relation_type != RelationType.UNKNOWN else ProvenanceSource.UNKNOWN,
    )
    return [relation], notes


def _dedupe_quantities(quantities: list[QuantityAnnotation]) -> tuple[list[QuantityAnnotation], list[str]]:
    deduped: list[QuantityAnnotation] = []
    notes: list[str] = []
    seen: set[tuple[str, int | None, int | None]] = set()

    for quantity in quantities:
        key = (quantity.surface_text, quantity.char_start, quantity.char_end)
        if key in seen:
            notes.append(f"deduped_quantity:{quantity.surface_text}@{quantity.char_start}")
            continue
        seen.add(key)
        deduped.append(quantity)

    return deduped, notes

