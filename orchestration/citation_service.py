# -*- coding: utf-8 -*-
"""
引用服务主接口

提供与A/E对接的引用校验服务
"""

from orchestration.evidence_index import EvidenceIndex
from orchestration.citation_verifier import CitationVerifier
from typing import Dict, List, Optional
import json
from pathlib import Path

class CitationService:
    """引用服务类"""

    def __init__(self, chunks_file: str):
        """
        初始化引用服务

        Args:
            chunks_file: chunks.jsonl文件路径
        """
        self.evidence_index = EvidenceIndex(chunks_file)
        self.verifier = CitationVerifier(self.evidence_index)

    def get_evidence(self, chunk_id: str) -> Optional[Dict]:
        """
        根据chunk_id获取证据信息

        Args:
            chunk_id: chunk ID

        Returns:
            Dict: 证据信息，如果不存在返回None
        """
        return self.verifier.get_evidence(chunk_id)

    def verify_claim(self, claim: str, chunk_ids: List[str]) -> Dict:
        """
        验证claim与证据的匹配度

        Args:
            claim: 需要验证的claim
            chunk_ids: 引用的chunk ID列表

        Returns:
            Dict: 验证结果
        """
        result = self.verifier.verify_claim(claim, chunk_ids)

        return {
            "claim": result.claim,
            "label": result.label,
            "confidence": result.confidence,
            "reason": result.reason,
            "evidences": result.evidences,
            "nli_result": result.nli_result,
            "llm_result": result.llm_result
        }

    def verify_multiple_claims(self, claims_with_evidence: List[Dict]) -> List[Dict]:
        """
        验证多个claim（每个claim可能包含多个事实）

        Args:
            claims_with_evidence: 列表，每个元素包含claim和对应的chunk_ids

        Returns:
            List[Dict]: 验证结果列表
        """
        results = []
        for item in claims_with_evidence:
            claim = item.get("claim", "")
            chunk_ids = item.get("chunk_ids", [])

            result = self.verify_claim(claim, chunk_ids)
            results.append(result)

        return results


def main():
    """主函数：测试引用服务"""
    ROOT = Path(__file__).resolve().parent.parent
    CHUNKS_FILE = ROOT / "data" / "chunks" / "chunks.jsonl"

    if not CHUNKS_FILE.exists():
        print(f"chunks文件不存在: {CHUNKS_FILE}")
        return

    # 创建引用服务
    service = CitationService(str(CHUNKS_FILE))

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

    print("引用服务测试:")
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"Claim: {test_case['claim']}")
        print(f"Chunk IDs: {test_case['chunk_ids']}")

        result = service.verify_claim(test_case['claim'], test_case['chunk_ids'])
        print(f"结果: {result['label']} (置信度: {result['confidence']:.2f})")
        print(f"理由: {result['reason']}")

        if result['evidences']:
            print("证据片段:")
            for evidence in result['evidences']:
                print(f"  - {evidence['chunk_id']}: {evidence['evidence_text']}")
                print(f"    来源: {evidence['source_url']}")


if __name__ == "__main__":
    main()
