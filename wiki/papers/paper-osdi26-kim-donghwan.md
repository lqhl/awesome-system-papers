---
type: paper
name: Cocoon
full_title: Cocoon: A System Architecture for Differentially Private Training with Correlated Noises
authors: [Donghwan Kim, Xin Gu, Jinho Baek, Timothy Lo, Younghoon Min, Kwangsik Shin, Jongryool Kim, Jongse Park, Kiwan Maeng]
venue: OSDI
year: 2026
tags: [differential-privacy, correlated-noise, memory-system, near-memory-processing, embedding]
source_pdf: "[[osdi26-kim-donghwan.pdf]]"
source_md: "[[osdi26-kim-donghwan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向相关噪声差分隐私训练的 Cocoon（OSDI 2026）

> **原题**：Cocoon: A System Architecture for Differentially Private Training with Correlated Noises

> **一句话总结**：相关噪声能改善差分隐私训练的精度，却把过去多个迭代的噪声历史变成容量和数据搬运瓶颈；Cocoon 将噪声历史按参数维度分布到 GPU、CPU 和 CXL 近内存处理设备，并为稀疏 embedding 做预计算与噪声合并，在非平凡设置下报告 1.23–10.82× 加速。

## 问题与动机

DP-SGD 在每次迭代加入独立 Gaussian 噪声，隐私保证明确，但噪声累积会损害模型精度。相关噪声机制（论文以 BandMF 为代表）利用跨迭代相关性抵消部分噪声，在精度上更有吸引力。问题是，每次生成新噪声都要读取并更新最近若干次噪声，所需历史大小约为 band size 与参数量的乘积。

以往相关噪声工作多在 GPU/TPU 充足的环境中评估，掩盖了小规模或经济型节点上的内存和 PCIe/CXL 数据传输成本。Cocoon 关注这类节点，并分别处理普通模型的大参数量和 DLRM 大型稀疏 embedding table 的访问模式。

## 关键观察 / 隐含假设

- **观察 1：噪声历史可能超过设备和主机容量。** 在 8×A5000、256GB DRAM 的节点上，历史大小可超过 GPU 总显存甚至 CPU 内存（图 2）。OPT 模型中，band size 增大还会挤压训练 microbatch，最终触发 OOM（图 3）。
  - **依赖假设**：训练使用中等数量 GPU，无法像大规模 TPU 集群一样用聚合显存容纳历史。
  - **可能失效场景**：GPU/TPU 数量足够、模型分片策略更激进或 band size 较小时，Cocoon 的额外层次化管理可能没有收益。
- **观察 2：相关噪声的计算开销随参数量近似线性增长，而 DLRM 的训练时间随 embedding table 大小次线性增长。** DLRM 上更好的 CPU-GEMV/GPU-GEMV 基线在 band size 8 和 16 时分别出现 2.03–8.62×、6.28–14.49× slowdown（图 4）。
  - **依赖假设**：embedding 访问足够稀疏，且未访问行的梯度为零但仍需满足隐私噪声语义。
  - **可能失效场景**：访问趋于均匀、batch 很大或单步训练本身足够重时，预计算的相对收益下降。
- **观察 3：历史落入 CXL 后，瓶颈从 GEMV 转向跨互连搬运。** GPT2-L 在 2 GPU 上有 63% 历史位于 CXL，slowdown 达 2.83–3.75×；增加 GPU 后部分历史回到显存，slowdown 降至 1.30–2.31×（图 6）。
  - **证据强度**：强，来自不同模型和 GPU 数量的端到端分解。
  - **可能失效场景**：成熟 CXL 设备的 memcpy 带宽、拓扑和并发能力不同于论文原型，结论需要在真实产品上复测。

## 核心方法

Cocoon 将噪声历史沿参数维度切分到 GPU、CPU DRAM 和 CXL NMP 设备。离线 profiling 估计各设备的 GEMV、训练延迟和可用容量，再以最慢并行路径为目标选择切分比例。GPU 负责训练和本地 GEMV，CPU 与 NMP 分别处理各自历史切片，结果按小块返回 GPU，减少整块历史的搬运（图 7）。这直接回应观察 1 和观察 3。

对大型 embedding table，Cocoon 按访问频率划分 hot/cold entry。cold entry 的相关噪声在训练前预计算，并采用 noise tiling 使复用的历史适合 GPU；训练时不再逐迭代对整张表执行 GEMV（图 8、图 9）。

预计算结果使用 noise coalescing 存储：如果一行 embedding 在若干迭代中未被访问，可把这段时间内应加入的噪声聚合，并在该行下一次访问前一次性加入。结果以 CSC 格式保存。hot entry 仍采用常规 GEMV，因为少量高频行会显著增加需要保存的预计算结果。Criteo 数据上，将阈值设为 3 可把平均噪声条目数从 238K 降至 105K，内存减少 2.3×（图 11）。

当历史使用 CXL 内存时，Cocoon 将 GEMV 下沉到 FPGA CXL 控制器中的 NMP 引擎。NMP 读取本地历史，仅把 GEMV 结果送回 GPU，避免 CPU/GPU 与 CXL 间的大量数据传输。原型峰值 GEMV 吞吐为 47.9GB/s，并通过 ring buffer 管理历史；每轮结束 flush 以控制一致性（图 12、图 13）。

## 设计取舍

