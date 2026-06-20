---
type: paper
name: GCR
full_title: "GPU Checkpoint/Restore Made Fast and Lightweight"
authors: [Shaoxun Zeng, Tingxu Ren, Jiwu Shu, Youyou Lu]
venue: FAST
year: 2026
tags: [gpu, checkpoint-restore, llm-inference, incremental-checkpoint, shadow-execution]
source_pdf: "[[fast2026-zeng.pdf]]"
source_md: "[[fast2026-zeng]]"
---

# GPU Checkpoint/Restore Made Fast and Lightweight (FAST 2026)

> **一句话总结**：GCR 观察到 driver-integrated C/R（cuda-ckpt）零执行开销但 data buffer 带宽仅 12% PCIe、interception-based C/R（PhOS）带宽高但全 API 拦截拖慢 8.7% 且 incremental 不可用；通过 control/data 分离 hybrid C/R + 虚拟/物理地址解耦 + CPU shadow execution 与 dirty templates，checkpoint 延迟比 cuda-ckpt/PhOS 降 72.1%/63.6%，restore 降 54.2%/87.1%，正常执行开销 <1%，incremental checkpoint 体积减 86.6%。

## 问题与动机

System-level GPU [[Checkpoint-Restore|C/R]] 是弹性 GPU serverless 扩缩、训练/推理任务切换、容错训练三类场景的共用 system primitive：把 GPU control state（CUDA context/stream 等，约 0.5 GB）与 data buffer（如 [[LLM]] 推理 30 GB 级 [[KV-Cache]]）整体保存并在恢复时透明续跑，无需每个应用各自实现 C/R。

现有方案分两类，但都无法同时满足 **低 C/R 延迟**、**正常执行低开销**、**高效 incremental checkpoint** 三目标：

- **Driver-integrated**（NVIDIA 官方 cuda-ckpt）：嵌入闭源 driver，normal execution 零开销，control state 处理高效；但 data buffer checkpoint/restore 带宽仅 3.0/7.2 GB/s（PCIe 4.0 理论 25 GB/s 的 12.0%/28.8%），闭源导致社区无法优化。
- **Interception-based**（[[PhoenixOS-SOSP25|PhOS]] 等）：LD_PRELOAD 拦截全部 GPU driver API，自管 resource handler；data buffer 异步 memcpy 可达 24.3 GB/s，但 handler 序列化占 data buffer checkpoint 时间 53.9%，control state checkpoint/restore 分别慢 3.5×/9.2×；全 API 拦截使 normal execution 平均慢 8.7%（峰值 49.6%）。
- **Incremental checkpoint 缺失**：Llama2-7B 推理后续 checkpoint 理想只需 4.1 GB dirty buffer（0.7 GB 新 [[KV-Cache]] + 3.4 GB 中间态），但 cuda-ckpt/PhOS 每次都 checkpoint ~30 GB，amplification 7.2×；PhOS 虽有 dirty 识别，常开会带来额外 12% 减速故默认关闭。

论文提出 **GCR**（GPU Checkpoint/Restore），目标是在不修改 GPU driver、不依赖专用硬件的前提下，同时解决上述三 limitation。

## 关键观察 / 隐含假设

- **观察 1：Control state 与 data buffer 的 C/R 瓶颈不同，可拆分处理。** Measurement 显示 cuda-ckpt 的 control state 快、data buffer 带宽差；PhOS 的 data buffer memcpy 快但 control state 序列化/反序列化主导延迟。GPU checkpoint 由两类组件组成，且 data buffer 占体积大头（LLM 推理 ~30 GB vs control ~0.5 GB）。
  - **依赖假设**：只需拦截 memory (de)allocation 即可完整追踪 data buffer 集合，其余 API 可交给 driver-integrated C/R。
  - **可能失效场景**：UVM、统一虚拟内存预取、或 driver 在 allocation 之外隐式修改 buffer 的应用；论文承认 UVM 集成留作 future work。

- **观察 2：Hybrid C/R 破坏 driver 黑盒保证的 buffer 虚拟地址一致性，但虚/物理可解耦。** cudaMalloc 不保证跨次分配同一虚拟地址；PhOS 依赖 cuMemAddressReserve 的 hint 语义，密集分配下可能失败。GCR 观察到地址一致性是虚拟地址问题，deallocation 同时涉及物理释放——可先 checkpoint GPU page table 保留虚拟地址，再 cuMemUnmap/cuMemRelease 释放物理，restore 时 cuMemCreate + cuMemMap 重映射。
  - **依赖假设**：NVIDIA 低层虚拟内存 API（cuMemAddressReserve/Map/Create/Unmap/Release）语义稳定，且 page table 可被 cuda-ckpt 正确 checkpoint/restore。
  - **可能失效场景**：驱动版本变更、非 NVIDIA GPU、或 API 行为与文档不一致时地址一致性可能破裂；论文仅在 A100 + CUDA 12.6 验证。

