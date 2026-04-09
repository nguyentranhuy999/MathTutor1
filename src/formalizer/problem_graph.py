"""Problem graph construction from a structured formalized problem."""
from __future__ import annotations

import re

from src.models import (
    FormalizedProblem,
    ProblemGraph,
    ProblemGraphEdge,
    ProblemGraphEdgeType,
    ProblemGraphNode,
    ProblemGraphNodeType,
    ProvenanceSource,
    QuantityAnnotation,
    QuantitySemanticRole,
    RelationType,
    SemanticTriple,
    TraceOperation,
)


_WORD_NUMBER_UNITS: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_WORD_NUMBER_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_WORD_NUMBER_MULTIPLIERS: dict[str, int] = {
    "hundred": 100,
    "thousand": 1000,
}
_WORD_NUMBER_ORDINALS: dict[str, int] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
_EVERY_YEARS_PATTERN = re.compile(r"\bevery\s+(?P<number>[a-z0-9\s-]+?)\s+years?\b", re.IGNORECASE)
_OVER_YEARS_PATTERN = re.compile(r"\bover\s+(?P<number>[a-z0-9\s-]+?)\s+years?\b", re.IGNORECASE)
_ORDINAL_VALUE_MAP: dict[str, int] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
_SUMMARY_STOPWORDS: set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "their",
    "there",
    "this",
    "to",
    "was",
    "were",
    "with",
    "every",
    "once",
    "over",
    "than",
}
_SUMMARY_PRONOUNS: set[str] = {"it", "he", "she", "they", "them", "its", "their", "his", "her"}
_SUMMARY_PREPOSITIONS: set[str] = {
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
    "than",
    "as",
}
_SUMMARY_AUXILIARY_VERBS: set[str] = {
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
_SUMMARY_VERB_HINTS: set[str] = {
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
_SUMMARY_RELATION_CUES: tuple[str, ...] = (
    "twice as many",
    "half as many",
    "more than",
    "less than",
    "exceeds",
    "rises from",
    "rises",
    "consumed",
    "received",
    "bought",
    "built",
    "costs",
    "ate",
)


def _first_quantity_with_role(
    quantities: list[QuantityAnnotation],
    role: QuantitySemanticRole,
) -> QuantityAnnotation | None:
    return next((quantity for quantity in quantities if quantity.semantic_role == role), None)


def _base_quantities(quantities: list[QuantityAnnotation]) -> list[QuantityAnnotation]:
    return [quantity for quantity in quantities if quantity.semantic_role == QuantitySemanticRole.BASE]


def _select_rate_unit_price_quantity(problem: FormalizedProblem) -> QuantityAnnotation | None:
    target_unit = problem.target.unit if problem.target is not None else None
    candidates = [
        quantity
        for quantity in problem.quantities
        if quantity.semantic_role == QuantitySemanticRole.UNIT_RATE
    ]
    if not candidates:
        return None
    if target_unit is not None:
        match = next((quantity for quantity in candidates if quantity.unit == target_unit), None)
        if match is not None:
            return match
    return next((quantity for quantity in candidates if "$" in quantity.surface_text), candidates[0])


def _select_rate_unit_base_quantity(problem: FormalizedProblem) -> QuantityAnnotation | None:
    target_unit = problem.target.unit if problem.target is not None else None
    base_candidates = _base_quantities(problem.quantities)
    if base_candidates:
        return base_candidates[0]

    for quantity in problem.quantities:
        if quantity.semantic_role in (QuantitySemanticRole.PERCENT, QuantitySemanticRole.THRESHOLD):
            continue
        if target_unit is not None and quantity.unit == target_unit:
            continue
        return quantity

    return next(
        (
            quantity
            for quantity in problem.quantities
            if quantity.semantic_role != QuantitySemanticRole.PERCENT
        ),
        None,
    )


def _target_ref(problem: FormalizedProblem) -> str:
    if problem.target is not None:
        return problem.target.target_variable
    return "answer"


def _parse_number_fragment(fragment: str) -> float | None:
    cleaned = (fragment or "").strip().lower()
    if not cleaned:
        return None

    direct_match = re.fullmatch(r"\d+(?:\.\d+)?", cleaned)
    if direct_match:
        try:
            return float(cleaned)
        except ValueError:
            return None

    tokens = re.findall(r"[a-z]+", cleaned)
    if not tokens:
        return None

    total = 0
    current = 0
    saw_numeric_token = False

    for token in tokens:
        if token == "and":
            continue
        if token in _WORD_NUMBER_UNITS:
            current += _WORD_NUMBER_UNITS[token]
            saw_numeric_token = True
            continue
        if token in _WORD_NUMBER_ORDINALS:
            current += _WORD_NUMBER_ORDINALS[token]
            saw_numeric_token = True
            continue
        if token in _WORD_NUMBER_TENS:
            current += _WORD_NUMBER_TENS[token]
            saw_numeric_token = True
            continue
        if token in _WORD_NUMBER_MULTIPLIERS:
            multiplier = _WORD_NUMBER_MULTIPLIERS[token]
            if current == 0:
                current = 1
            current *= multiplier
            saw_numeric_token = True
            if multiplier >= 1000:
                total += current
                current = 0
            continue
        return None

    if not saw_numeric_token:
        return None
    return float(total + current)


def _infer_progression_ratio(problem_text: str) -> float | None:
    lowered = (problem_text or "").lower()
    if "twice" in lowered or "double" in lowered:
        return 2.0
    if "triple" in lowered:
        return 3.0
    if "half" in lowered:
        return 0.5

    numeric_times = re.search(r"\b(\d+(?:\.\d+)?)\s+times\b", lowered)
    if numeric_times:
        try:
            value = float(numeric_times.group(1))
            if value > 0:
                return value
        except ValueError:
            return None

    word_times = re.search(r"\b([a-z]+(?:[\s-]+[a-z]+){0,3})\s+times\b", lowered)
    if word_times:
        parsed = _parse_number_fragment(word_times.group(1))
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _infer_term_count(problem: FormalizedProblem) -> int | None:
    text = problem.problem_text or ""

    over_match = _OVER_YEARS_PATTERN.search(text)
    every_match = _EVERY_YEARS_PATTERN.search(text)
    if over_match and every_match:
        over_value = _parse_number_fragment(over_match.group("number"))
        every_value = _parse_number_fragment(every_match.group("number"))
        if over_value and every_value and every_value > 0:
            ratio = over_value / every_value
            rounded = int(round(ratio))
            if rounded >= 2 and abs(ratio - rounded) < 1e-9:
                return rounded

    ordinals = [value for token, value in _ORDINAL_VALUE_MAP.items() if token in text.lower()]
    if ordinals:
        max_ordinal = max(ordinals)
        if max_ordinal >= 2:
            return max_ordinal
    return None


def _select_progression_total_quantity(problem: FormalizedProblem) -> QuantityAnnotation | None:
    target_unit = (problem.target.unit or "").lower() if problem.target is not None and problem.target.unit else ""
    best: QuantityAnnotation | None = None
    best_score = float("-inf")

    for quantity in problem.quantities:
        if quantity.semantic_role in (QuantitySemanticRole.PERCENT, QuantitySemanticRole.THRESHOLD):
            continue
        unit = (quantity.unit or "").lower()
        if "year" in unit:
            continue

        score = 0.0
        if target_unit and target_unit in unit:
            score += 4.0
        if quantity.semantic_role == QuantitySemanticRole.BASE:
            score += 2.0
        context = " ".join(quantity.notes).lower()
        if any(cue in context for cue in ("total", "consumed", "in all", "altogether", "sum")):
            score += 1.5
        score += min(quantity.value / 1000.0, 1.0)

        if score > best_score:
            best_score = score
            best = quantity

    return best


def _target_requests_first_term(problem: FormalizedProblem) -> bool:
    if problem.target is None:
        return False
    lowered = problem.target.surface_text.lower()
    return "first" in lowered


def _split_sentences_with_offsets(text: str) -> list[tuple[str, int, int]]:
    sentences: list[tuple[str, int, int]] = []
    if not text:
        return sentences
    for match in re.finditer(r"[^.!?]+[.!?]?", text):
        sentence = match.group(0).strip()
        if sentence:
            sentences.append((sentence, match.start(), match.end()))
    return sentences


def _clean_summary_subject(fragment: str) -> str:
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
        reduced = re.sub(r"\b(has|have|had|is|are|was|were|be|been)\b\s*$", "", cleaned, flags=re.IGNORECASE).strip()
        if reduced == cleaned:
            break
        cleaned = reduced

    cleaned = re.sub(r"^(a|an|the)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _clean_summary_object(fragment: str) -> str:
    cleaned = (fragment or "").strip(" ,;:-")
    lowered = cleaned.lower()
    for marker in (" because ", " then ", " so ", ",", " once every ", " every "):
        index = lowered.find(marker)
        if index > 0:
            cleaned = cleaned[:index].strip()
            lowered = cleaned.lower()
    for marker in (" as ", " to "):
        index = lowered.find(marker)
        if index > 0:
            cleaned = cleaned[:index].strip()
            lowered = cleaned.lower()

    cleaned = re.sub(r"^(from|on|in|at|to|of|for)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _split_summary_clauses(sentence: str) -> list[str]:
    parts = [part.strip() for part in re.split(r",\s+|;\s+|\s+so\s+", sentence) if part.strip()]
    return parts if parts else [sentence.strip()]


def _normalize_time_phrase(fragment: str) -> str:
    cleaned = (fragment or "").strip().lower()
    if not cleaned:
        return ""
    cleaned = re.sub(r"^(over|in|during|for|once every|every)\s+", "", cleaned).strip()

    numeric_fragment = re.sub(r"\byears?\b", "", cleaned).strip(" ,")
    parsed = _parse_number_fragment(numeric_fragment)
    if parsed is not None and parsed > 0:
        if abs(parsed - round(parsed)) < 1e-9:
            return f"{int(round(parsed))} years"
        return f"{parsed:g} years"

    tokens = re.findall(r"[a-z]+", cleaned)
    kept = [token for token in tokens if token not in _SUMMARY_STOPWORDS]
    if not kept:
        return ""
    return " ".join(kept[:4])


def _normalize_summary_phrase(fragment: str) -> str:
    tokens = re.findall(r"[a-z]+(?:-[a-z]+)?", (fragment or "").lower())
    if not tokens:
        return ""

    if "year" in tokens or "years" in tokens:
        return _normalize_time_phrase(fragment)

    filtered: list[str] = []
    numeric_words = set(_WORD_NUMBER_UNITS) | set(_WORD_NUMBER_TENS) | set(_WORD_NUMBER_MULTIPLIERS)
    for token in tokens:
        if token in _SUMMARY_STOPWORDS:
            continue
        if token in numeric_words:
            continue
        filtered.append(token)

    if not filtered:
        return ""
    return " ".join(filtered[:5])


def _find_summary_relation_cue(sentence: str) -> tuple[int, int, str] | None:
    lowered = sentence.lower()
    best_match: tuple[int, int, str] | None = None
    for cue in _SUMMARY_RELATION_CUES:
        match = re.search(rf"\b{re.escape(cue)}\b", lowered)
        if match is None:
            continue
        candidate = (match.start(), match.end(), cue)
        if best_match is None or candidate[0] < best_match[0] or (
            candidate[0] == best_match[0] and (candidate[1] - candidate[0]) > (best_match[1] - best_match[0])
        ):
            best_match = candidate
    if best_match is not None:
        return best_match

    token_matches = list(re.finditer(r"[a-z]+(?:-[a-z]+)?", lowered))
    for index, token_match in enumerate(token_matches):
        token = token_match.group(0)
        if not _looks_like_summary_verb(token):
            continue
        subject_candidate = lowered[:token_match.start()].strip()
        if not subject_candidate:
            continue

        predicate = token
        end = token_match.end()
        if index + 1 < len(token_matches):
            next_token = token_matches[index + 1].group(0)
            if next_token in _SUMMARY_PREPOSITIONS:
                predicate = f"{token} {next_token}"
                end = token_matches[index + 1].end()

        return token_match.start(), end, predicate
    return None


def _looks_like_summary_verb(token: str) -> bool:
    lowered = (token or "").lower()
    if not lowered:
        return False
    if lowered in _SUMMARY_AUXILIARY_VERBS:
        return False
    if lowered in _SUMMARY_VERB_HINTS:
        return True
    if lowered.endswith("ed") and len(lowered) >= 4:
        return True
    if lowered.endswith("ing") and len(lowered) >= 5:
        return True
    if lowered.endswith("es") and len(lowered) >= 4 and lowered not in _SUMMARY_STOPWORDS:
        return True
    if lowered.endswith("s") and len(lowered) >= 4 and lowered not in _SUMMARY_STOPWORDS and not lowered.endswith("ss"):
        return True
    return False


def _extract_period_relation(clause: str) -> tuple[str, ProblemGraphEdgeType] | None:
    every_match = re.search(r"\bevery\s+([a-z0-9\s-]+?)\s+years?\b", clause, flags=re.IGNORECASE)
    if every_match is not None:
        normalized = _normalize_time_phrase(f"{every_match.group(1)} years")
        if normalized:
            return normalized, ProblemGraphEdgeType.OCCURS_EVERY

    over_match = re.search(r"\bover\s+([a-z0-9\s-]+?)\s+years?\b", clause, flags=re.IGNORECASE)
    if over_match is not None:
        normalized = _normalize_time_phrase(f"{over_match.group(1)} years")
        if normalized:
            return normalized, ProblemGraphEdgeType.DURING_PERIOD

    in_match = re.search(r"\bin\s+([a-z0-9\s-]+?)\s+years?\b", clause, flags=re.IGNORECASE)
    if in_match is not None:
        normalized = _normalize_time_phrase(f"{in_match.group(1)} years")
        if normalized:
            return normalized, ProblemGraphEdgeType.DURING_PERIOD

    during_match = re.search(r"\bduring\s+([a-z0-9\s-]+?)\s+years?\b", clause, flags=re.IGNORECASE)
    if during_match is not None:
        normalized = _normalize_time_phrase(f"{during_match.group(1)} years")
        if normalized:
            return normalized, ProblemGraphEdgeType.DURING_PERIOD
    return None


def _summary_edge_type_for_verb(verb: str) -> ProblemGraphEdgeType:
    normalized = (verb or "").lower()
    if (normalized.startswith("rise") or normalized.startswith("rose")) and "from" in normalized:
        return ProblemGraphEdgeType.RISE_FROM
    if normalized in {"rise", "rises", "rose"}:
        return ProblemGraphEdgeType.HAS_ATTRIBUTE
    if normalized.startswith("consume") or normalized in {"eat", "eats"}:
        return ProblemGraphEdgeType.CONSUME
    if normalized.startswith("build") or normalized == "built":
        return ProblemGraphEdgeType.BUILT_OVER_TIME
    if any(token in normalized for token in ("twice", "half", "more than", "less than", "exceed", "times")):
        return ProblemGraphEdgeType.MULTIPLIER_OF
    if normalized in {"ate"}:
        return ProblemGraphEdgeType.ATE
    if normalized in {
        "cost",
        "costs",
        "receive",
        "received",
        "buy",
        "bought",
        "has",
        "have",
        "had",
        "contain",
        "contains",
        "include",
        "includes",
    }:
        return ProblemGraphEdgeType.HAS_ATTRIBUTE
    return ProblemGraphEdgeType.VERB_RELATION


def _quantity_sentence_index(
    quantity: QuantityAnnotation,
    sentences: list[tuple[str, int, int]],
) -> int | None:
    if quantity.sentence_index is not None and 0 <= quantity.sentence_index < len(sentences):
        return quantity.sentence_index
    if quantity.char_start is None:
        return None
    for sentence_index, (_, char_start, char_end) in enumerate(sentences):
        if char_start <= quantity.char_start < char_end:
            return sentence_index
    return None


def _resolve_summary_phrase_node(
    *,
    phrase: str,
    fallback_node_id: str | None,
    target_ref: str | None,
    problem: FormalizedProblem,
    nodes: list[ProblemGraphNode],
    seen_node_ids: set[str],
    concept_by_norm: dict[str, str],
) -> str | None:
    raw = (phrase or "").strip()
    if not raw:
        return None
    lowered = raw.lower()

    if target_ref is not None and any(cue in lowered for cue in ("how many", "how much", "what", "which")):
        return target_ref

    if lowered in _SUMMARY_PRONOUNS and fallback_node_id is not None:
        return fallback_node_id

    for entity in problem.entities:
        entity_lower = entity.surface_text.lower()
        if entity_lower in lowered or lowered in entity_lower:
            return entity.entity_id

    normalized = _normalize_summary_phrase(raw)
    if not normalized:
        return None
    if normalized in _SUMMARY_PRONOUNS and fallback_node_id is not None:
        return fallback_node_id

    existing = concept_by_norm.get(normalized)
    if existing is not None:
        return existing

    slug = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    base_node_id = f"concept_{slug or 'node'}"
    node_id = base_node_id
    suffix = 2
    while node_id in seen_node_ids:
        node_id = f"{base_node_id}_{suffix}"
        suffix += 1

    _add_node(
        nodes,
        seen_node_ids,
        ProblemGraphNode(
            node_id=node_id,
            node_type=ProblemGraphNodeType.ENTITY,
            label=normalized,
            confidence=0.62,
            provenance=ProvenanceSource.HEURISTIC,
            notes=["summary_concept"],
        ),
    )
    concept_by_norm[normalized] = node_id
    return node_id


def _add_summary_semantic_edge(
    *,
    edges: list[ProblemGraphEdge],
    seen_edge_ids: set[str],
    source_node_id: str,
    target_node_id: str,
    edge_seed: str,
    edge_type: ProblemGraphEdgeType,
    confidence: float,
    provenance: ProvenanceSource,
    notes: list[str],
    position: int | None = None,
) -> bool:
    if source_node_id == target_node_id:
        return False
    for existing_edge in edges:
        if (
            existing_edge.source_node_id == source_node_id
            and existing_edge.target_node_id == target_node_id
            and existing_edge.edge_type == edge_type
            and existing_edge.position == position
        ):
            return False

    edge_id = edge_seed
    suffix = 2
    while edge_id in seen_edge_ids:
        edge_id = f"{edge_seed}_{suffix}"
        suffix += 1

    _add_edge(
        edges,
        seen_edge_ids,
        ProblemGraphEdge(
            edge_id=edge_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            position=position,
            confidence=confidence,
            provenance=provenance,
            notes=notes,
        ),
    )
    return True


def _resolve_summary_triple_node(
    *,
    node_id_hint: str | None,
    text_hint: str | None,
    target_ref: str | None,
    problem: FormalizedProblem,
    nodes: list[ProblemGraphNode],
    seen_node_ids: set[str],
    concept_by_norm: dict[str, str],
) -> str | None:
    if node_id_hint is not None and node_id_hint in seen_node_ids:
        return node_id_hint

    if node_id_hint is not None and node_id_hint.startswith("concept_"):
        normalized = _normalize_summary_phrase(text_hint or node_id_hint[len("concept_"):].replace("_", " "))
        if normalized:
            existing = concept_by_norm.get(normalized)
            if existing is not None:
                return existing
            node_id = node_id_hint
            if node_id in seen_node_ids:
                return node_id
            _add_node(
                nodes,
                seen_node_ids,
                ProblemGraphNode(
                    node_id=node_id,
                    node_type=ProblemGraphNodeType.ENTITY,
                    label=normalized,
                    confidence=0.62,
                    provenance=ProvenanceSource.HEURISTIC,
                    notes=["summary_concept"],
                ),
            )
            concept_by_norm[normalized] = node_id
            return node_id

    if target_ref is not None and node_id_hint == target_ref:
        return target_ref

    phrase = text_hint or node_id_hint or ""
    return _resolve_summary_phrase_node(
        phrase=phrase,
        fallback_node_id=None,
        target_ref=target_ref,
        problem=problem,
        nodes=nodes,
        seen_node_ids=seen_node_ids,
        concept_by_norm=concept_by_norm,
    )


def _add_node(
    nodes: list[ProblemGraphNode],
    seen_node_ids: set[str],
    node: ProblemGraphNode,
) -> None:
    if node.node_id in seen_node_ids:
        return
    nodes.append(node)
    seen_node_ids.add(node.node_id)


def _add_edge(
    edges: list[ProblemGraphEdge],
    seen_edge_ids: set[str],
    edge: ProblemGraphEdge,
) -> None:
    if edge.edge_id in seen_edge_ids:
        return
    edges.append(edge)
    seen_edge_ids.add(edge.edge_id)


def _build_base_graph(problem: FormalizedProblem) -> tuple[list[ProblemGraphNode], list[ProblemGraphEdge], set[str], set[str]]:
    nodes: list[ProblemGraphNode] = []
    edges: list[ProblemGraphEdge] = []
    seen_node_ids: set[str] = set()
    seen_edge_ids: set[str] = set()

    for entity in problem.entities:
        _add_node(
            nodes,
            seen_node_ids,
            ProblemGraphNode(
                node_id=entity.entity_id,
                node_type=ProblemGraphNodeType.ENTITY,
                label=entity.surface_text,
                entity_id=entity.entity_id,
                confidence=0.95,
                provenance=ProvenanceSource.PROBLEM_TEXT,
            ),
        )

    for quantity in problem.quantities:
        _add_node(
            nodes,
            seen_node_ids,
            ProblemGraphNode(
                node_id=quantity.quantity_id,
                node_type=ProblemGraphNodeType.QUANTITY,
                label=quantity.surface_text,
                value=quantity.value,
                unit=quantity.unit,
                quantity_id=quantity.quantity_id,
                entity_id=quantity.entity_id,
                semantic_role=quantity.semantic_role,
                confidence=0.95,
                provenance=quantity.provenance,
                notes=list(quantity.notes),
            ),
        )
        if quantity.entity_id is not None:
            _add_edge(
                edges,
                seen_edge_ids,
                ProblemGraphEdge(
                    edge_id=f"edge_{quantity.entity_id}_owns_{quantity.quantity_id}",
                    source_node_id=quantity.entity_id,
                    target_node_id=quantity.quantity_id,
                    edge_type=ProblemGraphEdgeType.ENTITY_HAS_QUANTITY,
                    confidence=0.9,
                    provenance=ProvenanceSource.PROBLEM_TEXT,
                ),
            )

    if problem.target is not None:
        _add_node(
            nodes,
            seen_node_ids,
            ProblemGraphNode(
                node_id=problem.target.target_variable,
                node_type=ProblemGraphNodeType.TARGET,
                label=problem.target.surface_text,
                unit=problem.target.unit,
                target_variable=problem.target.target_variable,
                entity_id=problem.target.entity_id,
                confidence=problem.target.confidence,
                provenance=problem.target.provenance,
            ),
        )
        if problem.target.entity_id is not None:
            _add_edge(
                edges,
                seen_edge_ids,
                ProblemGraphEdge(
                    edge_id=f"edge_{problem.target.target_variable}_describes_{problem.target.entity_id}",
                    source_node_id=problem.target.target_variable,
                    target_node_id=problem.target.entity_id,
                    edge_type=ProblemGraphEdgeType.DESCRIBES_ENTITY,
                    confidence=0.82,
                    provenance=problem.target.provenance,
                ),
            )

    return nodes, edges, seen_node_ids, seen_edge_ids


def _ensure_value_node(
    nodes: list[ProblemGraphNode],
    seen_node_ids: set[str],
    node_id: str,
    node_type: ProblemGraphNodeType,
    label: str,
    unit: str | None,
    confidence: float,
    provenance: ProvenanceSource,
) -> None:
    _add_node(
        nodes,
        seen_node_ids,
        ProblemGraphNode(
            node_id=node_id,
            node_type=node_type,
            label=label,
            unit=unit,
            target_variable=node_id if node_type == ProblemGraphNodeType.TARGET else None,
            confidence=confidence,
            provenance=provenance,
        ),
    )


def _add_operation(
    nodes: list[ProblemGraphNode],
    edges: list[ProblemGraphEdge],
    seen_node_ids: set[str],
    seen_edge_ids: set[str],
    *,
    step_id: str,
    step_index: int,
    operation: TraceOperation,
    expression: str,
    input_refs: list[str],
    output_ref: str,
    explanation: str,
    output_type: ProblemGraphNodeType,
    output_unit: str | None,
    confidence: float,
    provenance: ProvenanceSource,
) -> None:
    op_node_id = f"op_{step_id}"
    _add_node(
        nodes,
        seen_node_ids,
        ProblemGraphNode(
            node_id=op_node_id,
            node_type=ProblemGraphNodeType.OPERATION,
            label=explanation,
            operation=operation,
            expression=expression,
            step_id=step_id,
            step_index=step_index,
            confidence=confidence,
            provenance=provenance,
        ),
    )
    _ensure_value_node(
        nodes,
        seen_node_ids,
        node_id=output_ref,
        node_type=output_type,
        label=output_ref,
        unit=output_unit,
        confidence=confidence,
        provenance=provenance,
    )

    for position, input_ref in enumerate(input_refs):
        _add_edge(
            edges,
            seen_edge_ids,
            ProblemGraphEdge(
                edge_id=f"edge_{input_ref}_to_{op_node_id}_{position}",
                source_node_id=input_ref,
                target_node_id=op_node_id,
                edge_type=ProblemGraphEdgeType.INPUT_TO_OPERATION,
                position=position,
                confidence=confidence,
                provenance=provenance,
            ),
        )

    _add_edge(
        edges,
        seen_edge_ids,
        ProblemGraphEdge(
            edge_id=f"edge_{op_node_id}_to_{output_ref}",
            source_node_id=op_node_id,
            target_node_id=output_ref,
            edge_type=ProblemGraphEdgeType.OUTPUT_FROM_OPERATION,
            confidence=confidence,
            provenance=provenance,
        ),
    )


def _add_rate_subgraph(
    problem: FormalizedProblem,
    nodes: list[ProblemGraphNode],
    edges: list[ProblemGraphEdge],
    seen_node_ids: set[str],
    seen_edge_ids: set[str],
    notes: list[str],
) -> None:
    unit_rate = _select_rate_unit_price_quantity(problem)
    percent = _first_quantity_with_role(problem.quantities, QuantitySemanticRole.PERCENT)
    threshold = _first_quantity_with_role(problem.quantities, QuantitySemanticRole.THRESHOLD)
    base = _select_rate_unit_base_quantity(problem)
    target_ref = _target_ref(problem)
    target_unit = problem.target.unit if problem.target is not None else None

    if not all((unit_rate, percent, threshold, base)):
        notes.append("graph_rate_relation_missing_components")
        return

    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_1_excess_quantity",
        step_index=1,
        operation=TraceOperation.SUBTRACT,
        expression=f"max({base.quantity_id} - {threshold.quantity_id}, 0)",
        input_refs=[base.quantity_id, threshold.quantity_id],
        output_ref="excess_quantity",
        explanation="Find how many units are beyond the discount threshold.",
        output_type=ProblemGraphNodeType.INTERMEDIATE,
        output_unit=base.unit,
        confidence=0.94,
        provenance=ProvenanceSource.HEURISTIC,
    )
    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_2_discount_per_unit",
        step_index=2,
        operation=TraceOperation.PERCENT_OF,
        expression=f"({percent.quantity_id} / 100) * {unit_rate.quantity_id}",
        input_refs=[percent.quantity_id, unit_rate.quantity_id],
        output_ref="discount_per_unit",
        explanation="Compute the discount value applied to each discounted unit.",
        output_type=ProblemGraphNodeType.INTERMEDIATE,
        output_unit=target_unit,
        confidence=0.93,
        provenance=ProvenanceSource.HEURISTIC,
    )
    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_3_total_discount",
        step_index=3,
        operation=TraceOperation.MULTIPLY,
        expression="excess_quantity * discount_per_unit",
        input_refs=["excess_quantity", "discount_per_unit"],
        output_ref="total_discount",
        explanation="Multiply discounted units by the discount per unit.",
        output_type=ProblemGraphNodeType.INTERMEDIATE,
        output_unit=target_unit,
        confidence=0.93,
        provenance=ProvenanceSource.HEURISTIC,
    )
    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_4_gross_total",
        step_index=4,
        operation=TraceOperation.MULTIPLY,
        expression=f"{base.quantity_id} * {unit_rate.quantity_id}",
        input_refs=[base.quantity_id, unit_rate.quantity_id],
        output_ref="gross_total",
        explanation="Compute the total before any discount.",
        output_type=ProblemGraphNodeType.INTERMEDIATE,
        output_unit=target_unit,
        confidence=0.94,
        provenance=ProvenanceSource.HEURISTIC,
    )
    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_5_final_total",
        step_index=5,
        operation=TraceOperation.SUBTRACT,
        expression="gross_total - total_discount",
        input_refs=["gross_total", "total_discount"],
        output_ref=target_ref,
        explanation="Subtract the total discount from the gross total.",
        output_type=ProblemGraphNodeType.TARGET,
        output_unit=target_unit,
        confidence=0.95,
        provenance=ProvenanceSource.HEURISTIC,
    )
    notes.append("graph_built_from_rate_relation")


