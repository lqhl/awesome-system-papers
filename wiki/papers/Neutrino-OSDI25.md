---
type: paper
name: Neutrino
full_title: "Neutrino: Fine-grained GPU Kernel Profiling via Programmable Probing"
authors: [Songlin Huang, Chenshu Wu]
venue: OSDI
year: 2025
tags: [gpu-profiling, ebpf, assembly-instrumentation, ai-systems, observability]
source_pdf: "[[osdi25-huang-songlin.pdf]]"
source_md: "[[osdi25-huang-songlin]]"
---

# Neutrino: Fine-grained GPU Kernel Profiling via Programmable Probing (OSDI 2025)

> **一句话总结**：GPU 版 eBPF——在 PTX/GCNAsm 层插入可编程 probe（snippet + tracepoint + 结构化 map），实现指令级、跨厂商（NVIDIA+AMD）、低开销（1.04×、+4.11 regs）的细粒度 kernel 剖析，并提出新可视化 DMAT。

## 问题

GPU 在 scaling-law 时代越发主导，但 kernel 剖析能力远落后于 CPU：(1) 硬件闭源、架构异构，外部工具很难探到细节；(2) GPU kernel 对 host OS 是原子的，eBPF/ptrace 等成熟 OS 工具链无法进入；(3) GPU 没有 timer interrupt 和锁的高效实现，采样式 profiler 失效。结果现有工具要么 kernel-exclusive 只给 FLOP/s 这种粗指标（如 torch.profiler），要么 hardware-dependent 依赖专有计数器（NCU、RGP），要么 instrumentation 但锁定在单个平台/编译器（NvBit 锁 NVIDIA 机器码、HIPAnalyzer 锁 LLVM）。缺的是 eBPF-like 统一的、跨平台的、可编程细粒度接口。

## 核心方法

Neutrino 借鉴 eBPF 三件套但移植到 GPU：**snippet**（汇编片段 + SAVE/OUT/IN 等 helper）、**tracepoint**（插入位置，细到单条 PTX 指令如 ld/st/cp.async/mma，粗到 kernel 入口/出口）、**structured map**（eBPF-style ndarray，形状由 launch config 决定，thread-level 用于 value profiling、warp-level 用于 time profiling，天然无锁）。把探针插在 PTX/GCNAsm 而非机器码或编译器 IR 的理由：汇编层是 AOT（CUDA C++）和 JIT（Triton/MLIR）两条编译链的公共汇聚点，能同时覆盖两类 workload，并保留 %clock、%globaltimer、hwreg 等硬件寄存器访问。

执行模型依赖 GPU SIMT 的时间-资源双分离：probe 指令沿 PC 顺序插入，不改变原程序指令顺序；probe 寄存器在汇编层独立声明，由 assembler 的 register allocation + dependency tracking 合并，通常不增加物理寄存器用量。Verifier 禁止三类危险操作：覆盖原寄存器、使用 flow control 指令、写 shared memory。

实现三件套：**Hook driver** 用 LD_PRELOAD 劫持 libcuda.so/libamdhip.so 的 cuModuleLoad/cuLaunchKernel 拿到 binary 和 launch config；**Probe engine** objdump binary、匹配 tracepoint、插 snippet、ptxas 重新汇编；**Python Tracing DSL 编译器** 把 @probe/@Map 装饰的 Python 函数 JIT 成 eBPF-like IR 再译成 PTX/GCNAsm。CLI 体验类似 bpftrace：`neutrino -p block_sched python -c "..."`。

同时提出 **DMAT（Densified Memory Access Timeline）** 可视化：把 page reference map 加上时间轴和并行 density 颜色深度，对比 FlashAttn-v1/v2 时能直观看出 memory efficiency 与 pipelining 区别。

## 关键结果

- kernel slowdown 只有 1.04×（多数 probe），平均额外物理寄存器仅 +4.11
- 支持 NVIDIA（CUDA）和 AMD（ROCm/HIP）双平台，assembly-level 设计天然面向未来架构
- 案例研究发现 torch.zeros(4096,4096) 里 vectorized_elementwise kernel 20% 时间花在 block scheduling，改成 persistent kernel 后实测 28% 加速
- 与 KPerfIR 对比：同会议，另一条路线——Neutrino 走 assembly 运行时 probing、与编译器解耦，KPerfIR 走编译器 pass 内嵌，各有侧重

## 相关

- **相关概念**：[[Flash-Attention]]、[[Attention]]
- **同类系统/工具**：[[KPerfIR-OSDI25]]（同会议，编译器 pass 路线），NvBit、HIPAnalyzer
- **同会议**：[[OSDI-2025]]
