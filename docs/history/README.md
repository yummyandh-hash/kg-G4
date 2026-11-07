# Gitee → GitHub 历史

源：https://gitee.com/tjuymh/kg-g5
目标：https://github.com/yummyandh-hash/kg-G4

## 保留范围

迁移基线含 17 个分支、138 个项目提交和 34 个 archive/gitee-pr/<编号>/head 或 MERGE 标签。原作者、提交者、日期和父子关系保留；四个大 JSON 转 LFS 后 SHA 改变，见[映射 CSV](original-to-github-commit-map.csv)。

[迁移 Release](https://github.com/yummyandh-hash/kg-G4/releases/tag/gitee-migration-archive)的原始项目 bundle 保留原对象，可离线审查。公开迁移不包含本地 stash、Codex 内部引用或本地 .env。LFS 对 17 条说明仅规范化末尾换行，迁移后对象不是原始对象的逐字节副本。

## 平台记录的完整性限制

[PR 索引](gitee-prs.md)覆盖 !1–!17（15 个合并、2 个关闭），但部分正文/操作记录经过浏览器服务归纳，不是无损 API 导出。!10 标题仍截断，未复核作者字段可能只是 provider author_text，不能与合并者混同。

活动页仅取得 10 条事件（6 次推送、2 次 PR 合并、2 次 PR 创建），相对时间原样保留，不能声称完整历史推送日志。两次 API 临时令牌创建均停在独立密码复核，未生成令牌，无需撤销。

GitHub 原生 PR 不能假造为原平台身份和时间。本仓库通过来源链接、代码标签和归档保存证据；后续 GitHub PR 使用真实当前身份和时间，编号与 Gitee 重复也不是同一条记录。

## 快照状态

归档附件生成时仓库仍私有，API 导出未完成。此后用户确认历史数据库旧密码失效，并恢复公开。附件中的 private / paused 描述当时状态，当前以 GitHub 为准。

[分支映射](branches.json)固定迁移基线，main 后续治理提交单独计入。补齐旧评论/审核需要合法授权后的官方导出，并核查分页及保留范围；不能保证恢复平台不再提供的事件。

## 不完整的历史嵌套仓库

kg-g5-stage1-9.3-lxg 原为没有 .gitmodules 和已知远端地址的 gitlink。新治理提交将当前空入口替换为说明目录，以修复 CI checkout；原始指针和 SHA 保留在历史中。父仓库 bundle 不包含一个未取得的完整子仓库，不能将其宣称为已还原。详见[入口说明](../../kg-g5-stage1-9.3-lxg/README.md)。
