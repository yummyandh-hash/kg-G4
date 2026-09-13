import json
import re
from pathlib import Path
from typing import Any, Iterable

from orchestration.models import Evidence, RetrievalContext


class AnalysisRouter:
    """Adapter from raw query text to the service Router contract."""

    def __init__(self):
        from orchestration.adaptive_router import AdaptiveRouter
        from orchestration.complexity_scorer import ComplexityScorer
        from orchestration.query_analyzer import QueryAnalyzer

        self.query_analyzer = QueryAnalyzer()
        self.complexity_scorer = ComplexityScorer()
        self.router = AdaptiveRouter()

    def route(self, query: str):
        query_type = self.query_analyzer.analyze(query)
        complexity_score = self.complexity_scorer.score(query)
        return self.router.route(query_type, complexity_score)


class RouteDispatchRetriever:
    """Dispatch retrieval to the retriever selected by the router."""

    def __init__(
        self,
        retrievers: dict[str, Any],
        *,
        vector_candidate_k: int = 50,
        enable_query_rewrite: bool = True,
        enable_rerank: bool = True,
        enable_graph_vector_support: bool = True,
        enable_neighbor_expansion: bool = True,
        neighbor_window: int = 2,
    ):
        self.retrievers = retrievers
        self.vector_candidate_k = vector_candidate_k
        self.enable_query_rewrite = enable_query_rewrite
        self.enable_rerank = enable_rerank
        self.enable_graph_vector_support = enable_graph_vector_support
        self.enable_neighbor_expansion = enable_neighbor_expansion
        self.neighbor_window = neighbor_window

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        selected_route = getattr(context, "selected_route", None)

        if selected_route == "hybrid":
            return self._retrieve_hybrid(query, context)

        if selected_route == "vector":
            return self._retrieve_vector_augmented(
                query,
                context,
                limit=context.top_k,
            )

        if (
            selected_route == "graph"
            and self.enable_graph_vector_support
        ):
            return self._retrieve_graph_with_vector_support(query, context)

        retriever = self.retrievers.get(selected_route)
        if retriever is None:
            raise ValueError(
                f"No retriever registered for route: {selected_route}"
            )

        return retriever.retrieve(query, context)

    def _retrieve_hybrid(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        graph_evidences = self._retrieve_route("graph", query, context)
        vector_evidences = self._retrieve_vector_augmented(
            query,
            context,
            support_evidences=graph_evidences,
            limit=context.top_k,
        )

        evidences = graph_evidences + vector_evidences
        if not evidences:
            raise ValueError("No retriever registered for route: hybrid")

        return self._merge_graph_and_vector(
            graph_evidences,
            vector_evidences,
            context.top_k,
        )

    def _retrieve_graph_with_vector_support(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        graph_evidences = self._retrieve_route("graph", query, context)
        vector_evidences = self._retrieve_vector_augmented(
            query,
            context,
            support_evidences=graph_evidences,
            limit=context.top_k,
        )
        return self._merge_graph_and_vector(
            graph_evidences,
            vector_evidences,
            context.top_k,
        )

    def _retrieve_route(
        self,
        route: str,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        retriever = self.retrievers.get(route)
        if retriever is None:
            return []

        route_context = RetrievalContext(
            query_type=context.query_type,
            complexity_score=context.complexity_score,
            top_k=context.top_k,
            selected_route=route,
        )
        return retriever.retrieve(query, route_context)

    def _retrieve_vector_augmented(
        self,
        query: str,
        context: RetrievalContext,
        *,
        support_evidences: list[Evidence] | None = None,
        limit: int,
    ) -> list[Evidence]:
        candidate_retrievers = [
            self.retrievers.get(route)
            for route in ("vector", "lexical")
            if self.retrievers.get(route) is not None
        ]
        if not candidate_retrievers:
            return []

        query_variants = (
            _rewrite_queries(query)
            if self.enable_query_rewrite
            else [query]
        )
        query_variants.extend(
            _support_queries_from_graph(query, support_evidences or [])
        )
        query_variants = _unique_non_empty(query_variants)

        candidate_k = max(context.top_k, self.vector_candidate_k)
        vector_context = RetrievalContext(
            query_type=context.query_type,
            complexity_score=context.complexity_score,
            top_k=candidate_k,
            selected_route="vector",
        )

        candidates: list[Evidence] = []
        for variant in query_variants:
            for retriever in candidate_retrievers:
                candidates.extend(retriever.retrieve(variant, vector_context))

        candidates = _dedupe_evidences(candidates)
        if self.enable_rerank:
            candidates = _rerank_vector_evidences(
                query_variants,
                candidates,
                context,
            )
        else:
            candidates.sort(
                key=lambda evidence: evidence.score or 0.0,
                reverse=True,
            )

        if (
            self.enable_neighbor_expansion
            and _should_expand_neighbors(context, query)
        ):
            candidates = self._expand_neighbor_evidences(
                query_variants,
                candidates,
                context,
            )

        if _is_summary_context(context, query):
            candidates = self._prioritize_summary_evidences(
                query,
                query_variants,
                support_evidences or [],
                candidates,
                context,
            )

        return candidates[:limit]

    def _prioritize_summary_evidences(
        self,
        query: str,
        query_variants: list[str],
        support_evidences: list[Evidence],
        candidates: list[Evidence],
        context: RetrievalContext,
    ) -> list[Evidence]:
        lexical = self.retrievers.get("lexical")
        if not hasattr(lexical, "summary_evidences"):
            return candidates

        summary_evidences = lexical.summary_evidences(
            query,
            support_evidences=support_evidences,
            candidate_evidences=candidates,
            limit=max(context.top_k, 5),
        )
        if not summary_evidences:
            return candidates

        reranked_rest = _rerank_vector_evidences(
            query_variants,
            candidates,
            context,
        )
        return _dedupe_evidences([*summary_evidences, *reranked_rest])

    def _expand_neighbor_evidences(
        self,
        query_variants: list[str],
        candidates: list[Evidence],
        context: RetrievalContext,
    ) -> list[Evidence]:
        lexical = self.retrievers.get("lexical")
        if not hasattr(lexical, "expand_neighbors"):
            return candidates

        neighbors = lexical.expand_neighbors(
            candidates[: max(context.top_k * 2, 8)],
            window=self.neighbor_window,
            limit=max(context.top_k * self.neighbor_window * 2, 12),
        )
        if not neighbors:
            return candidates

        expanded = _dedupe_evidences([*candidates, *neighbors])
        if self.enable_rerank:
            return _rerank_vector_evidences(
                query_variants,
                expanded,
                context,
            )

        expanded.sort(key=lambda evidence: evidence.score or 0.0, reverse=True)
        return expanded

    def _merge_graph_and_vector(
        self,
        graph_evidences: list[Evidence],
        vector_evidences: list[Evidence],
        top_k: int,
    ) -> list[Evidence]:
        graph_with_path = [
            evidence
            for evidence in graph_evidences
            if evidence.relation_path
        ]
        graph_without_path = [
            evidence
            for evidence in graph_evidences
            if not evidence.relation_path
        ]
        graph_without_path.sort(
            key=lambda evidence: evidence.score or 0.0,
            reverse=True,
        )

        # Keep graph paths for E's visualization, then keep top-k text chunks
        # for chunk-level scoring and answer grounding.
        return (
            graph_with_path
            + graph_without_path[:top_k]
            + vector_evidences[:top_k]
        )

def _rewrite_queries(query: str) -> list[str]:
    stripped = query.strip()
    cleaned = _clean_query(stripped)
    variants = [stripped, cleaned]

    anchor = _project_anchor(stripped)
    quoted_terms = _quoted_terms(stripped)
    if anchor and quoted_terms:
        variants.append(" ".join([anchor, *quoted_terms, cleaned]))
    elif quoted_terms:
        variants.append(" ".join([*quoted_terms, cleaned]))
    elif anchor:
        variants.append(f"{anchor} {cleaned}")

    clauses = _query_clauses(cleaned)
    if len(clauses) > 1:
        variants.extend(clauses[:3])
        variants.append(" ".join(clauses[:3]))

    return _unique_non_empty(variants)


def _clean_query(query: str) -> str:
    cleaned = query
    cleaned = re.sub(r"^按(.{1,20}?)项目正文[，,]?", r"\1 ", cleaned)
    cleaned = re.sub(r"^仅根据(.{1,20}?)正文[，,]?", r"\1 ", cleaned)
    cleaned = re.sub(r"^根据(.{1,20}?)正文[，,]?", r"\1 ", cleaned)
    for phrase in (
        "项目正文",
        "正文",
        "仅根据",
        "按",
        "请问",
        "请",
        "分别",
        "概括",
        "列出的",
        "文中记录的",
        "按材料记载回答",
        "不视作当前调查",
    ):
        cleaned = cleaned.replace(phrase, " ")
    cleaned = re.sub(r"[？?。；;：:，,、（）()《》“”\"']", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or query.strip()


def _project_anchor(query: str) -> str:
    patterns = (
        r"按(.{1,20}?)项目正文",
        r"仅根据(.{1,20}?)正文",
        r"根据(.{1,20}?)正文",
    )
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1).strip()
    return ""


def _quoted_terms(query: str) -> list[str]:
    terms = []
    for left, right in (("“", "”"), ("《", "》"), ('"', '"')):
        terms.extend(
            item.strip()
            for item in re.findall(
                re.escape(left) + r"(.{1,30}?)" + re.escape(right),
                query,
            )
            if item.strip()
        )
    return _unique_non_empty(terms)


def _query_clauses(query: str) -> list[str]:
    parts = re.split(r"[？?。；;，,]", query)
    return [
        part.strip()
        for part in parts
        if len(part.strip()) >= 4
    ]


def _support_queries_from_graph(
    query: str,
    evidences: list[Evidence],
) -> list[str]:
    variants = []
    for evidence in evidences:
        for relation in evidence.relation_path:
            source = relation.get("source", "")
            rel = relation.get("relation", "")
            target = relation.get("target", "")
            variants.append(
                " ".join(
                    item
                    for item in (query, source, rel, target)
                    if item
                )
            )
    return variants


def _dedupe_evidences(evidences: list[Evidence]) -> list[Evidence]:
    rows = []
    seen = set()
    for evidence in evidences:
        key = (
            evidence.source_id
            or evidence.evidence_id
            or evidence.content[:80]
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(evidence)
    return rows


def _should_expand_neighbors(
    context: RetrievalContext | None,
    query: str,
) -> bool:
    if context is not None:
        if context.selected_route in {"graph", "hybrid"}:
            return True
        if context.complexity_score >= 0.45:
            return True
        if context.query_type in {"constraint", "comparison"}:
            return True

    return any(cue in query for cue in _NEIGHBOR_EXPANSION_CUES)


def _is_summary_context(
    context: RetrievalContext | None,
    query: str,
) -> bool:
    if any(cue in query for cue in _SUMMARY_CUES):
        return True
    if context is None:
        return False
    return (
        context.query_type == "constraint"
        and context.complexity_score >= 0.45
        and any(cue in query for cue in _NEIGHBOR_EXPANSION_CUES)
    )


def _document_stats(evidences: list[Evidence]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for evidence in evidences:
        parsed = _parse_content_chunk_id(
            evidence.source_id or evidence.evidence_id or ""
        )
        if parsed is None:
            continue
        document_id, chunk_index = parsed
        row = stats.setdefault(
            document_id,
            {
                "count": 0,
                "indices": set(),
            },
        )
        row["count"] += 1
        if chunk_index is not None:
            row["indices"].add(chunk_index)
    return stats


def _doc_aware_bonus(
    evidence: Evidence,
    doc_stats: dict[str, dict[str, Any]],
) -> float:
    parsed = _parse_content_chunk_id(
        evidence.source_id or evidence.evidence_id or ""
    )
    if parsed is None:
        return 0.0

    document_id, chunk_index = parsed
    stats = doc_stats.get(document_id)
    if not stats:
        return 0.0

    count = int(stats["count"])
    indices = stats["indices"]
    bonus = min(0.28, max(0, count - 1) * 0.07)

    if chunk_index is not None and (
        chunk_index - 1 in indices or chunk_index + 1 in indices
    ):
        bonus += 0.12

    if evidence.retrieval_method == "neighbor_expansion":
        bonus += 0.08

    return bonus


def _rerank_vector_evidences(
    query_variants: list[str],
    evidences: list[Evidence],
    context: RetrievalContext | None = None,
) -> list[Evidence]:
    query_text = " ".join(query_variants)
    terms = _lexical_terms(query_text)
    important_terms = _important_query_terms(query_text)
    doc_stats = _document_stats(evidences)
    use_doc_aware = _should_expand_neighbors(context, query_text)

    def score(evidence: Evidence) -> float:
        base = (evidence.score or 0.0) * 0.55
        text = evidence.content or ""
        lexical = _lexical_overlap_score(terms, text)
        exact = 0.1 if _has_exact_query_term(query_variants, text) else 0.0
        important = _important_term_score(important_terms, text)
        chunk_type = _chunk_type_bonus(evidence)
        doc_aware = (
            _doc_aware_bonus(evidence, doc_stats)
            if use_doc_aware
            else 0.0
        )
        return base + lexical + exact + important + chunk_type + doc_aware

    return sorted(evidences, key=score, reverse=True)


def _lexical_terms(text: str) -> list[str]:
    cleaned = _clean_query(text)
    chunks = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", cleaned)
    terms: list[str] = []
    for chunk in chunks:
        if len(chunk) <= 1:
            continue
        if re.fullmatch(r"[A-Za-z0-9]+", chunk):
            terms.append(chunk.lower())
            continue
        terms.extend(_char_ngrams(chunk, 2))
        terms.extend(_char_ngrams(chunk, 3))
        if len(chunk) <= 8:
            terms.append(chunk)
    return _unique_non_empty(
        term
        for term in terms
        if term not in _QUERY_STOP_TERMS
    )


def _char_ngrams(text: str, n: int) -> list[str]:
    if len(text) < n:
        return []
    return [text[index:index + n] for index in range(len(text) - n + 1)]


def _lexical_overlap_score(terms: list[str], text: str) -> float:
    if not terms or not text:
        return 0.0
    normalized = text.lower()
    hits = sum(1 for term in terms if term.lower() in normalized)
    coverage = hits / max(len(terms), 1)
    return min(0.55, coverage * 0.75)


def _important_query_terms(query_text: str) -> list[str]:
    terms = []
    terms.extend(_quoted_terms(query_text))
    anchor = _project_anchor(query_text)
    if anchor:
        terms.append(anchor)
    cleaned = _clean_query(query_text)
    chunks = re.findall(r"[\u4e00-\u9fff]{2,12}", cleaned)
    terms.extend(
        chunk
        for chunk in chunks
        if chunk not in _QUERY_STOP_TERMS
    )
    return _unique_non_empty(terms)


def _important_term_score(terms: list[str], text: str) -> float:
    if not terms or not text:
        return 0.0
    hits = sum(1 for term in terms if term and term in text)
    return min(0.45, hits * 0.15)


def _chunk_type_bonus(evidence: Evidence) -> float:
    source_id = evidence.source_id or evidence.evidence_id or ""
    if "_content" in source_id:
        return 0.12
    if source_id.endswith(("_region", "_name", "_org")):
        return -0.30
    return 0.0


def _has_exact_query_term(query_variants: list[str], text: str) -> bool:
    for variant in query_variants:
        cleaned = _clean_query(variant)
        if len(cleaned) >= 6 and cleaned in text:
            return True
    return False


def _parse_content_chunk_id(chunk_id: str) -> tuple[str, int | None] | None:
    if "_content" not in chunk_id:
        return None

    document_id, _, suffix = chunk_id.partition("_content")
    if not document_id:
        return None

    if not suffix:
        return document_id, None

    if suffix.startswith("_") and suffix[1:].isdigit():
        return document_id, int(suffix[1:])

    return document_id, None


def _row_document_id(row: dict[str, str]) -> str | None:
    parsed = _parse_content_chunk_id(row.get("chunk_id", ""))
    if parsed is None:
        return None
    return parsed[0]


def _summary_aspects(query: str) -> list[str]:
    text = query.strip()
    from_match = re.search(r"从(.{2,80}?)(?:三个方面|三方面)", text)
    if from_match:
        text = from_match.group(1)
    else:
        for prefix in ("概括", "总结", "归纳", "说明"):
            if prefix in text:
                text = text.split(prefix, 1)[1]
                break

    text = re.sub(r"^(其|它|该项目|项目|正文)?的?", "", text)
    text = re.sub(r"^从", "", text)
    text = re.sub(r"(三个方面|三方面|方面)$", "", text)
    parts = re.split(r"[、，,；;。]|以及|和|与|及", text)
    aspects = []
    for part in parts:
        cleaned = re.sub(
            r"(三个方面|三方面|方面|特征|特点)$",
            "",
            part.strip(),
        )
        cleaned = cleaned.strip(" 的其。；;，,、")
        if len(cleaned) >= 2:
            aspects.append(cleaned)

    return _unique_non_empty(aspects[:6])


def _summary_terms(text: str) -> list[str]:
    core = _summary_core_text(text)
    terms = [core, text]
    terms.extend(_char_ngrams(core, 2))
    terms.extend(_char_ngrams(core, 3))
    return _unique_non_empty(
        term
        for term in terms
        if len(term) >= 2 and term not in _QUERY_STOP_TERMS
    )


def _summary_core_text(text: str) -> str:
    core = text
    for phrase in (
        "表演的",
        "配合方式",
        "方式",
        "设置",
        "变化",
        "特征",
        "特点",
        "主要",
        "内容",
        "方面",
        "艺术形成",
        "表现",
        "其",
        "的",
    ):
        core = core.replace(phrase, "")
    return core.strip() or text.strip()


def _summary_core_bonus(core: str, text: str) -> float:
    normalized = text or ""
    bonus = 0.0
    for term in _char_ngrams(core, 2):
        if term in _SUMMARY_BROAD_TERMS:
            continue
        if term in normalized:
            bonus += 0.08
    return min(0.24, bonus)


def _title_matches_anchor(source_name: str, anchor: str) -> bool:
    if not anchor:
        return False
    raw_source = re.sub(r"\s+", "", source_name)
    raw_target = re.sub(r"\s+", "", anchor)
    if raw_source and raw_target and (
        raw_target in raw_source or raw_source in raw_target
    ):
        return True

    source = _normalize_title(source_name)
    target = _normalize_title(anchor)
    return bool(source and target and (target in source or source in target))


def _normalize_title(value: str) -> str:
    value = re.sub(r"[（(].*?[）)]", "", value)
    value = re.sub(r"\s+", "", value)
    return value.strip()


def _document_hints_from_graph(evidences: list[Evidence]) -> set[str]:
    hints: set[str] = set()
    for evidence in evidences:
        for entity_id in evidence.entity_ids:
            hints.update(_document_ids_from_text(entity_id))
        for relation in evidence.relation_path:
            hints.update(_document_ids_from_text(relation.get("source", "")))
            hints.update(_document_ids_from_text(relation.get("target", "")))
    return hints


def _document_hints_from_chunks(evidences: list[Evidence]) -> set[str]:
    hints: set[str] = set()
    for evidence in evidences:
        parsed = _parse_content_chunk_id(
            evidence.source_id or evidence.evidence_id or ""
        )
        if parsed is not None:
            hints.add(parsed[0])
    return hints


def _document_ids_from_text(value: str) -> set[str]:
    return set(re.findall(r"ihchina_[0-9a-f]{12}", value or ""))


def _unique_non_empty(values: Iterable[str]) -> list[str]:
    rows = []
    seen = set()
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value).strip())
        if not normalized or normalized in seen:
            continue
        rows.append(normalized)
        seen.add(normalized)
    return rows


_QUERY_STOP_TERMS = {
    "什么",
    "哪些",
    "哪个",
    "哪座",
    "一种",
    "这个",
    "该种",
    "回答",
    "材料",
    "问题",
    "项目",
}

_NEIGHBOR_EXPANSION_CUES = {
    "分别",
    "概括",
    "总结",
    "说明",
    "归纳",
    "主要内容",
    "社会功能",
    "传承方式",
    "发展阶段",
    "结合材料",
    "根据正文",
    "多跳",
}

_SUMMARY_CUES = {
    "概括",
    "总结",
    "归纳",
    "主要内容",
    "社会功能",
    "传承方式",
    "正文",
}

_SUMMARY_BROAD_TERMS = {
    "男女",
    "表演",
    "方式",
    "设置",
    "变化",
    "特征",
    "特点",
    "内容",
}


class ChunkLexicalRetriever:
    """A-side lexical fallback over B chunks for exact-term evidence recall."""

    def __init__(self, chunks_file: str | Path):
        self.chunks_file = Path(chunks_file)
        self.rows = [
            json.loads(line)
            for line in self.chunks_file.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]
        self.rows_by_chunk_id = {
            row.get("chunk_id", ""): row
            for row in self.rows
            if row.get("chunk_id")
        }
        self.rows_by_doc_index = {}
        for row in self.rows:
            parsed = _parse_content_chunk_id(row.get("chunk_id", ""))
            if parsed is None:
                continue
            document_id, chunk_index = parsed
            if chunk_index is not None:
                self.rows_by_doc_index[(document_id, chunk_index)] = row

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        variants = _rewrite_queries(query)
        query_text = " ".join(variants)
        terms = _lexical_terms(query_text)
        important_terms = _important_query_terms(query_text)

        scored = []
        for row in self.rows:
            score = self._score_row(row, terms, important_terms)
            if score <= 0:
                continue
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            self._to_evidence(row, score)
            for score, row in scored[: context.top_k]
        ]

    def expand_neighbors(
        self,
        evidences: list[Evidence],
        *,
        window: int = 2,
        limit: int = 20,
    ) -> list[Evidence]:
        rows = []
        seen = {
            evidence.source_id or evidence.evidence_id
            for evidence in evidences
        }

        for evidence in evidences:
            parsed = _parse_content_chunk_id(
                evidence.source_id or evidence.evidence_id or ""
            )
            if parsed is None:
                continue
            document_id, chunk_index = parsed
            if chunk_index is None:
                continue

            for offset in range(-window, window + 1):
                if offset == 0:
                    continue
                neighbor_index = chunk_index + offset
                if neighbor_index < 0:
                    continue

                row = self.rows_by_doc_index.get(
                    (document_id, neighbor_index)
                )
                if not row:
                    continue

                chunk_id = row.get("chunk_id", "")
                if not chunk_id or chunk_id in seen:
                    continue

                parent_score = evidence.score or 0.0
                score = max(0.0, parent_score - abs(offset) * 0.03)
                rows.append((score, row))
                seen.add(chunk_id)

        rows.sort(key=lambda item: item[0], reverse=True)
        return [
            self._to_evidence(row, score, retrieval_method="neighbor_expansion")
            for score, row in rows[:limit]
        ]

    def summary_evidences(
        self,
        query: str,
        *,
        support_evidences: list[Evidence],
        candidate_evidences: list[Evidence],
        limit: int = 5,
    ) -> list[Evidence]:
        aspects = _summary_aspects(query)
        if not aspects:
            return []

        document_id = self._summary_document_id(
            query,
            support_evidences,
            candidate_evidences,
            aspects,
        )
        if not document_id:
            return []

        rows = [
            row
            for row in self.rows
            if _row_document_id(row) == document_id
        ]
        if not rows:
            return []

        selected: list[tuple[float, dict[str, str]]] = []
        seen: set[str] = set()

        for aspect in aspects:
            scored = [
                (
                    self._summary_row_score(row, [aspect]),
                    row,
                )
                for row in rows
            ]
            scored = [
                (score, row)
                for score, row in scored
                if score > 0 and row.get("chunk_id") not in seen
            ]
            if not scored:
                continue
            score, row = max(scored, key=lambda item: item[0])
            selected.append((score + 0.35, row))
            seen.add(row.get("chunk_id", ""))

        fill_rows = sorted(
            (
                (self._summary_row_score(row, aspects), row)
                for row in rows
                if row.get("chunk_id") not in seen
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        for score, row in fill_rows:
            if len(selected) >= limit:
                break
            if score <= 0:
                continue
            selected.append((score, row))
            seen.add(row.get("chunk_id", ""))

        return [
            self._to_evidence(
                row,
                score,
                retrieval_method="summary_document",
            )
            for score, row in selected[:limit]
        ]

    def _summary_document_id(
        self,
        query: str,
        support_evidences: list[Evidence],
        candidate_evidences: list[Evidence],
        aspects: list[str],
    ) -> str | None:
        anchor = _project_anchor(query)
        graph_hints = _document_hints_from_graph(support_evidences)
        candidate_hints = _document_hints_from_chunks(candidate_evidences)

        best: tuple[float, int, str] | None = None
        for index, row in enumerate(self.rows):
            parsed = _parse_content_chunk_id(row.get("chunk_id", ""))
            if parsed is None:
                continue
            document_id, _ = parsed
            source_name = row.get("source_name", "")
            title_match = _title_matches_anchor(source_name, anchor)
            if anchor and not title_match and document_id not in graph_hints:
                continue

            score = 0.0
            if title_match:
                score += 2.0
            if document_id in graph_hints:
                score += 1.5
            if document_id in candidate_hints:
                score += 0.5
            score += self._summary_row_score(row, aspects)

            if score <= 0:
                continue
            item = (score, -index, document_id)
            if best is None or item > best:
                best = item

        return best[2] if best else None

    def _summary_row_score(
        self,
        row: dict[str, str],
        aspects: list[str],
    ) -> float:
        content = row.get("content", "")
        source_name = row.get("source_name", "")
        text = f"{source_name} {content}"
        score = 0.0
        for aspect in aspects:
            core = _summary_core_text(aspect)
            terms = _lexical_terms(core)
            score += _lexical_overlap_score(terms, text)
            score += _important_term_score(_summary_terms(core), text)
            score += _summary_core_bonus(core, text)
        if row.get("chunk_type") == "detail_content":
            score += 0.05
        return score

    def _score_row(
        self,
        row: dict[str, str],
        terms: list[str],
        important_terms: list[str],
    ) -> float:
        content = row.get("content", "")
        source_name = row.get("source_name", "")
        text = f"{source_name} {content}"
        important = _important_term_score(important_terms, text)
        lexical = _lexical_overlap_score(terms, text)
        if important <= 0 and lexical <= 0:
            return 0.0
        chunk_type = row.get("chunk_type", "")
        type_bonus = 0.12 if chunk_type == "detail_content" else -0.08
        return important + lexical + type_bonus

    def _to_evidence(
        self,
        row: dict[str, str],
        score: float,
        *,
        retrieval_method: str = "lexical",
    ) -> Evidence:
        chunk_id = row.get("chunk_id", "")
        content = row.get("content", "")
        source_name = row.get("source_name", "")
        return Evidence(
            evidence_id=chunk_id,
            content=f"{source_name}\n{content}" if source_name else content,
            retrieval_method=retrieval_method,
            score=score,
            source_id=chunk_id,
            source_url=row.get("source_url") or None,
        )


class DRetrieverAdapter:
    """Adapt D retriever output into A's Evidence contract."""

    def __init__(self, retriever: Any, retrieval_method: str):
        self.retriever = retriever
        self.retrieval_method = retrieval_method

    def retrieve(
        self,
        query: str,
        context: RetrievalContext,
    ) -> list[Evidence]:
        raw_evidences = self._call_retriever(query, context)
        return [
            self._to_a_evidence(raw, index)
            for index, raw in enumerate(raw_evidences, start=1)
        ]

    def _call_retriever(
        self,
        query: str,
        context: RetrievalContext,
    ) -> Iterable[Any]:
        if hasattr(self.retriever, "retrieve"):
            return self.retriever.retrieve(
                query,
                context=context,
                top_k=context.top_k,
            )

        if hasattr(self.retriever, "_inner_retrieve"):
            from retrieval.base_retriever import RetrievalRequest

            request = RetrievalRequest(
                query=query,
                top_k=context.top_k,
                context=context,
            )
            return self.retriever._inner_retrieve(request)

        raise AttributeError(
            "Retriever must provide retrieve() or _inner_retrieve()."
        )

    def _to_a_evidence(self, raw: Any, index: int) -> Evidence:
        content = _first_present(raw, "evidence", "content", default="")
        score = _first_present(raw, "score", default=None)
        source_url = _first_present(raw, "source_url", default=None) or None
        chunk_id = _first_present(raw, "chunk_id", default=None)
        explicit_source_id = _first_present(raw, "source_id", default=None)
        source_id = chunk_id or explicit_source_id
        retriever_name = _first_present(raw, "retriever", default=None)
        evidence_id = (
            chunk_id
            or source_id
            or f"{self.retrieval_method}-{index:03d}"
        )
        relation_path = _relation_path(raw)

        return Evidence(
            evidence_id=str(evidence_id),
            content=str(content),
            retrieval_method=str(retriever_name or self.retrieval_method),
            score=_as_float(score),
            source_id=str(source_id) if source_id else None,
            source_url=source_url,
            entity_ids=_entity_ids(raw, relation_path),
            relation_path=relation_path,
        )


def _first_present(raw: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(raw, dict) and name in raw:
            return raw[name]
        if hasattr(raw, name):
            return getattr(raw, name)
    return default


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _relation_path(raw: Any) -> list[dict[str, str]]:
    path = _first_present(raw, "relation_path", default=None)
    if path:
        return _normalize_relation_path(path)

    d_path = _first_present(raw, "path", default=None)
    if d_path is None:
        return []

    return _normalize_relation_path(d_path)


def _normalize_relation_path(value: Any) -> list[dict[str, str]]:
    if isinstance(value, dict):
        relation = _relation_from_dict(value)
        return [relation] if relation else []

    if isinstance(value, str):
        return _parse_path_text(value)

    relations: list[dict[str, str]] = []
    flat_items: list[str] = []

    for item in value:
        if item is None:
            continue

        if isinstance(item, dict):
            relation = _relation_from_dict(item)
            if relation:
                relations.append(relation)
            continue

        if isinstance(item, str):
            parsed = _parse_path_text(item)
            if parsed:
                relations.extend(parsed)
            else:
                flat_items.append(item)
            continue

        flat_items.append(str(item))

    if relations:
        return relations

    return _flat_path_to_relations(flat_items)


def _relation_from_dict(value: dict[str, Any]) -> dict[str, str] | None:
    source = value.get("source")
    relation = value.get("relation")
    target = value.get("target")

    if not source or not relation or not target:
        return None

    return {
        "source": str(source),
        "relation": str(relation),
        "target": str(target),
    }


def _parse_path_text(path_text: str) -> list[dict[str, str]]:
    parts = re.split(r"\s*--\[(.*?)\]-->\s*", path_text.strip())
    parts = [part.strip() for part in parts if part.strip()]
    return _flat_path_to_relations(parts)


def _flat_path_to_relations(parts: list[str]) -> list[dict[str, str]]:
    if len(parts) < 3:
        return []

    relations = []
    for index in range(0, len(parts) - 2, 2):
        source = parts[index]
        relation = parts[index + 1]
        target = parts[index + 2]
        relations.append(
            {
                "source": source,
                "relation": relation,
                "target": target,
            }
        )

    return relations


def _entity_ids(raw: Any, relation_path: list[dict[str, str]]) -> list[str]:
    entity_ids = _first_present(raw, "entity_ids", default=None)
    if entity_ids:
        return [str(item) for item in entity_ids if item is not None]

    ids: list[str] = []

    for relation in relation_path:
        ids.extend(
            item
            for item in (
                relation.get("source"),
                relation.get("target"),
            )
            if item
        )

    source_name = _first_present(raw, "source_name", default=None)
    document_id = _first_present(raw, "document_id", default=None)
    ids.extend(item for item in (document_id, source_name) if item)

    return list(dict.fromkeys(str(item) for item in ids if item))
