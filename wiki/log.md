# Wiki Log

每条条目格式固定：`## [YYYY-MM-DD] {Page or Action}`，便于 `grep "^## \[" wiki/log.md | head -20` 解析。倒序排列，最新在上。

---

## [2026-05-26] FlashAttention-3-NeurIPS24 入库
- 下载 NeurIPS 官方 PDF + mineru + wiki paper：[[FlashAttention-3-NeurIPS24]]
- 更新：[[Flash-Attention]]、[[Attention]]、[[Continuous-Batching]]、[[Foundation]]、[[index]]
- 论文：面向 Hopper H100 重写 FA kernel，利用 TMA/WGMMA warp specialization、GEMM-softmax overlap、FP8 block quantization + incoherent processing；BF16 forward 最高 840 TFLOPs/s，FP8 forward 1.3 PFLOPs/s

## [2026-05-25] FlashAttention-2-ICLR24 入库
- 下载 arXiv PDF + mineru + wiki paper：[[FlashAttention-2-ICLR24]]
- 修复本地 MinerU：安装 `socksio`，脚本默认清理代理变量；Mac 上默认 `MINERU_DEVICE_MODE=cpu` 且关闭 formula/table 重模型，避免 MPS / formula / table 初始化卡住
- 更新：[[Flash-Attention]]、[[Attention]]、[[Continuous-Batching]]、[[Foundation]]、[[index]]
- 论文：在 FA1 exact attention 语义上优化 work partitioning，减少非 matmul FLOPs、沿 sequence length 并行、warp 内 split-Q；A100 attention forward 最高 230 TFLOPs/s，GPT-style 训练最高 225 TFLOPs/s/GPU

## [2026-05-24] FlashAttention-NeurIPS22 入库
- 下载 NeurIPS 官方 PDF + mineru + wiki paper：[[FlashAttention-NeurIPS22]]
- 更新：[[Flash-Attention]]、[[Attention]]、[[Sparse-Attention]]、[[Foundation]]、[[index]]
- 论文：IO-aware exact attention kernel，用 tiling + online softmax + backward recomputation 避免物化 `N x N` attention matrix，A100 上 attention 最高 7.6x 加速，显存线性随序列长度增长

## [2026-05-06] Finance 综述更新
- 更新：[[Finance]] 从 4 篇扩到 5 篇，新增 News Shock 分类 + 综述段落 + 方向 #5（News Shock 接入自动化 quant pipeline）
- index.md 已更新

## [2026-05-06] NewsShock-NBER26 入库
- 下载 PDF + mineru + wiki paper：[[NewsShock-NBER26]]
- 论文：将新闻 LLM embedding 正交分解为可预测部分与 news shock，后者构建的多空组合 Sharpe 3.1，为已知最大资产定价异常
- 未匹配到现有 entity/concept（金融 NLP 论文，与 AI 系统概念无交集）

## [2026-04-30] vLLM + SGLang 论文入库 + Foundation 综述更新
- 下载 PDF + mineru + wiki paper：[[vLLM-SOSP23]]、[[SGLang-NeurIPS24]]
- 新增 concept 页：[[RadixAttention]]
- 更新 entity 页：[[vLLM]]、[[SGLang]] 链接到 paper wiki
- 更新综述：[[Foundation]] 从 2 篇扩到 3 篇，新增 vLLM/SOSP 2023 作为「LLM Serving 基础设施」milestone

## [2026-04-30] AI-Infra 综述更新 + 6 篇新 paper wiki 页
- 新增 paper wiki：[[CacheGen-SIGCOMM24]]、[[CacheBlend-EuroSys25]]、[[LMCache-arXiv25]]、[[PASTA-ICLR24]]、[[LLMSteer-NeurIPSW24]]、[[Cartridges-ICLR26]]
- 更新综述：[[AI-Infra]] 从 5 篇扩到 12 篇，新增两条主线：KV Cache 跨请求复用与传输（CacheGen→CacheBlend→LMCache 三部曲）+ KV Cache 后处理与可编辑性（PASTA→LLMSteer→Cartridges 演化轨迹）
- 六篇均下载 PDF 到 papers/ai-infra/、mineru 解析到 markdowns/ai-infra/

