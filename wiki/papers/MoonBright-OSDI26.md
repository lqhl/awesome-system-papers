---
type: paper
name: MoonBright
full_title: "MoonBright: A GPU Memory Allocator with Device-Side Page Table Materialization and Deferred TLB Coherence"
authors: [Yangyu Zhang, Lei Chen, Chunwei Xia, Shuaijiang Li, Shuoming Zhang, Zhicheng Li, Qianqi Sun, Jiawei Xiao, Ruiyuan Xu, Ao Chen, Guangli Li, Xiaobing Feng, Huimin Cui, Chenxi Wang, Jiacheng Zhao]
venue: OSDI
year: 2026
tags: [gpu, memory-management, virtual-memory, page-table, tlb]
source_pdf: "[[osdi26-zhang-yangyu.pdf]]"
source_md: "[[osdi26-zhang-yangyu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 在设备侧构造页表并延迟 TLB 一致性的 GPU 内存分配器（OSDI 2026）

> **原题**：MoonBright: A GPU Memory Allocator with Device-Side Page Table Materialization and Deferred TLB Coherence

> **一句话总结**：论文测得 A100 上 page-table construction 占 `cudaMalloc` 延迟的 80%–99%，而新映射只要使用从未映射过的 VA 就不存在同地址 stale TLB；MOONBRIGHT 因而让 GPU kernel 并行写 device page table，并用 Always-Fresh VA 把 shootdown 延后到地址回收，在 2 GB fresh-mapping 微基准中把 36 ms 降至 14 µs，同时在 [[Prefix-Caching|prefix-cache]] [[LLM|LLM]] 实验中将 TTFT 最多降低 8.2 倍。

## 问题与动机

GPU kernel 已经能在几微秒内完成，但 memory allocation 仍沿 CPU runtime、driver、[[PCIe|PCIe]] 和 GPU MMU 的串行控制路径。以 A100 为例，128 MB `cudaMalloc` 约需 966 µs，其中 page-table build/transfer 就占 949 µs，真正的 physical allocation 只有 10 µs；即使硬件 TLB flush 只有数微秒，vendor path 为安全起见还会等待所有 stream 和 kernel 完成，形成 device-wide synchronization（表 2、§2.2）。

现有系统在两个坏选择间折中。`cudaMallocAsync`、[[PyTorch|PyTorch]] caching allocator 和 TensorFlow BFC 先申请大 pool，再在用户态复用 block，快但不能把分散 physical page 重新拼成连续 VA，长期动态 tensor 会产生 external fragmentation。低层 CUDA/HIP VMM 可以重映射，却要逐页经过 CPU driver，2 GB mapping 达到 36 ms，远慢于 kernel；vAttention、GMLake 等系统只能通过 scheduling 隐藏这段延迟，没有消除根因。

MOONBRIGHT 把“编码和填充大量 PTE”重新看作数据并行工作：host 继续掌握 VA 合法性和 physical frame ownership，GPU 只执行 runtime 生成的受信 page-table update kernel。另一个关键是区分 fresh mapping 与 same-VA update：只有后者可能命中旧 translation，前者可以用一次本地 page walk 代替全局 shootdown。

## 关键观察 / 隐含假设

- **观察 1：页表构造而非 physical allocation 主导大块 GPU allocation。** A100 上 2/16/128 MB `cudaMalloc` 的 page-table build 分别为 47/422/949 µs，占总延迟 80%–99%；MOONBRIGHT 对应总延迟为 24/27/32 µs（表 2）。
  - **依赖假设**：目标 mapping 有大量独立 leaf PTE，可以由 GPU 高带宽并行写；host validation、PFN allocation 和缺失的上层 page-table level 不是主瓶颈。
  - **可能失效场景**：2 MB 单页 mapping 只用一个 thread，收益主要受固定 launch latency 限制；频繁创建 page-table hierarchy 或 GSP physical allocation 时，CPU/firmware slow path 仍主导。
- **观察 2：fresh VA 没有同地址的有效 stale translation，因此 common allocation path 不必 flush TLB。** 第一次访问会 miss 并读取新 PTE；A100 上强制 page walk 比预热 hit 多 956 cycles，而 vendor flush path 为 26.8 µs（图 12）。
  - **依赖假设**：allocator 在 coherence epoch 内绝不重用 VA，stream ordering 保证消费者在 `pte_pop` 后运行，硬件不会把 invalid-prefetch 误当旧 PFN。
  - **可能失效场景**：VA recycle、permission change、unmap/remap 同一地址仍必须 quiesce 并 shootdown；NVIDIA negative caching 还要求新地址间隔至少 32 MB。
