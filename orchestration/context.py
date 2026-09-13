from typing import List, Tuple

from orchestration.models import Evidence


def _evidence_key(evidence: Evidence) -> str:
    """生成证据唯一标识，用于去重。"""
    relation_path = _format_relation_path(
        evidence.relation_path
    )

    return "|".join(
        [
            str(evidence.evidence_id or ""),
            evidence.content.strip(),
            str(evidence.source_id or ""),
            relation_path,
        ]
    )


def _evidence_score(evidence: Evidence) -> float:
    """安全获取证据相关性分数。"""
    try:
        return float(evidence.score)
    except (TypeError, ValueError):
        return 0.0


def _format_relation_path(relation_path) -> str:
    """将不同格式的关系路径统一格式化为可读字符串。"""
    if not relation_path:
        return ""

    # 情况 1：单个字符串
    if isinstance(relation_path, str):
        relation_path = relation_path.strip()

        if not relation_path:
            return ""

        # 尝试解析字符串化的 dict
        if relation_path.startswith("{") and relation_path.endswith("}"):
            import ast

            try:
                parsed = ast.literal_eval(relation_path)

                if isinstance(parsed, dict):
                    source = parsed.get("source")
                    relation = parsed.get("relation")
                    target = parsed.get("target")

                    if source and relation and target:
                        return (
                            f"{source} --[{relation}]--> {target}"
                        )
            except (ValueError, SyntaxError):
                pass

        return relation_path

    # 情况 2：list / tuple
    if isinstance(relation_path, (list, tuple)):
        if not relation_path:
            return ""

        # 2.1 ["A", "REL", "B"]
        # 或 ["A", "REL1", "B", "REL2", "C"]
        if all(isinstance(item, str) for item in relation_path):
            if (
                len(relation_path) >= 3
                and len(relation_path) % 2 == 1
            ):
                parts = []

                for index in range(0, len(relation_path) - 2, 2):
                    source = relation_path[index]
                    relation = relation_path[index + 1]
                    target = relation_path[index + 2]

                    parts.append(
                        f"{source} --[{relation}]--> {target}"
                    )

                return " ".join(parts)

            # 2.2 ["{'source': 'A', 'relation': 'REL', 'target': 'B'}"]
            import ast

            formatted_parts = []

            for item in relation_path:
                item = item.strip()

                if (
                    item.startswith("{")
                    and item.endswith("}")
                ):
                    try:
                        parsed = ast.literal_eval(item)

                        if isinstance(parsed, dict):
                            source = parsed.get("source")
                            relation = parsed.get("relation")
                            target = parsed.get("target")

                            if source and relation and target:
                                formatted_parts.append(
                                    f"{source} --[{relation}]--> {target}"
                                )
                                continue
                    except (ValueError, SyntaxError):
                        pass

                formatted_parts.append(item)

            return " ".join(formatted_parts)

        # 2.3 [{"source": "A", "relation": "REL", "target": "B"}]
        formatted_parts = []

        for item in relation_path:
            if isinstance(item, dict):
                source = item.get("source")
                relation = item.get("relation")
                target = item.get("target")

                if source and relation and target:
                    formatted_parts.append(
                        f"{source} --[{relation}]--> {target}"
                    )
                    continue

            formatted_parts.append(str(item))

        return " ".join(formatted_parts)

    # 其他类型
    return str(relation_path)


def _unique_evidences(evidences: List[Evidence]) -> List[Evidence]:
    """证据去重，并按照相关性分数降序排列。"""
    unique_evidences = []
    seen = set()

    for evidence in evidences:
        key = _evidence_key(evidence)

        if key in seen:
            continue

        seen.add(key)
        unique_evidences.append(evidence)

    unique_evidences.sort(
        key=_evidence_score,
        reverse=True,
    )

    return unique_evidences


def _collect_entities(evidences: List[Evidence]) -> List[str]:
    """从证据中收集相关实体 ID，并去重。"""
    entities = []
    seen = set()

    for evidence in evidences:
        for entity_id in evidence.entity_ids or []:
            entity_id = str(entity_id)

            if entity_id in seen:
                continue

            seen.add(entity_id)
            entities.append(entity_id)

    return entities


