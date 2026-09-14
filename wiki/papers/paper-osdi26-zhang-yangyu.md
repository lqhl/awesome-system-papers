---
type: paper
name: MoonBright
full_title: "MoonBright: A GPU Memory Allocator with Device-Side Page Table Materialization and Deferred TLB Coherence"
authors: [Yangyu Zhang, Lei Chen, Chunwei Xia, Shuaijiang Li, Shuoming Zhang, et al.]
venue: OSDI
year: 2026
tags: [gpu-memory, virtual-memory, memory-allocation, tlb-coherence, llm-inference]
source_pdf: "[[osdi26-zhang-yangyu.pdf]]"
source_md: "[[osdi26-zhang-yangyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-14
---

# 面向 GPU 的页表并行构造与延迟 TLB 一致性（OSDI 2026）

> **原题**：MoonBright: A GPU Memory Allocator with Device-Side Page Table Materialization and Deferred TLB Coherence

> **一句话总结**：MoonBright 观察到 CUDA VMM 的页表构造占分配延迟的 80%–99%，于是把 PTE 构造移到 GPU 并用 Always-Fresh VA 避免常规 TLB flush；在 2 GB 映射上把延迟从 36 ms 降到 14 µs，并在 prefix caching 推理中将 TTFT 最多降低 8.2×。

## 问题与动机

GPU 计算越来越细粒度，微秒级 kernel 可能被 CPU 驱动的内存管理操作阻塞。传统 `cudaMalloc`、CUDA VMM 和框架缓存分配器在灵活性、延迟和碎片之间取舍：缓存池减少驱动调用，却无法灵活重映射物理页；VMM 支持页粒度映射，却把页表更新和一致性维护放在串行的 host control path 上。

论文将瓶颈定位为两个部分。第一，CPU 串行生成并传输大量 PTE。第二，映射复用或重映射后，驱动往往用全局同步加 TLB shootdown 保证一致性。这使得异步、stream-ordered 的执行退化为阻塞式执行。MoonBright 试图在不修改 GPU 硬件的前提下，同时获得低分配延迟、灵活映射和外部碎片缓解。

## 关键观察 / 隐含假设

- **观察 1：页表构造是主要延迟来源。** 在 A100 上，128 MB `cudaMalloc` 约需 1 ms，页表构造与传输占总延迟的 80%–99%（表 2）。
  - **依赖假设：** 大量叶 PTE 的编码和写入彼此独立，适合 GPU 数据并行。
  - **可能失效场景：** 极小映射、频繁单页操作或驱动/硬件已具备高效批量映射时，固定 kernel 启动成本可能抵消收益。
- **观察 2：新 VA 不会与旧 VA 的 TLB 项发生同地址冲突。** 只要分配严格使用从未使用的虚拟地址，建立新映射无需立即 flush；代价只是首次访问的一次 page walk（图 10、图 12）。
  - **依赖假设：** VA 空间足够大，且地址回收可以延迟到 epoch 边界。
  - **可能失效场景：** 长时间运行、VA 空间受限、需要频繁复用固定指针，或应用要求原地改变权限时，仍必须执行 flush。
- **假设 1：物理页不需要连续。** 该假设支撑用分散物理页拼接连续 VA，并绕开 NVIDIA GSP 在约 512 MB 以上的分配延迟陡增。证据强度为中：论文在 NVIDIA 与 AMD 原型上验证，但未覆盖更多硬件代际。

## 核心方法

MoonBright 在 CUDA context 初始化时获取硬件多级页表页，并把它们映射到一个连续的 GPU 虚拟区域，形成线性化的 gPGT 视图（图 2）。CPU 可用 `Base + VPN × sizeof(PTE)` 确定条目位置，GPU kernel 则能直接读写这些页表页。host 仍负责 VA 合法性检查、元数据和物理页分配，页表物化转为设备端数据并行任务。

映射流程先创建缺失的页表目录，再把物理页帧号写入 GPU PFN buffer。`pte_pop` kernel 并行组合物理地址与访问权限位，生成硬件格式的 PTE 并写入 gPGT（图 3）。这一设计直接回应“页表构造占主导延迟”的观察，同时保留 host 对资源合法性的控制。

延迟 TLB 一致性协议采用 Always-Fresh VA：新分配从 VA frontier 获取未使用地址，不在常规路径回收旧 VA。只有 VA recycling、重映射或权限改变等可能产生同地址陈旧翻译的操作才调用 `tlb_flush`。被释放的 VA 进入 quarantine，在 epoch 边界批量回收。NVIDIA 后端还按 32 MB 对齐新 VA，以避开约 32 MB 的 translation prefetch window（图 10）。

用户接口包括 `Malloc`、`MallocAsync` 和 VMM 风格原语。小对象由 slab 管理；高频请求走带 coalescing 的 BFC 风格缓存路径，缓存耗尽时再申请物理页并异步执行页表更新。出现物理碎片但缺少连续空闲块时，系统申请连续 VA，把不连续物理页映射进去，实现不搬移数据的逻辑碎片整理。

## 设计取舍