- **观察 3：现代 GPU 的 VA 空间远大于 physical memory，可以用空间换同步。** Robson bound 给 80 GB GPU、2 MB page 约 693 GB VA；NVIDIA 为避开 32 MB prefetch window 将预算放大到约 11 TB，仍小于 prototype 暴露的 128 TB user VA（§3.2.2、§4.1）。
  - **依赖假设**：实际 churn 不会频繁绕完 epoch，page-table memory 与大范围 VA reservation 可接受。
  - **证据强度**：中。256 GB 人工 stress test 展示了 quarantine 和 batch reclaim，但没有跑到 11 TB 的保守 production budget。
- **观察 4：GPU vendor 的隐藏实现细节会改变最佳 policy，但不改变基本机制。** NVIDIA 有约 512 MB 的 GSP allocation cliff 和 32 MB TLB prefetch window，AMD MI210 上未观察到两者（图 10–11、§4）。
  - **依赖假设**：这些行为可通过 microbenchmark 稳定测出，并在 driver/GPU 更新后重新校准。
  - **证据强度**：中。跨 A100/H100/MI210 有结果，但 proprietary GSP 和 TLB 行为无法从公开 spec 验证。

## 核心方法

MOONBRIGHT 分为 driver primitive 和 runtime API 两层。CUDA/HIP context 创建时，driver 先把 hardware multi-level page-table page 映射到一段连续、专用的 device VA，形成线性 **gPGT view**；CPU 和 GPU 之后都能用 `Base + VPN × sizeof(PTE)` 定位 entry。CPU 仍用 red-black tree 管理 logical VA、验证请求并向 NVIDIA GSP 或 AMD buddy allocator 申请 PFN（图 1–2）。

五个 primitive 分工明确：`alloc_va` 预留 VA，`alloc_pfn` 获得 resident physical frame，`pgt_create` 补齐缺失的 page-table level，`pte_pop` 让成千上万 GPU thread 从 PFN buffer 生成 hardware PTE 并直接写 gPGT，`tlb_flush` 只处理会留下 same-address stale translation 的操作。Bulk mapping 因而从 host control path 变成 HBM 内的数据移动 kernel（图 3、§3.1）。

**Deferred TLB Coherence**用 Always-Fresh VA 实现。`MallocAsync` 的 slow path 从一个巨大 circular VA buffer 的 frontier 取新地址，物理页释放后先把旧 VA 放进 quarantine，而不是马上复用；只有 epoch 接近耗尽时，runtime 等待旧 work 完成、批量 flush 一次，再回收整批地址。Fresh mapping 的 `pte_pop` 是普通 stream-ordered kernel，可以和其他 stream 的独立 compute 重叠（§3.2.2、§3.2.4）。

Runtime 在这些 primitive 上重建 `Malloc`、`MallocAsync` 和 VMM-like API。小 object 仍走 slab/BFC cache；cache 缺少连续 block 但有足够分散 physical page 时，它分配一段 fresh contiguous VA，把不连续 PFN stitch 到一起，无需搬 tensor 数据。`MemMapAsync` 还可让多个 VA alias 同一 physical page，用于 prefix sharing 和 beam-search fork。相反，synchronous free 会等 kernel 完成、清 PTE、flush TLB 后才归还 PFN；覆盖已有 mapping 也不能走 zero-flush fast path。

实现约 14.1 KLoC，修改 NVIDIA open-gpu-kernel-modules 560.35.03、AMD ROCm 6.4.0 及用户态 runtime。NVIDIA backend 把超过约 512 MB 的 PFN request 切小，并按 32 MB 对齐 VA；AMD backend 不需要这两项 heuristic（§4）。

## 设计取舍

