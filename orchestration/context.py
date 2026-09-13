from typing import List

from orchestration.models import Evidence


def build_context(
    query: str,
    evidences: List[Evidence],
    max_evidence: int = 5,
) -> str:
    """Format retrieved evidence into text for answer generation."""

    selected = evidences[:max_evidence]

    if not selected:
        return f"User query: {query}\n\nNo retrieval evidence available."

    sections = [f"User query: {query}", "", "Retrieval evidence:"]

    for index, evidence in enumerate(selected, start=1):
        sections.append(f"[Evidence {index}]")
        sections.append(f"Retrieval method: {evidence.retrieval_method}")
        sections.append(f"Content: {evidence.content}")

        if evidence.source_url:
            sections.append(f"Source: {evidence.source_url}")

        if evidence.relation_path:
            sections.append(
                "Relation path: "
                + _format_relation_path(evidence.relation_path)
            )

        sections.append("")

    return "\n".join(sections)


def _format_relation_path(path) -> str:
    if all(isinstance(item, dict) for item in path):
        return " -> ".join(
            (
                f"{item.get('source')} --[{item.get('relation')}]--> "
                f"{item.get('target')}"
            )
            for item in path
            if item.get("source") and item.get("relation") and item.get("target")
        )

    return " -> ".join(str(item) for item in path)