def _collect_paths(
    evidences: List[Evidence],
    max_paths: int,
) -> List[str]:
    """
    从证据中提取关系路径。
    按证据相关性排序后的顺序保留，因此优先保留高分路径。
    """
    paths = []
    seen = set()

    for evidence in evidences:
        path = _format_relation_path(evidence.relation_path)

        if not path:
            continue

        if path in seen:
            continue

        seen.add(path)
        paths.append(path)

        if len(paths) >= max_paths:
            break

    return paths


def _collect_sources(
    evidences: List[Evidence],
) -> List[Tuple[str, str]]:
    """收集证据来源，并去重。"""
    sources = []
    seen = set()

    for evidence in evidences:
        source_id = evidence.source_id or ""
        source_url = evidence.source_url or ""

        # 两者都没有时，不作为有效来源
        if not source_id and not source_url:
            continue

        key = (source_id, source_url)

        if key in seen:
            continue

        seen.add(key)
        sources.append(key)

    return sources


def build_context(
    query: str,
    evidences: List[Evidence],
    max_evidence: int = 5,
    max_paths: int = 3,
    max_chars: int = 8000,
) -> str:
    """
    构建 Stage 2 Context Engineering V1 上下文。

    处理流程：
    1. 证据去重
    2. 按相关性分数排序
    3. Top-K 证据筛选
    4. 提取相关实体
    5. 提取关系路径
    6. 整理来源信息
    7. 统一组织成结构化 Context
    8. 限制最终 Context 长度
    """

    if not evidences:
        return f"用户问题：{query}\n\nNo retrieval evidence available."

    # --------------------------------------------------
    # 证据去重 + 排序
    # --------------------------------------------------
    unique_evidences = _unique_evidences(evidences)

    # --------------------------------------------------
    # Top-K
    # --------------------------------------------------
    selected = unique_evidences[:max_evidence]

    # --------------------------------------------------
    # 提取结构化信息
    # --------------------------------------------------
    entities = _collect_entities(selected)
    paths = _collect_paths(selected, max_paths=max_paths)
    sources = _collect_sources(selected)

    # --------------------------------------------------
    # 构建 Context
    # --------------------------------------------------
    sections = []

    # 用户问题
    sections.append(f"用户问题：{query}")

    # 相关实体
    sections.append("")
    sections.append("【相关实体】")

    if entities:
        for entity in entities:
            sections.append(f"- {entity}")
    else:
        sections.append("- 暂无明确实体信息")

    # 关系路径
    sections.append("")
    sections.append("【关系路径】")

    if paths:
        for index, path in enumerate(paths, start=1):
            sections.append(f"[路径 {index}] {path}")
    else:
        sections.append("- 当前证据未提供可用关系路径")

    # 检索证据
    sections.append("")
    sections.append("【检索证据】")

    for index, evidence in enumerate(selected, start=1):
        sections.append(f"[证据 {index}]")
        sections.append(
            f"检索方式：{evidence.retrieval_method}"
        )
        sections.append(
            f"相关性分数：{_evidence_score(evidence):.4f}"
        )
        sections.append(
            f"内容：{evidence.content}"
        )

        relation_path = _format_relation_path(
            evidence.relation_path
        )

        if relation_path:
            sections.append(
                f"关系路径：{relation_path}"
            )

        if evidence.source_id:
            sections.append(
                f"来源ID：{evidence.source_id}"
            )

        if evidence.source_url:
            sections.append(
                f"来源URL：{evidence.source_url}"
            )

        sections.append("")

    # 来源
    sections.append("【来源】")

    if sources:
        for index, (source_id, source_url) in enumerate(
            sources,
            start=1,
        ):
            sections.append(f"[来源 {index}]")

            if source_id:
                sections.append(
                    f"source_id：{source_id}"
                )

            if source_url:
                sections.append(
                    f"source_url：{source_url}"
                )
    else:
        sections.append("- 暂无来源信息")

    # --------------------------------------------------
    # 最终长度控制
    # --------------------------------------------------
    context = "\n".join(sections)

    if len(context) <= max_chars:
        return context

    truncated = context[:max_chars]

    return (
        truncated.rstrip()
        + "\n\n"
        "[Context 已达到长度限制，后续内容未纳入。]"
    )