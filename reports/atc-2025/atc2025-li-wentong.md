# PMR: Fast Application Response via Parallel Memory Reclaim on Mobile Devices

**作者**：Wentong Li (华东师范大学), Li-Pin Chang (阳明交通大学), Yu Mao (香港城市大学 / MBZUAI), Liang Shi (华东师范大学)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/li-wentong
**源文件**：[[atc2025-li-wentong.pdf]]

---

## 一、背景

移动应用的内存需求快速增长（社交、视频、浏览器等应用动辄占用数百 MB 到数 GB 内存），但移动设备的物理内存增长缓慢（iPhone 16 仅 8GB，Galaxy S25 Ultra 16GB）。Android 系统依赖三级内存回收机制来应对内存压力：异步的 kswapd 内存交换、同步的 direct reclaim、以及杀进程的 LMKD（Low Memory Killer Daemon）。LMKD 虽然能快速释放内存，但会导致应用上下文丢失和长时间冷启动延迟，严重影响用户体验。因此，高效的内核级内存回收（memory swapping + direct reclaim）对移动设备的用户体验至关重要。

---

## 二、要解决的问题

作者在真实移动设备上的实验揭示了当前内核级内存回收的三个核心问题：

1. **Page shrinking 与 page writeback 串行执行**：每轮内存回收必须先完成 page shrinking（从 LRU 列表选出 victim pages），再执行 page writeback（将 victim pages 写回存储），两步串行导致不必要的等待。实测显示 page shrinking 占总延迟的 54.8%，page writeback 占 45.2%。

2. **Page shrinking 效率低下**：内核期望每轮回收 39,340 页（约 154MB），但实际回收量远低于预期。原因是大量页面因"最近被引用"或"被锁定"而无法回收，导致 page shrinking 反复调用。

3. **Page writeback 的 I/O 碎片化**：page unmap 逐页执行（4KB 粒度），延迟高度不稳定，且产生碎片化的小 I/O，无法充分利用现代 Flash 存储设备的内部并行性。实测 Pixel 6 Pro（UFS 3.1）随机写带宽可达约 1000 MB/s，但内存回收吞吐量长期低于 150 MB/s。

这些问题导致系统频繁触发 LMKD（Pixel 6 Pro 在 5 分钟内发生 26 次进程杀死），应用切换时冷启动延迟是热启动的 3.1 倍。

---

## 三、洞察与设计

**关键洞察**：内存回收的瓶颈不在 I/O 冲突或存储硬件本身，而在于内核回收路径的设计——page shrinking 和 page writeback 的串行执行流，以及逐页 unmap/writeback 的碎片化 I/O 模式，使得系统软件无法充分利用不断升级的 Flash 存储性能。

基于此洞察，PMR（Parallel Memory Reclaim）重新设计内核回收路径，包含两个核心组件：

### Proactive Page Shrinking (PPS)

- 将 page shrinking 从 kswapd/direct reclaim 中解耦，交给独立的内核线程 **kshrinkd**
- kshrinkd 在系统启动时即开始收集 victim pages 到新的 **victim page list**，不依赖内存压力触发
- 通过 page shrinking watermark（默认 δ = 462MB）控制 victim page list 的容量
- 当内存回收发生时，page writeback 可以直接从 victim page list 获取已准备好的 victim pages，无需等待 page shrinking
- 使用 PG_ISOLATED 位标记已隔离的页面，用轻量级 spinlock 协调 kshrinkd 和 page writeback 之间的并发访问

### Storage-friendly Page Writeback (SPW)

- **Application-aware page unmap**：将 victim pages 按所属进程聚合，批量执行 unmap，而非逐页操作。利用 big.LITTLE 架构将 unmap 线程绑定到大核并提高优先级，避免被抢占
- **Batch write I/Os**：根据存储设备特性确定最优 I/O 大小（如 Pixel 6 Pro 为 10MB），将多个 unmapped pages 合并为大块 I/O 提交，充分利用 Flash 存储的内部并行性

---

## 四、实现细节

PMR 遵循最小侵入原则，尽量复用现有内核函数：

- **kshrinkd 初始化**：在 `start_kernel` 流程中通过 `kshrinkd_init` 调用 `kthread_run` 为每个内存节点创建 kshrinkd 线程（类似 kswapd 的创建方式）
- **新的页面列表类型**：引入 `LRU_VICTIM` 作为 page shrinking 和 page writeback 之间的中间缓冲
- kshrinkd 继承了原有 kswapd 的 page shrinking 算法（包括 LRU 扫描比例计算），但激活条件改为 victim page list 不足而非内存水位线
- SPW 通过 `/proc` 接口支持动态调整 unmap 单位大小（`mem_unmap_unit`）
- 与现有 LRU 页面替换策略正交，兼容任何 victim page 选择算法
- 不修改内存回收触发条件，专注于加速回收执行路径
- 基于 Android 13 / Linux Kernel 5.10 实现

---

## 五、实验结果

