# -*- coding: utf-8 -*-
"""
专门爬取传统美术类（类别16）的完整数据
1557个项目，3610个子项
"""

import json
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

def crawl_traditional_art():
    """爬取传统美术类"""
    print("=== 开始爬取传统美术类数据 ===")
    print("预计：1557个项目，3610个子项")

    category_id = "16"
    category_name = "传统美术"

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

    # 总页数
    total_pages = 722
    start_page = max_page + 1
    total_projects = 0
    page_count = 0

    print(f"将从第 {start_page} 页开始爬取，到第 {total_pages} 页")

    # 分批处理，避免一次运行太久
    batch_size = 50
    for batch_start in range(start_page, total_pages + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, total_pages)
        print(f"\n=== 批次 {batch_start}-{batch_end}/{total_pages} ===")

        for page in range(batch_start, batch_end + 1):
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

                if resp.content == 115:
                    print(f"  [结束] 第{page}页无数据，停止")
                    break

                data = resp.json()

                # 获取项目列表
                projects = data.get("list", [])

                if not projects:
                    print(f"  [结束] 第{page}页无数据，停止")
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

            except Exception as e:
                print(f"  [错误] 第{page}页请求失败: {e}")
                continue

        # 批次间休息
        if batch_end < total_pages:
            print(f"\n批次 {batch_start}-{batch_end} 完成，休息10秒...")
            time.sleep(10)

    print(f"\n传统美术类爬取完成！")
    print(f"总页数: {page_count}")
    print(f"总项目数: {total_projects}")
    return total_projects

def main():
    """主函数"""
    print("=== 非遗名录传统美术类完整爬虫 ===")
    print("目标：获取所有传统美术类项目")

    # 创建目录
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 爬取数据
    total_projects = crawl_traditional_art()

    if total_projects > 0:
        # 更新总manifest
        print(f"\n=== 更新总manifest ===")
        all_records = []

        # 读取所有类别manifest
        for category_dir in RAW_DIR.glob("category_*"):
            if category_dir.is_dir():
                manifest = category_dir / "manifest.jsonl"
                if manifest.exists():
                    content = manifest.read_text(encoding="utf-8")
                    for line in content.strip().split('\n'):
                        if line:
                            all_records.append(json.loads(line))

        # 排序并写入
        if all_records:
            all_records.sort(key=lambda x: (int(x["category_id"]), x["page"]))

            with MANIFEST.open("w", encoding="utf-8") as f:
                for record in all_records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

            # 生成统计
            stats = {
                "crawl_time": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
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

            print(f"\n[完成] 总项目数: {len(all_records)}")
            print("下一步: python crawler/clean_simple.py")
        else:
            print("\n[错误] 合并manifest失败")
    else:
        print("\n[错误] 未获取到任何数据")

if __name__ == "__main__":
    main()