- **观察 3：Fine-grained dirty 识别若放在 GPU 执行关键路径代价极高。** GPU 无硬件 dirty bit。PhOS speculation 把非 const kernel arg 整 buffer 标 dirty，vLLM reshape/cache kernel 在 13 GB [[KV-Cache]] 参数上仅写 0.7 GB，amplification 18.6×；Neutrino 式 instrumentation 慢 5.3× 且多占 7.1 GB GPU 内存。
  - **依赖假设**：多数 workload 的 dirty 模式可由 kernel store 指令的目标地址表达为 kernel argument + launch config 的函数，无需真正执行计算。
  - **可能失效场景**：pointer chasing、hash 计算、无文档闭源 kernel、或 dirty 地址依赖运行时 GPU 内存内容时，GCR fallback 到粗粒度标记或禁用 incremental。

- **观察 4：Concurrent C/R 在 evaluated 场景难以隐藏延迟。** PhOS concurrent restore 试图与推理重叠，但 prefill 1.1 s vs restore 26.9 s，且推理需要大部分 buffer；训练迭代 0.36 s vs checkpoint 5.7 s，concurrent checkpoint 期间参数全变 dirty。
  - **依赖假设**：论文聚焦 stop-the-world 同步 C/R（cudaDeviceSynchronize 后 checkpoint）足以覆盖 serverless 冷启、任务切换、周期性容错三类主场景。
  - **证据强度**：强。Figure 8/10/13 直接测量 concurrent 无效；GCR 因此未实现 concurrent C/R。

- **假设 1**：目标 workload 以 PyTorch/[[vLLM]]/DeepSpeed/Transformers 等开源 kernel 为主，PTX 可分析。
  - **证据强度**：中。实验覆盖 LLM/DNN/HPC，但闭源 cuBLAS/NCCL 仅靠文档标 dirty；无文档 kernel 会禁用 incremental，论文未量化这类 kernel 占比。

## 核心方法

GCR 由 C/R library + storage backend（当前 CPU memory，checkpoint 增量合并进前次 full checkpoint 以加速 restore）组成，CPU 侧用 [[CRIU]] 处理进程态。

### Hybrid C/R via control/data separation

回应观察 1–2。只通过 LD_PRELOAD 拦截 cuMemAlloc/cuMemFree（及 kernel launch 用于 dirty 追踪），记录 buffer 地址+长度（每 buffer 16 B），其余 API 不碰 → normal execution 开销 <1%。

**Checkpoint 流程**：cudaDeviceSynchronize → async cudaMemcpyAsync 把 intercepted data buffer 拷到 CPU（均 20.5 GB/s）→ cuMemUnmap+cuMemRelease 释放物理内存但保留虚拟地址 → 调用 cuda-ckpt checkpoint 剩余 control state（含 GPU page table）→ 清空虚拟地址回 driver pool。

**Restore 流程**：cuda-ckpt 恢复 control state（含原虚拟地址，因从未 deallocate 虚拟段）→ cuMemCreate 分配新物理内存 → cuMemMap 映射到保留虚拟地址（llama2-7B 27.3 GB 仅 432 µs）→ memcpy 恢复 buffer 内容（均 23.0 GB/s，92% PCIe 上限）。

这比 PhOS 全量 API replay 少掉 resource handler 序列化瓶颈，又比纯 cuda-ckpt 拿到接近饱和的 PCIe 带宽。

### Incremental checkpoint via shadow execution

回应观察 3。核心是把 dirty 识别移出 GPU 关键路径：

1. **离线 dirty templates**：对每个 open-source kernel 做 PTX-level [[Symbolic-Execution]]，枚举 store 指令，把目标地址/长度变换为 kernel argument 与 gridDim/blockDim 的表达式，剔除其余计算，编译为 C++ 库函数。
2. **Online 拦截**：拦截 cudaLaunchKernel 提取参数填模板；对 cuBLAS/NCCL 等闭源但文档齐全的 API 按文档标 dirty argument；memory alloc/free 不修改内容视为 clean；无模板 kernel fallback 标所有非 const arg 为 dirty。
3. **Shadow execution**：CPU 并行执行 dirty template（微秒级，如 14 µs，<1 MB CPU 内存），与 GPU kernel 重叠，输出 dirty 地址列表；incremental checkpoint 只拷贝 dirty buffer。

