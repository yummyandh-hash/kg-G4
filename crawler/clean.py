# -*- coding: utf-8 -*-
"""
清洗脚本 V2：data/raw/category_*/page_*.raw  ->  data/clean/documents/*.json

它做四件事（对应任务文档里 B 的"数据清洗 / 字别标准化 / provenance / 统计"）：
    1. 解析：把爬虫存下来的原始响应变成 Python 字典列表（parse_raw，唯一可能要改的函数）；
    2. 规范化：字段统一、地区名归一（"江苏省苏州市"为规范形）、项目别名拆分；
    3. 溯源：每条记录带上 source_url / document_id / retrieved_at 等 provenance 字段；
    4. 统计：条数、缺失率、重复率，打印并存到 reports/clean_report.md。

运行：python crawler/clean.py

新功能：支持多类别目录结构（data/raw/category_16/page_001 等）
"""

import json
import re
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DOC_DIR = ROOT / "data" / "clean" / "documents"
REPORT_PATH = ROOT / "reports" / "clean_report.md"

# 缺失字段一律显式写 None，绝不静默丢弃——这样下游（C 抽取、D 检索）能统计缺失率
CANONICAL_FIELDS = [
    "name", "aliases", "number", "category", "batch",
    "region", "region_norm", "org", "body",
    "source_url", "document_id", "chunk_source_page", "retrieved_at",
]


# ============================== 第 1 步：解析（唯一的 TODO） ==============================

def parse_raw(raw_bytes: bytes, content_type: str) -> list[dict]:
    """
    把一页原始响应变成 [ {项目字段...}, ... ] 列表。

    你 F12 看到接口返回什么格式，就在这里怎么解：
      * 大多数政府站点的列表接口返回 JSON，下面已写好通用解法；
      * 如果返回的是 HTML 片段，把 json 分支注释掉，用正则/BeautifulSoup 解析，
        解不出来随时把一页原始文件发给 AI 帮你写这段。

    返回的每个字典里字段名随意，第 2 步会统一改名。
    """
    # ---- 情况 A：接口返回 JSON ----
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = None

    if isinstance(data, dict):
        # JSON 里列表可能在某个键下面，逐个常见键名尝试
        for key in ("list", "data", "rows", "records", "result", "items", "list"):
            if isinstance(data.get(key), list):
                return data[key]
        # 有时分页信息在外层、列表在内层，例如 {"data": {"list": [...]}}
        for key in ("data", "result"):
            inner = data.get(key)
            if isinstance(inner, dict):
                for key2 in ("list", "rows", "records"):
                    if isinstance(inner.get(key2), list):
                        return inner[key2]
        return []

    if isinstance(data, list):
        return data

    # ---- 情况 B：接口返回 HTML 片段（TODO：看到了再回来写） ----
    # from bs4 import BeautifulSoup
    # soup = BeautifulSoup(raw_bytes.decode("utf-8"), "html.parser")
    # return [ ...把每个 <li>/<tr> 转成字典... ]
    print("[警告] 这页不是 JSON，parse_raw 返回空列表——看到真实数据后回来补 HTML 分支")
    return []


# ============================== 第 2 步：规范化 ==============================

# 行政区划后缀。规范形 = 去掉这些后缀："江苏省苏州市" -> "江苏苏州"
REGION_SUFFIXES = ("维吾尔自治区", "回族自治区", "壮族自治区", "自治区", "省", "市", "区", "县", "旗")

CATEGORY_NAMES = {
    # 十大门类的常见写法统一到标准名（键是页面可能出现的写法，值是规范名）
    "民间文学": "民间文学", "传统音乐": "传统音乐", "传统舞蹈": "传统舞蹈",
    "传统戏剧": "传统戏剧", "曲艺": "曲艺", "传统体育、游艺与杂技": "传统体育、游艺与杂技",
    "传统美术": "传统美术", "传统技艺": "传统技艺", "传统医药": "传统医药", "民俗": "民俗",
}


def norm_region(region: str) -> str:
    """地区规范化：剥掉一级行政区后缀，只留主体。'新疆维吾尔自治区' -> '新疆'。"""
    if not region:
        return ""
    out = region.strip()
    for suf in REGION_SUFFIXES:
        if out.endswith(suf) and len(out) > len(suf):
            return out[: -len(suf)]
    return out


