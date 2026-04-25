---
type: paper
name: PhoenixOS
full_title: "PhoenixOS: Concurrent OS-level GPU Checkpoint and Restore with Validated Speculation"
authors: [Xingda Wei, Zhuobin Huang, Tianle Sun, Yingyi Hao, Rong Chen, et al.]
venue: SOSP
year: 2025
tags: [gpu, checkpoint-restore, fault-tolerance, operating-systems, llm-serving]
source_pdf: "[[3731569.3764813.pdf]]"
source_md: "[[3731569.3764813]]"
---

# PhoenixOS: Concurrent OS-level GPU Checkpoint and Restore with Validated Speculation (SOSP 2025)

> **一句话总结**：PhoenixOS (PHOS) 首个让 GPU 进程并发 [[Checkpoint-Restore|C/R]] 的 OS 服务，通过"推测 + 验证"在无 GPU dirty bit 硬件支持下追踪读写集，Llama2-13B 迁移停机从 9.8s 压到 2.3s，冷启 622 ms 比 NVIDIA cuda-checkpoint 快 124-450%。

## 问题

OS 级 checkpoint/restore 对容错、迁移、serverless 冷启动至关重要，而 CPU 并发 C/R（copy-on-write / recopy / on-demand restore）已研究几十年。但 GPU 缺两项关键支持：(1) 硬件 dirty bit / present bit；(2) OS-mediated data path（GPU 执行绕开 OS 以追求性能）。现有 NVIDIA cuda-checkpoint、Singularity 都得 stop-the-world 拷完全部 GPU 状态：Llama2-13B 推理 restore 停顿 6.2 秒（比 TTFT 长 31×），训练 checkpoint 时间占迭代 46-87%，微软数据显示超 3.9% GPU 用户因迁移 stall 受影响。

## 核心方法

关键观察：GPU 执行虽不可见，但由一连串细粒度 API 调用（[[CUDA]]、[[cuBLAS]]、[[NCCL]]、自定义 kernel launch）驱动，其 launch 参数编码了访问的 buffer 指针——可以**推测**（speculate）每次 kernel 会读写哪些 GPU buffer。

**Validated speculation**：对 memcpy、cuBLAS、NCCL 等 spec 明确的 API 直接用规范；对 opaque `cudaLaunchKernel`，拦截 cudaMalloc 已知全部 buffer 范围，对每个参数若落入某 buffer 范围即标记该 buffer。为处理推测失败（如极罕见的 GPU 间接访问），在 PTX ISA 级 instrument 一个 validator twin kernel，对每条写指令加地址范围检查；失败则回退到更保守协议。

基于验证过的读写集，PHOS 把三类 CPU 并发 C/R 协议"软件化"到 GPU：**soft copy-on-write**（隔离 t1 后新写，适合容错）、**soft recopy**（停机追加补写差异，适合 live migration 要从最新态恢复）、**soft on-demand restore**（用 GPU 端 present bit 模拟实现随用随拷）。

GPU-specific 优化：coordinated checkpoint data transfer 避免 CPU/GPU 检查点及应用传输互相干扰；**execution context pool** 预分配 GPU context，restore 时绕开 context 创建的 3.1s 开销。基于 CRIU + LD_PRELOAD 拦截 CUDA 实现，支持多 GPU，backend 支持 SSD/DRAM/RDMA 多种介质。

## 关键结果

- 对 Llama2-13B 推理 restore：PHOS 622 ms vs cuda-checkpoint 及 Singularity 的 124-450% / 114-342% 慢速
- Llama2-13B 多 GPU 训练容错：相比 Singularity 浪费 GPU 时间减 76%
- Llama2-13B 推理迁移停机：9.8s → 2.3s
- checkpoint/restore 应用停顿最多减少 160%
- 开源：https://github.com/SJTU-IPADS/PhoenixOS

## 相关

- **相关概念**：[[Checkpoint-Restore]]、[[Copy-on-Write]]、[[CRIU]]、[[CUDA]]、[[GPU-Virtualization]]
- **同类系统**：NVIDIA cuda-checkpoint、Singularity（MSR）、Megatron、CRIU
- **同会议**：[[SOSP-2025]]
