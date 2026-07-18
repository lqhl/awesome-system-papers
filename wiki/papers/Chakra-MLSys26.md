---
type: paper
name: Chakra
full_title: "Chakra: Advancing Performance Benchmarking and Co-design using Standardized Execution Traces"
authors: [Srinivas Sridharan, Taekyung Heo, Louis Feng, Zhaodong Wang, Matt Bergeron, et al.]
venue: MLSys
year: 2026
tags: [benchmark, distributed-training, co-design, execution-trace, simulation]
source_pdf: "[[34173cb38f07f89ddbebc2ac9128303f.pdf]]"
source_md: "[[34173cb38f07f89ddbebc2ac9128303f]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Chakra: Advancing Performance Benchmarking and Co-design using Standardized Execution Traces (MLSys 2026)

> **一句话总结**：MLPerf 等全量 benchmark 适合已部署系统对比，但 AI 创新节奏要求更敏捷的 HW-SW co-design；Chakra 用最小可扩展图 schema 标准化 execution trace（ET），配套 converter/visualizer/generative 合成与 ASTRA-sim 仿真，让厂商在不泄露模型细节下交换 workload 并做性能投影——Transformer 扩 NPU 可持续提速，而 comm-bound 的 MLP-MP 在最低带宽下 exposed communication 可达总计算 **128×**。

## 问题与动机

现代分布式训练依赖 [[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]] 及 [[Expert-Parallelism]] 等混合并行，但最优并行策略仍是开放问题。社区共识是 benchmarking 与 HW-SW co-design 对下一代 AI 平台至关重要：**MLPerf 等全量 benchmark** 适合系统落地后的公平对比，却无法跟上模型与硬件的快速迭代；而面向未来系统的 simulator/emulator 需要更敏捷的 workload 规格化方法。

更深层的障碍是 **组织间 IP 壁垒**：超大规模云厂商与硬件厂商往往只能在 NDA 下用 spreadsheet 交换模型参数，多数 vendor 与学术研究者只能从公开 benchmark 反推 workload，容易 overfit 少数用例并忽视 Amdahl 定律。作者 claim：需要一种类似 instruction/memory trace 的 **execution trace（ET）**——编码算子维度、通信模式与依赖，但不暴露模型结构与数据集细节，使 SW 公司可向 HW 厂商共享内部 workload，HW 方用 proprietary simulator 优化下一代 NPU，反馈再指导 SW 侧 compute/network 配置。

当前痛点还包括：PyTorch/TensorFlow 等框架在运行时其实能拿到 ET 所需信息，却**没有统一交换 schema**；各框架 ET 格式不一阻碍跨组织协作；缺少 toolchain（converter、visualizer、feeder）；也缺少能在保护 IP 前提下合成「未来 what-if」trace 的机制。

## 关键观察 / 隐含假设

- **观察 1**：ML 任务本质是图——compute、memory、communication 算子及其依赖足以支撑性能建模，**不必泄露模型权重或数据**。
  - **依赖假设**：下游 simulator/replay benchmark 只关心算子规模、类型、依赖与（可选）耗时，不关心具体 tensor 语义；ET 粒度足以区分瓶颈在 compute 还是 exposed communication。
  - **可能失效场景**：需要精确数值行为（收敛、loss landscape）的 co-design；或算子 fusion/编译器重写使 pre-execution trace 与真实执行图严重偏离。

- **观察 2**：框架原生 ET（如 PyTorch Execution Graph Observer）最贴近真实执行，但 **post-execution trace 与采集系统强绑定**（NPU 数、计算时间、网络延迟耦合），难以直接用于未来硬件投影。
  - **依赖假设**：通过 schema 分层（pre- vs post-execution）+ simulator 侧重算 compute/comm 时间，可以把「结构 trace」与「时间 trace」解耦。
  - **可能失效场景**：论文明确承认——**如何在真实系统上采集又不 tightly bound 到该系统**仍是 open question；若优化策略随目标拓扑变化（不同 collective 算法、不同 overlap），单一 trace 可能不够。