def _add_single_step_subgraph(
    problem: FormalizedProblem,
    nodes: list[ProblemGraphNode],
    edges: list[ProblemGraphEdge],
    seen_node_ids: set[str],
    seen_edge_ids: set[str],
    *,
    relation_type: RelationType,
    notes: list[str],
) -> None:
    target_ref = _target_ref(problem)
    target_unit = problem.target.unit if problem.target is not None else None
    quantity_refs = [quantity.quantity_id for quantity in problem.quantities]
    if not quantity_refs:
        notes.append("graph_missing_quantity_nodes")
        return

    if relation_type == RelationType.ADDITIVE_COMPOSITION:
        operation = TraceOperation.ADD
        expression = " + ".join(quantity_refs)
        explanation = "Add the relevant quantities to obtain the target."
        note = "graph_built_from_additive_relation"
        step_id = "step_1_add_all"
    elif relation_type == RelationType.SUBTRACTIVE_COMPARISON:
        operation = TraceOperation.SUBTRACT
        expression = quantity_refs[0] if len(quantity_refs) == 1 else f"{quantity_refs[0]} - " + " - ".join(quantity_refs[1:])
        explanation = "Subtract the removed or compared quantities from the base quantity."
        note = "graph_built_from_subtractive_relation"
        step_id = "step_1_subtract"
    elif relation_type == RelationType.MULTIPLICATIVE_SCALING:
        operation = TraceOperation.MULTIPLY
        expression = " * ".join(quantity_refs[:2]) if len(quantity_refs) >= 2 else quantity_refs[0]
        explanation = "Multiply the relevant factors to obtain the target."
        note = "graph_built_from_multiplicative_relation"
        step_id = "step_1_multiply"
    elif relation_type == RelationType.PARTITION_GROUPING:
        operation = TraceOperation.DIVIDE
        expression = f"{quantity_refs[0]} / {quantity_refs[1]}" if len(quantity_refs) >= 2 else quantity_refs[0]
        explanation = "Divide the total by the group count or group size."
        note = "graph_built_from_partition_relation"
        step_id = "step_1_divide"
    else:
        notes.append("graph_unknown_relation_type")
        return

    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id=step_id,
        step_index=1,
        operation=operation,
        expression=expression,
        input_refs=quantity_refs if relation_type != RelationType.MULTIPLICATIVE_SCALING else quantity_refs[:2],
        output_ref=target_ref,
        explanation=explanation,
        output_type=ProblemGraphNodeType.TARGET,
        output_unit=target_unit,
        confidence=0.9,
        provenance=ProvenanceSource.HEURISTIC,
    )
    notes.append(note)


