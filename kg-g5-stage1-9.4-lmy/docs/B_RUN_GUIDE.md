# B 成员今晚运行指南（10 分钟版）

## 第 0 步：装依赖（一次性）

```bash
cd "D:/大三上课程/知识工程综合实践/王鑫项目/kg-g5"
pip install -r requirements.txt
```

## 第 1 步：F12 找接口（只有这步要你手工做）

1. Chrome 打开 `https://www.ihchina.cn/project.html#target1`
2. 按 **F12** → 选 **Network**（网络）标签 → 点 **Fetch/XHR** 筛选
3. 在网页上点一下 **下一页**（或换个筛选条件）
4. Network 里会新冒出一条请求，点它，看 **Payload（载荷）** 和 **Headers（标头）**：
   - 把 **Request URL** 抄进 `crawler/ihchina_crawler.py` 的 `ENDPOINT`
   - 把 **Request Method**（GET/POST）抄进 `METHOD`
   - 把 **Payload 里的参数名**抄进 `PARAMS`（页码参数值删掉留空串）

## 第 2 步：跑爬虫骨架

```bash
python crawler/ihchina_crawler.py
```
✅ 验收标准：`data/raw/` 出现 `page_000001` 等文件 + `manifest.jsonl` 有记录；
再跑一遍第二遍全是 `[跳过]`（这就是"断点续爬/幂等"，答辩要会讲）。

## 第 3 步：清洗 + 切块

```bash
python crawler/clean.py     # 可能要按 F12 看到的真实字段微调 normalize()
python crawler/chunk.py
```
✅ 验收标准：`data/clean/documents/` 有 json、`chunks.jsonl` 每行一个带前缀的 chunk、
`reports/clean_report.md` 有缺失率统计。

## 明早（9/4 上午）

1. `crawler/ihchina_crawler.py` 里 `MAX_PAGES = None`（全量爬，挂机跑完）
2. 重跑 clean + chunk
3. 把 `data/clean/` 和 `reports/clean_report.md` 发群里 @C @D —— **上午硬交棒点**

## 卡住了怎么办

- 接口返回不是 JSON / 字段对不上 → 把 `data/raw/page_000001` 文件发给 AI 帮你改 `parse_raw()`
- 请求被拒/超时 → 确认 F12 里请求是否带 Cookie 或特殊 Header，抄进 `HEADERS`
- 想验证爬得对不对 → 随机挑 5 个项目去官网人工核对字段（这个步骤以后写进测试）
