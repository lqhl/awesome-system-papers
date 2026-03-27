# Agent Rules for awesome-system-papers

awesome-system-papers 是我用来收集计算机系统领域论文的 repo。包括原始的论文文件（.pdf）以及下载用的脚本。

- 脚本统一放在 scripts/ 文件夹中
- 论文放在每个会议的目录中，例如 2026 年 OSDI 会议论文放在 osdi-2026/ 中
- agent-progress.md 存储 agent 的进展、学习到的东西以及踩过的坑
- agent 应该主动将值得注意或者记录的 rule 添加到该文件（AGENTS.md）

## 记住的偏好 (Learned Preferences)

- **数据提取**: 不要硬编码数据列表 → 始终从源页面动态提取真实数据
