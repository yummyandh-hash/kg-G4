"""非遗知识图谱 Ontology V1.

这一层只回答一件事：系统允许抽什么、连什么、怎么命名。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet


NODE_TYPES: FrozenSet[str] = frozenset(
    {
        "InheritProject",  # 非遗项目
        "Category",  # 类别
        "Bearer",  # 传承人
        "Region",  # 地区
        "ProtectionUnit",  # 保护单位
        "Technique",  # 技艺
        "CulturalElement",  # 文化元素
    }
)


RELATION_TYPES: FrozenSet[str] = frozenset(
    {
        "BELONGS_TO",  # 项目 -> 类别
        "LOCATED_IN",  # 项目/单位 -> 地区
        "HAS_BEARER",  # 项目 -> 传承人
        "PROTECTED_BY",  # 项目 -> 保护单位
        "USES_TECHNIQUE",  # 项目 -> 技艺
        "RELATED_TO",  # 项目 -> 文化元素
        "ALIAS_OF",  # 别名关系
        "SAME_AS",  # 融合后的规范等价关系
    }
)


EDGE_RULES: dict[str, tuple[str, str]] = {
    "BELONGS_TO": ("InheritProject", "Category"),
    "LOCATED_IN": ("InheritProject", "Region"),
    "HAS_BEARER": ("InheritProject", "Bearer"),
    "PROTECTED_BY": ("InheritProject", "ProtectionUnit"),
    "USES_TECHNIQUE": ("InheritProject", "Technique"),
    "RELATED_TO": ("InheritProject", "CulturalElement"),
    "ALIAS_OF": ("Alias", "Alias"),
    "SAME_AS": ("Entity", "Entity"),
}


@dataclass(frozen=True)
class OntologyHint:
    """给 LLM 的轻量本体提示。"""

    node_types: tuple[str, ...] = tuple(sorted(NODE_TYPES))
    relation_types: tuple[str, ...] = tuple(sorted(RELATION_TYPES))
    allowed_relations: dict[str, tuple[str, str]] = field(
        default_factory=lambda: dict(EDGE_RULES)
    )

    def to_prompt_text(self) -> str:
        lines = ["节点类型："]
        lines.extend(f"- {item}" for item in self.node_types)
        lines.append("关系类型：")
        lines.extend(f"- {item}" for item in self.relation_types)
        lines.append("关系约束：")
        for rel, (src, dst) in self.allowed_relations.items():
            lines.append(f"- {rel}: {src} -> {dst}")
        return "\n".join(lines)


ONTOLOGY_V1 = OntologyHint()

