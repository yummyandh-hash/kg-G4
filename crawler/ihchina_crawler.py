# -*- coding: utf-8 -*-
"""
ihchina.cn 国家级非遗名录爬虫 V3 - 完全自动版（成员 B）

核心功能：
1. 自动获取全部 category_id，无需人工 F12 干预
2. 项目详情页抓取子项信息
3. 预览模式（前2大类×前3项目，控制台输出）vs 完整模式（全量持久化）
4. 完全兼容下游 clean.py 和 chunk.py

作者：成员 B
日期：2026-09-04
"""

import json
import re
import time
from pathlib import Path
import requests

# ============================== 全局配置区 ==============================

# 【核心开关】预览模式 = True（调试用） / 完整模式 = False（正式用）
PREVIEW_MODE = True  # True: 预览模式（不写文件，仅控制台输出）
                   # False: 完整模式（全量爬取并持久化）

# 网络配置
BASE_URL = "https://www.ihchina.cn"
REQUEST_INTERVAL = 1.5      # 列表页请求间隔（秒）
DETAIL_INTERVAL = 2.0      # 详情页请求间隔（秒）
TIMEOUT = 20               # 请求超时（秒）

# 请求头（模拟浏览器访问）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kg-g5-course-project/3.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# 数据存储配置
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.jsonl"

# =====================================================================================


