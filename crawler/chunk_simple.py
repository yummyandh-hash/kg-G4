# -*- coding: utf-8 -*-
"""
简化版分块脚本
将清洗后的文档分块用于知识图谱构建
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_DIR = ROOT / "data" / "clean" / "documents"
CHUNK_DIR = ROOT / "data" / "chunks"

def chunk_document(doc: dict) -> list[dict]:
    """
    将单个文档分块

    分块策略：
    1. 如果内容超过512字符，按段落分割
    2. 每个块保留原始文档的provenance信息
    3. 为每个块生成唯一的chunk_id
    """
    chunks = []

    # 基本信息（每个块都有）
    base_info = {
        "source_name": doc["name"],
        "source_category": doc["category"],
        "source_region": doc["region"],
        "source_org": doc["org"],
        "source_url": doc["source_url"],
        "retrieved_at": doc["retrieved_at"],
        "document_id": doc["document_id"],
        "source_batch": doc["batch"]
    }

    # 项目编号和名称作为第一个块
    chunk1 = {
        "chunk_id": f"{doc['document_id']}_name",
        "chunk_type": "basic_info",
        "content": f"项目名称：{doc['name']}\n项目编号：{doc['number']}\n批次：{doc['batch']}\n类别：{doc['category']}",
        **base_info
    }
    chunks.append(chunk1)

    # 地区信息作为第二个块
    if doc["region"]:
        chunk2 = {
            "chunk_id": f"{doc['document_id']}_region",
            "chunk_type": "region_info",
            "content": f"申报地区：{doc['region']}\n地区简称：{doc['region_norm']}",
            **base_info
        }
        chunks.append(chunk2)

    # 保护单位作为第三个块
    if doc["org"]:
        chunk3 = {
            "chunk_id": f"{doc['document_id']}_org",
            "chunk_type": "organization",
            "content": f"保护单位：{doc['org']}",
            **base_info
        }
        chunks.append(chunk3)

    # 详细内容作为第四个块（如果有内容）
    if doc["body"]:
        # 如果内容很长，按句子分割
        content = doc["body"]
        if len(content) > 500:
            sentences = content.split("。")
            for i, sentence in enumerate(sentences):
                if sentence.strip():
                    chunk = {
                        "chunk_id": f"{doc['document_id']}_content_{i+1}",
                        "chunk_type": "detail_content",
                        "content": sentence.strip() + "。",
                        **base_info
                    }
                    chunks.append(chunk)
        else:
            chunk4 = {
                "chunk_id": f"{doc['document_id']}_content",
                "chunk_type": "detail_content",
                "content": content,
                **base_info
            }
            chunks.append(chunk4)

    return chunks

def main():
    """主函数"""
    # 创建输出目录
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)

    # 读取所有清洗后的文档
    all_chunks = []

    print("开始分块...")
    for doc_file in DOC_DIR.glob("*.json"):
        print(f"处理: {doc_file.name}")

        # 读取文档
        with doc_file.open(encoding="utf-8") as f:
            doc = json.load(f)

        # 分块
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)

        print(f"  生成 {len(chunks)} 个块")

    # 写入分块结果
    with (CHUNK_DIR / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # 写入统计信息
    stats = {
        "total_documents": len(list(DOC_DIR.glob("*.json"))),
        "total_chunks": len(all_chunks),
        "chunk_types": {}
    }

    # 统计 chunk 类型
    for chunk in all_chunks:
        chunk_type = chunk["chunk_type"]
        stats["chunk_types"][chunk_type] = stats["chunk_types"].get(chunk_type, 0) + 1

    with (CHUNK_DIR / "stats.json").open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n分块完成！")
    print(f"总文档数: {stats['total_documents']}")
    print(f"总块数: {stats['total_chunks']}")
    print("分块类型统计:")
    for chunk_type, count in stats["chunk_types"].items():
        print(f"  {chunk_type}: {count}")

    print(f"\n数据保存在: {CHUNK_DIR}")
    print("文件列表:")
    for file in CHUNK_DIR.glob("*"):
        print(f"  - {file.name}")

if __name__ == "__main__":
    main()