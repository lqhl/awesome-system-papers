---
type: paper
name: ThinkAhead
full_title: "How Soon is Now? Preloading Images for Virtual Disks with ThinkAhead"
authors: [Xinqi Chen, Yu Zhang, Erci Xu, Changhong Wang, Jifei Yi, et al.]
venue: FAST
year: 2026
tags: [ebs, virtual-disk, preloading, lazy-loading, cloud-storage, alibaba]
source_pdf: "[[fast2026-chen.pdf]]"
source_md: "[[fast2026-chen]]"
---

# How Soon is Now? Preloading Images for Virtual Disks with ThinkAhead (FAST 2026)

> **一句话总结**：阿里云 EBS 上把虚拟盘 image lazy loading 换成数据驱动 preloading，用 score-based genetic algorithm + zero-shot 元数据相似度，把 block hit rate 提升至 7.27×、tail wait latency 降 98.7%。

## 问题

阿里云 EBS 给云上 VM/容器提供虚拟盘（VD），用户从 image（VD snapshot 存在 OSS 远程对象存储）创建 VD。两种朴素方案都不够：

- **Full loading**：拉完整 image 再用，40 GiB image 在 20 MB/s 下要 34 分钟，cold-start 不可接受
- **Lazy loading**（业界默认）：按需拉块。Cold-start 快但首次访问每个块都阻塞远程拉取，成为 EBS 软件栈最大慢 I/O 来源

阿里生产数据（160k VD / 2.5k image / 2025 年 3-5 月 trace + 一年慢 I/O 统计）：

- Lazy loading 占慢 I/O（端到端 >1 s）的 **39.35%**，远超第二名 BlockClient queuing (26.44%)
- p99 lazy loading 延迟达 7 s，82% 的集群每天都有 lazy loading 慢 I/O
- 已有方案都不够：caching 在用户自定义 image 多变下命中率低；P2P 协作受 image 流行度和单机带宽限制；FlacIO 改 I/O 路径与 image 格式，不兼容生产

但 trace 也露出 4 个机会：(1) 同一 image 不同 VD 的 I/O 模式高相似（cosine sim > 0.9 占 84.8% 公共 image / 72.7% 用户自定义）；(2) 启动期访问的 LBA 仅 2.67%-4.55%，强空间局部性；(3) 历史 trace 量大（每天 4k image / 200k VD）；(4) VD 创建到首次 read 有 p50 > 4 s 的 grace period。

3 个挑战：I/O trace 因 burst loss/reorder 不可靠；OSS 带宽小时级波动 2-250 MB/s；zero-shot 场景（56.9% 用户只用单 image 建单 VD）。

## 核心方法

ThinkAhead 三个组件：

1. **Dataset preprocessing**（应对 trace 不可靠）：按访问块数对每个 image 的 trace 分 PDF category（截 top/bottom 2.5% 异常、找 local maxima/minima 切类），category 内再用 [[Pearson-Correlation-Coefficient|PCC]] 聚类成 group，每 group 取 centroid 代表。
2. **Score-based block selection**（应对带宽波动）：对每块 $b_i$ 算分 $S(b_i) = \alpha \cdot ac_i + \beta \cdot \frac{t_{max} - t_{avg,i}}{t_{max}} + (1-\alpha-\beta) \cdot \frac{t_{max} - t_{min,i}}{t_{max}}$（access count + 平均访问时间 + 最早访问时间）。$\alpha, \beta$ 用 [[Genetic-Algorithm]] 离线对每个 (image, bandwidth bin) 训练，预测 misses 时通过 centroid feature switching 在线切到匹配的 group 参数。
3. **Zero-shot prediction**（应对无历史 trace）：按 [[Jaccard-Index]] 的三层 fallback 选相似 image —— 同 image family（OS 发行版）→ 同用户 → 同 metadata（ISO 版本、性能等级），不够 5 条 trace 就放宽。

实现：Python ~1k lines（preloading 逻辑）+ C++ ~6k lines（preloading 系统）；central system 在每个 blockserver 跑 trace collector + 三优先级队列（missed > preload > left）。开源在 GitHub Master-Chen-Xin-Qi/FAST26\_AE。

## 关键结果

- Hit rate：vs Lazyload 提升 **7.27×**（公共 image）/ 2.64×（用户自定义）；vs History-based 提升 3.40× / 1.25×
- P50 wait latency：5 MB/s 带宽下 ThinkAhead 已经做到零，HB 仍 4.6 s
- P99 wait latency：低带宽下比 Lazyload 改进 **79.8%**；zero-shot 场景改进 98.7%
- Zero-shot：hit rate 仅比 HB 低 0.8%，accuracy 反而比 Lazyload 高 64.1%
- Overhead：训练 ~2 小时（day-level，参数跨集群复用），inference < 5 ms
- 真实生产带宽 trace（21,200 VD）下 hit rate 提 4.27× 和 3.44×、p50 wait 降 2.25× 和 1.93×

## 相关

- **相关概念**：[[Lazy-Loading]]、[[Preloading]]、[[Genetic-Algorithm]]、[[Pearson-Correlation-Coefficient]]、[[Jaccard-Index]]、[[Cold-Start]]
- **同类系统**：DADI（容器 image 加速）、Leap（远程内存预取）、FlacIO、AWS Snapshot Acceleration
- **同会议**：[[FAST-2026]]
