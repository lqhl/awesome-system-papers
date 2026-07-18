---
type: paper
name: Neutrino
full_title: "NEUTRINO: Fine-grained GPU Kernel Profiling via Programmable Probing"
authors: [Songlin Huang, Chenshu Wu]
venue: OSDI
year: 2025
tags: [gpu-profiling, ebpf, assembly, observability, ml-systems]
source_pdf: "[[osdi25-huang-songlin.pdf]]"
source_md: "[[osdi25-huang-songlin]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# NEUTRINO: Fine-grained GPU Kernel Profiling via Programmable Probing (OSDI 2025)

> **一句话总结**：NEUTRINO 在 PTX/GCNAsm 层运行时插桩，提供 eBPF 式可编程 probe + DMAT 可视化，NVIDIA/AMD 上多数 probe 仅 **1.04×** 慢、+4.11 寄存器，并能区分 FlashAttn v1/v2 的 memory 与 pipeline 行为差异。

## 问题与动机

GPU 在 scaling law 时代主导 ML 系统，但 kernel 对 host OS **原子不可见**；NCU/CUPTI 等采样依赖硬件 PM，难做 instruction-level、value+time 双域 profile。NvBit 等改 machine code，JIT/AOT 两路编译栈难统一。

## 关键观察 / 隐含假设

- **观察 1**：AOT（ATen）与 JIT（[[Triton]]/LLVM）在 **parallel assembly** 层汇合，运行时 assembly 插桩可 kernel-inclusive 且 hardware-independent。
  - **依赖假设**：驱动暴露足够接口以 hook 加载/替换 assembly；用户接受重启/重载 kernel。
  - **可能失效场景**：仅 machine code 可用、assembly 不可见的路径。
- **观察 2**：SIMT 下线程内顺序执行 + 独立 probe 寄存器组 → probe 可与原程序 **时间/资源虚拟分离**。
  - **依赖假设**：register allocator 可合并逻辑寄存器，物理寄存器增幅可控。
  - **证据强度**：强——平均 +4.11 regs，1.04× slowdown。
- **假设 1**：structured map（eBPF-like per-thread segment）可避免 atomic 风暴。
  - **证据强度**：强——对比 NvBit atomic PRM。

## 核心方法

**Probe = snippet + tracepoint + map**；Python DSL→TOML→probe engine；hook CUDA/ROCm driver。

**Cooperative probes**：寄存器/GMEM 临时存储跨 tracepoint 协作。

**DMAT**：Densified Memory Access Timeline，并行密度+物理时间。

模块：DSL compiler、hook driver、probe engine；CLI `neutrino -p <probe> <program>`。

## 设计取舍

- **取舍 1**：assembly 层，无法观测 cache 等不可编程结构（论文明确）。
- **取舍 2**：无 compiler 保护，靠虚拟化模型保证正确性。
- **边界条件**：极高并行 probe 仍可能增加压力。

## 实验与结果

- 正确性与准确度：执行流不变、profile 可信（§6）。
- 开销：多数 probe 1.04× latency；+4.11 寄存器平均。
- 可 profile 整模型含 LLM；FlashAttn v1 vs v2 DMAT 差异可量化。
- Case study：同步原语导致 CU 上 block tailing 效应。

## Critical Analysis

### 论证链条

GPU 黑盒 → assembly 统一层 → 可编程 probe → DMAT 洞察 → case study 找瓶颈。链条在 Linux+NVIDIA/AMD 闭合；Windows/其他 API 未claim。

### 假设压力测试

- 新 GPU ISA 变体可能破坏 assembly hook 稳定性。
- 与 [[KPerfIR]] IR 级工具互补：Neutrino 更泛 kernel，KPerfIR 更 compiler 协同。
- 生产默认开启 probe 的安全/性能政策未讨论。

### 实验可信度

开源+跨厂商；overhead 低。与 NCU 对比维度不同（fine vs aggregate），非直接替代关系。

### 系统性缺陷

论文未讨论：multi-GPU 时间关联、安全沙箱、probe _verifier_ 形式化。

## 局限与 Future Work

- **局限 1**：不可见 cache/硬件单元。
- **局限 2**：依赖 assembly 可获取与 driver hook。
- **Future work 1**：与 MLIR/Triton 前端符号关联（类似 KPerfIR 方向）。
- **Future work 2**：probe 验证器与生产级权限模型。

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]、eBPF
- **同类系统**：CUPTI、NCU、NvBit、[[KPerfIR]]
- **同会议**：[[OSDI-2025]]
