# 助教审查索引

课程没有明确评分细则；本页给出工程证据，不宣称必得满分。

| 检查项 | 证据 | 边界 |
| --- | --- | --- |
| 首页与运行入口 | README.md | main 和 Stage2 候选明确区分 |
| 五人职责与贡献 | CONTRIBUTOR 表、Git 提交、历史索引 | 账号映射及邀请接受状态需真实确认 |
| 分支与历史 | 17 个原分支、138 条提交、34 个 PR 标签、哈希映射 | 新治理提交另计，不改写旧历史 |
| 协作流程 | CONTRIBUTING.md、新 PR、Issue/PR 模板 | 新记录不冒充 Gitee 旧记录 |
| 自动检查 | Actions → Repository CI | main 11 个单测，不等于在线验收 |
| 门禁 | Settings → Branches / Rules | main 检查与真实批准；develop 先要求 PR/审核 |
| 可追溯发布 | Gitee migration archive Release | 原始 bundle 和完整性限制一并公开 |
| 维护配置 | CODEOWNERS、Dependabot、固定 Actions SHA、SECURITY.md | 模块负责人待协作者接受邀请后补齐 |

## 需要成员本人完成的事项

接受协作邀请，确认 GitHub 主页，验证历史邮箱，进行真正的交叉审核，以及共同确定代码许可证。工具不能代替这些行为。

Stage2 依赖/构建仍需验收；旧平台评论、审核和所有历史推送没有完成无损导出。不能靠补造历史审核、评论或空提交来填充证据。

[Stage2 成果](https://github.com/yummyandh-hash/kg-G4/tree/integration/stage2-base) · [测试范围](TESTING.md) · [迁移历史](history/README.md) · [协作](../CONTRIBUTING.md)
