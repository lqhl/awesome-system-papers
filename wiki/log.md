# Wiki Log

每条条目格式固定：`## [YYYY-MM-DD] {Page or Action}`，便于 `grep "^## \[" wiki/log.md | head -20` 解析。倒序排列，最新在上。

---

## [2026-04-24] TransferEngine: arXiv 版并入 MLSys26 版
- 背景：[[TransferEngine-MLSys26]] 正式发表，arXiv preprint 2510.27656v1 为同文早版本
- 清理 raw 层：删除 `papers/ai-infra/2510.27656v1.pdf`、`markdowns/ai-infra/2510.27656v1/`
- 清理 wiki 层：删除 `wiki/papers/TransferEngine-arXiv25.md`
- 重定向 wikilink：所有 `[[TransferEngine-arXiv25]]` → `[[TransferEngine-MLSys26]]`
  - index.md（arXiv / AI-Infra 专题列表 6→5 篇，TransferEngine 转入 MLSys-2026）
  - DeepSeek-V4-arXiv26、Libra-arXiv26、LatencyOptimal-MoELB-INET4AI25（同期/基础设施引用）
  - concepts: MoE / PagedAttention / KV-Cache / Disaggregation / Speculative-Decoding
  - themes/AI-Infra（主线二综述段 + 值得关注方向第 3 条）
  - entities/vLLM（演进时间线 / 相关论文 / 开放问题）
- MLSys26 paper 页「同类系统」删去对 arXiv25 的自引用

## [2026-04-24] Auto-Research 综述生成
- 生成：[[Auto-Research]]（wiki/themes/Auto-Research.md）
- 聚合 11 篇 paper wiki 页（全部新建，从 markdowns/autoresearch 提取）:[[MLAgentBench-ICML24]]、[[OpenHands-ICLR25]]、[[AI-Scientist-arXiv24]]、[[MLE-Bench-ICLR25]]、[[AI-Scientist-v2-arXiv25]]、[[Auto-Research-arXiv25]]、[[MLR-Bench-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[FunSearch-Nature24]]
- 分类 4 个：端到端自主科研系统 / Evolutionary 算法与架构发现 / ML Agent 评测基准 / 通用 Agent 平台
- 主题综述 5 段：从 benchmark 到真 discovery 的 arc / LLM-as-agent vs LLM-as-mutator 两条范式 / Benchmark 三层递进与可信度危机 / AlphaEvolve+OpenHands 部署即试金石 / "科学发现 scaling law" 是最激进 claim
- 值得关注方向 5 条，聚焦小团队可做：verifiable 窄域 discovery / integrity-first verifier / 领域特化 mini-AI-Scientist / compute-efficient scaling law 对照验证 / reproducibility infrastructure

## [2026-04-24] FluxMoE-arXiv26 paper wiki + wiki-update
- 生成：[[FluxMoE-arXiv26]]（wiki/papers/FluxMoE-arXiv26.md）
- 命名：系统名 FluxMoE（论文自命名，abstract & intro 反复使用）
- 补 wikilink：paper 页首次出现 [[MoE]]、[[vLLM]]、[[KV-Cache]]、[[SGLang]]、[[PagedAttention]]、[[Disaggregation]] 均在写入时直接加 link，无需二次补
- 更新：wiki/concepts/MoE.md、wiki/concepts/KV-Cache.md、wiki/concepts/PagedAttention.md、wiki/concepts/Disaggregation.md、wiki/entities/vLLM.md 的「引用本概念的论文」/「相关论文」节
- 无新 TODO 缺页（watchlist 里 Mooncake/DistServe/ZeRO-Infinity/FlexGen 等虽提及，本已在其他 log 条目中登记；lossless-compression 出现在 paper 但未列入 watchlist，暂不升级）
- 追加「批判与局限」节：7 点批判 + 定位——thesis 被 [[DeepSeek-V4-arXiv26|DeepSeek-V4]] 等模型侧 FP4 + KV 压缩釜底抽薪；context 只测 4K 无法外推；claim target PD-disaggregated decode 但没测 PD 分离；L40 硬件选择偏向自己；baseline 弱；无精度实证；规划器稳定性证据薄。定位：工程扎实但 thesis 适用窗口在快速收窄，不宜作 2026+ SOTA 对比基线

## [2026-04-24] Foundation 综述生成
- 生成：[[Foundation]]（wiki/themes/Foundation.md）
- 聚合 2 篇 paper wiki 页（[[Transformer-NeurIPS17]]、[[DeepSeek-V4-arXiv26]]，均为新建）
- 分类 2 个:架构基石 / 开源 Frontier 综合
- 主题综述聚焦 2017→2026 的 9 年架构传承线
- 值得关注方向 3 条:Transformer future work 富矿、foundation 可复现 benchmark、方法反向投射到小模型

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
  - [[TransferEngine-MLSys26]]（系统名；原 arXiv 版已于 2026-04-24 合并至 MLSys26 版）
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
