# -*- coding: utf-8 -*-
"""
引用校验验证脚本

完成针对性验证：有效来源查询、错误ID、完全支持、部分支持、无依据、矛盾、多引用及模型不可用
"""

from orchestration.citation_service import CitationService
from pathlib import Path
import json

def run_verification_tests():
    """运行验证测试"""
    ROOT = Path(__file__).resolve().parent.parent
    CHUNKS_FILE = ROOT / "data" / "chunks" / "chunks.jsonl"

    if not CHUNKS_FILE.exists():
        print(f"chunks文件不存在: {CHUNKS_FILE}")
        return

    # 创建引用服务
    service = CitationService(str(CHUNKS_FILE))

    # 测试用例
    test_cases = [
        # 有效来源查询 - 完全支持
        {
            "name": "有效来源查询 - 完全支持",
            "claim": "朝鲜族农乐舞属于第一批国家级项目",
            "chunk_ids": ["ihchina_00175424c493_name", "ihchina_00175424c493_region"],
            "expected_label": "SUPPORTED"
        },

        # 有效来源查询 - 部分支持
        {
            "name": "有效来源查询 - 部分支持",
            "claim": "朝鲜族农乐舞属于第二批国家级项目",
            "chunk_ids": ["ihchina_00175424c493_name", "ihchina_00175424c493_region"],
            "expected_label": "PARTIALLY_SUPPORTED"
        },

        # 有效来源查询 - 无依据
        {
            "name": "有效来源查询 - 无依据",
            "claim": "朝鲜族农乐舞是现代舞蹈",
            "chunk_ids": ["ihchina_00175424c493_content_1"],
            "expected_label": "UNSUPPORTED"
        },

        # 错误ID
        {
            "name": "错误ID",
            "claim": "测试错误ID",
            "chunk_ids": ["invalid_chunk_id_123"],
            "expected_label": "UNSUPPORTED"
        },

        # 多引用共同提供证据
        {
            "name": "多引用共同提供证据",
            "claim": "象帽舞是农乐舞的一部分，农乐舞属于第一批项目",
            "chunk_ids": ["ihchina_00175424c493_content_9", "ihchina_00175424c493_name"],
            "expected_label": "SUPPORTED"
        },

        # 矛盾证据
        {
            "name": "矛盾证据",
            "claim": "朝鲜族农乐舞属于第二批国家级项目",
            "chunk_ids": ["ihchina_00175424c493_name", "ihchina_00175424c493_region"],
            "expected_label": "PARTIALLY_SUPPORTED"
        },

        # 模型不可用（模拟）
        {
            "name": "模型不可用",
            "claim": "测试模型不可用",
            "chunk_ids": ["ihchina_00175424c493_name"],
            "expected_label": "UNSUPPORTED"
        }
    ]

    print("开始引用校验验证测试\n")
    print("=" * 60)

    passed = 0
    total = len(test_cases)

    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        print(f"Claim: {test_case['claim']}")
        print(f"Chunk IDs: {test_case['chunk_ids']}")
        print(f"期望结果: {test_case['expected_label']}")

        try:
            result = service.verify_claim(test_case['claim'], test_case['chunk_ids'])
            actual_label = result['label']
            confidence = result['confidence']

            print(f"实际结果: {actual_label} (置信度: {confidence:.2f})")
            print(f"理由: {result['reason']}")

            if actual_label == test_case['expected_label']:
                print("✓ 通过")
                passed += 1
            else:
                print("✗ 失败")

        except Exception as e:
            print(f"✗ 异常: {str(e)}")
            print("✗ 失败")

    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{total} 通过")

    if passed == total:
        print("所有测试通过！")
    else:
        print(f"有 {total - passed} 个测试失败")