**实验平台**：Google Pixel 5（8GB/UFS 2.1）、Redmi Note 11（6GB/UFS 2.2）、Google Pixel 6 Pro（12GB/UFS 3.1），均运行 Android 13，启用 2GB swap 分区。

**工作负载**：36 个应用（10 个前台切换 + 26 个后台运行），使用 UIAutomator 自动化操作，每组实验重复 10 轮取平均值。

**对比方案**：Original MR（原生 Linux）、Acclaim（ATC'20）、Fleet（ASPLOS'24）。

| 指标 | PMR vs Original MR | PMR vs Acclaim | PMR vs Fleet |
|------|-------------------|----------------|--------------|
| 应用响应时间 | 降低 43.6% | 显著优于 | 显著优于 |
| PMR+Fleet vs Original MR | 降低 67.4% | — | 比 Fleet 再降 38.9% |
| 峰值回收吞吐量 | 提升 82.8% | 提升 75.5% | — |
| LMKD 次数 | 减少 82% | 减少 54% | — |
| Direct reclaim 次数 | — | 减少 45% | — |
| CPU 开销 | 增加 5.3%（24.31→25.61） | — | — |
| Flash 写入量 | 增加 12.1% | — | — |

**存储利用率**：PMR 使 Pixel 6 Pro 的内存回收吞吐量显著高于 Pixel 5，有效利用了 UFS 3.1 相对于 UFS 2.1 的带宽优势，而 Original MR 和 Acclaim 在不同代际设备上几乎无差异。

**参数敏感性**：victim page list 容量 δ = 462MB 为最优；application-aware page unmap 大小因设备而异（Pixel 5 为 1MB，Pixel 6 Pro 为 10MB）。

---

## 六、批判性分析

1. **工作负载代表性有限**：实验使用固定的 36 个应用集合和特定切换模式，未涉及游戏类重度内存应用或后台持续消耗内存的场景（如导航 + 音乐 + 即时通讯同时运行），真实用户行为的多样性未被充分覆盖。

2. **δ 参数的固定值策略值得质疑**：作者自己也承认不同应用需要不同的回收量，但最终采用了固定的 462MB 经验值。在内存更小的设备（如 4GB 或更低）上，462MB 的 victim page list 可能占用过多有效内存。作者未讨论该参数在不同内存容量设备上的适应性。

3. **CPU 开销评估不够透彻**：虽然总体 CPU 开销仅增加 5.3%，但论文没有分析 kshrinkd 在系统空闲时的 CPU 唤醒频率和功耗影响——对于电池供电的移动设备，功耗是一个关键但被忽略的维度。

4. **Flash 写入增加 12.1% 的影响被轻描淡写**：作者用"存储容量增大缓解了寿命焦虑"来回应，但未提供具体的寿命估算。对于中低端设备（如 eMMC 存储、128GB 容量），写放大可能更为显著。

5. **仅在 Android 13 / Kernel 5.10 上验证**：现代 Android 版本（14/15）和更新的内核（5.15/6.x）引入了 MGLRU（Multi-Gen LRU）等新的内存管理机制，PMR 与这些新机制的兼容性未被讨论。

6. **与 Fleet 的组合实验不够完整**：PMR+Fleet 的结果仅报告了应用响应时间，未给出组合后的内存回收吞吐量、LMKD 次数等详细指标，无法全面评估组合效果。

---

## 七、AI Infra / MLSys 视角

1. **移动端 LLM 推理的内存管理启发**：作者在讨论中明确提到 LLM 部署到移动设备会带来巨大的内存压力。PMR 的预取式页面回收思想可以启发移动端 LLM 推理框架（如 LLM in a Flash）在 KV cache 换出策略上的优化——将 page shrinking（选择哪些 KV cache 块换出）和 writeback（实际写入 Flash）解耦并行化。

2. **批量 I/O 思想可迁移**：SPW 的 application-aware batch I/O 策略与 AI Infra 中的 checkpoint 写入、模型权重加载等场景高度相关。在分布式训练中，checkpoint 的写入同样面临小 I/O 碎片化问题，按模型层或 tensor 聚合后批量写入可提升吞吐。

3. **值得跟进的研究方向**：
   - 在移动端 LLM 推理中，结合 PMR 的并行回收思路，设计 KV cache 感知的内存回收策略，根据 attention score 或 token 访问模式选择换出对象
   - 将 PMR 的存储友好 I/O 设计扩展到边缘 AI 设备上的模型换入换出（model swapping），实现多模型共享有限内存时的快速切换

---

## 八、总结

PMR 通过重新设计 Android 内核的内存回收路径，将 page shrinking 和 page writeback 解耦并行化，并引入存储友好的批量 I/O，使内存回收吞吐量提升 82.8%，应用响应时间降低 43.6%，LMKD 次数减少 82%。其设计与现有的 victim page 选择策略和 ART GC 优化正交互补，适用于内存受限的移动设备场景。主要局限在于参数（δ、unmap 大小）依赖经验调优且缺乏自适应机制，以及对功耗影响和新内核版本兼容性的评估不足。
