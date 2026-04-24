---
type: paper
name: TritorX
full_title: "Agentic Operator Generation for ML ASICs"
authors: [Alec M. Hammond, Aram Markosyan, Aman Dontula, Simon Mahns, Zacharias Fisches, "et al."]
venue: MLSys
year: 2026
tags: [kernel-generation, agent, triton, mtia, pytorch, llm-coding]
source_pdf: "[[e2ef524fbf3d9fe611d5a8e90fefdc9c.pdf]]"
source_md: "[[e2ef524fbf3d9fe611d5a8e90fefdc9c]]"
---

# Agentic Operator Generation for ML ASICs (MLSys 2026)

> **一句话总结**：Meta 的 TritorX 用开源 LLM + FSM 反馈循环自动生成 Meta MTIA 加速器的 Triton PyTorch ATen kernel，覆盖 481 个 unique 算子（84.7% MTIA-compatible OpInfo 覆盖率），通过 20,000+ OpInfo 测试；目标是「overnight 生成完整 PyTorch ATen backend」。

## 问题

每新发一代 AI ASIC（如 Meta MTIA）都要重做 PyTorch ATen 算子库（>600 ops，覆盖多 dtype / shape / argument）。现有 kernel 生成工作（KernelBench 系等）多聚焦「少数关键 kernel 的 performance」，而新芯片上线首要是 **coverage / correctness**——没有 operator 覆盖，模型根本跑不通。手工编 kernel 耗时且新硬件文档滞后于编译器。

## 核心方法

**TritorX = LLM + 有限状态机 + 生产测试harness**：

1. **FSM 架构（不用 reasoning agent）**：状态包括 `Generate Kernel` → `Lint` → `JIT Compile + Test` → `Feedback`，显式 guardrail 好 debug，更适合生产。
2. **In-context 蒸馏 MTIA 语义**：初始 prompt 只给 ATen docstring + 3 个手写示例（exp / argmax / diag），靠执行反馈（linter / compiler / debugger）迭代学习 Triton MTIA 方言。
3. **自研 Linter 防"作弊"**：阻止 LLM 生成代码里调用未实现的 ATen 算子或 host fallback；确保 Triton MTIA 语法合法。
4. **双测试 harness**：(a) OpInfo（PyTorch 原生，一个 op 数百个 sample 覆盖各 dtype/shape/args）；(b) 生产模型 captured input data。每个 op 配对超 20,000 项测试。
5. **反馈策略**：compile 错误经次要 LLM 摘要压缩（避免 context 溢出）；runtime 崩溃加载 LLDB backtrace；accuracy error 摘要 tensor 值。
6. **规模化部署**：200 台生产 MTIA 设备，LLM 走内部中心推理服务，2 小时完成 95%，剩余尾部 6-8h。可用 QEMU 模拟未来 MTIA 代际。

## 关键结果

- **481 个 ATen 算子**通过全部 OpInfo 测试（84.7% MTIA-compatible 覆盖率，总 20,000+ 测试）。
- LLM 用 Code World Model (CWM) 或 GPT-OSS 120B（context 131K、temp 1.0）；Llama-4-Maverick 做反馈摘要。
- 算子类别差异大：Shape Manipulation 96.0%，Deep Learning 71.1%（GPT-OSS 好于 CWM 多数场景）。
- 端到端模型：NanoGPT、DLRM、两个 Meta 内部推荐模型，operator coverage 79.8-87.2%。OpInfo-validated kernel 直接套用生产数据通过率 80%+，refine 后再 +6-20%。
- 新一代 MTIA QEMU 模拟下单跑 73.1%，收集的 compiler failure 反馈给硬件/编译器团队。

## 相关

- **相关概念**：Kernel Generation、Triton、Finite State Machine、Agentic AI、Code Generation
- **相关系统**：KernelBench、[[Flash-Attention]]（Triton 典型用例）、PyTorch ATen
- **相关硬件**：Meta MTIA、Nvidia GPU、LPDDR vs HBM
- **同会议**：[[MLSys-2026]]
