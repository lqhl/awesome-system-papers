---
type: paper
name: BreakingTheIce
full_title: "Breaking the ICE: Analyzing Cold Start Latency in vLLM"
authors: [Huzaifa Shaaban Kabakibo, Animesh Trivedi, Lin Wang]
venue: MLSys
year: 2026
tags: [vllm, cold-start, serverless, inference, profiling, autoscaling]
source_pdf: "[[32bb90e8976aab5298d5da10fe66f21d.pdf]]"
source_md: "[[32bb90e8976aab5298d5da10fe66f21d]]"
---

# Breaking the ICE: Analyzing Cold Start Latency in vLLM (MLSys 2026)

> **一句话总结**：首次把 [[vLLM]] 冷启动拆成 6 个 CPU-bound 步骤并量化线性缩放规律，白盒分步回归预测器在 22 个模型上 MSE 仅 2.42 s，为 serverless LLM autoscaler 提供可解释的资源规划模型。

## 问题

Serverless LLM serving 在流量突发时要频繁拉起冷容器，冷启动延迟往往比 warm instance 高几个数量级，直接拉高 TTFT。社区已有 checkpoint 加速、[[Pipeline-Parallelism|pipeline parallelism]]、fast state materialization 等局部优化，但缺少对 [[vLLM]] 端到端启动过程的整体刻画——近 1.5 年 9 个 major release 启动时间方差 >4×，v0.9→v0.10 甚至减半。

难点在于：vLLM 代码库 ~280K 行 Python、V1 API 与 `torch.compile` 快速演进，且部署栈在 GPU/CPU/存储/模型族上高度异构。NVIDIA Dynamo、LLM-D 等容器化推理蓝图需要准确的 worker 启动成本模型，但现有 profiling 把启动当作整体生命周期的一环，未单独建模 engine initialization。

## 核心方法

**六步分解**（以 Llama3.2-3B 为例，总启动 20.32 s）：
1. **Framework Bootstrap**：平台探测、依赖 import、模型元数据拉取、Ray/multiprocessing worker 初始化；与模型规模基本无关
2. **Tokenizer Initialization**：词表文件加载；与 tokenizer 大小线性相关（PCC=0.99）
3. **Model Loading**：结构初始化 ~0.1 s；权重加载与参数量×精度线性相关（PCC=1.0）
4. **torch.compile**：Dynamo bytecode 变换 + compiled graph 加载；与 compiled graph 总大小线性相关（PCC≈0.96/0.95）
5. **KVCache Profiling**：dummy forward 测峰值显存以分配 [[KV-Cache]]；dense transformer 与模型大小线性，[[MoE]] 因 expert routing 偏离
6. **CUDA Graph Capturing**：与模型大小和 batch size 配置数均线性相关

核心发现：**整体启动以 CPU 为主**——除 KVCache profiling 和 CUDA graph capture 外，其余步骤 CPU-bound；换 H100→L40S GPU 几乎无加速，换 AMD EPYC 9354→Intel Xeon 8568Y+ CPU 影响更大。

**白盒分步预测器**：为每步独立拟合线性回归，按模型配置与环境参数聚合；验证集 MSE 2.42 s、最大误差 2.08 s（Llama3-3B），v0.11 上 MSE 2.62 s 仍准确。开源 profiler：https://github.com/upb-cn/vllm-startup-profiler

## 关键结果

- 22 个 LLM（dense/MoE/GQA/MLA 等）× H100/L40S × 多 CPU/存储配置的系统刻画
- vLLM 版本间启动时间差异可达 4×+；禁用 compile cache 时 graph storing 从 3–6 s 飙到 11–21 s
- SSD 冷读仅让 weight loading 慢 0.5×，总启动只改善 1.04×（该步仅占 7–10%）
- Tensorizer 加载 backend 比 Safetensors 快 53–60%；CoreWeave/Run:ai 等 streaming 方案可显著压缩 Model Loading
- 预测器可估计 sleep mode 等部分路径复用场景的启动成本

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[MoE]]、[[Chunked-Prefill]]
- **同类系统**：ServerlessLLM、ParaServe、Medusa、NVIDIA Dynamo、LLM-D、AIBrix
- **同会议**：[[MLSys-2026]]
- **对比**：[[vLLM-SOSP23]]（steady-state serving vs. 本文 cold start）