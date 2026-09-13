from typing import List

from orchestration.models import Evidence


def build_context(
    query: str,
    evidences: List[Evidence],
    max_evidence: int = 5,
) -> str:
    """
    将检索证据整理为供 LLM 使用的上下文。

    Stage 1：
    1. 限制证据数量
    2. 保留检索方法
    3. 保留证据内容
    4. 保留来源
    5. 保留关系路径
    """

    selected = evidences[:max_evidence]

    if not selected:
        return f"用户问题：{query}\n\n暂无可用检索证据。"

    sections = [f"用户问题：{query}", "", "检索证据："]

    for index, evidence in enumerate(selected, start=1):
        sections.append(f"[证据 {index}]")
        sections.append(f"检索方式：{evidence.retrieval_method}")
        sections.append(f"内容：{evidence.content}")

        if evidence.source_url:
            sections.append(f"来源：{evidence.source_url}")

        if evidence.relation_path:
            sections.append(
                "关系路径：" + " -> ".join(evidence.relation_path)
            )

        sections.append("")

    return "\n".join(sections)