## [2026-04-30] fabric-lib-MLSys26 arXiv v1→v2 更新
- arXiv 2510.27656 v2 (2026-04-13) 替换 v1
- 项目更名为 **fabric-lib**（TransferEngine 为其核心引擎），开源在 https://github.com/perplexityai/pplx-garden
- 新增：KvCache TTFT 端到端数据（Qwen3-235B A100）、RL 权重传输 latency breakdown、端到端 MoE decode speed 表、dual-batch overlap 分析、host-proxy CPU overhead 分解
- 新增：IMMCOUNTER PCIe ordering 正确性论证、Section 8 Discussion（GPU-initiated RDMA + 新 NIC 支持）、附录 A/B 伪代码
- 重跑 mineru + wiki-paper 覆盖

## [2026-04-25] ATC-2025 综述生成
- 生成：[[ATC-2025]]
- 聚合 100 篇 paper wiki 页
- 分类 11 个：LLM 推理与服务 / LLM/MoE 训练与 Checkpoint / GPU/加速器调度与 Kernel / 网络协议 CC 与在网计算 / 流媒体 RTC 云网关 / 卫星与空间计算 / OS 虚拟化 Container 内存 / 存储与文件系统 / 数据库与大数据 / 安全可靠性与故障 / 编译器 Shell 其他工具
- 此前 ATC 2025 无 paper wiki 页；13 个并行 agent 批量生成全部 100 篇
- 主线信号：LLM serving 多模型多租户托管 + 国内 hyperscaler 生产论文集中曝光 + SmartNIC/DPU/CXL/PIM/Tofino 异构硬件横贯 + Rust framekernel + model checking 工程交付（Asterinas/Converos）

## [2026-04-25] FAST-2026 综述生成
- 生成：[[FAST-2026]]
- 聚合 44 篇 paper wiki 页
- 分类 7 个：LLM 推理与训练存储 / 生产规模云存储经验 / CXL 解聚存储与跨虚拟化 I/O / SSD I/O 路径与内核栈 / 纠删码 GC 与数据放置 / 缓存分层与多资源调度 / 文件系统创新 / 索引同步时序与可信存储
- 此前 FAST 2026 无 paper wiki 页；8 个并行 agent 批量生成全部 44 篇

## [2026-04-25] SOSP-2025 综述生成
- 生成：[[SOSP-2025]]
- 聚合 66 篇 paper wiki 页
- 分类 11 个：LLM 推理与服务 / LLM 训练与多 GPU 系统 / GPU OS 与加速器抽象 / SmartNIC·RDMA·CXL·FPGA / 存储与文件系统 / 分布式系统·事务·规划 / 内存管理·远程内存 / OS 基础·嵌入式·教学 / 形式化验证·应用安全 / eBPF·可靠性·Fuzzing / Serverless·恢复·弹性
- 此前 SOSP 2025 无 paper wiki 页；9 个并行 agent 批量生成全部 66 篇

## [2026-04-24] wiki-lint
- Broken: 402（绝大多数是未建页橘色链接） | Hybrid paren: 2 | 缺页建议: 21 | Orphan: 0 | Frontmatter: 0 | Log 违规: 0 | Alias 冲突: 0 | 命名违规: 1
- 需人工修 hybrid paren：wiki/papers/T2C-OSDI25.md:44、wiki/papers/TrainCheck-OSDI25.md:45
- 高优先建页：LLM-Inference (inbound 13)、Prefix-Caching (13)、Transformer (8)、RAG (7)、RadixAttention (7)
- 模式：read-only

## [2026-04-24] OSDI-2025 综述生成
- 生成：[[OSDI-2025]]
- 聚合 53 篇 paper wiki 页
- 分类 10 个：LLM 推理与服务 / 分布式训练 / GPU Kernel·Compiler·Profiling / 存储与 I/O / 分布式系统与数据库 / 网络 / 内存管理与虚拟化 / 安全·沙箱·隐私 / 形式验证与可靠性 / 异构加速·Serverless·其他
- 此前 OSDI 2025 无 paper wiki 页；9 个并行 agent 批量生成全部 53 篇

