"""Low-level parsing and heuristic extraction helpers for problem formalization."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from src.models import (
    OperationType,
    ProblemEntity,
    ProblemGraphEdgeType,
    ProvenanceSource,
    QuantityAnnotation,
    QuantitySemanticRole,
    RelationCandidate,
    RelationType,
    SemanticTriple,
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

_TRIPLE_SPLIT_PATTERN = re.compile(r",\s+|;\s+|\s+so\s+|\s+then\s+", re.IGNORECASE)
_TRIPLE_PREPOSITIONS = {
    "from",
    "to",
    "in",
    "on",
    "at",
    "with",
    "for",
    "of",
    "over",
    "under",
    "into",
    "onto",
    "through",
    "across",
    "within",
    "during",
    "as",
    "than",
}
_TRIPLE_AUXILIARY = {
    "am",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "do",
    "does",
    "did",
    "has",
    "have",
    "had",
    "will",
    "would",
    "can",
    "could",
    "should",
    "may",
    "might",
    "must",
}
_TRIPLE_VERB_HINTS = {
    "buy",
    "bought",
    "sell",
    "sold",
    "cost",
    "costs",
    "rise",
    "rises",
    "rose",
    "consume",
    "consumed",
    "eat",
    "eats",
    "ate",
    "build",
    "built",
    "receive",
    "received",
    "give",
    "gave",
    "remain",
    "remains",
    "left",
    "travel",
    "traveled",
    "walk",
    "walked",
    "run",
    "ran",
    "increase",
    "increased",
    "decrease",
    "decreased",
    "contain",
    "contains",
    "share",
    "shared",
    "split",
    "divide",
    "divided",
    "exceed",
    "exceeds",
}
_TRIPLE_NUMBER_WORDS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
    "hundred",
    "thousand",
    "million",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
}
_TRIPLE_VERB_BLOCKLIST = {
    "year",
    "years",
    "month",
    "months",
    "day",
    "days",
    "time",
    "people",
    "person",
    "ship",
    "ships",
}
_TRIPLE_WEAK_PREDICATES = {"has", "have", "had", "is", "are", "was", "were", "be", "been", "being"}
_TRIPLE_RELATION_CUES = (
    "twice as many",
    "half as many",
    "more than",
    "less than",
    "rises from",
    "rises",
    "consumed",
    "received",
    "bought",
    "built",
    "costs",
    "ate",
    "has",
    "have",
    "had",
    "is",
    "are",
    "was",
    "were",
)
_TRIPLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "for",
    "from",
    "in",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
_TRIPLE_PRONOUNS = {"it", "he", "she", "they", "them", "its", "their", "his", "her"}
_TRIPLE_CLAUSE_TRIM_MARKERS = (" because ", " which ", " who ", " that ", " then ", " so ", " but ", " to ")


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


def _looks_like_triple_verb(token: str) -> bool:
    lowered = (token or "").lower()
    if not lowered:
        return False
    if lowered in _TRIPLE_VERB_BLOCKLIST:
        return False
    if lowered in _TRIPLE_NUMBER_WORDS:
        return False
    if lowered in _TRIPLE_AUXILIARY:
        return False
    if lowered in _TRIPLE_VERB_HINTS:
        return True
    if lowered.endswith("ed") and len(lowered) >= 4:
        return True
    if lowered.endswith("ing") and len(lowered) >= 5:
        return True
    if lowered.endswith("es") and len(lowered) >= 4 and lowered not in _TRIPLE_STOPWORDS:
        return True
    if lowered.endswith("s") and len(lowered) >= 4 and lowered not in _TRIPLE_STOPWORDS and not lowered.endswith("ss"):
        return True
    return False


def _find_triple_relation_cue(clause: str) -> tuple[int, int, str] | None:
    lowered = (clause or "").lower()
    best_match: tuple[tuple[int, int, int], tuple[int, int, str]] | None = None
    for cue in sorted(_TRIPLE_RELATION_CUES, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(cue)}\b", lowered)
        if match is None:
            continue
        weak_score = 1 if cue in _TRIPLE_WEAK_PREDICATES else 0
        rank = (weak_score, match.start(), -(match.end() - match.start()))
        candidate = (match.start(), match.end(), cue)
        if best_match is None or rank < best_match[0]:
            best_match = (rank, candidate)
    if best_match is not None:
        return best_match[1]

    token_matches = list(re.finditer(r"[a-z]+(?:-[a-z]+)?", lowered))
    for index, token_match in enumerate(token_matches):
        token = token_match.group(0)
        if not _looks_like_triple_verb(token):
            continue
        predicate = token
        end = token_match.end()
        if index + 1 < len(token_matches):
            next_token = token_matches[index + 1].group(0)
            if next_token in _TRIPLE_PREPOSITIONS:
                predicate = f"{token} {next_token}"
                end = token_matches[index + 1].end()
        return token_match.start(), end, predicate
    return None


def _clean_triple_subject(fragment: str) -> str:
    cleaned = (fragment or "").strip(" ,;:-")
    if "," in cleaned:
        cleaned = cleaned.split(",")[-1].strip()
    lowered = cleaned.lower()
    for marker in (" so ", " then ", " but ", " and "):
        if marker in lowered:
            split_at = lowered.rfind(marker)
            cleaned = cleaned[split_at + len(marker):].strip()
            lowered = cleaned.lower()
    while True:
        reduced = re.sub(r"\b(has|have|had|is|are|was|were|be|been|being)\b\s*$", "", cleaned, flags=re.IGNORECASE).strip()
        if reduced == cleaned:
            break
        cleaned = reduced
    cleaned = re.sub(r"^(so|then|but|and)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^(over|during|in|for)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^(a|an|the)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _clean_triple_object(fragment: str) -> str:
    cleaned = (fragment or "").strip(" ,;:-")
    lowered = cleaned.lower()
    for marker in _TRIPLE_CLAUSE_TRIM_MARKERS:
        index = lowered.find(marker)
        if index > 0:
            cleaned = cleaned[:index].strip()
            lowered = cleaned.lower()

    cleaned = re.sub(
        r"\bonce every\s+[a-z0-9\s-]+?\s+years?\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"\b(?:every|over|during|in|for)\s+[a-z0-9\s-]+?\s+years?\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r"^(from|to|in|on|at|with|for|of|over|during|as|than)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _normalize_concept_phrase(fragment: str) -> str:
    tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", (fragment or "").lower())
    if not tokens:
        return ""

    if "year" in tokens or "years" in tokens:
        time_tokens: list[str] = []
        for token in tokens:
            if token in _TRIPLE_STOPWORDS:
                continue
            if token in {"year", "years"} or token in _TRIPLE_NUMBER_WORDS or token.isdigit():
                time_tokens.append(token)
        if time_tokens:
            return " ".join(time_tokens[:5])

    kept: list[str] = []
    for token in tokens:
        if token in _TRIPLE_STOPWORDS:
            continue
        if token in _TRIPLE_NUMBER_WORDS:
            continue
        if token.isdigit():
            continue
        kept.append(token)
    if not kept:
        return ""
    return " ".join(kept[:6])


def _extract_period_hint(clause: str) -> tuple[str, ProblemGraphEdgeType] | None:
    every_match = re.search(r"\bevery\s+([a-z0-9\s-]+?)\s+years?\b", clause, flags=re.IGNORECASE)
    if every_match is not None:
        return f"{every_match.group(1).strip()} years", ProblemGraphEdgeType.OCCURS_EVERY

    for pattern in (
        r"\bover\s+([a-z0-9\s-]+?)\s+years?\b",
        r"\bin\s+([a-z0-9\s-]+?)\s+years?\b",
        r"\bduring\s+([a-z0-9\s-]+?)\s+years?\b",
        r"\bfor\s+([a-z0-9\s-]+?)\s+years?\b",
    ):
        match = re.search(pattern, clause, flags=re.IGNORECASE)
        if match is not None:
            return f"{match.group(1).strip()} years", ProblemGraphEdgeType.DURING_PERIOD
    return None


def _triple_edge_type(predicate: str) -> ProblemGraphEdgeType:
    normalized = (predicate or "").lower()
    if (normalized.startswith("rise") or normalized.startswith("rose")) and "from" in normalized:
        return ProblemGraphEdgeType.RISE_FROM
    if normalized.startswith("consume"):
        return ProblemGraphEdgeType.CONSUME
    if normalized in {"eat", "eats", "ate"}:
        return ProblemGraphEdgeType.ATE
    if normalized.startswith("build") or normalized == "built":
        return ProblemGraphEdgeType.BUILT_OVER_TIME
    if any(cue in normalized for cue in ("twice", "half", "double", "triple", "more than", "less than", "times")):
        return ProblemGraphEdgeType.MULTIPLIER_OF
    if normalized in {"has", "have", "had", "contains", "contain", "includes", "include"}:
        return ProblemGraphEdgeType.HAS_ATTRIBUTE
    return ProblemGraphEdgeType.VERB_RELATION


def _quantity_ids_by_sentence(
    quantities: list[QuantityAnnotation],
    sentences: list[tuple[str, int, int]],
) -> dict[int, list[QuantityAnnotation]]:
    grouped: dict[int, list[QuantityAnnotation]] = {}
    for quantity in quantities:
        sentence_index: int | None = quantity.sentence_index
        if sentence_index is None and quantity.char_start is not None:
            for idx, (_, start, end) in enumerate(sentences):
                if start <= quantity.char_start < end:
                    sentence_index = idx
                    break
        if sentence_index is None:
            continue
        grouped.setdefault(sentence_index, []).append(quantity)
    return grouped


def _resolve_triple_node_id(
    *,
    phrase: str,
    target: Optional[TargetSpec],
    entities: list[ProblemEntity],
    concept_ids_by_norm: dict[str, str],
    concept_labels_by_id: dict[str, str],
    used_node_ids: set[str],
    fallback_node_id: str | None = None,
) -> str | None:
    cleaned = (phrase or "").strip()
    lowered = cleaned.lower()
    if not cleaned:
        return fallback_node_id

    if target is not None and any(cue in lowered for cue in ("how many", "how much", "what", "which", "who")):
        return target.target_variable

    if lowered in _TRIPLE_PRONOUNS and fallback_node_id is not None:
        return fallback_node_id

    for entity in entities:
        entity_lower = entity.surface_text.lower()
        if lowered == entity_lower or entity_lower in lowered or lowered in entity_lower:
            return entity.entity_id

    normalized = _normalize_concept_phrase(cleaned)
    if not normalized:
        return fallback_node_id

    existing = concept_ids_by_norm.get(normalized)
    if existing is not None:
        return existing

    base_node_id = f"concept_{_slugify(normalized, fallback='node')}"
    node_id = base_node_id
    suffix = 2
    while node_id in used_node_ids:
        node_id = f"{base_node_id}_{suffix}"
        suffix += 1

    concept_ids_by_norm[normalized] = node_id
    concept_labels_by_id[node_id] = normalized
    used_node_ids.add(node_id)
    return node_id


def _node_label_from_id(
    node_id: str,
    *,
    target: Optional[TargetSpec],
    quantities_by_id: dict[str, QuantityAnnotation],
    entities_by_id: dict[str, ProblemEntity],
    concept_labels_by_id: dict[str, str],
) -> str:
    if target is not None and node_id == target.target_variable:
        return target.surface_text
    if node_id in quantities_by_id:
        return quantities_by_id[node_id].surface_text
    if node_id in entities_by_id:
        return entities_by_id[node_id].surface_text
    if node_id in concept_labels_by_id:
        return concept_labels_by_id[node_id]
    if node_id.startswith("concept_"):
        return node_id[len("concept_"):].replace("_", " ")
    return node_id


def _add_semantic_triple(
    triples: list[SemanticTriple],
    seen_keys: set[tuple[str, str, str, int | None, int | None]],
    *,
    triple_id: str,
    subject_node_id: str,
    predicate_text: str,
    object_node_id: str,
    subject_text: str,
    object_text: str,
    sentence_index: int | None,
    clause_index: int | None,
    edge_type: ProblemGraphEdgeType,
    confidence: float,
    notes: list[str],
) -> bool:
    predicate = predicate_text.strip().lower()
    key = (subject_node_id, predicate, object_node_id, sentence_index, clause_index)
    if key in seen_keys:
        return False
    seen_keys.add(key)
    triples.append(
        SemanticTriple(
            triple_id=triple_id,
            subject_text=subject_text,
            predicate_text=predicate_text.strip(),
            object_text=object_text,
            subject_node_id=subject_node_id,
            object_node_id=object_node_id,
            edge_type=edge_type,
            sentence_index=sentence_index,
            clause_index=clause_index,
            confidence=confidence,
            provenance=ProvenanceSource.HEURISTIC,
            notes=notes,
        )
    )
    return True


def _extract_semantic_triples(
    problem_text: str,
    target: Optional[TargetSpec],
    entities: list[ProblemEntity],
    quantities: list[QuantityAnnotation],
) -> list[SemanticTriple]:
    if not (problem_text or "").strip():
        return []

    sentences = _split_sentences(problem_text)
    quantities_per_sentence = _quantity_ids_by_sentence(quantities, sentences)
    quantities_by_id = {quantity.quantity_id: quantity for quantity in quantities}
    entities_by_id = {entity.entity_id: entity for entity in entities}

    triples: list[SemanticTriple] = []
    seen_keys: set[tuple[str, str, str, int | None, int | None]] = set()
    triple_counter = 1

    used_node_ids: set[str] = set(quantities_by_id)
    used_node_ids.update(entities_by_id)
    if target is not None:
        used_node_ids.add(target.target_variable)

    concept_ids_by_norm: dict[str, str] = {}
    concept_labels_by_id: dict[str, str] = {}
    previous_subject_node_id: str | None = None

    for sentence_index, (sentence, _, _) in enumerate(sentences):
        clauses = [part.strip() for part in _TRIPLE_SPLIT_PATTERN.split(sentence) if part.strip()] or [sentence]
        for clause_index, clause in enumerate(clauses):
            cue = _find_triple_relation_cue(clause)
            subject_node_id: str | None = None
            object_node_id: str | None = None

            if cue is not None:
                cue_start, cue_end, predicate = cue
                subject_fragment = _clean_triple_subject(clause[:cue_start])
                object_fragment = _clean_triple_object(clause[cue_end:])

                if predicate in {"twice as many", "half as many"}:
                    comparative_match = re.search(
                        rf"{re.escape(predicate)}\s+(?P<object>[a-z0-9\s-]+?)\s+as\s+(?P<reference>.+)$",
                        clause,
                        flags=re.IGNORECASE,
                    )
                    if comparative_match is not None:
                        object_fragment = _clean_triple_object(comparative_match.group("reference"))

                subject_node_id = _resolve_triple_node_id(
                    phrase=subject_fragment,
                    target=target,
                    entities=entities,
                    concept_ids_by_norm=concept_ids_by_norm,
                    concept_labels_by_id=concept_labels_by_id,
                    used_node_ids=used_node_ids,
                    fallback_node_id=previous_subject_node_id,
                )
                object_node_id = _resolve_triple_node_id(
                    phrase=object_fragment,
                    target=target,
                    entities=entities,
                    concept_ids_by_norm=concept_ids_by_norm,
                    concept_labels_by_id=concept_labels_by_id,
                    used_node_ids=used_node_ids,
                )

                if subject_node_id is not None and object_node_id is not None and subject_node_id != object_node_id:
                    subject_label = _node_label_from_id(
                        subject_node_id,
                        target=target,
                        quantities_by_id=quantities_by_id,
                        entities_by_id=entities_by_id,
                        concept_labels_by_id=concept_labels_by_id,
                    )
                    object_label = _node_label_from_id(
                        object_node_id,
                        target=target,
                        quantities_by_id=quantities_by_id,
                        entities_by_id=entities_by_id,
                        concept_labels_by_id=concept_labels_by_id,
                    )
                    added = _add_semantic_triple(
                        triples,
                        seen_keys,
                        triple_id=f"triple_{triple_counter}",
                        subject_node_id=subject_node_id,
                        predicate_text=predicate,
                        object_node_id=object_node_id,
                        subject_text=subject_label,
                        object_text=object_label,
                        sentence_index=sentence_index,
                        clause_index=clause_index,
                        edge_type=_triple_edge_type(predicate),
                        confidence=0.7,
                        notes=[f"clause={clause.strip()}"],
                    )
                    if added:
                        triple_counter += 1

                normalized_subject = _normalize_concept_phrase(subject_fragment)
                if (
                    subject_node_id is not None
                    and normalized_subject
                    and normalized_subject not in _TRIPLE_PRONOUNS
                ):
                    previous_subject_node_id = subject_node_id

            period_hint = _extract_period_hint(clause)
            period_subject_node_id = subject_node_id or previous_subject_node_id
            if period_hint is not None and period_subject_node_id is not None:
                period_text, period_edge_type = period_hint
                period_node_id = _resolve_triple_node_id(
                    phrase=period_text,
                    target=target,
                    entities=entities,
                    concept_ids_by_norm=concept_ids_by_norm,
                    concept_labels_by_id=concept_labels_by_id,
                    used_node_ids=used_node_ids,
                )
                if period_node_id is not None and period_node_id != period_subject_node_id:
                    subject_label = _node_label_from_id(
                        period_subject_node_id,
                        target=target,
                        quantities_by_id=quantities_by_id,
                        entities_by_id=entities_by_id,
                        concept_labels_by_id=concept_labels_by_id,
                    )
                    period_label = _node_label_from_id(
                        period_node_id,
                        target=target,
                        quantities_by_id=quantities_by_id,
                        entities_by_id=entities_by_id,
                        concept_labels_by_id=concept_labels_by_id,
                    )
                    predicate = "occurs every" if period_edge_type == ProblemGraphEdgeType.OCCURS_EVERY else "during"
                    added = _add_semantic_triple(
                        triples,
                        seen_keys,
                        triple_id=f"triple_{triple_counter}",
                        subject_node_id=period_subject_node_id,
                        predicate_text=predicate,
                        object_node_id=period_node_id,
                        subject_text=subject_label,
                        object_text=period_label,
                        sentence_index=sentence_index,
                        clause_index=clause_index,
                        edge_type=period_edge_type,
                        confidence=0.69,
                        notes=["period_relation"],
                    )
                    if added:
                        triple_counter += 1

            sentence_quantities = quantities_per_sentence.get(sentence_index, [])
            for quantity in sentence_quantities:
                if subject_node_id is not None and subject_node_id != quantity.quantity_id:
                    subject_label = _node_label_from_id(
                        subject_node_id,
                        target=target,
                        quantities_by_id=quantities_by_id,
                        entities_by_id=entities_by_id,
                        concept_labels_by_id=concept_labels_by_id,
                    )
                    added = _add_semantic_triple(
                        triples,
                        seen_keys,
                        triple_id=f"triple_{triple_counter}",
                        subject_node_id=subject_node_id,
                        predicate_text="has quantity",
                        object_node_id=quantity.quantity_id,
                        subject_text=subject_label,
                        object_text=quantity.surface_text,
                        sentence_index=sentence_index,
                        clause_index=clause_index,
                        edge_type=ProblemGraphEdgeType.HAS_ATTRIBUTE,
                        confidence=0.66,
                        notes=["link=subject_quantity"],
                    )
                    if added:
                        triple_counter += 1

                if object_node_id is not None and object_node_id != quantity.quantity_id:
                    object_label = _node_label_from_id(
                        object_node_id,
                        target=target,
                        quantities_by_id=quantities_by_id,
                        entities_by_id=entities_by_id,
                        concept_labels_by_id=concept_labels_by_id,
                    )
                    added = _add_semantic_triple(
                        triples,
                        seen_keys,
                        triple_id=f"triple_{triple_counter}",
                        subject_node_id=quantity.quantity_id,
                        predicate_text="supports",
                        object_node_id=object_node_id,
                        subject_text=quantity.surface_text,
                        object_text=object_label,
                        sentence_index=sentence_index,
                        clause_index=clause_index,
                        edge_type=ProblemGraphEdgeType.HAS_ATTRIBUTE,
                        confidence=0.66,
                        notes=["link=quantity_object"],
                    )
                    if added:
                        triple_counter += 1

    return triples
