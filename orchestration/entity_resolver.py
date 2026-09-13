# -*- coding: utf-8 -*-
"""
三层融合实体归一模块

实现任务一要求的三层融合实体归一：
1. 规则词典（非遗俗称、别名）
2. 语义相似度
3. 图谱地域/门类约束辅助消歧

输出entity_candidate.json，包含标准实体名、全部别名、所属地域/门类、置信分数
"""

from __future__ import annotations
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

# 非遗相关规则词典
NON_INTANGIBLE_RULES = {
    "剪纸": ["剪纸艺术", "纸剪", "剪花", "窗花"],
    "皮影戏": ["皮影", "灯影戏", "皮影艺术"],
    "京剧": ["京戏", "国剧", "皮黄"],
    "昆曲": ["昆剧", "昆腔", "昆腔戏"],
    "中医针灸": ["针灸", "针刺", "艾灸"],
    "书法": ["毛笔字", "书道", "翰墨"],
    "国画": ["中国画", "水墨画", "丹青"],
    "陶瓷": ["瓷器", "陶器", "瓷艺"],
    "刺绣": ["绣花", "丝绣", "针黹"],
    "剪纸": ["窗花", "剪花", "纸剪"],
    "皮影": ["灯影", "皮影戏", "影戏"],
    "评剧": ["蹦蹦戏", "平戏", "唐山落子"],
    "越剧": ["绍兴戏", "嵊州戏", "女子越剧"],
    "黄梅戏": ["黄梅调", "采茶戏", "怀腔"],
    "豫剧": ["河南梆子", "河南高调", "梆子腔"],
    "川剧": ["川昆", "高腔", "胡琴"],
    "粤剧": ["广东大戏", "广府戏", "红船"],
    "秦腔": ["乱弹", "梆子腔", "陕西梆子"],
    "晋剧": ["中路梆子", "山西梆子", "蒲州梆子"],
    "河北梆子": ["京梆子", "直隶梆子", "卫梆子"],
    "评弹": ["苏州评弹", "弹词", "说书"],
    "相声": ["口技", "说相声", "相生"],
    "京剧": ["京戏", "国剧", "皮黄"],
    "昆曲": ["昆剧", "昆腔", "昆腔戏"],
    "中医针灸": ["针灸", "针刺", "艾灸"],
    "书法": ["毛笔字", "书道", "翰墨"],
    "国画": ["中国画", "水墨画", "丹青"],
    "陶瓷": ["瓷器", "陶器", "瓷艺"],
    "刺绣": ["绣花", "丝绣", "针黹"],
}

# 行政区划后缀
REGION_SUFFIXES = (
    "维吾尔自治区", "回族自治区", "壮族自治区", "自治区", "特别行政区",
    "自治州", "自治县", "省", "市", "区", "县", "旗", "盟"
)

# 机构线索
ORG_HINTS = (
    "保护中心", "保护管理办公室", "保护管理中心", "非物质文化遗产保护中心",
    "非遗中心", "文化馆", "博物馆", "纪念馆", "研究院", "研究所",
    "传习所", "传承中心", "文化中心", "艺术团", "剧团", "歌舞团",
    "学校", "学院", "大学", "协会", "学会", "委员会", "管理局",
    "办公室", "局", "馆", "所", "院", "中心"
)

# 批次标记
BATCH_MARKERS = (
    "第一批", "第二批", "第三批", "第四批", "第五批",
    "第六批", "第七批", "第八批", "第九批", "第十批"
)

# 十大门类标准名称
CATEGORY_NAMES = {
    "民间文学": "民间文学", "传统音乐": "传统音乐", "传统舞蹈": "传统舞蹈",
    "传统戏剧": "传统戏剧", "曲艺": "曲艺", "传统体育、游艺与杂技": "传统体育、游艺与杂技",
    "传统美术": "传统美术", "传统技艺": "传统技艺", "传统医药": "传统医药", "民俗": "民俗",
}

@dataclass
class EntityCandidate:
    """实体候选记录"""
    canonical_name: str
    aliases: List[str]
    category: str
    region: str
    confidence: float
    source_documents: List[str] = field(default_factory=list)

