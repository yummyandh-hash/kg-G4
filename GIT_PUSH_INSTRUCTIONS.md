# Git 推送指南

## 推送到 Gitee 步骤

### 1. 检查当前状态
```bash
cd kg-g5-stage1-9.3-lxg
git status
git log --oneline -5
```

### 2. 添加所有文件
```bash
git add .
```

### 3. 创建提交
```bash
git commit -m "feat: 实现爬虫V3和数据完整流程

- 新增全自动爬虫V3（支持预览和完整模式）
- 成功获取第一批10个非遗项目数据
- 完成数据清洗和分块处理
- 生成30个chunks，包含完整provenance字段
- 准备交付给C和D成员使用

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

### 4. 推送到 Gitee
```bash
git push origin main
# 或者如果有 feature 分支：
# git push origin feature/member-b-work
```

## 新增文件说明

### 核心文件
- `crawler/ihchina_crawler_simple.py` - 简化版爬虫（V3）
- `crawler/clean_simple.py` - 简化版清洗脚本
- `crawler/chunk_simple.py` - 简化版分块脚本

### 数据文件
- `data/raw/category_0/manifest.jsonl` - 全部数据
- `data/raw/category_1/manifest.jsonl` - 第一批数据
- `data/clean/documents/` - 清洗后的10个项目文档
- `data/chunks/chunks.jsonl` - 30个分块数据
- `data/chunks/stats.json` - 分块统计信息

### 交付文档
- `DELIVERY_C_D_CHUNKS_2026-09-04.md` - 给C和D成员的交付说明

## 注意事项

1. 确保已经接受 Gitee 的邀请
2. 如果使用 SSH 密钥，确保已配置
3. 如果遇到冲突，需要先 pull 再 push
4. 提交信息使用中文，符合团队规范