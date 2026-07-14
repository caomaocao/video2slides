# 以 MIT 开源发布,公开镜像走「过滤保史」而非原样推送

**背景**:Cuepoint 长期只在私有 Codeup 仓开发,现决定以 MIT 协议开源到 GitHub(`caomaocao/cuepoint`,public)。私有仓保留为个人权威副本,GitHub 为公开镜像。

**决定**:
- **协议**:MIT(`LICENSE`,Copyright (c) 2026 caomaocao)。
- **范围(curated)**:公开仓只含核心 skill(`scripts/`、`tests/`、`SKILL.md`、`schemas/`、各 `AGENTS.md`/`CLAUDE.md`)+ 当前设计规格(spec v0.5 与两份专题 spec)。**剔除**内部过程制品:开发日报、`superpowers` 计划/规格、已废止的 spec v0.3/v0.4;并清洗 `test-videos.md` 中的一处**本机个人文件路径**(含私有渠道标识)。
- **历史**:保留完整提交叙事,但用 `git-filter-repo` 把上述剔除文件与那处个人路径从**所有**提交中抹除后再推公开镜像——而非在末梢 `git rm`(那样旧提交里仍可检出)。因此公开镜像的提交哈希与私有仓不同,是预期结果。
- **展示**:README 首屏用 ASCII 管线图 + 指向 GitHub Pages 的实跑 deck live demo(公开来源视频的成品,`gh-pages` 分支托管,`main` 保持精简)。

**理由/权衡**:
- 完整历史 vs 全新单提交:选前者以保真实构建过程,代价是必须重写历史来兼顾「不泄漏个人路径 / 不夹带内部过程噪声」——二者不可兼得,重写是唯一同时满足的路径。
- 截图 vs 整包 deck:live demo 用公开来源视频的成品;deck 内含第三方视频截帧,故只托管公开来源者(排除个人视频号本地 deck),规避 IP 暴露。

**后果**:公开镜像与私有仓历史分叉(哈希不同),两地不再互为 fast-forward;后续如需同步,以私有仓为源、重跑过滤推公开镜像。