@dataclass
class ResolutionDecision:
    """实体解析决策"""
    canonical_name: str
    matched: bool
    score: float
    reason: str
    aliases: List[str] = field(default_factory=list)
    category: Optional[str] = None
    region: Optional[str] = None


def _norm(text: str) -> str:
    """标准化文本：小写、去除标点和空格"""
    text = text.strip().lower()
    text = re.sub(r"[（）()\[\]【】·•、，,;；\s]", "", text)
    text = text.replace("中华人民共和国", "")
    for token in ("维吾尔自治区", "回族自治区", "壮族自治区", "自治区", "特别行政区", "省", "市"):
        text = text.replace(token, "")
    return text


def normalize_region_name(text: str) -> str:
    """标准化地区名称"""
    text = text.strip()
    text = re.sub(r"\s+", "", text)
    text = text.replace("中华人民共和国", "")
    for token in ("维吾尔自治区", "回族自治区", "壮族自治区", "自治区", "特别行政区", "省", "市"):
        text = text.replace(token, "")
    return text


def normalize_org_name(text: str) -> str:
    """标准化机构名称"""
    text = text.strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[（）()\[\]【】·•]", "", text)
    return text


def looks_like_batch(text: str) -> bool:
    """判断是否像批次标记"""
    text = (text or "").strip()
    if not text:
        return False
    return any(marker in text for marker in BATCH_MARKERS) or bool(re.search(r"\d{4}", text))


def looks_like_protection_unit(text: str) -> bool:
    """判断是否像保护单位"""
    text = normalize_org_name(text)
    if not text:
        return False
    if any(hint in text for hint in ORG_HINTS):
        return True
    if looks_like_batch(text):
        return False
    return False


def looks_like_region(text: str) -> bool:
    """判断是否像地区名称"""
    text = (text or "").strip()
    if not text:
        return False
    if looks_like_protection_unit(text):
        return False
    text = re.sub(r"\s+", "", text)
    if not text:
        return False
    if re.search(r"(维吾尔自治区|回族自治区|壮族自治区|自治区|特别行政区|自治州|自治县)", text):
        return True
    if re.search(r"(省|市|区|县|州|盟|旗)", text):
        return True
    return False


def find_non_intangible_synonyms(name: str) -> List[str]:
    """查找非遗相关的同义词"""
    synonyms = []
    for key, values in NON_INTANGIBLE_RULES.items():
        if key in name:
            synonyms.extend(values)
        for value in values:
            if value in name:
                synonyms.append(key)
    return synonyms


def similarity(a: str, b: str) -> float:
    """计算字符串相似度"""
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def correct_entity_type(name: str, entity_type: str, context: Dict) -> Tuple[str, str]:
    """规则层兜底：根据上下文纠正实体类型"""
    if not name:
        return entity_type, "empty-name"

    # 如果有上下文信息，优先使用上下文
    if context.get("region") and looks_like_region(name):
        return "Region", "place-name from context"
    if context.get("org") and looks_like_protection_unit(name):
        return "ProtectionUnit", "organization-name from context"

    # 基于名称本身判断
    if entity_type == "ProtectionUnit" and looks_like_region(name):
        return "Region", "place-name override"
    if entity_type == "Region" and looks_like_protection_unit(name):
        return "ProtectionUnit", "organization-name override"

    return entity_type, "as-is"


