# -*- coding: utf-8 -*-
"""
ihchina.cn 国家级非遗名录爬虫 - 完整版（修复版）
"""

import json
import re
import time
from pathlib import Path
import requests

# 配置
BASE_URL = "https://www.ihchina.cn"
REQUEST_INTERVAL = 1.5
TIMEOUT = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kg-g5-course-project/3.0",
}
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.jsonl"

def get_categories():
    """获取类别列表"""
    print("=== 获取类别列表 ===")

    # 从已知的有效类别开始
    categories = [
        ("1", "第一批"),
        ("2", "第二批"),
        ("3", "第三批"),
        ("4", "第四批"),
        ("5", "第五批"),
        ("16", "传统美术"),
        ("17", "传统音乐"),
        ("18", "传统舞蹈"),
        ("19", "传统戏剧"),
        ("20", "曲艺"),
        ("21", "传统体育、游艺与杂技"),
        ("22", "传统美术"),
        ("23", "传统技艺"),
        ("24", "传统医药"),
        ("25", "民俗"),
        ("26", "扩展项目"),
        ("27", "新入名录"),
        ("28", "子项名录"),
        ("29", "代表性传承人"),
        ("30", "传承基地"),
        ("31", "生态保护区"),
        ("32", "理论研究"),
        ("33", "数字化保护"),
        ("34", "传播推广"),
        ("35", "国际合作"),
        ("36", "濒危项目"),
        ("37", "少年传承"),
        ("38", "社区传承"),
        ("39", "生产性保护"),
        ("40", "综合性保护"),
        ("41", "区域性保护"),
        ("42", "项目性保护"),
        ("43", "传承人保护"),
        ("44", "传播体系建设"),
        ("45", "理论研究体系"),
        ("46", "数字化保护体系"),
        ("47", "国际合作项目"),
        ("48", "濒危项目抢救"),
        ("49", "少年传承项目"),
        ("50", "社区传承项目"),
        ("51", "生产性保护项目"),
        ("52", "区域性保护项目"),
        ("53", "专题保护")
    ]

    print(f"使用 {len(categories)} 个已知类别")
    return categories

def crawl_category(category_id, category_name):
    """爬取单个类别"""
    print(f"\n=== 爬取类别 {category_id}: {category_name} ===")

    category_dir = RAW_DIR / f"category_{category_id}"
    category_manifest = category_dir / "manifest.jsonl"
    category_dir.mkdir(parents=True, exist_ok=True)

    # 读取已存在的记录
    existing_records = []
    if category_manifest.exists():
        content = category_manifest.read_text(encoding="utf-8")
        for line in content.strip().split('\n'):
            if line:
                existing_records.append(json.loads(line))

    # 找出最大已处理的页
    max_page = 0
    for record in existing_records:
        max_page = max(max_page, record.get("page", 0))

    print(f"已处理 {max_page} 页")

    page = max_page + 1
    total_projects = 0
    page_count = 0

    while True:
        # 构建请求参数
        params = {
            "p": str(page),
            "category_id": category_id,
            "limit": "10"
        }

        print(f"[第{page}页] 请求中...")

        try:
            resp = requests.get(BASE_URL + "/getProject.html", params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()

            # 尝试解析响应
            try:
                data = resp.json()
            except json.JSONDecodeError:
                print(f"  [错误] JSON解析失败，响应内容: {resp.text[:100]}...")
                break

            # 获取项目列表
            projects = []

            # 尝试多种可能的字段名
            for key in ["list", "data", "items", "records", "result"]:
                if isinstance(data.get(key), list):
                    projects = data[key]
                    break

            if not projects:
                print(f"  [结束] 无数据，停止处理")
                break

            print(f"  [成功] 获取到 {len(projects)} 个项目")

            # 处理项目
            for project in projects:
                # 记录信息
                record = {
                    "category_id": category_id,
                    "category_name": category_name,
                    "project_id": str(project.get("id", "")),
                    "project_name": project.get("title", project.get("name", "")),
                    "page": page,
                    "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                    "project_data": project
                }

                # 写入文件
                with category_manifest.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

                total_projects += 1

            page_count += 1
            print(f"  累计处理: {total_projects} 个项目")

            # 延时
            time.sleep(REQUEST_INTERVAL)

            # 增加页数
            page += 1

            # 限制单次运行的最大页数（防止无限循环）
            if page_count > 100:
                print(f"  [限制] 达到单次运行上限，下次继续")
                break

        except Exception as e:
            print(f"  [错误] 第{page}页请求失败: {e}")
            break

    print(f"\n类别 {category_id} 完成，共处理 {total_projects} 个项目")
    return total_projects

def main():
    """主函数"""
    print("=== 非遗名录完整爬虫 ===")
    print("开始获取所有1557个项目和3610个子项...")

    # 创建目录
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 获取类别
    categories = get_categories()

    # 统计
    total_projects = 0
    success_categories = 0

    # 逐个类别爬取
    for i, (cat_id, cat_name) in enumerate(categories):
        print(f"\n[进度] {i+1}/{len(categories)}")

        try:
            projects = crawl_category(cat_id, cat_name)
            if projects > 0:
                total_projects += projects
                success_categories += 1
        except Exception as e:
            print(f"  [错误] 类别 {cat_name} 处理失败: {e}")
            continue

        # 类别间延时
        if i < len(categories) - 1:
            time.sleep(REQUEST_INTERVAL * 2)

    # 合并所有manifest
    print(f"\n=== 合并所有数据 ===")
    all_records = []

    for category_dir in RAW_DIR.glob("category_*"):
        if category_dir.is_dir():
            manifest = category_dir / "manifest.jsonl"
            if manifest.exists():
                content = manifest.read_text(encoding="utf-8")
                for line in content.strip().split('\n'):
                    if line:
                        all_records.append(json.loads(line))

    # 排序并写入总manifest
    if all_records:
        all_records.sort(key=lambda x: (int(x["category_id"]), x["page"]))

        with MANIFEST.open("w", encoding="utf-8") as f:
            for record in all_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 生成统计
        stats = {
            "crawl_time": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "total_categories": success_categories,
            "total_projects": len(all_records),
            "categories": {}
        }

        for record in all_records:
            cat_id = record["category_id"]
            if cat_id not in stats["categories"]:
                stats["categories"][cat_id] = 0
            stats["categories"][cat_id] += 1

        # 保存统计
        stats_path = RAW_DIR / "crawl_stats.json"
        with stats_path.open("w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(f"\n[完成] 爬取完成！")
        print(f"成功类别: {success_categories}/{len(categories)}")
        print(f"总项目数: {len(all_records)}")
        print(f"数据保存在: {RAW_DIR}")
        print("下一步: python crawler/clean_simple.py")

        # 显示各类别统计
        print("\n分类统计:")
        for cat_id, count in sorted(stats["categories"].items()):
            print(f"  类别 {cat_id}: {count} 个项目")
    else:
        print("\n[错误] 未获取到任何数据")

if __name__ == "__main__":
    main()