def _add_expression_fallback_subgraph(
    problem: FormalizedProblem,
    nodes: list[ProblemGraphNode],
    edges: list[ProblemGraphEdge],
    seen_node_ids: set[str],
    seen_edge_ids: set[str],
    notes: list[str],
) -> None:
    relation = problem.relation_candidates[0] if problem.relation_candidates else None
    if relation is None or relation.expression is None:
        notes.append("graph_missing_relation_expression")
        return

    lowered = relation.expression.lower()
    if "unresolved_relation(" in lowered or "rate_or_percent_relation(" in lowered:
        notes.append("graph_placeholder_relation_expression")
        return

    rhs = relation.expression.split("=", 1)[-1].strip()
    target_ref = _target_ref(problem)
    target_unit = problem.target.unit if problem.target is not None else None
    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_1_relation_expression",
        step_index=1,
        operation=TraceOperation.DERIVE,
        expression=rhs,
        input_refs=list(relation.source_quantity_ids),
        output_ref=target_ref,
        explanation="Use the relation expression provided by the formalizer.",
        output_type=ProblemGraphNodeType.TARGET,
        output_unit=target_unit,
        confidence=max(relation.confidence - 0.1, 0.35),
        provenance=relation.provenance,
    )
    notes.append("graph_built_from_relation_expression")


