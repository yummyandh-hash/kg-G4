# 协作指南

## 分支与合入

- main：公开审查基线，通过 PR 更新，用 merge commit 保留原提交与合入节点。
- develop：开发集成分支，通过 PR 更新。
- integration/stage2-base：迁移的 Stage2 候选，尚未自动合入 main。
- 原 feat/、feature/、fix/、backup/ 分支保留，不在合并后自动删除。
- 新分支建议 feat/A-功能、feat/B-功能、fix/问题、docs/说明、chore/管理任务。
- archive/gitee-pr/<编号>/head 与 MERGE 是溯源标签，不作日常开发分支。

main 的检查必须通过；启用保护后的变更还需要一位有写权限且不是作者的成员真实批准，并解决讨论。develop 未部署新 CI 时不虚设必需检查，但仍要求 PR 和审核。不使用管理员权限或工具伪造审核来绕过门禁。

本次文件、模板和 CI 的首次引入是引导变更：保护启用前走真实 PR 和自动检查。若其他成员尚未加入，不把这一引导变更描述为已完成人类交叉审核。

## 日常流程

1. 用 Issue 或 PR 说明问题、范围与验收条件。
2. 建立独立分支，完成可审查的一项变更。
3. 执行适用测试，记录命令、实际结果和未验证范围。
4. 打开 PR，关联 Issue，说明上下游与接口影响。
5. 请求其他真实成员审核，修复意见并重跑检查。
6. 审核和检查通过后合入，原迁移分支保留。

推荐提交说明 feat(scope): ...、fix(scope): ...、docs(scope): ...、test(scope): ...、chore(scope): ...。不批量改写旧提交。

## 模块接口

编排协议以 orchestration/models.py 为准：retrieve(query, context) 返回 Evidence 列表。D 的独立请求模型通过 Stage2 的 DRetrieverAdapter 对接，A 不重复实现具体检索算法。改变 route、Evidence 或 API 时，在 PR 列明调用方、适配器和测试影响。

## 账号与贡献

Gitee 账号、Git 作者和 GitHub 账号不是同一概念。成员自行在 GitHub 添加并验证本人持有的历史提交邮箱，才能让可关联的提交归属到账号。贡献热力图还取决于分支等统计条件。

成员接受邀请后才有写权限，才能参加有效互审。不得为增加评分证据而伪造历史 PR、审批、时间、身份或空提交。当前分工与账号状态见 CONTRIBUTOR 表。

## 配置与数据

真实配置保存在本地 .env 或受控 Secrets；示例使用占位符。大 JSON 延续现有 Git LFS 属性，数据来源和许可单独记录。

## 官方依据

- [导入器范围](https://docs.github.com/en/migrations/importing-source-code/using-github-importer/about-github-importer)
- [提交邮箱与贡献关联](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/viewing-contributions-on-your-profile)
- [分支保护](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