- **设备端页表写入换取 host 控制路径缩短。** host 仍维护元数据和分配验证，避免把所有资源管理责任交给 kernel；但页表布局、权限编码和 vendor-specific 行为进入了软件运行时的维护范围。
- **Always-Fresh VA 换取 VA 空间和回收复杂度。** 常规分配避免全局同步，但需要 quarantine、epoch 管理和足够大的 VA 预算。NVIDIA 的 32 MB 对齐会使保守 VA 预算从约 693 GB 增至约 11 TB。
- **虚拟碎片整理避免数据搬移，但不消除所有开销。** 它减少外部碎片，却不能解决物理页申请、页表目录创建或首次访问 page walk 的成本。

## 实验与结果

- 在 2 MB 单页映射上，MoonBright 将 CUDA VMM 的约 45 µs 降至 2.6 µs；在 2 GB 新映射上从 36 ms 降至 14 µs，超过 2,500×（图 4）。
- 1–4 张 A100 同时映射 2 GB 时，CUDA VMM 延迟从 36 ms 增至约 180 ms；MoonBright 近似保持不变，四卡场景约快 12,700×（图 5）。
- 端到端分配测试中，NVIDIA 平台最高降低 99.3%、平均降低 76.5%；AMD 平台最高降低 98.3%、平均降低 60.3%（图 6）。
- 训练碎片测试中，DenseNet 的 memory efficiency 从 PyTorch 的 57.6% 提高到 97.7%；Qwen1.5-MoE 在 Z+O+R 配置下从 72.8% 提高到 97.8%（图 7）。
- prefix-cached Llama-2-7B 和 Llama-3-8B 推理的 TTFT 分别最多降低 8.2× 和 2.9×；长上下文完整 prefill 场景因计算占比达到 192K token 时约 85%，收益最多约 5%（图 8）。
- Llama-3-8B beam search 在 batch size 128、beam width 2/4 时吞吐分别达到 vLLM 的 2.5×/3.6×（图 9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| GPU 端 PTE 构造能消除主要映射瓶颈 | 表 2、图 4 | A100，2 MB–2 GB，CUDA VMM 对比 | 强 |
| Always-Fresh VA 可把 flush 从常规路径移到例外路径 | 图 10、图 12–13 | NVIDIA A100，合成压力工作负载 | 中 |
| 虚拟重映射能缓解训练外部碎片 | 图 7 | 四张 A100，四个训练模型与特定优化组合 | 中 |
| 映射优化能改善动态 LLM 服务 | 图 8–9 | Llama-2-7B/Llama-3-8B，prefix caching 与 beam search | 中 |

## 批判性分析

### 论证链条

论文的主要链条较闭合：表 2 先显示页表构造占比，再用设备端并行 PTE 写入降低映射延迟，最后在训练和推理中观察到收益。收益高度依赖映射强度：完整长上下文中计算占主导，端到端提升很小；prefix caching 和 beam search 才暴露出控制路径瓶颈。

### 假设压力测试

Always-Fresh VA 将一致性问题转化为地址空间管理问题。论文展示了 256 GB wraparound 压力测试，并估计 1 TB epoch 仅需约 8 MB 页表空间，但真实服务的 VA 生命周期、进程重启、跨进程共享和固定地址 API 约束未充分覆盖。32 MB prefetch 对齐是 NVIDIA 特定策略，AMD 后端不能直接沿用。

### 实验可信度

基线包含 CUDA VMM、PyTorch caching allocator、GMLake、vAttention 和 vLLM，且覆盖 NVIDIA、AMD、多 GPU、训练和推理。仍需注意，训练配置和模型集合有限，部分对比依赖拦截 vendor allocation API；论文没有展示生产级多租户隔离、故障恢复、并发 context 或更大 GPU 集群上的运维成本。

### 系统性缺陷

设备端直接修改硬件页表依赖 vendor 页表布局、页表页可映射性和权限语义。论文以 CUDA 与 ROCm 6.4.0 原型证明可行，但兼容性随驱动版本变化的风险较高。页表更新本身作为 kernel 还会占用 GPU 调度和带宽；当计算已接近带宽上限时，异步重叠未必免费。论文未系统讨论恶意 kernel、页表损坏、错误恢复和跨租户安全隔离。

## 局限与后续工作

- **局限 1：硬件与驱动依赖。** 需要为不同 GPU 代际重新确认页表暴露方式、TLB prefetch 行为和物理页分配策略。
- **局限 2：VA 回收压力。** 应测量真实长时 trace 下 quarantine 的峰值、epoch flush 对 P99 延迟的影响，以及多进程 VA 空间竞争。
- **后续工作 1：** 将页表 kernel 的 GPU 带宽、调度占用和计算重叠收益加入端到端成本模型，并在更大规模多租户推理集群中验证 P99、隔离和恢复行为。

## 相关

- **相关概念：** [[GPU Memory]]、[[Virtual Memory]]、[[TLB]]、[[Memory Fragmentation]]
- **同类系统：** [[vAttention]]、[[GMLake]]、[[vLLM]]
- **同会议：** [[OSDI-2026]]
