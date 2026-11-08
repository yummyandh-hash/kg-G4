from __future__ import annotations

# -*- coding: utf-8 -*-
"""
引用校验模块

实现事实级引用校验，提供独立可调用的Python接口
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import re
from pathlib import Path
import json

@dataclass
class VerificationResult:
    """引用校验结果"""
    claim: str
    evidences: List[Dict]
    label: str  # SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED
    confidence: float
    reason: str
    nli_result: Optional[Dict] = None
    llm_result: Optional[Dict] = None

class CitationVerifier:
    """引用校验器"""

    def __init__(self, evidence_index):
        """
        初始化引用校验器

        Args:
            evidence_index: EvidenceIndex实例
        """
        self.evidence_index = evidence_index

    def verify_claim(self, claim: str, chunk_ids: List[str]) -> VerificationResult:
        """
        验证claim与证据的匹配度

        Args:
            claim: 需要验证的claim
            chunk_ids: 引用的chunk ID列表

        Returns:
            VerificationResult: 验证结果
        """
        # 获取证据
        evidences = []
        for chunk_id in chunk_ids:
            evidence = self.evidence_index.get_evidence(chunk_id)
            if evidence:
                evidences.append(evidence)

        if not evidences:
            return VerificationResult(
                claim=claim,
                evidences=[],
                label="UNSUPPORTED",
                confidence=0.0,
                reason="找不到指定的证据"
            )

        # 双通道校验
        nli_result = self._nli_verification(claim, evidences)
        llm_result = self._llm_verification(claim, evidences)

        # 综合结果
        final_result = self._combine_results(nli_result, llm_result)

        return VerificationResult(
            claim=claim,
            evidences=[
                {
                    "chunk_id": e.chunk_id,
                    "evidence_text": e.evidence_text[:100] + "..." if len(e.evidence_text) > 100 else e.evidence_text,
                    "source_url": e.source_url
                } for e in evidences
            ],
            label=final_result["label"],
            confidence=final_result["confidence"],
            reason=final_result["reason"],
            nli_result=nli_result,
            llm_result=llm_result
        )

    def _nli_verification(self, claim: str, evidences: List[EvidenceSource]) -> Dict:
        """NLI模型校验"""
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
                "status": "supported",
                "max_similarity": max_similarity,
                "confidence": max_similarity,
                "reason": "文本匹配度高"
            }
        elif max_similarity >= 0.6:
            return {
                "status": "partially_supported",
                "max_similarity": max_similarity,
                "confidence": max_similarity,
                "reason": "部分文本匹配"
            }
        else:
            return {
                "status": "unsupported",
                "max_similarity": max_similarity,
                "confidence": max_similarity,
                "reason": "文本匹配度低"
            }

    def _llm_verification(self, claim: str, evidences: List[EvidenceSource]) -> Dict:
        """LLM复核（模拟实现）"""
        # 这里应该是实际的LLM调用
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

        # 模拟LLM结果
        if max_similarity >= 0.85:
            return {
                "status": "supported",
                "max_similarity": max_similarity,
                "confidence": max_similarity,
                "reason": "LLM判断支持"
            }
        elif max_similarity >= 0.6:
            return {
                "status": "partially_supported",
                "max_similarity": max_similarity,
                "confidence": max_similarity,
                "reason": "LLM判断部分支持"
            }
        else:
            return {
                "status": "unsupported",
                "max_similarity": max_similarity,
                "confidence": max_similarity,
                "reason": "LLM判断不支持"
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

    def _combine_results(self, nli_result: Dict, llm_result: Dict) -> Dict:
        """综合NLI和LLM结果"""
        # 简单的加权平均
        nli_confidence = nli_result.get('confidence', 0.0)
        llm_confidence = llm_result.get('confidence', 0.0)

        # 加权平均（NLI权重0.6，LLM权重0.4）
        combined_confidence = 0.6 * nli_confidence + 0.4 * llm_confidence

        # 确定最终标签
        if combined_confidence >= 0.8:
            label = "SUPPORTED"
            reason = "NLI和LLM均支持"
        elif combined_confidence >= 0.5:
            label = "PARTIALLY_SUPPORTED"
            reason = "部分支持"
        else:
            label = "UNSUPPORTED"
            reason = "证据不足"

        return {
            "label": label,
            "confidence": combined_confidence,
            "reason": reason
        }

    def get_evidence(self, chunk_id: str) -> Optional[Dict]:
        """
        根据chunk_id获取证据信息

        Args:
            chunk_id: chunk ID

        Returns:
            Dict: 证据信息，如果不存在返回None
        """
        evidence = self.evidence_index.get_evidence(chunk_id)
        if not evidence:
            return None

        return {
            "chunk_id": evidence.chunk_id,
            "evidence_text": evidence.evidence_text[:200] + "..." if len(evidence.evidence_text) > 200 else evidence.evidence_text,
            "source_url": evidence.source_url,
            "source_name": evidence.source_name,
            "source_category": evidence.source_category,
            "source_region": evidence.source_region,
            "source_batch": evidence.source_batch
        }


def main():
    """主函数：测试引用校验功能"""
    # 假设已经创建了EvidenceIndex
    # evidence_index = EvidenceIndex("data/chunks/chunks.jsonl")
    # verifier = CitationVerifier(evidence_index)

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

    print("引用校验测试用例:")
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"Claim: {test_case['claim']}")
        print(f"Chunk IDs: {test_case['chunk_ids']}")

        # 这里应该调用verifier.verify_claim，但由于没有实际索引，只展示格式
        print("结果格式:")
        print("  - label: SUPPORTED/PARTIALLY_SUPPORTED/UNSUPPORTED")
        print("  - confidence: 0.0-1.0")
        print("  - reason: 简短判断理由")
        print("  - evidences: 证据列表")


if __name__ == "__main__":
    main()
