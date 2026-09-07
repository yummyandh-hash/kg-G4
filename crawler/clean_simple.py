# -*- coding: utf-8 -*-
"""
简化版清洗脚本
"""

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DOC_DIR = ROOT / "data" / "clean" / "documents"

def parse_raw(raw_bytes: bytes, content_type: str) -> list[dict]:
    """解析原始响应"""
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = None

    if isinstance(data, dict):
        # 查找列表数据
        for key in ("list", "data", "rows", "records", "result", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        # 检查嵌套结构
        for key in ("data", "result"):
            inner = data.get(key)
            if isinstance(inner, dict):
                for key2 in ("list", "rows", "records"):
                    if isinstance(inner.get(key2), list):
                        return inner[key2]
        return []
    elif isinstance(data, list):
        return data
    return []

def normalize(raw: dict, category_id: str, retrieved_at: str) -> dict:
    """规范化数据"""
    # 从实际数据中提取字段
    name = raw.get("title", "")
    project_num = raw.get("project_num", "")
    province = raw.get("province", "")
    unit = raw.get("unit", "")
    protect_unit = raw.get("protect_unit", "")
    content = raw.get("content", "")

    # 从project_data中提取类别信息
    project_data = raw.get("project_data", {})
    actual_category = project_data.get("type", "第一批")  # 使用实际的type字段
    actual_batch = project_data.get("batch", "2006")

    doc = {
        "name": name,
        "aliases": [],
        "number": project_num,
        "category": actual_category,  # 使用实际的类别
        "batch": actual_batch,       # 使用实际的批次
        "region": province,
        "region_norm": province.replace("省", "").replace("市", "").replace("县", ""),
        "org": unit or protect_unit,
        "body": content,
        "source_url": f"https://www.ihchina.cn/project/{raw.get('id', '')}",
        "document_id": "",
        "chunk_source_page": int(category_id),
        "retrieved_at": retrieved_at,
        "heritage_category": actual_category,  # 添加heritage_category字段
        "raw_category_name": actual_category  # 添加raw_category_name字段
    }

    # 生成document_id
    key = doc["number"] or doc["name"]
    doc["document_id"] = f"ihchina_{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}"
    return doc

def main():
    """主函数"""
    records = []

    # 遍历所有类别目录
    for category_dir in RAW_DIR.glob("category_*"):
        if not category_dir.is_dir():
            continue

        category_id = category_dir.name.replace("category_", "")
        print(f"处理类别 {category_id}...")

        # 读取manifest
        manifest = category_dir / "manifest.jsonl"
        if not manifest.exists():
            continue

        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            meta = json.loads(line)

            # 解析项目数据
            project_data = meta.get("project_data", {})
            records.append(normalize(project_data, category_id, meta["retrieved_at"]))

    if not records:
        print("未找到数据")
        return

    # 去重
    seen = {}
    dup = 0
    for r in records:
        if r["document_id"] in seen:
            dup += 1
            continue
        seen[r["document_id"]] = r

    # 保存
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    for old in DOC_DIR.glob("*.json"):
        old.unlink()

    for doc in seen.values():
        (DOC_DIR / f"{doc['document_id']}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"清洗完成：{len(seen)} 条")

if __name__ == "__main__":
    main()