# Wiki Log

每条条目格式固定：`## [YYYY-MM-DD] {Page or Action}`，便于 `grep "^## \[" wiki/log.md | head -20` 解析。倒序排列，最新在上。

---

## [2026-04-24] MLSys-2026 综述生成
- 生成：[[MLSys-2026]]（wiki/conferences/MLSys-2026.md）
- 聚合 79 篇 paper wiki 页（全部新建，从 markdowns/mlsys-2026 提取）
- 分类 13 个：LLM 推理 / Attention-KV / Speculative / MoE / 分布式训练 / GPU Kernel / AI4AI / 量化 / Agent / 扩散视频 / 联邦隐私 / 可复现基准 / 边缘应用
- 研究趋势 6 段，均带具体 paper wikilink 作证据
- 值得关注方向 6 条，聚焦小团队可做

## [2026-04-24] Phase 4 局部：删除旧产物
- 打 git tag `pre-wiki-migration` 留 rollback 锚点
- 删除：`reports/`（484 篇旧报告 + 各级 README）
- 删除：`ideas/`（7 篇研究方向）
- 删除：`.claude/skills/paper-report/` 和 `.claude/skills/papers-digest/`
- 触发：用户确认后立刻执行，不等 Phase 3 全量

## [2026-04-24] Phase 2: ai-infra theme + index 更新
- 生成：[[AI-Infra]]（wiki/themes/AI-Infra.md），3 主线综述 + 3 个 open problems direction
- 更新：[[index]] 加入 7 个 seed 页 + 1 个 theme 页 + 5 篇 paper 索引

## [2026-04-24] Phase 2: 7 个 seed entity/concept 页
- entities: [[vLLM]]、[[SGLang]]
- concepts: [[KV-Cache]]、[[MoE]]、[[PagedAttention]]、[[Speculative-Decoding]]、[[Disaggregation]]
- 数据来源：从 5 篇 ai-infra paper wiki 页 + 已读 markdown 提取
- 这些页存在后，5 篇 paper 里的 wikilink 自动解析（橘色 → 蓝色）

## [2026-04-24] Phase 1 mini pilot：ai-infra 5 篇 wiki paper 页
- 生成：
  - [[TransferEngine-arXiv25]]（系统名）
  - [[Libra-arXiv26]]（系统名）
  - [[AttnRes-arXiv26]]（方法名）
  - [[MSA-arXiv26]]（方法名）
  - [[LatencyOptimal-MoELB-INET4AI25]]（方法名 + workshop）
- 命名验证：3 个用系统名/方法名，1 个用 workshop 简写做后缀
- 暂未做：自动 wiki-update（wiki/entities, wiki/concepts 还是空的，无可补 wikilink 的目标页）—— 已在下一条 Phase 2 中通过补 seed 页解决

## [2026-04-24] wiki 初始化
- 新建目录结构：`papers/`、`conferences/`、`entities/`、`concepts/`、`comparisons/`、`themes/`
- 新建占位：`index.md`、`log.md`
- 触发：落地 Karpathy 风格 LLM Wiki 架构，废弃旧 `reports/` 和 `ideas/`
