# PageFlex: Flexible and Efficient User-space Delegation of Linux Paging Policies with eBPF

**作者**：Anil Yelam, Kan Wu (Google); Zhiyuan Guo (UC San Diego); Suli Yang (Google); Rajath Shashidhara (University of Washington); Wei Xu, Stanko Novaković (Google); Alex C. Snoeren (Google and UC San Diego); Kimberly Keeton (Google)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/yelam
**源文件**：[[atc2025-yelam.pdf]]

---

## 一、背景

在超大规模数据中心中，内存成本占总拥有成本（TCO）的比例持续增长。Google 的 g-swap 和 Meta 的 TMO 等系统通过将"冷"页面透明地卸载到更便宜的存储层（如压缩内存 zswap、NVMe SSD）来提升平台内存效率，已实现 20–30% 的内存节省。

这些系统依赖 Linux 内核的页面回收（page reclamation）和预取（prefetching）策略来决定卸载哪些页面、何时卸载以及如何预取。当前部署普遍使用 LRU 近似算法（如 active/inactive lists、MGLRU、g-swap 的 per-page age），但学术界已提出许多更优的驱逐算法（Hyperbolic caching、LHD、LIRS 等）和预取策略（Leap 等），在 trace 模拟中展现出显著优势。论文通过对真实工作负载 trace 的模拟发现，LRU 与最优策略（Belady's MIN）之间存在 14–38% 的内存节省差距。

---

## 二、要解决的问题

1. **内核策略部署困难**：在大规模 fleet 中滚动部署内核变更缓慢且高风险，Google 内部反馈"月度级别的内核 rollout 都难以容忍"。实验性或应用特定的策略更难被上游接受，需要维护独立分支。

2. **userfaultfd 方案性能开销大**：将整个 paging 机制迁移到用户态会使 page fault 成本增加超过 50%（zero-page fault 从 1.2 µs 增至 5.6 µs），直接损害应用性能。此外还需在用户态重新实现整套 swap 基础设施。

3. **自定义库方案侵入性强**：DiLOS、AIFM 等绕过 OS 的方案需要修改应用代码，且即使不卸载内存也会引入高达 40% 的性能开销（因绕过 TLB/MMU 硬件加速），同样存在 swap 基础设施兼容性问题。

4. **缺乏应用感知的策略支持**：现有方案对所有内存区域和执行阶段使用统一策略，无法针对不同访问模式（如图处理中顺序遍历边 vs. 随机访问顶点）进行差异化优化。

---

## 三、洞察与设计

**关键洞察**：页面回收和预取的策略决策（policy decisions）与底层执行机制（mechanisms）可以解耦——策略决策本身不在应用的关键路径上（proactive reclamation 和 prefetching 都是异步执行的），因此可以安全地外部化到用户态，而无需将整个 paging 机制搬出内核。

基于此洞察，PageFlex 的设计核心是：只将非性能关键的策略决策委托到内核外部，内核继续负责页面访问跟踪、按需缺页处理和实际的页面回收/换入机制。具体设计：

- **eBPF 事件处理器**：策略通过 eBPF 程序订阅内核 paging 事件（OnPageAlloc、OnPageFree、OnPageScanned、OnPageFault），在事件触发时同步执行，获得低开销的内核内存状态视图。
- **通用 per-page 权重模型**：将 g-swap 的 per-page LRU age 推广为通用的 per-page weight，不同策略通过自定义 UpdateWeight 函数实现不同的驱逐排序（LRU、LFU、Hyperbolic caching 等）。
- **低开销 per-page 状态**：在内核 page struct 中预留 4 字节字段供 eBPF 独占使用（0.1% 内存开销），通过 writable tracepoints 提供安全写入访问。
- **用户态 agent 执行与强制**：专用用户态进程通过 process_madvise() 批量发出 page in/out 决策，amortize syscall 开销。
- **区域与阶段感知**：支持对同一进程内不同内存区域绑定不同的回收和预取策略，通过 IPC 接口接收应用 hints。
- **策略隔离**：基于 cgroup 的 enclave 机制，不同工作负载可运行不同策略，PageFlex 失败时自动回退到内核默认策略。

---

## 四、实现细节

- **内核修改**：608 行代码变更，主要是定义 tracepoints 和支持 page struct 中的预留字段。基于 Linux 5.10。
- **用户态 agent**：2,900 行 C++ 代码。
- **eBPF 程序**：700 行代码支持核心组件和简化策略接口。
- **Tracepoints**：在 cgroup page charge/uncharge、page fault handling、页表扫描等位置插入 tracepoints，导出 memcg ID 和 page struct 预留字段的 writable 指针。
- **Per-page 状态持久化**：通过复用 swap cgroup maps（已有的 cgroup 级 swap accounting 数据结构）在 swap-out 时保存状态，swap-in 时恢复。
- **eBPF maps**：使用 HASH map 做策略配置、ARRAY map 做统计、RINGBUF 做事件通知、histogram hash map 传递权重分布。Region-aware 策略维护 VMA 到子策略的 hash map（每 enclave 256 slots）。
- **批量 madvise**：每次 process_madvise 调用批量处理 64 个页面，将单页 6.9 µs 的开销 amortize 到 4.9 µs/page。
- **策略代码量极小**：Hyperbolic caching 17 行 eBPF、LRU 6 行、LFU 8 行、Leap prefetching 187 行（其中 160 行复用原始实现）。

---

## 五、实验结果

实验平台：双路 Intel Xeon E5-2696（24 核），128 GB 内存，Linux 5.10 + g-swap，swap 后端为 zswap 或 SSD 模拟（50 µs 中位延迟）。