## [2026-04-24] 补齐 Top 10 缺页 concept
- 背景：lint 发现 141 个"被引用但无文档"的 wiki 页，inbound 最高的 10 条全部是核心 concept
- 新建 concept 页 10 篇（均在 wiki/concepts/）：
  - [[Flash-Attention]]（inbound 26，aliases 含 FlashAttention 系列）
  - [[Tensor-Parallelism]]（inbound 21）
  - [[Continuous-Batching]]（inbound 21）
  - [[Attention]]（inbound 18，foundational）
  - [[Quantization]]（inbound 16）
  - [[Expert-Parallelism]]（inbound 16）
  - [[Pipeline-Parallelism]]（inbound 15）
  - [[Chunked-Prefill]]（inbound 15）
  - [[RDMA]]（inbound 10）
  - [[LoRA]]（inbound 9）
- 每页 frontmatter 齐全（aliases / parent / introduced_by / tags）+ "引用本概念的论文" 节点名对齐实际 wikilink
- concept 目录从 5 页扩到 15 页，剩余 131 个缺页由后续 /wiki-lint 按阈值分批补

## [2026-04-24] Finance 综述生成
- 生成：[[Finance]]
- 聚合 4 篇 paper wiki 页(全部新建,从 markdowns/finance 提取):[[101-Alphas-arXiv15]]、[[151-Trading-Strategies-SSRN18]]、[[TimesFM-Fin-arXiv24]]、[[RD-Agent-Quant-arXiv25]]
- 分类 3 个:Formulaic alpha 与策略参考库 / LLM-driven 多 agent 自动化 quant R&D / Time-series foundation model 金融适配
- 主题综述 3 段:从封闭披露到公开自动化 10 年 / agent 路线 vs foundation-model 路线 / Kakushadze 2015 在 2025 仍是基线的信息论解释
- 值得关注方向 4 条,聚焦小团队可做:大规模 formulaic alpha 语料扩写 / TimesFM-Fin 金融 scaling 曲线 / agent+foundation joint system / Kakushadze 公式集的独立复现基准

## [2026-04-24] TransferEngine: arXiv 版并入 MLSys26 版
- 背景：[[fabric-lib-MLSys26]] 正式发表，arXiv preprint 2510.27656v1 为同文早版本
- 清理 raw 层：删除 `papers/ai-infra/2510.27656v1.pdf`、`markdowns/ai-infra/2510.27656v1/`
- 清理 wiki 层：删除 `wiki/papers/TransferEngine-arXiv25.md`
- 重定向 wikilink：所有 `[[TransferEngine-arXiv25]]` → `[[fabric-lib-MLSys26]]`
  - index.md（arXiv / AI-Infra 专题列表 6→5 篇，TransferEngine 转入 MLSys-2026）
  - DeepSeek-V4-arXiv26、Libra-ICLR26、LatencyOptimal-MoELB-INET4AI25（同期/基础设施引用）
  - concepts: MoE / PagedAttention / KV-Cache / Disaggregation / Speculative-Decoding
  - themes/AI-Infra（主线二综述段 + 值得关注方向第 3 条）
  - entities/vLLM（演进时间线 / 相关论文 / 开放问题）
- MLSys26 paper 页「同类系统」删去对 arXiv25 的自引用

