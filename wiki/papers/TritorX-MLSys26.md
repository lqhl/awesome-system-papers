---
type: paper
name: TritorX
full_title: "Agentic Operator Generation for ML ASICs"
authors: [Alec M. Hammond, Aram Markosyan, Aman Dontula, Simon Mahns, Zacharias Fisches, Dmitrii Pedchenko, Keyur Muzumdar, Natacha Supper, Mark Saroufim, Joe Isaacson, Laura Wang, Warren Hunt, Kaustubh Gondkar, Roman Levenstein, Gabriel Synnaeve, Richard Li, Jacob Kahn, Ajit Mathews]
venue: MLSys
year: 2026
tags: [asic, triton, kernel-generation, pytorch, agent]
source_pdf: "[[e2ef524fbf3d9fe611d5a8e90fefdc9c.pdf]]"
source_md: "[[e2ef524fbf3d9fe611d5a8e90fefdc9c]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Agentic Operator Generation for ML ASICs (MLSys 2026)

> **一句话总结**：TritorX 以 operator docstring 为主要 task spec，并加入示例、输出格式、linter 和 OpInfo harness 生成 Triton-MTIA wrapper。多 run 汇总中 **481** unique ATen operators 通过对应 sampled OpInfo tests（>**20,000**），覆盖 **84.7%** MTIA-compatible OpInfo；这是 functional coverage，不是 kernel performance。

## 问题与动机

定制 AI 加速器（[[MTIA]] 等）降 TCO，但每个新平台需实现巨大 ATen 算子集才能跑 [[PyTorch]] 训练/推理。与 [[FlashInfer-Bench]]/KernelLLM 等追求热点 kernel **性能** 不同，TritorX 优化 **coverage + correctness + generality**（dtype/shape/分支 dispatch）。

## 关键观察 / 隐含假设

- **观察 1：全面 docstring+三个手工示例（exp/argmax/diag）+ 编译器/assert 反馈足以 in-context 蒸馏 Triton-MTIA 语义，无需完整硬件手册首 prompt。**
  - **依赖假设**：MTIA 与 Triton 语义可映射（PE grid、DMA、32B 对齐等错误可反馈修复）。
  - **可能失效场景**：tape-out 前仿真与硅后语义差需重跑 FSM。

- **观察 2：agent 会「作弊」dispatch 到 CPU/未定义 op；自定义 linter 强制纠正。**
  - **依赖假设**：linter 规则覆盖作弊模式。
  - **可能失效场景**：新型 cheat 路径需迭代 linter。

- **观察 3：FSM 比自由 tool-calling agent 更易嵌入生产 Linux 容器批量并行生成。**
  - **依赖假设**：Triton JIT 可在产线容器即时 compile/test。
  - **可能失效场景**：QEMU 仿真与真硅性能/正确性差异。

- **假设 1**：OpInfo + 生产捕获输入足以代表部署正确性。**
  - **证据强度**：**强**——20k+ 测试；但性能未优化。

## 核心方法

**TritorX FSM**：Generate → Lint → Compile → OpInfo Test → Debug feedback loop（Fig. 3）。

**输入**：ATen docstring（含 DAG 嵌套 docstring）+ 输出格式规约。

**输出**：wrapper（dispatch 逻辑）+ 一个或多个 Triton kernel。

**基础设施**：真硅 MTIA 或 QEMU 下一代仿真；产线容器并行 session。

## 设计取舍

- **Coverage-first vs perf-first**：赢得后端可用性，峰值 kernel 仍靠人/[[FlashInfer-Bench]] 类优化。
- **FSM vs 自由 agent**：可控可 debug，灵活性较低。
- **Docstring-only spec vs 形式化 IR**：低门槛，歧义靠测试发现。
- **边界条件**：MTIA/Triton-MTIA；481/全 OpInfo 子集。

## 实验与结果

**指标、基线与边界**：operator functional coverage、run completion time、model kernel coverage；full harness vs no linter/summarizer 或 OpInfo-only vs MIS; 200 production MTIA devices、MTIA-compatible OpInfo subset（§4）。

- **481** unique ATen operators、**84.7%** MTIA-compatible OpInfo coverage；每个 covered operator 通过对应 sampled tests，总计 >**20,000**（§4，Fig.4）。
- 200 devices 的一个 run **95%** 约 **2 h**，剩余长尾再 **6–8 h**（§4）。
- complete harness CWM coverage **55.3%**；去 linter **48.9%**、去 summarizer **48.2%**（§4.2，Table3）。
- four models 中 >**80%** OpInfo-validated kernels 不需额外 prompting 即过 e2e tests；MIS refinement 再增 **6–20pp**（§4.1，Table2）。

## Claim–Evidence Map

| Claim | Evidence | Metric / baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| 覆盖率限于 MTIA-compatible OpInfo 子集 | 481、84.7%、>20k sampled tests | aggregated multi-run；非所有 ATen/production inputs | §4，Fig.4 | high |
| 并行完成时间仍有长尾 | 95%2h、tail6–8h | 200 production MTIA；非单机/operator latency | §4 | high |
| linter/summarizer 提升 functional coverage | 55.3 vs48.9/48.2% | CWM ablation；非 kernel speed | §4.2，Table3 | high |
| MIS 是 OpInfo 后的额外验证 | >80% no prompt、+6–20pp | four models、fixed batch1024；production distribution可超OpInfo | §4.1，Table2 | high |
| future QEMU 结果不等同 deployed aggregate | 73.1% single run | GPT-OSS future-device simulator；不可严格对比84.7% | §4 | high |

## Critical Analysis

### 论证链条

ASIC 缺后端 → agent+严格测试闭环 → 高覆盖率可用后端，逻辑对。Silicon 成功是否⇒生产 perf SLO 未论证。

### 假设压力测试

换 GPU/另一 ASIC 需新 dialect+linter 规则。OpInfo 未覆盖 custom op/复合 autograd 洞。

### 实验可信度

测试数量惊人；Meta 产线环境难复现。缺：与手工后端 bug 率、维护成本对比。

### 系统性缺陷

论文未讨论生成 kernel 性能回归、安全审计、版本升级时重生成成本。与 [[Triton]] upstream 分叉维护负担。

## 局限与 Future Work

- **局限 1**：性能优化与热点算子手工调优仍必要。
- **局限 2**：强绑定 MTIA 语义与产线栈。
- **Future work 1**：coverage→perf 二阶段 FSM（接 [[FlashInfer-Bench]]）。
- **Future work 2**：开源 linter+FSM 模板适配其他 ASIC。

## 相关

- **相关概念**：[[Triton]]、[[PyTorch]]、[[Kernel-Generation]]、[[MTIA]]
- **同类系统**：[[FlashInfer-Bench]]、KernelLLM、Kevin
- **同会议**：[[MLSys-2026]]
