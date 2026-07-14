# docs/ · AGENTS.md

文档目录。**全中文**(repo 约定)。这里是设计与决策的落点,代码改动前先在此对齐意图。

## 权威顺序

- **`cuepoint-spec-v0.5.md`** —— 设计 source of truth(2026-07-13「制品升格」决议版,reviewed)。做架构判断以它为准。
- **`cuepoint-spec-v0.4.md`** / **`cuepoint-spec-v0.3.md`** —— 历史快照,**只读勿改**,保留用于追溯。
- **`test-videos.md`** —— 27 个已核实测试源 + 全部试产发现的登记册。新发现**追加**,不删旧结论;矩阵按 ASR 分家实跑标注。

## 子目录

- **`superpowers/plans/`** —— 各切片的实现计划(TDD 任务分解 + 写死的验收编号),命名 `YYYY-MM-DD-<slice>.md`;拆票形态用目录 `YYYY-MM-DD-<slice>/NN-<slug>.md`(一票一文件,按依赖序编号,票内声明 Blocked by)。
- **`superpowers/specs/`** —— 设计定稿产物。
- **`daily-report/`** —— 每日日报,一天一文件,命名 `YYYY-MM-DD.md`。

## 写日报的规矩(照已有文件的格式)

- 结构:一句话概要 → (背景)→ 今日完成(**按 commit 主题分组**,每条带短哈希 `abc1234`)→ 校验状态 → 遗留/下一步。
- **只写可核实的里程碑**:测试通过数只有当天真跑过才写;历史里程碑引用 commit message 里确有的(如覆盖率 98.1%、ASR 实跑 23/27),不编数字。
- 跨天承接用 `[链接](YYYY-MM-DD.md)` 相互指引。

## 改文档时

- 保持中文;spec 的小节编号(§N)被代码注释和 SKILL.md 引用,调整编号要一并搜改引用点。