## [2026-04-24] Auto-Research 综述生成
- 生成：[[Auto-Research]]
- 聚合 11 篇 paper wiki 页（全部新建，从 markdowns/autoresearch 提取）:[[MLAgentBench-ICML24]]、[[OpenHands-ICLR25]]、[[AI-Scientist-arXiv24]]、[[MLE-Bench-ICLR25]]、[[AI-Scientist-v2-arXiv25]]、[[Auto-Research-arXiv25]]、[[MLR-Bench-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[FunSearch-Nature24]]
- 分类 4 个：端到端自主科研系统 / Evolutionary 算法与架构发现 / ML Agent 评测基准 / 通用 Agent 平台
- 主题综述 5 段：从 benchmark 到真 discovery 的 arc / LLM-as-agent vs LLM-as-mutator 两条范式 / Benchmark 三层递进与可信度危机 / AlphaEvolve+OpenHands 部署即试金石 / "科学发现 scaling law" 是最激进 claim
- 值得关注方向 5 条，聚焦小团队可做：verifiable 窄域 discovery / integrity-first verifier / 领域特化 mini-AI-Scientist / compute-efficient scaling law 对照验证 / reproducibility infrastructure

## [2026-04-24] FluxMoE-arXiv26 paper wiki + wiki-update
- 生成：[[FluxMoE-arXiv26]]
- 命名：系统名 FluxMoE（论文自命名，abstract & intro 反复使用）
- 补 wikilink：paper 页首次出现 [[MoE]]、[[vLLM]]、[[KV-Cache]]、[[SGLang]]、[[PagedAttention]]、[[Disaggregation]] 均在写入时直接加 link，无需二次补
- 更新：wiki/concepts/MoE.md、wiki/concepts/KV-Cache.md、wiki/concepts/PagedAttention.md、wiki/concepts/Disaggregation.md、wiki/entities/vLLM.md 的「引用本概念的论文」/「相关论文」节
- 无新 TODO 缺页（watchlist 里 Mooncake/DistServe/ZeRO-Infinity/FlexGen 等虽提及，本已在其他 log 条目中登记；lossless-compression 出现在 paper 但未列入 watchlist，暂不升级）
- 追加「批判与局限」节：7 点批判 + 定位——thesis 被 [[DeepSeek-V4-arXiv26|DeepSeek-V4]] 等模型侧 FP4 + KV 压缩釜底抽薪；context 只测 4K 无法外推；claim target PD-disaggregated decode 但没测 PD 分离；L40 硬件选择偏向自己；baseline 弱；无精度实证；规划器稳定性证据薄。定位：工程扎实但 thesis 适用窗口在快速收窄，不宜作 2026+ SOTA 对比基线

## [2026-04-24] Foundation 综述生成
- 生成：[[Foundation]]
- 聚合 2 篇 paper wiki 页（[[Transformer-NeurIPS17]]、[[DeepSeek-V4-arXiv26]]，均为新建）
- 分类 2 个:架构基石 / 开源 Frontier 综合
- 主题综述聚焦 2017→2026 的 9 年架构传承线
- 值得关注方向 3 条:Transformer future work 富矿、foundation 可复现 benchmark、方法反向投射到小模型

## [2026-04-24] MLSys-2026 综述生成
- 生成：[[MLSys-2026]]
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
- 生成：[[AI-Infra]]，3 主线综述 + 3 个 open problems direction
- 更新：[[index]] 加入 7 个 seed 页 + 1 个 theme 页 + 5 篇 paper 索引

## [2026-04-24] Phase 2: 7 个 seed entity/concept 页
- entities: [[vLLM]]、[[SGLang]]
- concepts: [[KV-Cache]]、[[MoE]]、[[PagedAttention]]、[[Speculative-Decoding]]、[[Disaggregation]]
- 数据来源：从 5 篇 ai-infra paper wiki 页 + 已读 markdown 提取
- 这些页存在后，5 篇 paper 里的 wikilink 自动解析（橘色 → 蓝色）

## [2026-04-24] Phase 1 mini pilot：ai-infra 5 篇 wiki paper 页
- 生成：
  - [[fabric-lib-MLSys26]]（系统名；原 arXiv 版已于 2026-04-24 合并至 MLSys26 版）
  - [[Libra-ICLR26]]（系统名）
  - [[AttnRes-arXiv26]]（方法名）
  - [[MSA-arXiv26]]（方法名）
  - [[LatencyOptimal-MoELB-INET4AI25]]（方法名 + workshop）
- 命名验证：3 个用系统名/方法名，1 个用 workshop 简写做后缀
- 暂未做：自动 wiki-update（wiki/entities, wiki/concepts 还是空的，无可补 wikilink 的目标页）—— 已在下一条 Phase 2 中通过补 seed 页解决

## [2026-04-24] wiki 初始化
- 新建目录结构：`papers/`、`conferences/`、`entities/`、`concepts/`、`comparisons/`、`themes/`
- 新建占位：`index.md`、`log.md`
- 触发：落地 Karpathy 风格 LLM Wiki 架构，废弃旧 `reports/` 和 `ideas/`
