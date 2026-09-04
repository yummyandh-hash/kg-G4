"""C 模块的数据结构定义。

这里负责把抽取结果锁进可验证的 JSON 形状里。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


NodeType = Literal[
    "InheritProject",
    "Category",
    "Bearer",
    "Region",
    "ProtectionUnit",
    "Technique",
    "CulturalElement",
]


RelationType = Literal[
    "BELONGS_TO",
    "LOCATED_IN",
    "HAS_BEARER",
    "PROTECTED_BY",
    "USES_TECHNIQUE",
    "RELATED_TO",
    "ALIAS_OF",
    "SAME_AS",
]


@dataclass
class Provenance:
    source_url: str
    document_id: str
    chunk_id: str
    retrieved_at: str
    source_name: str | None = None
    source_category: str | None = None
    source_region: str | None = None
    source_org: str | None = None
    source_batch: str | None = None
    evidence_text: str | None = None


@dataclass
class EntityRecord:
    entity_id: str
    entity_type: NodeType
    name: str
    canonical_name: str | None = None
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    provenance: list[Provenance] = field(default_factory=list)


@dataclass
class RelationRecord:
    relation_type: RelationType
    source_entity_id: str
    target_entity_id: str
    confidence: float = 0.0
    provenance: list[Provenance] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    entities: list[EntityRecord] = field(default_factory=list)
    relations: list[RelationRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

