"""实体消歧与融合。

这个模块同时承担两件事：
1. 纯字符串层面的候选归并；
2. 规则层面的类型纠偏，避免把地名误判成保护单位。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re


REGION_SUFFIXES = (
    "维吾尔自治区",
    "回族自治区",
    "壮族自治区",
    "自治区",
    "特别行政区",
    "自治州",
    "自治县",
    "省",
    "市",
    "区",
    "县",
    "旗",
    "盟",
)

ORG_HINTS = (
    "保护中心",
    "保护管理办公室",
    "保护管理中心",
    "非物质文化遗产保护中心",
    "非遗中心",
    "文化馆",
    "博物馆",
    "纪念馆",
    "研究院",
    "研究所",
    "传习所",
    "传承中心",
    "文化中心",
    "艺术团",
    "剧团",
    "歌舞团",
    "学校",
    "学院",
    "大学",
    "协会",
    "学会",
    "委员会",
    "管理局",
    "办公室",
    "局",
    "馆",
    "所",
    "院",
    "中心",
)

BATCH_MARKERS = (
    "第一批",
    "第二批",
    "第三批",
    "第四批",
    "第五批",
    "第六批",
    "第七批",
    "第八批",
    "第九批",
    "第十批",
)


def _norm(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[（）()\[\]【】·•、，,;；\s]", "", text)
    text = text.replace("中华人民共和国", "")
    for token in ("维吾尔自治区", "回族自治区", "壮族自治区", "自治区", "特别行政区", "省", "市"):
        text = text.replace(token, "")
    return text


def normalize_region_name(text: str) -> str:
    """把省市区县名压到更稳定的 key，但保留区县层级。"""
    text = text.strip()
    text = re.sub(r"\s+", "", text)
    text = text.replace("中华人民共和国", "")
    for token in ("维吾尔自治区", "回族自治区", "壮族自治区", "自治区", "特别行政区", "省", "市"):
        text = text.replace(token, "")
    return text


def normalize_org_name(text: str) -> str:
    """机构名只做轻度清洗，不强行删地域前缀。"""
    text = text.strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[（）()\[\]【】·•]", "", text)
    return text


def looks_like_batch(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    return any(marker in text for marker in BATCH_MARKERS) or bool(re.search(r"\d{4}", text))


def looks_like_protection_unit(text: str) -> bool:
    text = normalize_org_name(text)
    if not text:
        return False
    if any(hint in text for hint in ORG_HINTS):
        return True
    if looks_like_batch(text):
        return False
    return False


def looks_like_region(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    if looks_like_protection_unit(text):
        return False
    text = re.sub(r"\s+", "", text)
    if not text:
        return False
    # 地名常常是“省+市+区县”连写，不能先把后缀全删掉再判断。
    if re.search(r"(维吾尔自治区|回族自治区|壮族自治区|自治区|特别行政区|自治州|自治县)", text):
        return True
    if re.search(r"(省|市|区|县|州|盟|旗)", text):
        return True
    return False


@dataclass
class ResolutionDecision:
    canonical_name: str
    matched: bool
    score: float
    reason: str
    aliases: list[str] = field(default_factory=list)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def correct_entity_type(name: str, entity_type: str) -> tuple[str, str]:
    """规则层兜底：把明显的地名/机构纠错到更合理的类型。"""
    if not name:
        return entity_type, "empty-name"
    if entity_type == "ProtectionUnit" and looks_like_region(name):
        return "Region", "place-name override"
    if entity_type == "Region" and looks_like_protection_unit(name):
        return "ProtectionUnit", "organization-name override"
    return entity_type, "as-is"


def resolve_entity(name: str, candidates: list[str]) -> ResolutionDecision:
    """给定一个名称和候选列表，返回最可能的规范名。"""
    if not candidates:
        return ResolutionDecision(
            canonical_name=name,
            matched=False,
            score=0.0,
            reason="no candidates",
        )

    scored = sorted(
        ((similarity(name, cand), cand) for cand in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best_name = scored[0]
    aliases = [cand for score, cand in scored[1:] if score >= 0.78 and cand != best_name]

    return ResolutionDecision(
        canonical_name=best_name,
        matched=best_score >= 0.85,
        score=best_score,
        reason="string similarity baseline",
        aliases=aliases,
    )


def merge_equivalents(names: list[str], threshold: float = 0.88) -> list[list[str]]:
    """把高度相似实体聚成一组。"""
    groups: list[list[str]] = []
    used: set[str] = set()

    for name in names:
        if name in used:
            continue
        group = [name]
        used.add(name)
        for other in names:
            if other in used:
                continue
            if similarity(name, other) >= threshold:
                group.append(other)
                used.add(other)
        groups.append(group)
    return groups