def split_name_alias(name: str) -> tuple[str, list[str]]:
    """
    项目名拆别名：非遗名录里常见"苏绣（苏州刺绣）"的写法。
    返回 (规范名, 别名列表)。这个 aliases 之后会交给模块五（实体候选生成）直接使用。
    """
    name = (name or "").strip()
    m = re.match(r"^(.*?)（(.+?)）$", name)
    if m:
        return m.group(1).strip(), [a.strip() for a in m.group(2).split("、") if a.strip()]
    return name, []


def normalize(raw: dict, category_id: str, retrieved_at: str) -> dict:
    """把接口返回的一条原始记录映射成统一 schema。字段名以你实际看到的为准，改这里。"""
    name, aliases = split_name_alias(str(raw.get("name", "") or raw.get("title", "")))
    region = str(raw.get("region") or raw.get("province") or "").strip()
    category = CATEGORY_NAMES.get(str(raw.get("type", "")).strip(), str(raw.get("type", "")).strip())

    doc = {
        "name": name,
        "aliases": aliases,
        "number": str(raw.get("number") or raw.get("id") or "").strip(),
        "category": category,
        "batch": str(raw.get("batch") or raw.get("bath") or "").strip(),
        "region": region,
        "region_norm": norm_region(region),
        "org": str(raw.get("org") or raw.get("unit") or "").strip(),  # 保护单位
        "body": str(raw.get("intro") or raw.get("content") or "").strip(),
        # ---------- provenance：全链路溯源字段，一个都不能少 ----------
        "source_url": str(raw.get("url") or "https://www.ihchina.cn/project.html"),
        "document_id": "",
        "chunk_source_page": int(category_id),  # 改用类别ID作为来源页面标识
        "retrieved_at": retrieved_at,
    }
    # document_id：用项目编号；没有编号就用名字哈希，保证同一条数据永远拿到同一个 id
    key = doc["number"] or doc["name"]
    doc["document_id"] = f"ihchina_{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}"
    return doc


# ============================== 第 3、4 步：落盘 + 统计 ==============================

def main() -> None:
    records: list[dict] = []

    # 遍历所有类别目录
    for category_dir in RAW_DIR.glob("category_*"):
        if not category_dir.is_dir():
            continue

        category_id = category_dir.name.replace("category_", "")
        print(f"处理类别 {category_id}...")

        # 读取该类别的 manifest
        manifest = category_dir / "manifest.jsonl"
        if not manifest.exists():
            print(f"  [跳过] 无 manifest 文件")
            continue

        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            meta = json.loads(line)

            # 解析原始响应
            raw_bytes = (category_dir / meta["raw_file"]).read_bytes()
            for item in parse_raw(raw_bytes, meta["content_type"]):
                records.append(normalize(item, category_id, meta["retrieved_at"]))

    if not records:
        raise SystemExit("解析出 0 条记录：先确认爬虫已经存到数据，再检查 parse_raw。")

    # 按项目编号去重（同一项目在不同批次页出现时只留一条）
    seen: dict[str, dict] = {}
    dup = 0
    for r in records:
        if r["document_id"] in seen:
            dup += 1
            continue
        seen[r["document_id"]] = r

    DOC_DIR.mkdir(parents=True, exist_ok=True)
    for old in DOC_DIR.glob("*.json"):
        old.unlink()
    for doc in seen.values():
        (DOC_DIR / f"{doc['document_id']}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---------- 质量统计（9/7 PPT 素材的第一版就靠这个脚本） ----------
    n = len(seen)
    lines = [
        "# 数据清洗报告", "",
        f"- 生成时间：{__import__('time').strftime('%Y-%m-%d %H:%M')}",
        f"- 原始记录：{len(records)} 条；去重后：{n} 条（重复 {dup} 条）", "",
        "## 字段缺失率", "",
        "| 字段 | 缺失条数 | 缺失率 |", "|---|---:|---:|",
    ]
    for f in CANONICAL_FIELDS:
        miss = sum(1 for d in seen.values() if not d.get(f))
        lines.append(f"| {f} | {miss} | {miss / n:.1%} |")
    report = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"清洗完成：{n} 条 -> {DOC_DIR}")
    print(report)
    print("下一步：python crawler/chunk.py")


if __name__ == "__main__":
    main()