**策略等价性（PageFlex LRU vs g-swap LRU）**：

| 工作负载 | 性能差异 | 说明 |
|---------|---------|------|
| Redis (zipf 0.5) | ≤ 0.98% 慢 | 所有 swap 比例下 refault rate 几乎一致 |
| userfaultfd（+4µs 模拟） | 最多 13.3% 慢 | 相同 refault rate 下 |

**预取策略（PageFlex read-ahead vs kernel read-ahead）**：

| 场景 | 指标 | 结果 |
|------|------|------|
| Sequential + zswap | 预取命中率 | 两者均命中 50% 页面 |
| Sequential + SSD | 性能提升 | kernel 82%, PageFlex 76% |
| Strided + SSD | 无预取开销 | PageFlex 仅 0.8% 慢 |
| Strided + SSD + Leap | 性能提升 | 比 Linux read-ahead 提升 75.4% |

**新策略收益**：

| 策略 | 工作负载 | 收益 |
|------|---------|------|
| LFU | 合成 LFU 友好负载 | 同 10% 性能下降时，swap 利用率 41% vs LRU 的 20%（2× 内存节省） |
| Hyperbolic caching | Memcached trace | 同 refault rate 下多 5% 内存节省 |
| 区域感知策略 | KV store | 比 LRU 多 36% 内存节省 |
| ExtMem 策略 | GAPBS PageRank | 内存使用减少 6.4%，性能开销 < 2% |

**基础设施开销**：

| 组件 | 开销 |
|------|------|
| 页表扫描（eBPF hook） | 比 g-swap 慢 17%（≈50ns/page） |
| 用户态 paging（批量 madvise） | 比 kreclaimd 慢 14%（4.9 µs/page vs 4.3 µs/page） |

---

## 六、批判性分析

1. **评估硬件陈旧**：实验使用 Xeon E5-2696（Broadwell 时代，2015 年），这是超过 10 年前的服务器 CPU。考虑到 eBPF overhead 是固定的（≈50ns/invocation），而现代 CPU 的内存带宽和 TLB 性能大幅提升，论文中量化的相对开销比例（如 17% 页表扫描开销）在现代硬件上可能有显著变化。

2. **与 userfaultfd 的比较不够公平**：论文通过注入 4 µs 延迟来模拟 userfaultfd 开销，而非实际运行 userfaultfd 方案。作者承认无法做到 apples-to-apples 比较，但这削弱了论文的核心论点之一。

3. **策略改进幅度有限**：Hyperbolic caching 相比 LRU 仅多 5% 内存节省，LFU 的 2× 优势需要特定友好的工作负载。这不禁让人质疑 LRU 与 MIN 之间 14–38% 的差距中，有多少是实际可捕获的（而非仅在有 oracle 信息时才可达）。

4. **Region-aware 策略需要应用配合**：虽然声称"application portability"是优势，但区域感知策略仍需修改应用代码（如 PageRank 案例需加 10 行代码）或开发专门的 agent 来检测访问模式，这与论文强调的"无需修改应用"目标存在张力。

5. **eBPF 表达能力限制被淡化**：论文承认 eBPF verifier 限制使得 LRB 等基于 ML 模型的策略难以实现，但 4.3 节对此讨论不足。既然 LRU 与 MIN 之间差距显著，而简单启发式（Hyperbolic、LFU）收益有限，真正能逼近 MIN 的可能恰恰是被 eBPF 限制排除的复杂策略。

6. **缺乏端到端 fleet 级评估**：作为 Google 内部工作，论文没有报告 PageFlex 在实际生产 fleet 中的部署结果和端到端 TCO 影响，所有实验都在单机基准测试上完成。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理的 KV cache 管理**：PageFlex 的区域感知策略思路可直接借鉴到 LLM 推理的 KV cache 管理。不同请求、不同 attention head、不同层的 KV cache 具有显著不同的访问模式和重要性，PageFlex 的 per-region policy + hints 机制为 KV cache 的分层驱逐（如 prefill vs decode 阶段差异化策略）提供了系统设计参考。

2. **GPU 显存管理的 eBPF 化**：当前 GPU 显存管理（如 vLLM 的 PagedAttention、FlexGen 的 offloading）都在用户态实现。PageFlex 展示了通过 eBPF 在内核级别做低开销策略注入的可行性。随着 GPU 统一虚拟内存（UVM）的演进，类似的 hook 机制可能用于 GPU 页面迁移策略的定制。

3. **训练 checkpoint 和内存卸载**：大模型训练中的 activation checkpointing 和 optimizer state offloading 本质上也是"冷数据卸载"问题。PageFlex 的 per-page weight 模型（替代简单 LRU）可以启发更智能的 offloading 策略——例如根据 layer 的 recomputation cost 和 access frequency 联合优化。

4. **可操作的 follow-up 方向**：将 PageFlex 的通用权重模型扩展到 GPU 场景，为 CUDA Unified Memory 的页面迁移策略提供可编程接口，是一个有价值的研究切入点。

---

## 八、总结

PageFlex 通过将 paging 策略与机制解耦，利用 eBPF 在内核内提供低开销的内存状态视图，同时将策略决策委托到用户态执行，实现了灵活且高效的 Linux 分页策略定制。其核心贡献是证明了策略外部化可以在几乎不损失应用性能（<1%）的前提下完成，并通过通用的 per-page weight 模型支持多种驱逐和预取策略。主要局限在于 eBPF 的表达能力限制排除了复杂的 ML-based 策略，且实际收益在简单启发式下相对有限。该框架最适合需要快速迭代策略、支持多租户差异化策略的超大规模数据中心场景。
