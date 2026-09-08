# -*- coding: utf-8 -*-
"""
测试几个关键类别的数据获取
"""

import json
import requests
from pathlib import Path

BASE_URL = "https://www.ihchina.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kg-g5-course-project/3.0",
}

def test_category(category_id, category_name):
    """测试单个类别"""
    print(f"\n=== 测试类别 {category_id}: {category_name} ===")

    params = {
        "p": "1",
        "category_id": category_id,
        "limit": "5"
    }

    try:
        resp = requests.get(BASE_URL + "/getProject.html", params=params, headers=HEADERS, timeout=20)
        print(f"状态码: {resp.status_code}")
        print(f"响应大小: {len(resp.content)} 字节")

        if resp.status_code == 200 and resp.content:
            data = resp.json()
            print(f"响应键: {list(data.keys())}")

            # 尝试获取列表
            projects = None
            for key in ["list", "data", "items", "records", "result"]:
                if key in data:
                    projects = data[key]
                    break

            if projects:
                print(f"成功获取 {len(projects)} 个项目")
                for i, project in enumerate(projects[:3], 1):
                    print(f"  {i}. {project.get('title', project.get('name', '未知'))}")

                # 获取总数信息
                total = data.get("total", "未知")
                links = data.get("links", {})
                end_page = links.get("end", {})
                if "text" in end_page:
                    print(f"  总页数: {end_page['text']}")
                print(f"  总项目数: {total}")
            else:
                print("未找到项目列表")
        else:
            print("响应为空或失败")
            if resp.text:
                print(f"响应内容: {resp.text[:200]}...")

    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    # 测试几个重要的类别
    test_categories = [
        ("1", "第一批"),
        ("16", "传统美术"),
        ("17", "传统音乐"),
        ("23", "传统技艺"),
        ("25", "民俗")
    ]

    for cat_id, cat_name in test_categories:
        test_category(cat_id, cat_name)
        print("\n" + "="*50)