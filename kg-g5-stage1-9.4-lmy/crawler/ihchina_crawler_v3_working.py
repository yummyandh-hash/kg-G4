# -*- coding: utf-8 -*-
"""
ihchina.cn 国家级非遗名录爬虫 V3 - 工作版（成员 B）

核心功能：
1. 使用正确的参数格式获取数据
2. 支持预览模式和完整模式
3. 自动类别获取
"""

import json
import re
import time
from pathlib import Path
import requests

# ============================== 配置区 ==============================

# 【核心开关】预览模式 = True（调试用） / 完整模式 = False（正式用）
PREVIEW_MODE = True

# 网络配置
BASE_URL = "https://www.ihchina.cn"
REQUEST_INTERVAL = 1.5
DETAIL_INTERVAL = 2.0
TIMEOUT = 20

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kg-g5-course-project/3.0",
}

# 数据存储配置
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.jsonl"

# =====================================================================================

def auto_fetch_categories():
    """自动获取类别列表"""
    print("\n=== 自动获取类别列表 ===")

    # 访问主页获取类别
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

        # 去重并排序
        categories = list(dict.fromkeys(categories))
        categories.sort(key=lambda x: int(x[0]))

        print(f"[成功] 找到 {len(categories)} 个类别")
        for cat_id, cat_name in categories[:10]:  # 显示前10个
            print(f"  ID:{cat_id} - {cat_name}")

        return categories

    except Exception as e:
        print(f"[失败] 获取类别失败: {e}")
        return []

def fetch_category_data(category_id: str, category_name: str):
    """抓取单个类别数据"""
    print(f"\n=== 开始处理类别 {category_id}: {category_name} ===")

    # 创建类别目录
    category_dir = RAW_DIR / f"category_{category_id}"
    category_dir.mkdir(parents=True, exist_ok=True)

    # 预览模式限制
    if PREVIEW_MODE:
        max_pages = 1
        max_projects = 3
        print(f"[预览模式] 只处理前 {max_pages} 页，每类前 {max_projects} 个项目")
    else:
        max_pages = None  # 所有页
        max_projects = None  # 所有项目

    page = 1
    total_projects = 0

    while True:
        if max_pages is not None and page > max_pages:
            print(f"[预览模式] 达到页数限制 {max_pages}，停止")
            break

        # 构建正确参数
        params = {
            "p": str(page),
            "category_id": category_id,
            "limit": "10",
        }

        try:
            print(f"\n[第{page}页] 正在请求...")
            resp = requests.get(BASE_URL + "/getProject.html", params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()

            # 解析响应
            data = resp.json()
            projects = data.get("list", [])

            if not projects:
                print(f"[结束] 第{page}页无数据，停止处理")
                break

            print(f"[成功] 第{page}页获取到 {len(projects)} 个项目")

            # 处理项目
            for project in projects:
                if max_projects is not None and total_projects >= max_projects:
                    print(f"\n[预览模式] 达到项目数量限制 {max_projects}，停止")
                    return

                project_id = str(project.get("id", project.get("number", "unknown")))
                project_name = project.get("name", "未知项目")

                print(f"\n[项目 {total_projects + 1}] {project_name}")
                print(f"编号: {project.get('number', '')}")
                print(f"类型: {project.get('type', '')}")
                print(f"地区: {project.get('region', '')}")

                # 预览模式不保存详情
                if not PREVIEW_MODE:
                    # 保存项目数据
                    record = {
                        "category_id": category_id,
                        "category_name": category_name,
                        "project_id": project_id,
                        "project_name": project_name,
                        "page": page,
                        "endpoint": BASE_URL + "/getProject.html",
                        "params": params,
                        "status_code": resp.status_code,
                        "content_type": resp.headers.get("Content-Type", ""),
                        "byte_size": len(resp.content),
                        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                        "project_data": project
                    }

                    # 保存到类别manifest
                    category_manifest = category_dir / "manifest.jsonl"
                    with category_manifest.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

                total_projects += 1
                time.sleep(DETAIL_INTERVAL)

            page += 1
            time.sleep(REQUEST_INTERVAL)

        except Exception as e:
            print(f"[错误] 第{page}页请求失败: {e}")
            break

    print(f"\n=== 类别 {category_id} 处理完成 ===")
    print(f"总计处理项目数: {total_projects}")

def main():
    """主函数"""
    # 模式提示
    if PREVIEW_MODE:
        print("\n" + "=" * 60)
        print("⚠️ 预览模式激活")
        print("⚠️ 当前模式：预览模式（前2类别×前1页×前3项目）")
        print("⚠️ 不生成文件，仅控制台输出")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("🚀 完整模式激活")
        print("🚀 当前模式：完整模式（全量数据持久化）")
        print("=" * 60)

    print(f"\n开始执行爬虫任务...")

    # 创建数据目录
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 获取类别
    categories = auto_fetch_categories()

    if not categories:
        print("\n[错误] 未获取到类别")
        return

    # 预览模式限制类别
    if PREVIEW_MODE:
        categories = categories[:2]
        print(f"\n[预览模式] 只处理前 {len(categories)} 个类别")

    # 开始爬取
    for i, (category_id, category_name) in enumerate(categories):
        print(f"\n[进度] 正在处理第 {i+1}/{len(categories)} 个类别")
        fetch_category_data(category_id, category_name)

        if i < len(categories) - 1:
            time.sleep(REQUEST_INTERVAL * 2)

    # 完整模式合并manifest
    if not PREVIEW_MODE:
        print("\n[完成] 正在合并所有类别数据...")
        all_records = []

        for category_dir in RAW_DIR.glob("category_*"):
            if category_dir.is_dir():
                manifest = category_dir / "manifest.jsonl"
                if manifest.exists():
                    for line in manifest.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            record = json.loads(line)
                            all_records.append(record)

        # 排序并写入总manifest
        all_records.sort(key=lambda x: (int(x["category_id"]), x["page"]))

        with MANIFEST.open("w", encoding="utf-8") as f:
            for record in all_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"\n[完成] 爬虫任务全部完成！")
        print(f"总项目数: {len(all_records)}")
        print(f"数据保存在: {RAW_DIR}")
        print("下一步: python crawler/clean.py")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()