from typing import List

from orchestration.models import Evidence


def _evidence_key(evidence: Evidence) -> str:
    """
    生成证据去重键。

    优先使用 evidence_id；
    如果没有稳定的 evidence_id，则使用内容 + 来源。
    """
    if evidence.evidence_id:
        return str(evidence.evidence_id)

    return "|".join(
        [
            evidence.content.strip(),
            evidence.source_url or "",
        ]
    )


def _evidence_score(evidence: Evidence) -> float:
    """安全获取 evidence score，用于排序。"""
    try:
        return float(evidence.score)
    except (TypeError, ValueError):
        return 0.0


def _format_relation_path(evidence: Evidence) -> str:
    """整理关系路径，兼容 list / tuple / 字符串等情况。"""
    path = evidence.relation_path

    if not path:
        return ""

    if isinstance(path, (list, tuple)):
        return " -> ".join(str(item) for item in path)

    return str(path)


def build_context(
    query: str,
    evidences: List[Evidence],
    max_evidence: int = 5,
    max_chars: int = 8000,
) -> str:
    """
    Stage 2 Context Engineering。

    对检索结果进行：
    1. Evidence 去重
    2. 按检索分数排序
    3. 限制 Evidence 数量
    4. 整理 Evidence 内容
    5. 保留检索方式
    6. 保留来源
    7. 保留关系路径
    8. 限制最终 Context 长度

    返回可直接提供给 LLM 的结构化上下文。
    """

    if not evidences:
        return f"用户问题：{query}\n\n暂无可用检索证据。"

    # ---------------------------------------------------------
    # Evidence 去重
    # ---------------------------------------------------------
    unique_evidences = []
    seen = set()

    for evidence in evidences:
        key = _evidence_key(evidence)

        if key in seen:
            continue

        seen.add(key)
        unique_evidences.append(evidence)

    # ---------------------------------------------------------
    # 按 score 从高到低排序
    # ---------------------------------------------------------
    unique_evidences.sort(
        key=_evidence_score,
        reverse=True,
    )

    # ---------------------------------------------------------
    # 限制 Evidence 数量
    # ---------------------------------------------------------
    selected = unique_evidences[:max_evidence]

    sections = [
        f"用户问题：{query}",
        "",
        "检索证据：",
    ]

    # ---------------------------------------------------------
    # 构造结构化 Context
    # ---------------------------------------------------------
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

        if evidence.source_url:
            sections.append(
                f"来源：{evidence.source_url}"
            )

        relation_path = _format_relation_path(evidence)

        if relation_path:
            sections.append(
                f"关系路径：{relation_path}"
            )

        sections.append("")

    # ---------------------------------------------------------
    # Token / 长度控制
    # ---------------------------------------------------------
    context = "\n".join(sections)

    if len(context) <= max_chars:
        return context

    # 保留完整的开头信息，并截断超长 Context。
    truncated = context[:max_chars]

    return (
        truncated.rstrip()
        + "\n\n"
        "[Context 已达到长度限制，后续证据未纳入。]"
    )