- **预计算换取运行期延迟**：embedding 噪声不能跨 job 复用，因此预计算仍需完成全部 GEMV；收益来自 GPU 空闲期、数据复用和稀疏合并，不是减少隐私噪声总量。
- **较弱的威胁模型换取 embedding 优化**：该优化假设攻击者只能看到最终模型，不能看到中间梯度；若必须防御可访问中间梯度的攻击者，论文没有证明噪声延迟/合并仍保持同一保证。
- **CXL NMP 换取硬件依赖**：NMP 减少搬运，但需要支持 GEMV 的设备。原型 memcpy 仅 5–7GB/s，论文用 22GB/s 的实测 CXL memcpy 对端到端开销作了分析缩放，因此部分结果并非完整真实硬件闭环。

## 实验与结果

- DLRM 上，band size 大于 8 时，Cocoon 相对 CPU-GEMV/GPU-GEMV 中较优基线加速 2.46–4.87×；band size 为 64 时达到 4.87×（图 14）。
- 在 A100 上使用 4–16GB 模型和 2–4× embedding entries，非平凡设置获得 2.33–10.82× 加速（图 16）。
- Criteo Kaggle 三 epoch、约 1800 次迭代中，coalesced noise 的实际内存开销为模型大小的 4.3–31.6×，低于不少 band size 16/32 的基线历史开销（图 17）。
- LLM 加 CXL NMP 时，Cocoon 相对较优基线加速 1.23–2.32×（图 18）；GPT2-L、OPT-1.3B、GPT2-XL 中 NMP GEMV 可被训练过程部分或完全隐藏。
- GPT2-XL、band size 64 的成本分析假设约 413GB 噪声历史。Cocoon+NMP 比仅扩展 GPU 或 CPU 内存更省硬件和峰值功耗，但吞吐/成本比与 CPU-GEMV 接近（表 1）。
- DLRM 使用未来 TB/s 级 NMP 吞吐的分析投影显示可再获得 2.4×，但这不是当前原型的实测结果（§5.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 相关噪声在经济型节点上会造成容量和运行时间瓶颈 | 图 2–6；DLRM slowdown 最高 14.49× | A5000、Xeon、256GB DRAM，BandMF，单节点 | 强 |
| 噪声分布和 NMP 能减少 CXL 数据搬运 | 图 7、图 18；1.23–2.32× | LLM，CXL 原型，部分 memcpy 开销按 22GB/s 缩放 | 中 |
| embedding 稀疏性支持预计算和噪声合并 | 图 8–11、14–17；2.33–10.82× | Criteo 及合成 Zipf 访问，特定 batch/访问频率 | 强 |
| 方法可扩展到更大模型或 band size | 图 19 与 §5.5 的 projection | 部分数据点是扩容 CXL 或 TB/s NMP 的分析投影 | 中 |

## 批判性分析

### 论证链条

论文的链条较完整：相关噪声产生历史依赖，经济型硬件无法容纳历史，外存搬运成为瓶颈；因此应按内存位置切分并在数据所在处执行 GEMV。DLRM 额外利用访问稀疏性，解释了为何预计算和合并能绕开逐步 GEMV。

但“相关噪声适合广泛 DP 算法”的系统结论主要建立在计算形式等价于 banded GEMV 的机制上。其他混合矩阵若带来不同的稀疏结构、随机数生成或同步要求，仍需单独测量。

### 假设压力测试

Cocoon 假设能预先知道 embedding 访问序列，并在预计算和训练中使用相同随机种子。数据管线重排、在线采样、故障恢复或动态 batch 会破坏这一条件。论文也没有评估训练中断后预计算噪声的恢复与隐私账本处理。

CXL NMP 的收益依赖 GEMV 吞吐高于 CPU/互连搬运的组合。多租户时原型采用命令 FIFO，论文未测量争用下的 P99 延迟或隔离性。多节点扩展只在 §6.1 中作定性讨论，且当聚合 GPU/CPU 内存充足时 NMP 的边际价值会下降。

### 实验可信度

实验覆盖 DLRM、ViT、CNN 和多个规模的 LLM，包含 band size、batch、硬件、模型规模和 Zipf 偏度敏感性。主要端到端结果有明确基线与设备边界。限制在于 NMP 部分采用真实 GEMV 与分析缩放结合的混合方法，且成本估算不含跨节点网络、电源和机箱等扩展成本。没有报告训练精度、隐私预算变化或长时间运行稳定性，这些指标无法由性能实验替代。

### 系统性缺陷

实现增加了 profiling、跨设备同步、CXL coherence flush、随机数状态管理和预计算存储生命周期。论文未讨论这些组件在 checkpoint、抢占、重试和多 job 并发中的运维复杂度。embedding 优化依赖静态访问计划，可能放大数据管线与训练代码之间的耦合。

## 局限与后续工作

- **局限 1**：当前 NMP 原型吞吐不足以帮助 DLRM；DLRM+NMP 结果是基于未来 TB/s 级设备的分析投影，而非实测。
- **局限 2**：NMP LLM 结果的 memcpy 部分按 22GB/s 缩放，不能完全代表一台成熟 CXL 系统的端到端行为。
- **局限 3**：embedding 预计算采用较弱威胁模型，并要求预知访问序列；对中间梯度可见攻击和动态数据管线的保证未覆盖。
- **后续工作 1**：在支持故障恢复和多租户的真实 CXL NMP 设备上测量 P50/P99、带宽争用和 checkpoint 恢复成本，并重新核对隐私状态。
- **后续工作 2**：构造动态采样或在线推荐工作负载，比较静态 noise coalescing、增量预计算和不做预计算时的隐私、内存与吞吐边界。

## 相关

- **相关概念**：[[Differential Privacy]]、[[Near-Memory Processing]]、[[CXL]]、[[Embedding]]
- **同类系统**：[[LazyDP]]
- **同会议**：[[OSDI-2026]]