- **以 GPU page-table write 权限换低延迟**：数据面并行消除 host 串行构造，但 page table 成为 device code 可达的 privileged state；当前只允许 trusted runtime 生成 update kernel。
- **以 VA 消耗换 common-path coherence**：Always-Fresh 避免每次 allocation shootdown，却要维护大 VA ring、quarantine 和 epoch wrap；NVIDIA 的 32 MB padding 又把保守需求放大 16 倍。
- **以 virtual stitching 换较复杂 driver**：不搬数据即可消除 external fragmentation、支持 alias，但依赖 vendor page-table layout、PFN interface 和 kernel module 修改。
- **保留 slow path 保证正确性**：free、same-VA remap 和 permission update 仍同步并 flush；MOONBRIGHT 优化的是新 allocation/mapping 主路径，不是所有 VM operation。
- **边界条件**：single-tenant、trusted kernel、动态 fresh mapping 多且 VA 充裕时最合适；恶意 multi-tenant、频繁 address reuse 或 driver 无法开放 page-table layout 时不适用。

## 实验与结果

- **硬件、基线与口径**：在 NVIDIA A100、H100 和 AMD MI210 上评测。低层 primitive 对比 CUDA/HIP VMM、`cudaMalloc`、`hipMalloc`；训练对比 PyTorch caching allocator 和 GMLake；[[LLM-Inference|LLM inference]] 对比 vAttention 与 [[vLLM]]。Mapping 微基准统一使用 2 MB page、fresh VA，范围 2 MB–2 GB；应用指标分别是 memory-management latency、训练 allocator memory efficiency、TTFT 和 beam-search token/s（§5.1）。
- **fresh-mapping 微基准**：A100 上 2 MB mapping 从 CUDA VMM 的约 45 µs 降至 2.6 µs；2 GB 从 36 ms 降至 14 µs，即超过 2,500 倍。四块 A100 同时 map 2 GB 时，CUDA VMM 从单卡 36 ms 增至 180 ms，MOONBRIGHT 近似不变，因此达到 12,700 倍。该倍率只比较已获得 PFN、面向 fresh VA 的 mapping primitive，不是完整 application speedup（图 4–5、§5.2）。
- **通用 allocation suite**：在 CUDA Samples、ROCm Samples 和 HeCBench 共 1,013 个 case 中，相对 vendor allocator，NVIDIA 平均 allocation-time 降幅为 76.5%、最高 99.3%；AMD 平均 60.3%、最高 98.3%。Allocation 越大、越频繁，收益越高（图 6）。
- **训练 fragmentation**：四块 A100 上训练 DenseNet、GPT-2、Llama-2-7B、Qwen1.5-[[MoE|MoE]]，并组合 recomputation、virtual pipeline、[[ZeRO|ZeRO]]、offload。MOONBRIGHT 将 DenseNet 的 `peak allocated / peak reserved` 从 PyTorch 的 57.6% 提到 97.7%；动态最强的 Qwen Z+O+R 从 72.8% 提到 97.8%，其余模型至少 96.1%。这是 allocator-level memory-efficiency 指标，不等同于模型吞吐或最大可训练规模（图 7、§5.3.1）。
- **LLM inference**：单块 A100 上，无 prefix cache 的 4K–192K long-context 已有约 85% 时间用于 compute，MOONBRIGHT 相对 vAttention 最多只快约 5%。Prefix cache 把瓶颈转向 remapping 后，Llama-2-7B 和 Llama-3-8B 的 TTFT 最多分别降低 8.2 倍、2.9 倍。Llama-3-8B beam search 在 batch 128 时，相对 vLLM 的 token/s 在 beam width 2/4 下提高 2.5/3.6 倍（图 8–9）。
- **Always-Fresh 稳定性**：A100 first-touch miss 比 TLB hit 多 956 cycles；NVIDIA fresh VA 距已 probe invalid VA 达 32 MB 后，访问从超过 40K cycles 降到约 1.2K cycles。Cache-defeating workload 在 256 GB wrap threshold 下让 quarantine 累积后批量 reclaim；256 GB/1 TB VA flattening 的 page-table memory 分别少于 2/约 8 MB。论文展示了机制可控，但没有报告长时间 production churn 的 wrap frequency（图 10、图 12–13）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| device-side PTE materialization 消除了 bulk fresh mapping 的 CPU 串行瓶颈 | 表 2、图 4–5 | 2 MB page、2 MB–2 GB fresh mapping；A100/H100/MI210，最多 4 GPU | 强 |
| Always-Fresh VA 可把 common-path shootdown 换成低成本 first touch | 图 10、图 12–13、§5.5 | A100 timing microbenchmark；NVIDIA 需 32 MB padding；256 GB 人工 epoch | 中到强 |
| 低层改进能减少训练 allocator external fragmentation | 图 7、§5.3.1 | 4 个 model、4 块 A100；metric 为 allocated/reserved，不是 end-to-end speedup | 强 |
| 动态 remapping 密集时可显著改善 LLM inference | 图 8–9、§5.3.2–5.3.3 | 单 A100、Llama-2-7B/Llama-3-8B、prefix cache 或 beam search | 强 |
| 方案适用于安全的 multi-tenant GPU | §6 | 当前假定 trusted/cooperative workload；MIG 只可缩小实例边界，完整 security architecture 未实现 | 弱 |