def _add_progression_subgraph(
    problem: FormalizedProblem,
    nodes: list[ProblemGraphNode],
    edges: list[ProblemGraphEdge],
    seen_node_ids: set[str],
    seen_edge_ids: set[str],
    notes: list[str],
) -> bool:
    ratio = _infer_progression_ratio(problem.problem_text)
    term_count = _infer_term_count(problem)
    total_quantity = _select_progression_total_quantity(problem)
    target_ref = _target_ref(problem)
    target_unit = problem.target.unit if problem.target is not None else None

    if ratio is None or term_count is None or total_quantity is None:
        return False
    if term_count < 2 or ratio <= 0:
        return False
    if not _target_requests_first_term(problem):
        return False

    multipliers: list[float] = []
    current_multiplier = 1.0
    for _ in range(term_count):
        multipliers.append(current_multiplier)
        current_multiplier *= ratio

    multiplier_terms = " + ".join(f"{value:g}" for value in multipliers)
    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_1_progression_multiplier",
        step_index=1,
        operation=TraceOperation.ADD,
        expression=multiplier_terms,
        input_refs=[total_quantity.quantity_id],
        output_ref="progression_multiplier_sum",
        explanation="Build the geometric-series multiplier sum from progression cues.",
        output_type=ProblemGraphNodeType.INTERMEDIATE,
        output_unit=None,
        confidence=0.86,
        provenance=ProvenanceSource.HEURISTIC,
    )
    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_2_first_term",
        step_index=2,
        operation=TraceOperation.DIVIDE,
        expression=f"{total_quantity.quantity_id} / progression_multiplier_sum",
        input_refs=[total_quantity.quantity_id, "progression_multiplier_sum"],
        output_ref="first_term_value",
        explanation="Compute the first term from total and geometric multiplier sum.",
        output_type=ProblemGraphNodeType.INTERMEDIATE,
        output_unit=target_unit,
        confidence=0.88,
        provenance=ProvenanceSource.HEURISTIC,
    )
    _add_operation(
        nodes,
        edges,
        seen_node_ids,
        seen_edge_ids,
        step_id="step_3_target_first_term",
        step_index=3,
        operation=TraceOperation.DERIVE,
        expression="first_term_value",
        input_refs=["first_term_value"],
        output_ref=target_ref,
        explanation="Map the first progression term to the requested target.",
        output_type=ProblemGraphNodeType.TARGET,
        output_unit=target_unit,
        confidence=0.9,
        provenance=ProvenanceSource.HEURISTIC,
    )
    notes.append(f"graph_built_from_progression_relation:ratio={ratio:g},terms={term_count}")
    return True