def resolve_entity(name: str, candidates: List[str], context: Optional[Dict] = None) -> ResolutionDecision:
    """给定一个名称和候选列表，返回最可能的规范名"""
    context = context or {}

    if not candidates:
        return ResolutionDecision(
            canonical_name=name,
            matched=False,
            score=0.0,
            reason="no candidates",
        )

    # 第一层：规则词典匹配
    rule_matches = []
    for rule_name, synonyms in NON_INTANGIBLE_RULES.items():
        if name == rule_name or name in synonyms:
            rule_matches.append(rule_name)

    if rule_matches:
        # 如果有多个规则匹配，选择最相似的
        best_match = max(rule_matches, key=lambda x: similarity(name, x))
        return ResolutionDecision(
            canonical_name=best_match,
            matched=True,
            score=1.0,
            reason="rule dictionary match",
            aliases=[syn for syn in synonyms if syn != best_match],
        )

    # 第二层：语义相似度匹配
    scored = sorted(
        ((similarity(name, cand), cand) for cand in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best_name = scored[0]

    # 第三层：图谱约束辅助消歧
    corrected_type, reason = correct_entity_type(name, "Entity", context)

    aliases = [cand for score, cand in scored[1:] if score >= 0.78 and cand != best_name]

    return ResolutionDecision(
        canonical_name=best_name,
        matched=best_score >= 0.85,
        score=best_score,
        reason=f"string similarity + {reason}",
        aliases=aliases,
        category=context.get("category"),
        region=context.get("region"),
    )


def merge_equivalents(names: List[str], threshold: float = 0.88) -> List[List[str]]:
    """把高度相似实体聚成一组"""
    groups: List[List[str]] = []
    used: Set[str] = set()

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


def extract_entities_from_documents(documents: List[Dict]) -> List[EntityCandidate]:
    """从文档中提取实体候选"""
    entity_map = defaultdict(lambda: {
        "names": set(),
        "categories": set(),
        "regions": set(),
        "sources": set()
    })

    for doc in documents:
        name = doc.get("name", "")
        if not name:
            continue

        # 添加主名称
        entity_map[name]["names"].add(name)

        # 添加别名（如果有）
        aliases = doc.get("aliases", [])
        for alias in aliases:
            if alias:
                entity_map[name]["names"].add(alias)

        # 添加类别
        category = doc.get("category", "")
        if category:
            entity_map[name]["categories"].add(category)

        # 添加地区
        region = doc.get("region", "")
        if region:
            entity_map[name]["regions"].add(region)

        # 添加来源文档
        doc_id = doc.get("document_id", "")
        if doc_id:
            entity_map[name]["sources"].add(doc_id)

    # 合并等价实体
    all_names = list(entity_map.keys())
    merged_groups = merge_equivalents(all_names)

    candidates = []
    for group in merged_groups:
        if not group:
            continue

        # 选择规范名（最短的作为规范名）
        canonical_name = min(group, key=len)

        # 收集所有别名
        all_aliases = set()
        for name in group:
            if name != canonical_name:
                all_aliases.add(name)

        # 获取类别和地区信息
        entity_data = entity_map[canonical_name]
        categories = list(entity_data["categories"])
        regions = list(entity_data["regions"])

        # 计算置信度（基于合并的实体数量和信息的完整性）
        confidence = 0.5 + (len(group) - 1) * 0.1  # 基础0.5，每增加一个同义实体增加0.1
        if categories:
            confidence += 0.2
        if regions:
            confidence = min(confidence + 0.2, 1.0)  # 置信度不超过1.0

        candidates.append(EntityCandidate(
            canonical_name=canonical_name,
            aliases=sorted(list(all_aliases)),
            category=categories[0] if categories else "未知",
            region=regions[0] if regions else "未知",
            confidence=confidence,
            source_documents=sorted(list(entity_data["sources"]))
        ))

    return sorted(candidates, key=lambda x: x.confidence, reverse=True)


def generate_entity_candidate_file(documents: List[Dict], output_path: str) -> None:
    """生成实体候选文件"""
    candidates = extract_entities_from_documents(documents)

    output_data = []
    for candidate in candidates:
        output_data.append({
            "canonical_name": candidate.canonical_name,
            "aliases": candidate.aliases,
            "category": candidate.category,
            "region": candidate.region,
            "confidence": candidate.confidence,
            "source_documents": candidate.source_documents
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"生成实体候选文件: {output_path}")
    print(f"共生成 {len(output_data)} 个实体候选")


def main():
    """主函数：从清洗后的文档生成实体候选"""
    ROOT = Path(__file__).resolve().parent.parent
    DOC_DIR = ROOT / "data" / "clean" / "documents"
    OUTPUT_PATH = ROOT / "data" / "entity_candidate.json"

    # 读取所有清洗后的文档
    documents = []
    for doc_file in DOC_DIR.glob("*.json"):
        with open(doc_file, "r", encoding="utf-8") as f:
            doc = json.load(f)
            documents.append(doc)

    if not documents:
        print("没有找到清洗后的文档")
        return

    # 生成实体候选文件
    generate_entity_candidate_file(documents, OUTPUT_PATH)


if __name__ == "__main__":
    main()