- **观察 3**：生产 collective trace 共享既可能泄露模型信息，又体量过大无法全量 replay；**master trace + hierarchical generative model** 可在满足 replay 硬约束下压缩、合成并自然脱敏。
  - **依赖假设**：通信子图的 collective 类型组成、message size 分布、rank 间约束可用统计模型近似；合成 trace 在 replay 系统上行为正确即足够代表生产 workload。
  - **可能失效场景**：compute-communication overlap、细粒度依赖结构尚未纳入生成模型（论文称可扩展但未验证）；攻击者若结合多份合成 trace 可能部分反推模型结构——论文未做隐私威胁模型分析。

- **观察 4**：分布式训练性能往往受 **exposed communication**（未与计算 overlap 的通信）主导，扩 NPU 或加带宽并不单调改善端到端时间。
  - **依赖假设**：ASTRA-sim 类离散事件仿真 + Chakra ET 能分解 compute vs exposed comm，并外推到新拓扑/带宽。
  - **可能失效场景**：仿真假设各 NPU 可异步执行不同算子、通信时间可从 ET 直读或按带宽模型估算——真实 NCCL 调度、拥塞、kernel launch 开销可能使投影偏差；论文仅在 2D-torus 与 DGX2-like 两种拓扑、三档模型上验证。

- **假设 1**：**每 NPU 一份独立 trace** 足以覆盖当前工业界 replay/simulation 需求。
  - **证据强度**：**中**——简化采集与 feeder 实现，与 PARAM/Mystique 生产路径一致；但牺牲全局 scheduler 动态重分配能力，论文在 §3.3.2 已承认。

- **假设 2**：行业会采纳开放 schema 而非各自维护私有 ET 格式。
  - **证据强度**：**弱**——论文为 workshop/ecosystem 倡议型工作，converter 仅覆盖 PyTorch/FlexFlow，TensorFlow 列为 future work；正文以 soliciting feedback 收尾，尚无广泛第三方采纳证据。

## 核心方法

Chakra 是以 **Chakra ET** 为中心的 performance modeling 基础设施（Figure 1）：框架采集 ET → converter 归一化 → simulator/replay benchmark 消费。

### Chakra ET schema（回应观察 1）

节点最小字段：`id`、`name`、`type`、`parent`（依赖）、`attribute`（key-value 扩展，借鉴 ONNX）。`type` 枚举覆盖 `MEM_LOAD/STORE`、`COMP`、`COMM_SEND/RECV/COLL`。设计目标：**minimal yet extensible**、可建模 memory/compute/network、可表达任意执行阶段（pre/post-execution）。额外元数据全部塞进 `attribute`，代价是 collection/parsing 代码更复杂。

### 采集与合成（回应观察 2–3）

**真实采集**：扩展 PyTorch **Execution Graph Observer**（非侵入式开关即可采集），trace 贴近真实执行但绑定采集系统。

**合成**：对 collective 子图引入 **master trace**——在遵守 process group 硬约束下对多 rank trace 做无损压缩，再从中学习分布。Hierarchical generative model（Figure 2）分阶段生成：Comm Type Generator（拟合 collective 组成聚类）、Message Size Generator（GMM 拟合各 collective 的 message size 分布）等，并建模 comm sequence length、GPU size、autocorrelation、message split 等。优势是模块化、可调试；论文报告合成 trace 在训练集群 replay **正确**。

### 开源工具链（回应观察 1）

- **ET converter**：PyTorch JSON、FlexFlow graphviz → Chakra；按节点名识别 `record_param_comms` / `nccl:` 子节点；多 NPU 输入需正确切分。FlexFlow collective 被拆成多 P2P，与 PyTorch 语义不同。
- **Execution trace visualizer**：graphviz/PDF 展示依赖（Figure 3）。
- **Timeline visualizer**：对接 callback-based simulator 的 CSV，Chrome tracing 查看 compute/comm overlap 与瓶颈（Figure 4）。
- **Test case generator**：C++ API 手写 DP/MP/PP 合成 trace。
- **Trace feeder**：C++ 库供 ASTRA-sim 等解析节点与依赖（Snippet 3）。

### 用例闭环（回应观察 4）