def build_problem_summary_graph(problem: FormalizedProblem) -> ProblemGraph:
    """Build a non-executable summary graph (entities, quantities, target, semantic relations)."""
    nodes, edges, seen_node_ids, seen_edge_ids = _build_base_graph(problem)
    notes = ["summary_graph_without_operations"]

    relation = problem.relation_candidates[0] if problem.relation_candidates else None
    target_ref = _target_ref(problem) if problem.target is not None else None
    relation_edge_count = 0
    sentence_semantic_edges = 0
    concept_by_norm: dict[str, str] = {}
    if problem.semantic_triples:
        triples: list[SemanticTriple] = sorted(
            problem.semantic_triples,
            key=lambda triple: (
                triple.sentence_index if triple.sentence_index is not None else -1,
                triple.clause_index if triple.clause_index is not None else -1,
                triple.triple_id,
            ),
        )
        for triple in triples:
            subject_node_id = _resolve_summary_triple_node(
                node_id_hint=triple.subject_node_id,
                text_hint=triple.subject_text,
                target_ref=target_ref,
                problem=problem,
                nodes=nodes,
                seen_node_ids=seen_node_ids,
                concept_by_norm=concept_by_norm,
            )
            object_node_id = _resolve_summary_triple_node(
                node_id_hint=triple.object_node_id,
                text_hint=triple.object_text,
                target_ref=target_ref,
                problem=problem,
                nodes=nodes,
                seen_node_ids=seen_node_ids,
                concept_by_norm=concept_by_norm,
            )
            if subject_node_id is None or object_node_id is None:
                continue
            predicate = triple.predicate_text.strip().lower()
            verb_slug = re.sub(r"[^a-z0-9]+", "_", predicate).strip("_") or "relation"
            relation_edge_type = (
                _summary_edge_type_for_verb(predicate)
                if triple.edge_type == ProblemGraphEdgeType.VERB_RELATION
                else triple.edge_type
            )
            edge_seed = (
                f"edge_{subject_node_id}_{verb_slug}_to_{object_node_id}"
                f"_s{triple.sentence_index if triple.sentence_index is not None else 0}"
                f"_{triple.clause_index if triple.clause_index is not None else 0}_{triple.triple_id}"
            )
            added = _add_summary_semantic_edge(
                edges=edges,
                seen_edge_ids=seen_edge_ids,
                source_node_id=subject_node_id,
                target_node_id=object_node_id,
                edge_seed=edge_seed,
                edge_type=relation_edge_type,
                confidence=max(min(triple.confidence, 0.95), 0.2),
                provenance=triple.provenance,
                notes=[
                    f"triple_id={triple.triple_id}",
                    f"predicate={triple.predicate_text}",
                    f"sentence_index={triple.sentence_index}",
                    f"clause_index={triple.clause_index}",
                ]
                + list(triple.notes),
            )
            if added:
                sentence_semantic_edges += 1
        notes.append(f"summary_semantic_triples_used={len(triples)}")
    else:
        previous_subject_node_id: str | None = None
        sentences = _split_sentences_with_offsets(problem.problem_text)
        quantities_by_sentence: dict[int, list[QuantityAnnotation]] = {}
        for quantity in problem.quantities:
            sentence_index = _quantity_sentence_index(quantity, sentences)
            if sentence_index is None:
                continue
            quantities_by_sentence.setdefault(sentence_index, []).append(quantity)

        for sentence_index, (sentence, _, _) in enumerate(sentences):
            clauses = _split_summary_clauses(sentence)
            for clause_index, clause in enumerate(clauses):
                cue = _find_summary_relation_cue(clause)
                subject_node_id: str | None = None
                object_node_id: str | None = None

                if cue is None:
                    continue

                cue_start, cue_end, verb = cue
                subject_fragment = _clean_summary_subject(clause[:cue_start])
                object_fragment = _clean_summary_object(clause[cue_end:])
                relation_edge_type = _summary_edge_type_for_verb(verb)
                verb_slug = re.sub(r"[^a-z0-9]+", "_", verb.lower()).strip("_") or "relation"

                # Comparative phrases usually have an explicit reference object after "as ...".
                if verb in {"twice as many", "half as many"}:
                    comparative_match = re.search(
                        rf"{re.escape(verb)}\s+(?P<object>[a-z0-9\s-]+?)\s+as\s+(?P<reference>.+)$",
                        clause,
                        flags=re.IGNORECASE,
                    )
                    if comparative_match is not None:
                        object_fragment = _clean_summary_object(comparative_match.group("reference"))

                if verb == "built" and "over time" in clause.lower():
                    object_fragment = "time"

                subject_node_id = _resolve_summary_phrase_node(
                    phrase=subject_fragment,
                    fallback_node_id=previous_subject_node_id,
                    target_ref=target_ref,
                    problem=problem,
                    nodes=nodes,
                    seen_node_ids=seen_node_ids,
                    concept_by_norm=concept_by_norm,
                )
                object_node_id = _resolve_summary_phrase_node(
                    phrase=object_fragment,
                    fallback_node_id=None,
                    target_ref=target_ref,
                    problem=problem,
                    nodes=nodes,
                    seen_node_ids=seen_node_ids,
                    concept_by_norm=concept_by_norm,
                )

                if subject_node_id is not None and object_node_id is not None:
                    added = _add_summary_semantic_edge(
                        edges=edges,
                        seen_edge_ids=seen_edge_ids,
                        source_node_id=subject_node_id,
                        target_node_id=object_node_id,
                        edge_seed=f"edge_{subject_node_id}_{verb_slug}_to_{object_node_id}_s{sentence_index}_{clause_index}",
                        edge_type=relation_edge_type,
                        confidence=0.7,
                        provenance=ProvenanceSource.HEURISTIC,
                        notes=[f"verb={verb}", f"sentence_index={sentence_index}", f"clause_index={clause_index}"],
                    )
                    if added:
                        sentence_semantic_edges += 1

                period_relation = _extract_period_relation(clause) or _extract_period_relation(sentence)
                if period_relation is not None and subject_node_id is not None:
                    period_phrase, period_edge_type = period_relation
                    period_node_id = _resolve_summary_phrase_node(
                        phrase=period_phrase,
                        fallback_node_id=None,
                        target_ref=target_ref,
                        problem=problem,
                        nodes=nodes,
                        seen_node_ids=seen_node_ids,
                        concept_by_norm=concept_by_norm,
                    )
                    if period_node_id is not None:
                        added = _add_summary_semantic_edge(
                            edges=edges,
                            seen_edge_ids=seen_edge_ids,
                            source_node_id=subject_node_id,
                            target_node_id=period_node_id,
                            edge_seed=(
                                f"edge_{subject_node_id}_{period_edge_type.value}_{period_node_id}"
                                f"_s{sentence_index}_{clause_index}"
                            ),
                            edge_type=period_edge_type,
                            confidence=0.69,
                            provenance=ProvenanceSource.HEURISTIC,
                            notes=["period_relation", f"sentence_index={sentence_index}", f"clause_index={clause_index}"],
                        )
                        if added:
                            sentence_semantic_edges += 1

                normalized_subject = _normalize_summary_phrase(subject_fragment)
                if subject_node_id is not None and normalized_subject and normalized_subject not in _SUMMARY_PRONOUNS:
                    previous_subject_node_id = subject_node_id

                for quantity in quantities_by_sentence.get(sentence_index, []):
                    if subject_node_id is not None:
                        added = _add_summary_semantic_edge(
                            edges=edges,
                            seen_edge_ids=seen_edge_ids,
                            source_node_id=subject_node_id,
                            target_node_id=quantity.quantity_id,
                            edge_seed=(
                                f"edge_{subject_node_id}_has_quantity_{quantity.quantity_id}_s{sentence_index}_{clause_index}"
                            ),
                            edge_type=ProblemGraphEdgeType.HAS_ATTRIBUTE,
                            confidence=0.66,
                            provenance=ProvenanceSource.HEURISTIC,
                            notes=["link=subject_quantity", f"sentence_index={sentence_index}", f"clause_index={clause_index}"],
                        )
                        if added:
                            sentence_semantic_edges += 1

                    if object_node_id is not None:
                        added = _add_summary_semantic_edge(
                            edges=edges,
                            seen_edge_ids=seen_edge_ids,
                            source_node_id=quantity.quantity_id,
                            target_node_id=object_node_id,
                            edge_seed=(
                                f"edge_{quantity.quantity_id}_supports_{object_node_id}_s{sentence_index}_{clause_index}"
                            ),
                            edge_type=ProblemGraphEdgeType.HAS_ATTRIBUTE,
                            confidence=0.66,
                            provenance=ProvenanceSource.HEURISTIC,
                            notes=["link=quantity_object", f"sentence_index={sentence_index}", f"clause_index={clause_index}"],
                        )
                        if added:
                            sentence_semantic_edges += 1

    if relation is not None and target_ref is not None and target_ref in seen_node_ids:
        for position, source_quantity_id in enumerate(relation.source_quantity_ids):
            if source_quantity_id not in seen_node_ids:
                continue
            added = _add_summary_semantic_edge(
                edges=edges,
                seen_edge_ids=seen_edge_ids,
                source_node_id=source_quantity_id,
                target_node_id=target_ref,
                edge_seed=f"edge_{source_quantity_id}_semantic_to_{target_ref}_{position}",
                edge_type=ProblemGraphEdgeType.SEMANTIC_RELATION,
                position=position,
                confidence=max(min(relation.confidence, 0.95), 0.2),
                provenance=relation.provenance,
                notes=[
                    f"relation_id={relation.relation_id}",
                    f"relation_type={relation.relation_type.value}",
                    f"operation_hint={relation.operation_hint.value}",
                ]
                + ([f"expression={relation.expression}"] if relation.expression else []),
            )
            if added:
                relation_edge_count += 1

    if relation is not None:
        notes.append(f"summary_relation_type={relation.relation_type.value}")
    notes.append(f"summary_relation_edges={relation_edge_count}")
    notes.append(f"summary_sentence_semantic_edges={sentence_semantic_edges}")
    notes.append(f"summary_concept_nodes={len(concept_by_norm)}")

    return ProblemGraph(
        nodes=nodes,
        edges=edges,
        target_node_id=target_ref,
        confidence=max(min(problem.confidence, 0.98), 0.4),
        provenance=problem.provenance if problem.provenance != ProvenanceSource.UNKNOWN else ProvenanceSource.HEURISTIC,
        notes=notes,
    )