## 批判性分析

### 论证链条

论文先把 `cudaMalloc` 分解到 PTE build/transfer，再把这个并行工作移到 GPU；又把 TLB coherence 区分为 fresh 与 same-address 两类，分别用 no-flush 和 slow path 处理，设计与测量直接对应。跨 vendor primitive、1,013-case allocation suite、training fragmentation 和两类 LLM remapping 说明改底层 substrate 确实能传到应用。需要警惕的是倍率口径：2,500 倍和 12,700 倍来自 2 GB mapping primitive，不含 reserve/create、application compute 和其他 memory operation；端到端最高 8.2 倍只出现在 prefix cache remapping 很重的 Llama-2-7B。

### 假设压力测试

如果 workload 高频释放并把 physical page 真正归还 driver，或反复修改同一 VA 的 permission/mapping，MOONBRIGHT 仍需 synchronize 和 flush，优势会下降。若 mapping kernel 与 latency-sensitive compute 争同一 GPU，device-side control work 也可能干扰 tail latency；论文只说不同 stream 可 overlap，没有系统量化 interference。Always-Fresh 在 NVIDIA 上每次至少跨 32 MB，使极端细粒度 churn 快速消耗 VA；256 GB stress epoch 证明能 wrap，不代表 11 TB budget 在长期服务中很少触发。以上是适用性推断，不能从 fresh-mapping microbenchmark 直接排除。

### 实验可信度

三代/两厂 GPU、低层与应用实验和针对 TLB/GSP 的 microbenchmark 组成了较完整证据链；mapping 对比保持相同 2 MB granularity，且明确把 reserve/create/unmap 分开。薄弱处是 application 范围：LLM 只有 7B/8B、单 A100，training 图主要报告 fragmentation ratio，没有公开 production trace、P99 allocation latency 或模型吞吐变化。TLB counter 不能直接归因 page walk，论文用 timing 间接推断；GSP 原因因 firmware 不公开也只是解释性 inference。

### 系统性缺陷

MOONBRIGHT 需要约 14.1 KLoC runtime/driver 改动，并依赖 vendor-specific page-table encoding、GSP/PFN interface 和 TLB 行为；driver 或 GPU generation 更新都可能破坏它。更重要的是，把 hardware page table 映射进 device VA 会扩大攻击面：作者明确只支持可信、合作的 single-tenant workload，MPS 不是安全边界，KASLR-style hiding 也不够。论文没有实现 capability、verified mapping kernel、page-table corruption recovery、multi-process ownership check 或 crash-consistent metadata；因此当前不能作为通用云 GPU allocator。

## 局限与后续工作

- **局限 1：安全模型窄。** 用 adversarial CUDA kernel 测任意 PTE write、alias、越权 PFN 和 race，并实现 driver-owned capability 与 sandboxed update kernel。
- **局限 2：same-VA slow path 未充分量化。** 分别控制 free、permission change、remap 和 epoch wrap 比例，报告吞吐、P99 latency 与 flush 次数的退化曲线。
- **局限 3：应用覆盖不足。** 在多 GPU 70B 模型、长时间 serving trace 和动态训练上测 TTFT/TPOT、throughput、OOM batch-size ceiling 与 memory efficiency。
- **后续工作 1：验证跨版本可维护性。** 在至少两版 NVIDIA driver、两版 ROCm 和下一代 GPU 上自动发现 page-table/PFN/TLB 参数，量化 porting diff 与回归风险。
- **后续工作 2：控制 device-side interference。** 给 `pte_pop` 设 stream priority 或 bandwidth budget，并测它与并发 inference kernel 的尾延迟隔离。

## 相关

- **相关概念**：[[GPU-Memory]]、[[Virtual-Memory]]、[[Page-Table]]、[[TLB]]、[[CUDA-VMM]]、[[Memory-Fragmentation]]
- **同类系统**：GMLake、vAttention、[[vLLM]]
- **同会议**：[[OSDI-2026]]