1. **Replay benchmark**：PARAM Comms Replay → Mystique（PARAM Full Replay）用 PyTorch ET 从生产 fleet 自动生成 benchmark；Chakra 标准化后可接入多框架来源。
2. **Simulation**：修改 **ASTRA-sim-v2** 读 Chakra ET——workload layer 用图驱动替换 v1 文本输入；支持每 NPU 不同算子并发；节点耗时可从 ET 直读（建模真实采集系统）或由 simulator 按算力/带宽重算（建模未来系统）。
3. **组件级建模**：Dreamshard、GPU performance model 等已用 trace 做 embedding sharding 与 iteration latency 估计（<10% GMAE 级误差，引用工作）。

## 设计取舍

- **Schema 极简 + attribute 扩展**：降低跨组织采纳摩擦，但 parser/feeder 复杂度高，且缺少强类型字段易导致语义漂移（不同 converter 对同一 attribute key 解释不一致）。
- **Pre-execution vs post-execution 兼容**：提升投影灵活性，但采集侧如何产出「结构正确、时间解耦」的 trace 尚无标准答案——converter 往往只能拿到 post-execution 时间戳。
- **每 NPU 独立 trace**：采集/replay 简单，牺牲全局调度与跨 NPU 动态负载均衡 co-design。
- **Execution trace vs execution graph**：Chakra 面向 replay/simulation，不保证可执行正确性；与 ONNX（模型交换）目标正交。
- **Generative 先 comm 后 full trace**：快速解决 IP 共享与 collective benchmark 代表集问题，但 compute 节点、overlap、端到端依赖尚未纳入生成闭环。
- **边界条件**：最适合 **已有内部 trace 的超大规模训练方 + 有 proprietary simulator 的硬件厂商** 之间的 NDA 外交换；对无 trace 采集能力的学术小组，test case generator 只能覆盖合成小规模样例。

## 实验与结果

- **端到端 PoC**：PyTorch ET → Chakra converter → **ASTRA-sim-v2** 驱动分布式训练仿真（Figure 5）。
- **扩 NPU（4/16/64，2D-torus vs DGX2-like）**（Figure 6–7）：仅 **Transformer**（165M，hybrid MP-DP + ZeRO-2）在 2D-torus 上随 NPU 增加性能持续提升——四 NPU 时总 compute 约为总 comm 的 **25×**，扩 NPU 降 compute 收益大于 exposed comm 增长。**MLP-MP** 则 exposed comm 主导，扩 NPU 反而变慢。**DLRM**（embedding MP + MLP DP）介于两者之间。
- **变网络带宽（64 NPU）**（Figure 8）：2D-torus 普遍优于 DGX2-like；**MLP-MP** 对带宽最敏感——最低带宽组合下 exposed communication 为总 computation 的 **128×**。
- **合成 trace**：hierarchical model 生成的 collective trace 通过 replay 系统验证，可在训练集群正确运行。
- **模型来源**：MLP ET 为 synthetic；Transformer/DLRM ET 来自真实模型经 converter 转换。

## Critical Analysis

### 论证链条

问题（IP 壁垒 + 无统一 ET + co-design 敏捷性）→ Chakra schema + toolchain + generative synthesis → ASTRA-sim PoC 与 PARAM/Mystique 生产路径衔接，逻辑在 **「交换结构化 workload 规格」** 这一层闭合。较弱环节：从 **合成/转换后的 ET** 到 **未来硬件性能数字** 的跳步依赖 ASTRA-sim 建模假设与少量拓扑/模型，尚未证明跨 vendor simulator 可互操作；生态采纳属于愿景，实验主要是 **自洽 PoC** 而非第三方复现竞赛。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效 |
|------|-----------|----------|
| ET 足以代表生产 training workload | Mystique/PARAM 先例 + Chakra 转换 DLRM/Transformer | 推理、多模态、动态 shape、频繁 graph break 时 ET 维护成本高 |
| 合成 collective trace 可代表生产 | Replay 正确性 + 分布对齐 | 未验证端到端训练时间误差；compute 未合成时无法评估 overlap 敏感作业 |
| ASTRA-sim 投影可指导硬件投资 | 扩 NPU/带宽趋势与 breakdown 合理 | 未与真实集群测量对比；仅 2 种拓扑、3 个模型 |
| Schema 开放即可形成生态 | 开源工具链存在 | ONNX 亦开放但 interoperability 仍靠持续对齐；attribute 语义标准化缺位 |

