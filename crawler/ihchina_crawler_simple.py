# -*- coding: utf-8 -*-
"""
ihchina.cn 国家级非遗名录爬虫 V3 - 简化版（成员 B）
"""

import json
import re
import time
from pathlib import Path
import requests

# 预览模式
PREVIEW_MODE = True

# 配置
BASE_URL = "https://www.ihchina.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kg-g5-course-project/3.0",
}
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

def get_categories():
    """获取类别列表"""
    print("\n=== 获取类别列表 ===")
    try:
        resp = requests.get(BASE_URL + "/project.html", headers=HEADERS, timeout=20)
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
        print(f"错误: {e}")
        return []

def crawl_category(category_id, category_name):
    """爬取单个类别"""
    print(f"\n=== 处理类别 {category_id}: {category_name} ===")

    # 创建目录
    category_dir = RAW_DIR / f"category_{category_id}"
    category_dir.mkdir(parents=True, exist_ok=True)

    # 限制页数
    max_pages = 1 if PREVIEW_MODE else None
    page = 1

    while True:
        if max_pages and page > max_pages:
            print("[预览模式] 达到页数限制")
            break

        params = {
            "p": str(page),
            "limit": "10",
        }

        try:
            print(f"[第{page}页] 请求中...")
            resp = requests.get(BASE_URL + "/getProject.html", params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()

            data = resp.json()
            projects = data.get("list", [])

            if not projects:
                print("无数据，停止")
                break

            print(f"获取到 {len(projects)} 个项目")

            # 保存项目
            for project in projects:
                record = {
                    "category_id": category_id,
                    "category_name": category_name,
                    "project_id": str(project.get("id", "")),
                    "project_name": project.get("name", ""),
                    "page": page,
                    "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                    "project_data": project
                }

                # 保存到manifest
                manifest = category_dir / "manifest.jsonl"
                with manifest.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

                # 打印信息
                print(f"  项目: {project.get('name', '')}")

            page += 1
            time.sleep(1.5)

        except Exception as e:
            print(f"错误: {e}")
            break

    print(f"类别 {category_id} 完成")

def main():
    """主函数"""
    print("=== 非遗名录爬虫 V3 ===")
    print(f"模式: {'预览模式' if PREVIEW_MODE else '完整模式'}")

    # 创建目录
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 获取类别
    categories = get_categories()

    if not categories:
        print("未获取到类别")
        return

    # 限制类别数
    if PREVIEW_MODE:
        categories = categories[:2]

    # 爬取
    for i, (cat_id, cat_name) in enumerate(categories):
        print(f"\n[进度] {i+1}/{len(categories)}")
        crawl_category(cat_id, cat_name)

        if i < len(categories) - 1:
            time.sleep(3)

    print("\n爬虫完成")

    if not PREVIEW_MODE:
        print("下一步: python crawler/clean.py")

if __name__ == "__main__":
    main()