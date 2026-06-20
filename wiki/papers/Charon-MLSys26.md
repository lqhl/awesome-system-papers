---
type: paper
name: Charon
full_title: "CHARON: A UNIFIED AND FINE-GRAINED SIMULATOR FOR LARGE-SCALE LLM TRAINING AND INFERENCE"
authors: [Mengtian Yang, Zhekun Zhang, Mingheng Wu, Jianwen Yan, Hanshi Sun, Li-wen Chang]
venue: MLSys
year: 2026
tags: [llm-simulation, training, inference, design-space, parallelism]
source_pdf: "[[c9f0f895fb98ab9159f51fd0297e236d.pdf]]"
source_md: "[[c9f0f895fb98ab9159f51fd0297e236d]]"
---

# CHARON: A UNIFIED AND FINE-GRAINED SIMULATOR FOR LARGE-SCALE LLM TRAINING AND INFERENCE (MLSys 2026)

> **一句话总结**：现有 LLM simulator 训练/推理割裂且需手工 mock 模型，Charon 用 compiler-style pass 在原生 [[PyTorch]]/[[HuggingFace]]/[[vLLM]] 图上注入 [[TP]]/[[PP]]/[[FSDP]]/[[EP]] 并 hybrid profiling+analytical backend，端到端误差 **<5.35%**（大规模训练 **<3.74%**），并在 Llama-3-70B 推理案例中发现优于人工调优的部署配置。

## 问题与动机

[[LLM]] 训练/推理在万卡规模下，并行策略、拓扑、batch、fusion 的 design space 爆炸；集群 profiling 单点可达数百 GPU-hour，全空间探索不现实。既有 simulator（ASTRA-Sim、SimAI、Vidur 等）往往只覆盖训练或推理一端，需手工建 workload 或重建模型，算子级通信/重叠建模不足，难做 what-if 优化。

Charon  claim：把 simulation 当作 compiler transformation pipeline，统一训练+推理、原生模型接口、算子级多后端、可插拔 pass。

## 关键观察 / 隐含假设

- **观察 1：对称 Transformer 可单 block 仿真加速且保持数值/架构 fidelity；PP/非对称需 per-rank FX graph。**
  - **依赖假设**：单 block FLOPs/通信比例可代表全模型；prefill/decode 可拆图做 disaggregated 仿真。
  - **可能失效场景**：强 PP imbalance、encoder-decoder、或大量 custom op 时单 block 近似失效。

- **观察 2：混合 profiling DB + RF predictor + roofline analytical + 拓扑标定通信模型，可在速度与精度间 fallback。**
  - **依赖假设**：profiling DB 覆盖常见 op-shape；新 op 可退化 analytical 而不崩。
  - **可能失效场景**：全新 kernel/硬件代际无 DB 条目时误差上升，需重标定 cluster。

- **观察 3：图级 liveness 分析可比 layer-level simulator 更准确估 peak activation memory（ZeRO/FSDP 关键）。**
  - **依赖假设**：backward joint graph 由 `aot_autograd` 可靠生成。
  - **可能失效场景**：动态 shape、CUDA graph、或 custom autograd 时 trace 不完整。

- **假设 1：ratio + bandwidth-aware 重叠模型足以刻画 comm-compute overlap，无需 cycle-accurate NCCL。**
  - **证据强度**：**中**——与真机对比误差低，但拥塞极端场景可能低估。

## 核心方法

**Frontend**：`torch.fx`/`torch.compile` trace 原生模型 → pass 注入 shard（[[TP]]/[[SP]]/[[EP]]）、[[PP]] send/recv（1F1B、DualPipe）、[[DDP]]/[[FSDP]]/ZeRO 通信 → 融合/量化 rewrite → 多粒度 analyzer（MFU、timeline、peak memory）。

**Backend**：profiling / prediction / analytical / fused 四引擎 per-op 仿真；精度感知 FLOPs 与带宽；Ring/Tree collective 分解为 per-hop 标定延迟。

**Overlap processor**：comm-compute 与 comm-comm 重叠 slowdown；带宽感知 comm-comm 时间线。

**Design explorer**：参数搜索 + 剪枝找 cost-performance 最优配置。

## 设计取舍

- **单 block vs 全模型**：快但 PP/异构需例外路径。
- **Profiling 精度 vs 成本**：DB 缓存降本，新 shape 靠 predictor，最准最慢。
- **Analytical 可移植 vs 绝对精度**：跨平台靠标定 per-hop，非峰值规格纸面参数。
- **边界条件**：验证覆盖 LLaMA3/Qwen 系列；NPU 后端提及但 GPU 为主。

## 实验与结果

- 端到端误差：总体 **≤5.35%**；大规模 GPU 集群训练 **≤3.74%**。
- 对比 ASTRA-Sim/SimAI/Vidur 等：Charon 在更多配置下可给出有效结果且误差更低（Fig. 7）。
- 案例：Llama-3-70B 推理自动搜配置 **优于** 工程手工 baseline 吞吐。
- 相对集群 profiling 宣称 **>30k×** 成本降幅（需结合具体实验设定理解）。

## Critical Analysis

### 论证链条

碎片化痛点 → compiler pass 统一表示 → 多引擎 per-op + overlap → 低误差与 DSE 价值，逻辑闭合。单 block 外推全模型是主要未完全实验封闭的跳步。

### 假设压力测试

MoE 路由倾斜、故障恢复、弹性调度未建模时，production tail 行为可能偏离。Predictor 对超大 batch/长 context 新 shape 外推风险高。

### 实验可信度

与真机对比模型/配置多样；算子级 breakdown 支撑 claim。缺：与最新 [[SGLang]]/[[vLLM]] 线上 trace 闭环校验、多租户 inference scheduler。

### 系统性缺陷

论文未讨论 simulator 维护成本（随 PyTorch/vLLM 版本 drift）。安全/故障注入、straggler（对比 [[Guard]]）未集成。

## 局限与 Future Work

- **局限 1**：极端动态 workload、复杂 custom kernel 可能 trace 失败。
- **局限 2**：NCCL 拥塞仅近似，非 packet-level。
- **Future work 1**：与 production trace 自动校准 predictor，量化误差随时间漂移。
- **Future work 2**：集成 straggler/fault 模型做 resilient training what-if。

## 相关

- **相关概念**：[[Tensor-Parallelism|Tensor-Parallel]]、[[Pipeline-Parallelism|Pipeline-Parallel]]、[[FSDP]]、[[Expert-Parallelism|Expert-Parallel]]、[[Disaggregation]]
- **同类系统**：[[ASTRA-Sim]]、[[SimAI]]、[[Vidur]]
- **同会议**：[[MLSys-2026]]