### 实验可信度

**强项**：结合工业界 PARAM/Mystique 生产 benchmark 叙事；ASTRA-sim-v2 改动清晰（图驱动 workload + 每 NPU 异构执行）；结果强调 **exposed comm** 分解，解释「扩 NPU 不总是更快」的反直觉现象；合成模型有 modular ablation 空间。**弱点**：（1）仿真未与真实硬件端到端校验同一 Chakra ET；（2）模型与规模有限（165M Transformer、合成 MLP、DLRM），无千亿级 MoE；（3）generative 评估偏 collective 正确性与分布拟合，缺 **simulator 输出误差** 量化；（4）原文 ACM 格式标注 MLBench'23 workshop，篇幅与评估深度偏倡议型——wiki 标注 MLSys 2026 时读者应意识到可能是扩展/再发表版本，核心证据仍来自 workshop 级 PoC。

### 系统性缺陷

- **互操作与语义一致性**：attribute key-value 扩展灵活，但跨组织 **schema 版本与语义契约** 论文未讨论；converter 对无法识别节点标 `INVALID` 并丢弃，可能静默丢失关键路径。
- **隐私与安全**：generative obfuscation 无形式化隐私保证；多份合成 trace 或 side channel 反推风险 **论文未讨论**。
- **运维与规模**：全 fleet 定期采集 ET 的数据量、存储、合规与 retention 仅一笔带过；「代表 trace 子集」选择算法未给出。
- **尾延迟与故障**：replay benchmark 不建模 straggler、checkpoint 失败、网络抖动；simulation 为周期精确抽象，**论文未讨论** tail 行为。
- **可观测性**：visualizer 利于 debug，但生产 pipeline 中 ET 质量监控、converter 回归测试框架 **论文未展开**。
- **实时 co-design**：ET 采集与合成偏 offline；在线训练过程中动态反馈硬件设计 **未覆盖**。

## 局限与 Future Work

- **局限 1**：**post-execution trace 与采集系统绑定** 问题未解决，性能投影仍依赖 simulator 重算或接受偏差。
- **局限 2**：generative model 当前主要覆盖 **communication 子图**，compute、compute-comm overlap、全局依赖结构仍待扩展。
- **局限 3**：**每 NPU 独立 trace** 假设限制全局调度类 co-design；schema 不禁止全局 trace，但 tooling 未实现。
- **局限 4**：converter **未支持 TensorFlow**；FlexFlow 与 PyTorch collective 语义差异需人工理解。
- **局限 5**：评估以 ASTRA-sim 为主，缺少 **多 simulator（SST 等）交叉验证** 与第三方独立采纳案例。
- **Future work 1**：定义 **pre-execution 采集规范**（时间解耦、拓扑无关 collective 规格），并用同一 ET 在真实系统 vs simulator 上量化投影误差。
- **Future work 2**：将 generative pipeline 扩展到 **full trace**（compute + overlap + 依赖），并以 end-to-end simulator GMAE 作为合成质量门槛，而非仅 replay 正确性。
- **Future work 3**：建立 **Chakra schema 版本化与 conformance test suite**（类似 MLPerf 的 ET 互认），降低 attribute 语义漂移风险。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Data-Parallelism]]、[[Expert-Parallelism]]、execution trace、HW-SW co-design、replay benchmark
- **同类系统**：MLPerf、ASTRA-sim、PARAM replay / Mystique、ONNX（模型交换，目标不同）、FlexFlow
- **同会议**：[[MLSys-2026]]
- **对比**：ONNX 交换 **可执行模型图**；Chakra 交换 **性能建模用执行 trace**。MLPerf 提供端到端 benchmark score；Chakra 提供可敏捷更新、可脱敏的 **算子级 workload 规格**，更适合 simulator 与未部署硬件