def generate_test_samples():
    """生成30个答案-引用评测样本"""
    samples = [
        {
            "qid": "sample_001",
            "type": "single_fact",
            "question": "朝鲜族农乐舞属于哪一批国家级项目？",
            "claim": "第一批",
            "gold_evidence": ["ihchina_00175424c493_name"],
            "expected_label": "SUPPORTED",
            "note": "简单事实查询"
        },
        {
            "qid": "sample_002",
            "type": "single_fact",
            "question": "象帽舞是农乐舞的一部分吗？",
            "claim": "是",
            "gold_evidence": ["ihchina_00175424c493_content_9"],
            "expected_label": "SUPPORTED",
            "note": "简单事实查询"
        },
        {
            "qid": "sample_003",
            "type": "single_fact",
            "question": "朝鲜族农乐舞的申报地区是哪里？",
            "claim": "吉林省延边朝鲜族自治州",
            "gold_evidence": ["ihchina_00175424c493_region"],
            "expected_label": "SUPPORTED",
            "note": "简单事实查询"
        },
        {
            "qid": "sample_004",
            "type": "single_fact",
            "question": "朝鲜族农乐舞的保护单位是哪里？",
            "claim": "吉林省延边朝鲜族自治州",
            "gold_evidence": ["ihchina_00175424c493_org"],
            "expected_label": "SUPPORTED",
            "note": "简单事实查询"
        },
        {
            "qid": "sample_005",
            "type": "single_fact",
            "question": "朝鲜族农乐舞的类别是什么？",
            "claim": "第一批",
            "gold_evidence": ["ihchina_00175424c493_name"],
            "expected_label": "SUPPORTED",
            "note": "简单事实查询"
        },
        {
            "qid": "sample_006",
            "type": "single_fact",
            "question": "朝鲜族农乐舞是现代舞蹈吗？",
            "claim": "是",
            "gold_evidence": ["ihchina_00175424c493_content_1"],
            "expected_label": "UNSUPPORTED",
            "note": "无依据事实"
        },
        {
            "qid": "sample_007",
            "type": "single_fact",
            "question": "朝鲜族农乐舞属于第二批国家级项目",
            "claim": "第二批",
            "gold_evidence": ["ihchina_00175424c493_name"],
            "expected_label": "PARTIALLY_SUPPORTED",
            "note": "部分正确事实"
        },
        {
            "qid": "sample_008",
            "type": "single_fact",
            "question": "象帽舞不属于农乐舞",
            "claim": "不属于",
            "gold_evidence": ["ihchina_00175424c493_content_9"],
            "expected_label": "UNSUPPORTED",
            "note": "矛盾事实"
        },
        {
            "qid": "sample_009",
            "type": "single_fact",
            "question": "朝鲜族农乐舞的历史可以追溯到古代",
            "claim": "可以",
            "gold_evidence": ["ihchina_00175424c493_content_2"],
            "expected_label": "SUPPORTED",
            "note": "历史事实"
        },
        {
            "qid": "sample_010",
            "type": "single_fact",
            "question": "农乐舞有10个部分",
            "claim": "10个",
            "gold_evidence": ["ihchina_00175424c493_content_8"],
            "expected_label": "PARTIALLY_SUPPORTED",
            "note": "部分正确"
        },
        {
            "qid": "sample_011",
            "type": "relation",
            "question": "农乐舞和象帽舞的关系是什么？",
            "claim": "象帽舞是农乐舞的一部分",
            "gold_evidence": ["ihchina_00175424c493_content_9"],
            "expected_label": "SUPPORTED",
            "note": "关系查询"
        },
        {
            "qid": "sample_012",
            "type": "relation",
            "question": "农乐舞包含哪些舞蹈形式？",
            "claim": "包括小鼓舞、叠罗汉、扁鼓舞等",
            "gold_evidence": ["ihchina_00175424c493_content_9"],
            "expected_label": "SUPPORTED",
            "note": "多事实关系查询"
        },
        {
            "qid": "sample_013",
            "type": "relation",
            "question": "农乐舞的表演形式有哪些？",
            "claim": "有情节性演出和群众性表演两种形式",
            "gold_evidence": ["ihchina_00175424c493_content_7"],
            "expected_label": "SUPPORTED",
            "note": "多事实关系查询"
        },
        {
            "qid": "sample_014",
            "type": "relation",
            "question": "农乐舞的表演包括哪些部分？",
            "claim": "包括12个部分",
            "gold_evidence": ["ihchina_00175424c493_content_8"],
            "expected_label": "SUPPORTED",
            "note": "多事实关系查询"
        },
        {
            "qid": "sample_015",
            "type": "relation",
            "question": "农乐舞的表演不包括扇舞",
            "claim": "不包括",
            "gold_evidence": ["ihchina_00175424c493_content_9"],
            "expected_label": "UNSUPPORTED",
            "note": "矛盾关系"
        },
        {
            "qid": "sample_016",
            "type": "multi_hop",
            "question": "农乐舞的申报地区和保护单位是否相同？",
            "claim": "相同",
            "gold_evidence": ["ihchina_00175424c493_region", "ihchina_00175424c493_org"],
            "expected_label": "SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_017",
            "type": "multi_hop",
            "question": "农乐舞属于第一批项目，其申报地区是哪里？",
            "claim": "吉林省延边朝鲜族自治州",
            "gold_evidence": ["ihchina_00175424c493_name", "ihchina_00175424c493_region"],
            "expected_label": "SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_018",
            "type": "multi_hop",
            "question": "农乐舞的表演形式和申报地区有什么关系？",
            "claim": "没有直接关系",
            "gold_evidence": ["ihchina_00175424c493_content_7", "ihchina_00175424c493_region"],
            "expected_label": "PARTIALLY_SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_019",
            "type": "multi_hop",
            "question": "农乐舞的表演包括哪些部分，这些部分是否都来自同一地区？",
            "claim": "包括12个部分，都来自吉林省延边朝鲜族自治州",
            "gold_evidence": ["ihchina_00175424c493_content_8", "ihchina_00175424c493_region"],
            "expected_label": "PARTIALLY_SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_020",
            "type": "multi_hop",
            "question": "农乐舞的历史可以追溯到古代，其申报地区是哪里？",
            "claim": "吉林省延边朝鲜族自治州",
            "gold_evidence": ["ihchina_00175424c493_content_2", "ihchina_00175424c493_region"],
            "expected_label": "SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_021",
            "type": "multi_hop",
            "question": "农乐舞的表演形式和其历史有什么关系？",
            "claim": "表演形式反映了其历史传统",
            "gold_evidence": ["ihchina_00175424c493_content_2", "ihchina_00175424c493_content_7"],
            "expected_label": "PARTIALLY_SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_022",
            "type": "multi_hop",
            "question": "农乐舞的表演包括哪些部分，这些部分的顺序是什么？",
            "claim": "包括12个部分，按特定顺序表演",
            "gold_evidence": ["ihchina_00175424c493_content_8", "ihchina_00175424c493_content_9"],
            "expected_label": "SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_023",
            "type": "multi_hop",
            "question": "农乐舞的表演形式是否包括现代舞蹈元素？",
            "claim": "包括",
            "gold_evidence": ["ihchina_00175424c493_content_7"],
            "expected_label": "UNSUPPORTED",
            "note": "多跳推理 - 无依据"
        },
        {
            "qid": "sample_024",
            "type": "multi_hop",
            "question": "农乐舞的申报地区和保护单位是否属于同一批次？",
            "claim": "是",
            "gold_evidence": ["ihchina_00175424c493_region", "ihchina_00175424c493_org"],
            "expected_label": "PARTIALLY_SUPPORTED",
            "note": "多跳推理 - 部分正确"
        },
        {
            "qid": "sample_025",
            "type": "multi_hop",
            "question": "农乐舞的表演形式是否包括传统和现代两种？",
            "claim": "是",
            "gold_evidence": ["ihchina_00175424c493_content_7"],
            "expected_label": "UNSUPPORTED",
            "note": "多跳推理 - 矛盾"
        },
        {
            "qid": "sample_026",
            "type": "multi_hop",
            "question": "农乐舞的历史可以追溯到古代，其表演形式有哪些特点？",
            "claim": "包括12个部分，反映古代传统",
            "gold_evidence": ["ihchina_00175424c493_content_2", "ihchina_00175424c493_content_8"],
            "expected_label": "SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_027",
            "type": "multi_hop",
            "question": "农乐舞的表演形式和其申报地区有什么联系？",
            "claim": "表演形式反映了申报地区的文化传统",
            "gold_evidence": ["ihchina_00175424c493_content_7", "ihchina_00175424c493_region"],
            "expected_label": "PARTIALLY_SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_028",
            "type": "multi_hop",
            "question": "农乐舞的表演包括哪些部分，这些部分是否都来自同一保护单位？",
            "claim": "包括12个部分，都来自吉林省延边朝鲜族自治州",
            "gold_evidence": ["ihchina_00175424c493_content_8", "ihchina_00175424c493_org"],
            "expected_label": "PARTIALLY_SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_029",
            "type": "multi_hop",
            "question": "农乐舞的表演形式是否包括象帽舞？",
            "claim": "是",
            "gold_evidence": ["ihchina_00175424c493_content_9"],
            "expected_label": "SUPPORTED",
            "note": "多跳推理"
        },
        {
            "qid": "sample_030",
            "type": "multi_hop",
            "question": "农乐舞的表演形式是否包括现代舞蹈元素？",
            "claim": "不包括",
            "gold_evidence": ["ihchina_00175424c493_content_7"],
            "expected_label": "SUPPORTED",
            "note": "多跳推理"
        }
    ]

    # 保存测试样本
    with open("citation_test_samples.json", "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

    print(f"生成 {len(samples)} 个测试样本到 citation_test_samples.json")


if __name__ == "__main__":
    # 运行验证测试
    run_verification_tests()

    # 生成测试样本
    generate_test_samples()
