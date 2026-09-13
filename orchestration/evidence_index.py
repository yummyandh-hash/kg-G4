# -*- coding: utf-8 -*-
"""
证据来源索引模块

实现细粒度证据溯源，建立可按 chunk_id 查询的证据索引
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import re
from collections import defaultdict

@dataclass
class EvidenceSource:
    """证据来源记录"""
    document_id: str
    chunk_id: str
    evidence_text: str
    source_url: str
    retrieved_at: str
    source_name: str
    source_category: str
    source_region: str
    source_org: str
    source_batch: str
    chunk_type: str
    content: str

class EvidenceIndex:
    """证据来源索引类"""

    def __init__(self, chunks_file: str):
        """
        初始化证据索引

        Args:
            chunks_file: chunks.jsonl文件路径
        """
        self.chunks_file = chunks_file
        self.index: Dict[str, EvidenceSource] = {}
        self._build_index()

    def _build_index(self):
        """构建证据索引"""
        print(f"构建证据索引: {self.chunks_file}")

        with open(self.chunks_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    chunk = json.loads(line)
                    evidence_source = EvidenceSource(
                        document_id=chunk.get('document_id', ''),
                        chunk_id=chunk.get('chunk_id', ''),
                        evidence_text=self._extract_evidence_text(chunk),
                        source_url=chunk.get('source_url', ''),
                        retrieved_at=chunk.get('retrieved_at', ''),
                        source_name=chunk.get('source_name', ''),
                        source_category=chunk.get('source_category', ''),
                        source_region=chunk.get('source_region', ''),
                        source_org=chunk.get('source_org', ''),
                        source_batch=chunk.get('source_batch', ''),
                        chunk_type=chunk.get('chunk_type', ''),
                        content=chunk.get('content', '')
                    )

                    self.index[chunk['chunk_id']] = evidence_source

                except json.JSONDecodeError:
                    print(f"跳过无效行: {line[:50]}...")
                    continue

        print(f"索引构建完成，共 {len(self.index)} 个chunk")

    def _extract_evidence_text(self, chunk: dict) -> str:
        """提取证据文本，区分正文原文与结构化字段拼接的文本"""
        content = chunk.get('content', '')

        # 如果是结构化字段（basic_info, region_info, organization），返回完整内容
        if chunk.get('chunk_type') in ['basic_info', 'region_info', 'organization']:
            return content

        # 对于detail_content，提取实际文本内容（去除HTML标签）
        if chunk.get('chunk_type') == 'detail_content':
            # 简单去除HTML标签
            text = re.sub(r'<[^>]+>', '', content)
            text = re.sub(r'&[a-z]+;', '', text)
            return text.strip()

        return content

    def get_evidence(self, chunk_id: str) -> Optional[EvidenceSource]:
        """
        根据chunk_id获取证据来源

        Args:
            chunk_id: chunk ID

        Returns:
            EvidenceSource: 证据来源信息，如果不存在返回None
        """
        return self.index.get(chunk_id)

    def verify_claim(self, claim: str, chunk_ids: List[str]) -> Dict:
        """
        验证claim与证据的匹配度

        Args:
            claim: 需要验证的claim
            chunk_ids: 引用的chunk ID列表

        Returns:
            Dict: 验证结果，包含标签、置信分数和理由
        """
        if not chunk_ids:
            return {
                "status": "no_evidence",
                "label": "UNSUPPORTED",
                "confidence": 0.0,
                "reason": "没有提供证据"
            }

        # 获取所有证据
        evidences = []
        for chunk_id in chunk_ids:
            evidence = self.get_evidence(chunk_id)
            if evidence:
                evidences.append(evidence)

        if not evidences:
            return {
                "status": "evidence_not_found",
                "label": "UNSUPPORTED",
                "confidence": 0.0,
                "reason": "找不到指定的证据"
            }

        # 实现双通道校验：确定性规则核对 + NLI模型校验
        rule_result = self._rule_based_verification(claim, evidences)
        nli_result = self._nli_verification(claim, evidences)

        # 综合结果
        final_result = self._combine_results(rule_result, nli_result)

        return final_result

    def _rule_based_verification(self, claim: str, evidences: List[EvidenceSource]) -> Dict:
        """确定性规则核对"""
        # 检查批次、地区、类别等结构化字段
        matched_fields = 0
        total_fields = 0

        for evidence in evidences:
            # 检查批次
            if evidence.source_batch and evidence.source_batch in claim:
                matched_fields += 1
            total_fields += 1

            # 检查地区
            if evidence.source_region and evidence.source_region in claim:
                matched_fields += 1
            total_fields += 1

            # 检查类别
            if evidence.source_category and evidence.source_category in claim:
                matched_fields += 1
            total_fields += 1

        if total_fields == 0:
            return {
                "status": "no_structured_fields",
                "matched_fields": 0,
                "total_fields": 0,
                "confidence": 0.0
            }

        rule_confidence = matched_fields / total_fields

        if rule_confidence >= 0.8:
            return {
                "status": "rule_supported",
                "matched_fields": matched_fields,
                "total_fields": total_fields,
                "confidence": rule_confidence
            }
        elif rule_confidence >= 0.5:
            return {
                "status": "rule_partially_supported",
                "matched_fields": matched_fields,
                "total_fields": total_fields,
                "confidence": rule_confidence
            }
        else:
            return {
                "status": "rule_unsupported",
                "matched_fields": matched_fields,
                "total_fields": total_fields,
                "confidence": rule_confidence
            }

    def _nli_verification(self, claim: str, evidences: List[EvidenceSource]) -> Dict:
        """NLI模型校验（模拟实现）"""
        # 这里应该是实际的NLI模型调用
        # 由于没有实际模型，使用模拟逻辑

        # 检查claim是否在证据文本中
        claim_lower = claim.lower()
        evidence_texts = [e.evidence_text.lower() for e in evidences]

        # 计算文本相似度（简化版）
        max_similarity = 0.0
        for text in evidence_texts:
            similarity = self._text_similarity(claim_lower, text.lower())
            if similarity > max_similarity:
                max_similarity = similarity

        # 模拟NLI结果
        if max_similarity >= 0.85:
            return {
                "status": "nli_supported",
                "max_similarity": max_similarity,
                "confidence": max_similarity
            }
        elif max_similarity >= 0.6:
            return {
                "status": "nli_partially_supported",
                "max_similarity": max_similarity,
                "confidence": max_similarity
            }
        else:
            return {
                "status": "nli_unsupported",
                "max_similarity": max_similarity,
                "confidence": max_similarity
            }

    def _text_similarity(self, text1: str, text2: str) -> float:
        """简单的文本相似度计算"""
        # 这里使用简单的子串匹配，实际应使用更复杂的NLI模型
        if text1 in text2 or text2 in text1:
            return 0.9
        elif any(word in text2 for word in text1.split()) or any(word in text1 for word in text2.split()):
            return 0.7
        else:
            return 0.3

    def _combine_results(self, rule_result: Dict, nli_result: Dict) -> Dict:
        """综合规则和NLI结果"""
        # 简单的加权平均
        rule_confidence = rule_result.get('confidence', 0.0)
        nli_confidence = nli_result.get('confidence', 0.0)

        # 加权平均（规则权重0.4，NLI权重0.6）
        combined_confidence = 0.4 * rule_confidence + 0.6 * nli_confidence

        # 确定最终标签
        if combined_confidence >= 0.8:
            label = "SUPPORTED"
            reason = "规则和NLI均支持"
        elif combined_confidence >= 0.5:
            label = "PARTIALLY_SUPPORTED"
            reason = "部分支持"
        else:
            label = "UNSUPPORTED"
            reason = "证据不足"

        return {
            "status": "verified",
            "label": label,
            "confidence": combined_confidence,
            "reason": reason,
            "rule_result": rule_result,
            "nli_result": nli_result,
            "evidences": [
                {
                    "chunk_id": e.chunk_id,
                    "evidence_text": e.evidence_text[:100] + "..." if len(e.evidence_text) > 100 else e.evidence_text,
                    "source_url": e.source_url
                } for e in evidences
            ]
        }


def main():
    """主函数：测试证据索引和验证功能"""
    ROOT = Path(__file__).resolve().parent.parent
    CHUNKS_FILE = ROOT / "data" / "chunks" / "chunks.jsonl"

    if not CHUNKS_FILE.exists():
        print(f"chunks文件不存在: {CHUNKS_FILE}")
        return

    # 创建证据索引
    index = EvidenceIndex(str(CHUNKS_FILE))

    # 测试用例
    test_cases = [
        {
            "claim": "朝鲜族农乐舞属于第一批国家级项目",
            "chunk_ids": ["ihchina_00175424c493_name", "ihchina_00175424c493_region"]
        },
        {
            "claim": "象帽舞是农乐舞的一部分",
            "chunk_ids": ["ihchina_00175424c493_content_9"]
        },
        {
            "claim": "苏绣是第二批国家级项目",
            "chunk_ids": ["ihchina_00175424c493_name"]  # 假设的苏绣chunk
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"Claim: {test_case['claim']}")
        print(f"Chunk IDs: {test_case['chunk_ids']}")

        result = index.verify_claim(test_case['claim'], test_case['chunk_ids'])
        print(f"结果: {result['label']} (置信度: {result['confidence']:.2f})")
        print(f"理由: {result['reason']}")

        if result['evidences']:
            print("证据片段:")
            for evidence in result['evidences']:
                print(f"  - {evidence['chunk_id']}: {evidence['evidence_text']}")
                print(f"    来源: {evidence['source_url']}")


if __name__ == "__main__":
    main()