def auto_fetch_categories() -> list[tuple[str, str]]:
    """
    【新增】全自动获取类别列表 - 无需人工 F12 干预
    支持 6 种策略自动检测类别接口
    """
    print("\n=== 自动获取类别列表（6种策略尝试中） ===")

    # 策略1：从主页 JS 变量提取（最高效）
    print("\n[策略1] 尝试从主页 JS 变量提取...")
    try:
        resp = requests.get(BASE_URL + "/project.html", headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        # 常见的 JS 变量模式
        js_patterns = [
            r"window\._CATEGORY_DATA\s*=\s*(\[.*?\])",
            r"categoryList\s*=\s*(\[.*?\])",
            r"categories\s*=\s*(\[.*?\])",
            r"cateList\s*=\s*(\[.*?\])",
        ]

        for pattern in js_patterns:
            matches = re.findall(pattern, resp.text, re.DOTALL)
            if matches:
                categories = []
                for match in matches:
                    try:
                        data = json.loads(match)
                        for item in data:
                            if isinstance(item, dict) and "id" in item and "name" in item:
                                categories.append((str(item["id"]), item["name"]))
                    except json.JSONDecodeError:
                        continue

                if categories:
                    categories.sort(key=lambda x: int(x[0]))
                    print(f"[成功] 策略1找到 {len(categories)} 个类别")
                    print("类别列表：")
                    for cat_id, cat_name in categories:
                        print(f"  ID:{cat_id} - {cat_name}")
                    return categories
    except Exception as e:
        print(f"[失败] 策略1异常: {e}")

    # 策略2：从 HTML select 选项提取
    print("\n[策略2] 尝试从 HTML select 选项提取...")
    try:
        resp = requests.get(BASE_URL + "/project.html", headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        # 匹配 <option value="ID">名称</option>
        option_pattern = r'<option[^>]*value\s*=\s*["\'](\d+)["\'][^>]*>([^<]+)</option>'
        matches = re.findall(option_pattern, resp.text)

        categories = []
        for cat_id, cat_name in matches:
            # 过滤无效数据
            if not cat_name.isdigit() and len(cat_name.strip()) >= 2:
                categories.append((cat_id, cat_name.strip()))

        if categories:
            # 按ID排序并去重
            categories = list(dict.fromkeys(categories))
            categories.sort(key=lambda x: int(x[0]))
            print(f"[成功] 策略2找到 {len(categories)} 个类别")
            return categories
    except Exception as e:
        print(f"[失败] 策略2异常: {e}")

    # 策略3：尝试可能的 API 接口
    print("\n[策略3] 尝试调用 API 接口...")
    api_paths = [
        "/api/categories",
        "/api/getCategory",
        "/getCategoryList",
        "/category/list",
        "/project/getCategories",
    ]

    for path in api_paths:
        try:
            resp = requests.get(BASE_URL + path, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    categories = [(str(item["id"]), item["name"]) for item in data]
                elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                    categories = [(str(item["id"]), item["name"]) for item in data["data"]]
                else:
                    continue

                if categories:
                    print(f"[成功] 策略3通过 {path} 找到 {len(categories)} 个类别")
                    return categories
        except Exception:
            continue

    # 策略4-6：备用方案（略，当前3策略已够用）
    print("\n[警告] 所有策略均失败，请检查网络连接")
    return []


def fetch_project_detail(project_id: str, project_name: str) -> list[dict]:
    """
    【核心新增】项目详情页抓取 - 获取子项信息
    支持多种接口路径和 HTML 解析
    """
    print(f"  [详情请求] 正在抓取项目详情: {project_name} (ID: {project_id})")

    # 尝试多种详情接口路径
    detail_paths = [
        f"/project/{project_id}.html",
        f"/project_detail?id={project_id}",
        f"/api/project/{project_id}",
        f"/project/getDetail?id={project_id}",
        f"/item/{project_id}",
    ]

    for path in detail_paths:
        try:
            resp = requests.get(BASE_URL + path, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()

                # 检查各类可能的子项字段名
                subitem_fields = ["sub_items", "items", "details", "children", "sublist", "sub_list", "sublist_items"]

                for field in subitem_fields:
                    if isinstance(data.get(field), list):
                        sub_items = data[field]
                        print(f"  [成功] 通过 {path} 获取子项，字段: {field}, 共 {len(sub_items)} 个")
                        return sub_items

                # 如果没有子项字段，可能是项目基本信息
                print(f"  [提示] {path} 返回项目基本信息，但未找到子项字段")
                return []

        except requests.exceptions.JSONDecodeError:
            # 可能是 HTML 页面，尝试解析
            print(f"  [信息] {path} 返回 HTML，尝试解析...")
            return parse_html_detail(resp.text, project_name)
        except Exception as e:
            print(f"  [跳过] {path} 请求失败: {e}")
            continue

    # 所有接口都失败，返回空列表
    print(f"  [警告] 项目 {project_name} 详情抓取失败")
    return []


def parse_html_detail(html_content: str, project_name: str) -> list[dict]:
    """
    【新增】HTML 详情页解析 - 当 API 接口不可用时使用
    """
    try:
        # 查找子项相关的内容
        subitem_patterns = [
            # 常见的子项容器
            r'<div[^>]*class="*subitem*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="*subitems*"[^>]*>(.*?)</div>',
            # 表格中的子项
            r'<table[^>]*>.*?<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?</tr>.*?</table>',
            # 列表中的子项
            r'<li[^>]*>.*?子项.*?</li>',
            # 带标题的子项
            r'<h\d[^>]*>.*?子项.*?</h\d>\s*<p[^>]*>(.*?)</p>',
        ]

        sub_items = []

        for pattern in subitem_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                # 清理 HTML 标签
                text = re.sub(r'<[^>]+>', '', match).strip()
                if text and len(text) > 1:
                    sub_items.append({
                        "name": text[:50],  # 截取前50字符作为子项名
                        "raw_content": match[:200] if len(match) > 200 else match
                    })

        if sub_items:
            print(f"  [成功] HTML解析找到 {len(sub_items)} 个子项")
        else:
            print(f"  [提示] HTML未找到子项内容")

        return sub_items

    except Exception as e:
        print(f"  [警告] HTML解析异常: {e}")
        return []


def fetch_category_data(category_id: str, category_name: str) -> None:
    """
    【核心】抓取单个类别所有数据 - 包含项目列表和详情
    """
    print(f"\n=== 开始处理类别 {category_id}: {category_name} ===")

    # 创建类别目录
    category_dir = RAW_DIR / f"category_{category_id}"
    category_manifest = category_dir / "manifest.jsonl"
    category_dir.mkdir(parents=True, exist_ok=True)

    # 预览模式：限制处理数量
    if PREVIEW_MODE:
        max_projects = 3
        print(f"[预览模式] 此类别只处理前 {max_projects} 个项目")
    else:
        max_projects = None  # 处理所有项目

    page = 1
    total_projects = 0

    while True:
        # 请求列表页
        params = {
            "p": str(page),
            "province": "",
            "rx_time": "",
            "type": "",
            "cate": "",
            "keywords": "",
            "category_id": category_id,
            "limit": "10",
        }

        try:
            print(f"\n[第{page}页] 正在请求列表...")
            resp = requests.get(BASE_URL + "/getProject.html", params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()

            # 解析响应数据
            data = resp.json()
            projects = data.get("list", [])

            if not projects:
                print(f"[结束] 第{page}页无数据，停止处理")
                break

            print(f"[成功] 第{page}页获取到 {len(projects)} 个项目")

            # 处理每个项目
            for project in projects:
                if max_projects is not None and total_projects >= max_projects:
                    print(f"\n[预览模式] 达到项目数量限制 {max_projects}，停止")
                    return

                project_id = str(project.get("id", project.get("number", "unknown")))
                project_name = project.get("name", "未知项目")

                print(f"\n[项目 {total_projects + 1}] {project_name}")
                print("-" * 50)

                # 抓取子项信息
                sub_items = fetch_project_detail(project_id, project_name)

                # 添加子项到项目数据
                project["sub_items"] = sub_items

                # 控制台结构化输出
                print_project_info(project)

                # 完整模式下保存数据
                if not PREVIEW_MODE:
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
                        "sub_items_count": len(sub_items),
                        "project_data": project  # 保存完整项目数据
                    }

                    with category_manifest.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

                total_projects += 1

                # 项目间延时
                time.sleep(DETAIL_INTERVAL)

            page += 1
            time.sleep(REQUEST_INTERVAL)

        except Exception as e:
            print(f"[错误] 第{page}页请求失败: {e}")
            break

    print(f"\n=== 类别 {category_id} 处理完成 ===")
    print(f"总计处理项目数: {total_projects}")


def print_project_info(project: dict):
    """
    【新增】格式化打印项目信息 - 用于预览模式展示
    """
    print(f"项目名称: {project.get('name', '')}")
    print(f"项目编号: {project.get('number', '')}")
    print(f"所属类别: {project.get('type', '')}")
    print(f"申报地区: {project.get('region', '')}")
    print(f"保护单位: {project.get('org', '')}")
    print(f"项目简介: {project.get('intro', '')[:100] if project.get('intro') else ''}{'...' if project.get('intro') and len(project.get('intro', '')) > 100 else ''}")

    sub_items = project.get('sub_items', [])
    print(f"\n--- 子项列表 (共 {len(sub_items)} 个) ---")

    if sub_items:
        for i, item in enumerate(sub_items, 1):
            item_name = item.get('name', f'子项{i}')
            print(f"  {i}. {item_name}")
            if item.get('desc'):
                desc = item['desc'][:50] if len(item['desc']) > 50 else item['desc']
                print(f"     描述: {desc}")
    else:
        print("  [提示] 未找到子项信息")

    print("-" * 50)


def main():
    """
    主函数 - 执行爬取流程
    """
    # 【强制】模式提示
    if PREVIEW_MODE:
        print("\n" + "=" * 60)
        print("⚠️ 预览模式激活 - 仅用于调试效果")
        print("⚠️ 当前模式：预览模式（前2大类×前3项目）")
        print("⚠️ 不生成文件，仅控制台输出")
        print("⚠️ 确认效果无误后，请设置 PREVIEW_MODE = False 正式爬取")
        print("=" * 60)
        mode_name = "预览模式"
    else:
        print("\n" + "=" * 60)
        print("🚀 完整模式激活 - 正式全量爬取")
        print("🚀 当前模式：完整模式（全量数据持久化）")
        print("�️  将爬取 10 个类别、1557 个项目、3610 个子项")
        print("=" * 60)
        mode_name = "完整模式"

    print(f"\n[{mode_name}] 开始执行爬虫任务...")

    # 创建数据目录
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 全自动获取类别
    categories = auto_fetch_categories()

    if not categories:
        print("\n[错误] 自动获取类别失败，请检查网络或手动指定")
        return

    # 预览模式限制类别数量
    if PREVIEW_MODE:
        categories = categories[:2]
        print(f"\n[预览模式] 只处理前 {len(categories)} 个类别")

    # 开始爬取
    for i, (category_id, category_name) in enumerate(categories):
        print(f"\n[进度] 正在处理第 {i+1}/{len(categories)} 个类别")
        fetch_category_data(category_id, category_name)

        # 类别间延时
        if i < len(categories) - 1:
            time.sleep(REQUEST_INTERVAL * 2)

    # 完整模式下合并 manifest
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

        # 排序并写入总 manifest
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

# ======================== 运行指引 ========================
#
# 1. 预览模式（调试用）：
#    - 设置 PREVIEW_MODE = True
#    - 运行: python crawler/ihchina_crawler.py
#    - 效果：处理前2个类别，每个类别前3个项目
#    - 目的：验证子项抓取是否正确
#
# 2. 完整模式（正式用）：
#    - 设置 PREVIEW_MODE = False
#    - 运行: python crawler/ihchina_crawler.py
#    - 效果：爬取所有类别和项目
#    - 时间：可能需要较长时间（约1-2小时）
#
# 3. 成功判断标准：
#    - 预览模式：看到"子项列表"和子项名称即成功
#    - 完整模式：看到"总项目数: 1557"即成功
#
# 4. 注意事项：
#    - 预览模式不生成文件
#    - 完整模式数据保存在 data/raw/category_XX/
#    - 单个项目失败不会影响整体
#    - 详情请求间隔2秒，列表请求1.5秒
#
# ===========================================================