vLLM 推理场景还利用 workload 先验：model parameter read-only、[[KV-Cache]] 部分写入、中间 buffer 全 dirty——初始化时两行代码标记 parameter/KV cache 地址，只对 KV 相关 kernel 启用 templates。

## 设计取舍

- **Hybrid 换实现复杂度**：要维护两套 C/R 路径（driver + selective interception）及虚/物理地址生命周期。收益是兼得零开销 control 处理与高带宽 data 拷贝；代价是 restore 必须先 driver 再 remap，fault-tolerant training 中 checkpoint 后需 restore data buffer 才能续训，stall 比 PhOS concurrent checkpoint 略高（3 min 间隔时仍占训练时间 3.0%，effective ratio 99.1%）。

- **Dirty templates 换通用性**：只对可符号化的 store 模式生成模板；pointer chasing/hash/无文档 kernel 退化。收益是 <1% 执行开销 + instruction-level 精度；代价是每新 kernel 需离线分析，框架升级可能需重新生成模板库。

- **Stop-the-world 换正确性与简单性**：放弃 concurrent C/R。收益是语义清晰、无 race 下 dirty 追踪；代价是在 C/R 比迭代快一个数量级以外的场景（论文称尚未遇到有效 concurrent 场景）无法隐藏延迟。

- **CPU memory backend 换 restore 速度**：checkpoint 存 CPU DRAM，增量与 full 预合并。收益是实验冷启场景 restore 无合并开销；代价是 checkpoint 规模受 host 内存限制，SSD/远程存储仅 future work。

- **边界条件**：单/多 GPU（每 GPU 独立并行 C/R）、NVIDIA A100 + CUDA 12.6、开源框架 workload 下表现最佳；PhOS 对照因 commit 47d64ab 无法跑 vLLM/DeepSpeed/多 GPU，GCR 在更广 workload 上的优势部分来自 baseline 可运行性差异。

## 实验与结果

- **硬件**：2× A100-40GB，NVLink，PCIe 4.0。软件：CUDA 12.6，PyTorch 2.7.1，Transformers 4.53.3/v4.30.0（PhOS 对照），[[vLLM]] 0.9.1，DeepSpeed 0.17.5。
- **Full checkpoint**：相对 cuda-ckpt 延迟 -72.1%，相对 PhOS -63.6%；control state 开销较 cuda-ckpt <0.1%；data buffer 带宽 20.5 GB/s vs 3.0/11.2 GB/s。
- **Restore / serverless cold-start**：相对 cuda-ckpt cold-start -54.2%，相对 PhOS -87.1%；data buffer restore 带宽 23.0 GB/s（3.4×/11.5×）；restore 后 application execution 与无 C/R 相比 <0.1% 开销（PhOS concurrent restore 使 execution 慢 11.1×）。
- **Task switching**（训练↔推理）：switch 总延迟相对 cuda-ckpt -71.6%、PhOS -74.1%；checkpoint -77.9%，restore -58.9%（vs PhOS -51.8%/-82.5%）。
- **Fault-tolerant training**（opt-1.3B）：stall 时间相对 cuda-ckpt -78.4%；5 min 间隔 effective training ratio 99.1%；PhOS concurrent checkpoint 因迭代快于 C/R 无效。
- **Incremental checkpoint**（vLLM/Transformers 推理）：第二次 checkpoint 体积归一化 -86.6%，延迟 -43.8%；cuda-ckpt/PhOS 体积与延迟几乎不变。
- **Normal execution overhead**：吞吐 >99.9%（<1%）；PhOS 平均 92.1%（-8.7%），峰值 50.4%。
- **Application-level C/R**：相对 DeepSpeed save_checkpoint / Transformers save_pretrained / [[ServerlessLLM]] restore 分别 -87.8%/-77.6%/-83.3%。

## Critical Analysis

### 论证链条

主链条闭合且证据充分：两类现有 C/R 的瓶颈可分解（§3 measurement）→ control/data 分离 + 最小拦截可同时获得 bandwidth 与低 overhead（§4.1）→ 虚/物理解耦解决 hybrid 下的地址一致性（§4.1 challenge）→ shadow execution + dirty templates 把 fine-grained dirty 识别移出 GPU 关键路径（§4.2）→ 三场景实验数字支撑 claim（§6）。

较弱环节是 **incremental 收益对 workload 先验的依赖**：vLLM 实验显式 wrap parameter/KV cache allocation，并 selective 应用 templates；这不是完全应用透明的 incremental，而是「系统 C/R + 少量应用提示」混合方案。论文将其归为 exploiting workload characteristics，但外推到任意 GPU 应用时需重新标注或接受 fallback 粗粒度。

### 假设压力测试