def build_problem_graph(problem: FormalizedProblem) -> ProblemGraph:
    """Build a typed problem graph from the current structured formalization."""
    nodes, edges, seen_node_ids, seen_edge_ids = _build_base_graph(problem)
    notes: list[str] = []

    relation = problem.relation_candidates[0] if problem.relation_candidates else None
    relation_type = relation.relation_type if relation is not None else RelationType.UNKNOWN

    if _add_progression_subgraph(problem, nodes, edges, seen_node_ids, seen_edge_ids, notes):
        pass
    elif relation_type == RelationType.RATE_UNIT_RELATION:
        _add_rate_subgraph(problem, nodes, edges, seen_node_ids, seen_edge_ids, notes)
    elif relation_type in (
        RelationType.ADDITIVE_COMPOSITION,
        RelationType.SUBTRACTIVE_COMPARISON,
        RelationType.MULTIPLICATIVE_SCALING,
        RelationType.PARTITION_GROUPING,
    ):
        _add_single_step_subgraph(
            problem,
            nodes,
            edges,
            seen_node_ids,
            seen_edge_ids,
            relation_type=relation_type,
            notes=notes,
        )
    else:
        _add_expression_fallback_subgraph(problem, nodes, edges, seen_node_ids, seen_edge_ids, notes)

    confidence = 0.35 if not any(node.node_type == ProblemGraphNodeType.OPERATION for node in nodes) else 0.9
    return ProblemGraph(
        nodes=nodes,
        edges=edges,
        target_node_id=_target_ref(problem) if problem.target is not None else None,
        confidence=max(min(problem.confidence, 0.98), confidence),
        provenance=problem.provenance if problem.provenance != ProvenanceSource.UNKNOWN else ProvenanceSource.HEURISTIC,
        notes=notes,
    )
