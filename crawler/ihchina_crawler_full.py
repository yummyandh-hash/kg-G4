# -*- coding: utf-8 -*-
"""
ihchina.cn 国家级非遗名录爬虫 - 完整版（成员 B）

功能：获取所有1557个项目和3610个子项
"""

import json
import re
import time
from pathlib import Path
import requests

# 配置
PREVIEW_MODE = False  # 完整模式
BASE_URL = "https://www.ihchina.cn"
REQUEST_INTERVAL = 1.5
DETAIL_INTERVAL = 2.0
TIMEOUT = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kg-g5-course-project/3.0",
}
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.jsonl"

def get_all_categories():
    """获取所有类别"""
    print("=== 获取所有类别 ===")

    try:
        resp = requests.get(BASE_URL + "/project.html", headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        # 提取类别
        option_pattern = r'<option[^>]*value\s*=\s*["\'](\d+)["\'][^>]*>([^<]+)</option>'
        matches = re.findall(option_pattern, resp.text)

        categories = []
        for cat_id, cat_name in matches:
            if not cat_name.isdigit() and len(cat_name.strip()) >= 2:
                categories.append((cat_id, cat_name.strip()))

        categories = list(dict.fromkeys(categories))
        categories.sort(key=lambda x: int(x[0]))

        print(f"找到 {len(categories)} 个类别")
        return categories
    except Exception as e:
        print(f"获取类别失败: {e}")
        return []

def crawl_all_data():
    """爬取所有数据"""
    print("=== 开始完整爬取 ===")
    print(f"模式: {'完整模式' if not PREVIEW_MODE else '预览模式'}")

    categories = get_all_categories()
    if not categories:
        print("未获取到类别")
        return

    all_records = []

    for i, (cat_id, cat_name) in enumerate(categories):
        print(f"\n[进度] {i+1}/{len(categories)} - {cat_name}")

        # 获取该类别的总页数
        params = {
            "p": "1",
            "category_id": cat_id,
            "limit": "10"
        }

        try:
            resp = requests.get(BASE_URL + "/getProject.html", params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            total_pages = int(data.get("links", {}).get("end", {}).get("text", "1").strip("...").strip())
            total_projects = data.get("total", 0)
            print(f"  总页数: {total_pages}, 总项目数: {total_projects}")

            # 爬取所有页
            for page in range(1, total_pages + 1):
                params["p"] = str(page)

                # 检查是否已存在
                category_dir = RAW_DIR / f"category_{cat_id}"
                category_manifest = category_dir / "manifest.jsonl"

                # 跳过已处理的页
                if category_manifest.exists():
                    existing_records = json.loads(category_manifest.read_text(encoding="utf-8"))
                    max_page = max(r["page"] for r in existing_records) if existing_records else 0
                    if page <= max_page:
                        print(f"  [跳过] 第{page}页已处理")
                        continue

                # 请求当前页
                resp = requests.get(BASE_URL + "/getProject.html", params=params, headers=HEADERS, timeout=TIMEOUT)
                resp.raise_for_status()

                page_data = resp.json()
                projects = page_data.get("list", [])

                if not projects:
                    print(f"  [结束] 第{page}页无数据")
                    break

                print(f"  [成功] 第{page}页获取到 {len(projects)} 个项目")

                # 处理每个项目
                category_dir.mkdir(parents=True, exist_ok=True)
                for project in projects:
                    # 记录基本信息
                    record = {
                        "category_id": cat_id,
                        "category_name": cat_name,
                        "project_id": str(project.get("id", "")),
                        "project_name": project.get("title", ""),
                        "page": page,
                        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                        "project_data": project
                    }

                    # 保存记录
                    with category_manifest.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

                    all_records.append(record)

                time.sleep(REQUEST_INTERVAL)

        except Exception as e:
            print(f"  [错误] 处理类别 {cat_name} 时出错: {e}")
            continue

    # 合并所有manifest
    if all_records:
        print(f"\n=== 合并所有数据 ===")

        # 排序并写入总manifest
        all_records.sort(key=lambda x: (int(x["category_id"]), x["page"]))

        with MANIFEST.open("w", encoding="utf-8") as f:
            for record in all_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 统计总数
        total_projects = len(all_records)
        print(f"\n[完成] 爬取完成！")
        print(f"总项目数: {total_projects}")
        print(f"数据保存在: {RAW_DIR}")
        print("下一步: python crawler/clean_simple.py")

        # 生成统计信息
        stats = {
            "total_categories": len(categories),
            "total_projects": total_projects,
            "category_stats": {}
        }

        # 统计每个类别的项目数
        for record in all_records:
            cat_id = record["category_id"]
            if cat_id not in stats["category_stats"]:
                stats["category_stats"][cat_id] = 0
            stats["category_stats"][cat_id] += 1

        # 保存统计信息
        stats_path = RAW_DIR / "crawl_stats.json"
        with stats_path.open("w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print("\n分类统计:")
        for cat_id, count in stats["category_stats"].items():
            print(f"  类别 {cat_id}: {count} 个项目")

    else:
        print("\n[错误] 未获取到任何数据")

if __name__ == "__main__":
    crawl_all_data()