**NVIDIA 绑定**：全部设计依赖 cuda-ckpt、CUDA 虚拟内存 API、PTX 工具链。AMD HIP 有类似 API（论文 Discussion 提及），但未实现验证 — **推断**可移植，非 **已证明**。

**Driver 黑盒依赖**：control state 正确性仍托付 cuda-ckpt 闭源实现；GCR 无法独立验证 page table checkpoint 完备性。驱动升级可能破坏 hybrid 流程 — **论文未讨论** regression 测试策略。

**Dirty template 覆盖度**：闭源/复杂 kernel fallback 到整 buffer dirty 时，incremental 收益消失。训练场景参数每个 iteration 都变，incremental 价值有限（论文主要展示推理/task switching）— **已证明**推理场景收益，训练 incremental **未充分评估**。

**Checkpoint 存储**：CPU memory only，30 GB 级 checkpoint 多实例/多租户时的 DRAM 压力、故障后持久化、跨节点迁移 — **论文未讨论**。

**Multi-GPU**：标注 ⋆ 的 workload 测了并行 per-GPU C/R，但未深入 NCCL 集合通信状态、GPU 间 NVLink buffer 一致性 — **部分覆盖**。

### 实验可信度

Baseline 选择代表性强：cuda-ckpt（官方）、PhOS（SOTA interception）。PhOS 版本老旧且不支持 vLLM/DeepSpeed/多 GPU，使部分对比呈现「GCR 能跑、PhOS 不能跑」 asymmetry；作者对 PhOS 共用 workload 降级 Transformers 4.30.0 以保证公平，设计合理。

Workload 覆盖 LLM 推理/训练、DNN、HPC（comd）、单/多 GPU、application-level C/R，对 FAST 系统论文属充分。弱点：(1) 缺少 tail latency / P99 cold-start；(2) incremental 主要测 inference multi-checkpoint，训练 periodic incremental 未展示；(3) 未与 GPREEMPT、GPU snapshot 等专用硬件/驱动修改方案比；(4) shadow execution 正确性依赖符号执行完备性，无形式化证明或 fuzz 验证。

### 系统性缺陷

- **同步 checkpoint 停顿**：serverless 冷启优化的是 restore，但 task switching switch-out 仍需全量/增量 checkpoint；高频切换时 pause 时间论文有 switch latency 但未给 P99。
- **故障恢复路径**：checkpoint 存 CPU memory，host crash 丢 checkpoint；无 replication/持久化 — **论文未讨论**。
- **资源隔离**：多租户共享节点上 LD_PRELOAD 拦截与全局 checkpoint 的隔离语义 — **论文未讨论**。
- **可观测性**：dirty template 缺失、fallback 粗粒度、地址 remap 失败等运维信号 — **论文未讨论** operator API。
- **与 concurrent C/R 的关系**：设计上 dirty templates 可支撑 concurrent checkpoint，但未实现；未来若迭代变慢或 checkpoint 变快，架构选择可能变化。

## 局限与 Future Work

- **局限 1**：checkpoint 仅存 CPU memory，未实现 SSD/远程存储 backend 及对应带宽优化。
- **局限 2**：未实现 concurrent C/R；在 C/R 相对执行变慢的场景可能落后 PhOS 类方案。
- **局限 3**：dirty templates 对无文档/不可符号化 kernel 退化，incremental 非对所有应用透明生效。
- **局限 4**：仅 NVIDIA A100 + CUDA 12.6 验证，driver 闭源部分正确性不可独立审计。
- **Future work 1**：测量 production serverless trace 上 incremental hit rate、checkpoint DRAM footprint、跨节点 restore 带宽，验证 CPU memory backend 是否可扩展。
- **Future work 2**：将 dirty templates 扩展到 load 指令分析，实现 concurrent restore，并在训练 iteration 变长、checkpoint 变快的 regime 重新 benchmark 对 PhOS 的优劣。
- **Future work 3**：集成 UVM、kernel 中途抢占（[[GPREEMPT]]）与多存储 tier，评估 hybrid C/R 在统一地址空间下的地址一致性维护成本。

## 相关

- **相关概念**：[[Checkpoint-Restore]]、[[KV-Cache]]、[[Symbolic-Execution]]、[[Copy-on-Write]]、[[CUDA]]、[[CRIU]]
- **同类系统**：[[PhoenixOS-SOSP25]]、cuda-ckpt、ServerlessLLM、Neutrino、CRIU-GPU
- **同会议**：[[FAST-2026]]
- **对比**：GCR 可视为对 PhOS「全 interception + concurrent C/R」的反面——最小拦截 + hybrid driver + 离线 shadow dirty 追踪；与 application-level C/R（DeepSpeed/ServerlessLLM）比强调应用透明与更低延迟