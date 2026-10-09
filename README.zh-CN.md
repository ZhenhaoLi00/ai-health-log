# AI Health Log

[English](README.md)

一个供多个 AI 助手共享的**个人健康数据中心**。训练、饮食、睡眠和身体指标统一保存在一个 Git 仓库中，Muse、ChatGPT、Codex 等 AI 都可以根据约定读取和更新这些信息，无须每次更换助手都重新介绍自己的情况。

> **隐私优先：** 这是一个公开的**模板仓库**。请基于模板创建自己的 **Private（私有）仓库**，用于保存真实健康数据。不要提交 API 密钥或令牌。详细步骤参见 [SETUP.md](SETUP.md)。同步脚本会检查所有 GitHub 推送目标；只有目标被确认是私有仓库时才允许推送。

## 让 AI 帮你完成初始化

将下面的**英文提示词原样复制**给 ChatGPT、Claude、Codex、Muse 等 AI 助手。它会引导你完成整个配置过程。

---

I want to set up my own AI health log from this template:
https://github.com/ZhenhaoLi00/ai-health-log

Please:
1. Read README.md and SETUP.md in the template repo first.
2. Ask me for: my timezone, height, current weight, primary goal (fat loss /
   muscle gain / maintenance), daily protein and calorie targets (suggest them
   if I don't know), training frequency, and which training app I use
   (e.g. SynFit (训记), Apple Health, or manual logging).
3. Walk me through each step: creating a PRIVATE repo from the template,
   filling in profile.md, getting my training app's API key and storing it
   outside the repo (chmod 600), configuring git access (deploy key or PAT),
   running scripts/health-daily-sync.py, and scheduling it to run daily.
4. Follow the repo conventions: never commit secrets, cache API responses by
   date (never re-fetch the same date twice in one day), and always show me a
   change summary and wait for my confirmation before writing anything back
   to a third-party API.

---

## 为什么做这个项目？

灵感来自[这期访谈](https://www.youtube.com/watch?v=0Z-vhBvBmUY)（邵艾伦 Alan × 孙宇晨：《年轻人如何抓住 AI 时代的机会？》）。访谈中谈到了让 AI 管理饮食、训练和睡眠的想法。

这个项目希望实现类似目标，但避免被某一个平台锁定：**Git 仓库是唯一的数据来源（single source of truth）**，不同的 AI 助手遵守相同的文件规范，读取和更新同一套数据。

## 仓库结构

```text
README.md            英文项目说明
README.zh-CN.md      中文项目说明（本文件）
SETUP.md             逐步配置指南
SUMMARY.md           自动生成的健康概览，请勿手动编辑
profile.md           个人目标与基础指标，建议先填写
data/daily/          每日 Markdown 日志：YYYY-MM-DD.md
data/meals/          饮食记录，每餐一个文件
data/workouts/       每日训练 API 原始 JSON（按日期缓存）
data/metrics/        体重、体脂等身体指标快照
reports/daily/       自动生成的每日报告
scripts/             自动化同步脚本
```

为方便跨平台协作，仓库内的结构化记录和约定统一使用英文。

## AI 助手协作规范

1. **先读取，再写入。** 添加内容前检查 `profile.md` 和当天的 `data/daily/` 日志。
2. **每日一个文件。** `data/daily/YYYY-MM-DD.md` 包含 `## Sleep`、`## Meals`、`## Training`、`## Body metrics` 和 `## Notes`。
3. **按日期缓存。** API 原始响应存放在 `data/workouts/YYYY-MM-DD.json`。对应的 `YYYY-MM-DD.meta.json` 会记录 UTC 时间的 `fetched_at`；有效缓存当天不重复获取，除非使用 `--force-refresh`。
4. **绝不提交密钥。** API 密钥保存在仓库之外，参见 [SETUP.md](SETUP.md)。
5. **重新生成，不要手动修改。** `SUMMARY.md` 和 `reports/daily/` 由同步脚本生成。
6. **写回第三方 API 前必须确认。** 先展示修改摘要，获得用户明确同意后再操作。

## AI 健康管理 Skill（可选）

本模板已经提供 [AGENTS.md](AGENTS.md)，用于约束 AI 的数据读写、
隐私保护和协作方式。另外新增了可按需调用的
[Health Log Coach Skill](.agents/skills/health-log-coach/SKILL.md)，
指导 AI 记录饮食、分析 SynFit 训练、汇总睡眠数据，以及生成每日/每周健康回顾。
它借鉴了访谈中的工作流，但不采用未经验证的健康结论。

Codex 可从 `.agents/skills/` 发现该 Skill；Claude Code 的入口位于
`.claude/skills/`。Muse、ChatGPT 等其他助手可在获得相应文件访问权限后
按照同一套说明执行。

**直接告诉 AI（提示词保持英文）：**

~~~text
Read AGENTS.md and .agents/skills/health-log-coach/SKILL.md in my private
health-log repository. Follow the skill to review my last seven calendar days.
Use only the data available, label estimates and missing records, and propose
changes before writing anything.
~~~

请只在包含真实记录的**私有仓库**中使用该流程，不要把个人健康数据提交到公开模板。

## 使用 AI 构建本地 Dashboard（可选）

你可以让 **Muse、Claude Code、Codex 或其他能访问本地文件的编程助手**，将私有健康仓库中的数据转换为可视化 Dashboard。无须依赖在线仪表盘服务：私有 Git 仓库继续作为数据来源，Dashboard 在本地读取文件。

Dashboard 可以展示训练频率与训练量、体重趋势、热量与蛋白质估算、睡眠时长，以及记录的完整程度。缺失的数据和估算值应明确标注，不能当作实测数据展示。

**将下面的英文提示词复制给 AI 编程助手：**

```text
I have a private health-log repository based on:
https://github.com/ZhenhaoLi00/ai-health-log

Please build a local-only health dashboard from my existing files.
First read README.md, AGENTS.md, profile.md, SUMMARY.md (if present),
and the formats in data/daily/, data/workouts/, data/meals/,
and data/metrics/. Do not assume any data source is complete.

Requirements:
- Show useful daily/weekly/monthly views of training, body metrics,
  nutrition and sleep, with date filters and clear trend charts.
- Indicate source, units, missing records and estimated values.
- Use a lightweight local app (for example, Streamlit) with clear
  setup and run commands. Prefer a read-only data layer.
- Keep all personal health data on my machine: no hosting, telemetry,
  external analytics, API uploads, remote dashboards or CDN resources.
- Do not alter any source health logs, generated reports or API keys.
  Place new code in dashboard/; keep personal data out of the code.
- Work gracefully when some categories have no records yet.
- Add a short README for running and extending the dashboard.

Show me the proposed file changes and any new dependencies before
installing software or modifying my repository.
```

请使用**包含真实记录的私有仓库副本**运行 Dashboard，不要直接在这个公开模板上保存私人数据。Dashboard 在本地运行，并不意味着所有 AI 助手都不会读取或上传文件；授权前仍需要检查对应工具的访问权限和数据处理政策。

## 数据来源

| 来源 | 数据内容 | 接入方式 |
|---|---|---|
| SynFit（训记）Open API | 力量训练日志 | 每日运行 `scripts/health-daily-sync.py` |
| Apple Health / HealthKit | 跑步、球类运动、训练、睡眠 | AI 助手的健康数据连接器 |
| 手动记录 | 饮食、身体指标、备注 | 直接告诉 AI 助手 |

## 许可证

[MIT](LICENSE) 许可证适用于模板代码和文档，**不适用于你的私人健康数据**。未经授权，不得公开或再分发个人日志。
