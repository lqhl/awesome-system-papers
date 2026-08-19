---
type: theme
topic: Foundation
theme_kind: lens
member_tag: lens/foundation
paper_count: 7
first_generated: 2026-04-24
last_updated: 2026-08-18
tags: [topic-overview, foundation, milestones]
---

# 基础里程碑（Foundation）综述

> 本主题收录 7 篇奠定后续路线的工作：[[Transformer-NeurIPS17|Transformer 2017]] 定义模型架构；[[FlashAttention-NeurIPS22|FlashAttention]]、[[FlashAttention-2-ICLR24|FlashAttention-2]] 和 [[FlashAttention-3-NeurIPS24|FlashAttention-3]] 定义精确注意力的系统实现范式；[[vLLM-SOSP23|vLLM]] 与 [[SGLang-NeurIPS24|SGLang]] 分别代表通用模型服务和程序感知服务；[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 则给出 2026 年开源前沿模型的综合基线。

## 阅读提示

- **注意力（attention）**让模型按输入内容动态汇聚信息；**自注意力（self-attention）**表示查询、键和值均来自同一序列。
- **注意力内核（attention kernel）**是直接在加速器上执行注意力计算的底层程序；每秒浮点运算次数（floating-point operations per second，FLOPs/s）衡量其计算吞吐。
- **预填充（prefill）**一次处理输入提示，**解码（decode）**逐步生成新词元。两阶段形状不同，因此适合不同的注意力和键值缓存实现。
- 键值缓存（Key-Value Cache，KV Cache）保存历史词元的中间状态，避免生成每个新词元时重复计算；其容量、碎片和复用方式直接限制并发服务能力。
- 文中的“精确注意力”指在不改变数学结果的前提下优化实现；稀疏或压缩注意力则通过减少参与计算的连接来降低成本，可能改变输出。
- 低精度格式包括 16 位脑浮点数（Brain Floating Point 16，BF16）、8 位浮点数（FP8）和 4 位浮点数（FP4）；位宽越低，通常越节省计算与存储，但越需要控制数值误差。
- BLEU 衡量机器翻译与参考译文的词组重合程度；数值越高通常表示译文越接近参考答案。WMT 2014 是论文采用的机器翻译基准。
- **归一化指数函数（softmax）**把一组分数转换为总和为 1 的权重，是注意力的核心计算步骤。

## 核心论文

### 架构基石（1 篇）

- [[Transformer-NeurIPS17|Attention Is All You Need]] — 提出完全基于自注意力的 Transformer，在 WMT 2014 英德翻译任务达到 28.4 BLEU；多头注意力、缩放点积注意力和正余弦位置编码成为现代大语言模型的共同基础。

### 注意力内核基础设施（3 篇）

- [[FlashAttention-NeurIPS22|FlashAttention]] — 用面向输入输出开销的分块、在线 softmax 和反向传播重计算，避免物化 `N×N` 注意力矩阵；A100 上注意力计算最高加速 7.6 倍。
- [[FlashAttention-2-ICLR24|FlashAttention-2]] — 沿序列长度并行，并在一个线程束内拆分查询；A100 前向计算最高达到 230 TFLOPs/s。
- [[FlashAttention-3-NeurIPS24|FlashAttention-3]] — 利用 Hopper 的张量内存加速器（Tensor Memory Accelerator，TMA）、线程束组矩阵乘加指令（Warpgroup Matrix Multiply-Accumulate，WGMMA）、线程束专门化，以及矩阵乘法与 softmax 重叠；在 H100 上以 BF16 计算最高达到 840 TFLOPs/s，并支持 FP8。

### 大语言模型服务基础设施（2 篇）

- [[vLLM-SOSP23|vLLM / PagedAttention]] — 用 [[KV-Cache|键值缓存]]的虚拟内存式分页、块表、按需分配和写时复制实现前缀共享，成为大语言模型服务的事实标准基线。
- [[SGLang-NeurIPS24|SGLang]] — 用语言模型程序领域专用语言、RadixAttention 跨调用共享前缀，以及压缩有限状态机跳过确定路径；相对 vLLM v0.2.5，吞吐最高提高 6.4 倍。

### 开源前沿模型综合（1 篇）

- [[DeepSeek-V4-arXiv26|DeepSeek-V4]] — 采用 1.6 万亿参数的[[MoE|混合专家模型]]，每次计算激活 490 亿参数，并支持 100 万词元上下文；压缩稀疏注意力（Compressed Sparse Attention，CSA）与强压缩注意力（Heavily Compressed Attention，HCA）把 100 万上下文的计算量和键值缓存分别压到 V3.2 的 27% 与 10%。训练栈还使用 Muon 优化器、流形约束超连接（Manifold-Constrained Hyper-Connections，mHC）和 FP4 量化感知训练。

## 主题综述

### 九年的架构传承

从 [[Transformer-NeurIPS17|Transformer]] 到 [[DeepSeek-V4-arXiv26|DeepSeek-V4]]，主干仍是堆叠的自注意力、前馈网络、残差连接和层归一化，但每个组件都被重做：前馈网络从稠密计算转向混合专家模型；注意力从复杂度为 $O(n^2)$ 的稠密计算，经过 FlashAttention 系列精确内核，再延伸到 CSA 与 HCA 压缩稀疏注意力；位置编码从正余弦编码转向部分旋转位置编码和注意力汇聚点；残差权重则从固定值转向 mHC 与 [[AttnRes-arXiv26|AttnRes]] 的可学习聚合。

### 注意力内核的三次瓶颈迁移

[[FlashAttention-NeurIPS22|FlashAttention]] 解决把 $N×N$ 中间矩阵写入高带宽显存（High Bandwidth Memory，HBM）的开销；[[FlashAttention-2-ICLR24|FlashAttention-2]] 在输入输出效率提高后，把瓶颈推进到线程块、线程束分工和序列并行的硬件占用率；[[FlashAttention-3-NeurIPS24|FlashAttention-3]] 则针对 Hopper 上 softmax 指数运算与矩阵乘法高达 256 倍的吞吐差，用生产者—消费者线程束和 FP8 重排改变计算形状。三代共同假设精确注意力仍值得优化，这与 [[NSA-ACL25|NSA]] 等稀疏路线形成对照。

### 服务栈分为通用引擎与程序感知运行时

[[vLLM-SOSP23|vLLM]] 把每次生成视为独立请求，用 [[PagedAttention]] 解决键值缓存碎片与共享；[[SGLang-NeurIPS24|SGLang]] 则假设语言模型程序会产生 50%–99% 的前缀重叠，用基数树跨调用复用键值缓存，并用压缩有限状态机跳过结果确定的多个词元。两条路线的分歧在于是否向运行时暴露工作负载结构。vLLM 后续也加入前缀缓存，但 SGLang 的缓存感知调度和分叉提示仍是程序感知路线的代表。

### 系统工程承载能力增长

Transformer 用 8 块 P100 训练 6500 万至 2.13 亿参数模型；DeepSeek-V4 用 33 万亿词元训练 1.6 万亿参数模型，基础设施单独成章，包括专家并行巨型内核、TileLang 算子生成语言、FP4 量化感知训练和 DSec 沙箱执行平台。与模型能力规模的增长相比，架构主干变化较慢，系统实现与硬件协同因而成为前沿竞争的主要战场。

## 设计空间矩阵

| 论文 | 奠定的抽象 | 主要瓶颈 | 核心机制 | 代表性证据 | 适用边界 |
|---|---|---|---|---|---|
| [[Transformer-NeurIPS17\|Transformer]] | 基于自注意力的序列模型 | 循环计算限制并行 | 多头注意力、位置编码 | WMT 2014 英德翻译 28.4 BLEU | 原始设计假设序列长度小于表示维度 |
| [[FlashAttention-NeurIPS22\|FlashAttention]] | 精确且输入输出感知的注意力内核 | 中间矩阵读写 HBM | 分块、在线 softmax、重计算 | A100 最高加速 7.6 倍 | 解码时查询极短，序列并行收益有限 |
| [[FlashAttention-2-ICLR24\|FlashAttention-2]] | 更高并行度的精确内核 | 线程块与线程束分工 | 序列并行、查询拆分 | A100 前向最高 230 TFLOPs/s | 仍保留稠密注意力计算量 |
| [[FlashAttention-3-NeurIPS24\|FlashAttention-3]] | Hopper 感知内核 | 指数运算与矩阵乘法吞吐不均 | 异步流水、线程束专门化、FP8 | H100 BF16 最高 840 TFLOPs/s | 短查询解码应采用其他路径 |
| [[vLLM-SOSP23\|vLLM]] | 分页式键值缓存管理 | 显存碎片和动态请求长度 | 块表、按需分配、写时复制 | 通用服务吞吐基线 | 短序列或键值缓存充裕时收益缩小 |
| [[SGLang-NeurIPS24\|SGLang]] | 程序感知的模型服务 | 跨调用重复前缀 | RadixAttention、压缩有限状态机 | 相对 vLLM v0.2.5 最高提高 6.4 倍 | 前缀重叠低时缓存命中率接近零 |
| [[DeepSeek-V4-arXiv26\|DeepSeek-V4]] | 长上下文前沿模型综合栈 | 百万词元下的计算与键值缓存 | CSA、HCA、混合专家、FP4 量化感知训练 | 计算量与键值缓存为 V3.2 的 27% 与 10% | 压缩注意力可能限制精确远距离访问 |

## 共同观察

1. **注意力瓶颈随工作负载形状迁移。** FlashAttention 假设物化注意力矩阵是主要显存开销；FlashAttention-2 转向硬件占用率和非矩阵乘法开销；FlashAttention-3 关注 Hopper 上指数运算所占周期；DeepSeek-V4 则假设 100 万上下文中的计算量和键值缓存都必须从算法层压缩。解码阶段查询仅有一个或数个词元时，FlashAttention-3 的序列并行收益有限，应采用 PagedAttention 或拆分键值计算的路径。
2. **键值缓存管理是服务核心抽象，但复用语义的归属决定系统形态。** vLLM 假设块表分页和按需分配足以服务多数请求；SGLang 假设跨调用前缀局部性足够强，值得维护基数树和缓存感知调度。短序列、缓存充裕或计算受限时，vLLM 的相对优势缩小；租户无关且输出较长的聊天任务中，SGLang 的缓存命中率接近零。
3. **精确注意力仍是默认，稀疏和压缩更多是叠加而非替代。** Transformer 的二次复杂度在长上下文下成为主要矛盾，但 FlashAttention 系列保持数学语义并优化实现；DeepSeek-V4 用 CSA 与 HCA 压缩计算，同时保留 Transformer 骨架。需要完整注意力图或精确远距离单词元访问时，压缩块内的因果限制仍是边界。
4. **里程碑工作的价值在于跨时间锚定。** 研究内核优化可沿 FlashAttention 三代追踪，研究键值缓存管理可连接 Transformer、vLLM 和 SGLang，研究 100 万上下文则可从 DeepSeek-V4 的 CSA 与 HCA 权衡切入；这种组织方式与 [[AI-Infra]] 的当前热点聚类互补。

## 假设冲突与脆弱点

1. **独立请求与程序感知复用。** vLLM 把连续批处理和分页键值缓存视为通用解；SGLang 则把语言模型程序的分叉与前缀结构提升为一等语义，并允许等待队列增长时驱逐缓存换取更大批次。高周转短提示会放大基数树维护成本，最长前缀优先也可能使冷启动请求饥饿。需要在同一智能体或检索增强生成（Retrieval-Augmented Generation，RAG）轨迹上比较两者的命中率与 P99。
2. **精确内核与算法压缩。** FlashAttention-3 假设预填充和训练仍以稠密精确注意力为主；DeepSeek-V4 假设 100 万上下文必须用 CSA 与 HCA 压缩计算量和键值缓存。64K 以下上下文或短输出解码可能更适合精确路线；干草堆找针测试的变体则会暴露压缩块的因果限制。需要在同模型规模上比较质量、延迟和内存。
3. **PagedAttention 的收益取决于内存瓶颈。** vLLM 的批判性分析指出，OPT-175B 与 Alpaca 短序列中，理想化 Orca 也能批处理很多请求，PagedAttention 优势因此缩小。预填充密集、多模态或混合专家工作负载会让其他瓶颈主导；这也与 SGLang 在缓存和运行中请求之间分配显存的选择形成对照。
4. **Transformer 的原始规模假设已经失效。** 原论文假设序列长度 $n$ 远小于表示维度 $d$；今天 4K 至 100 万词元的上下文使 $O(n^2)$ 成为系统主要矛盾。FlashAttention、分块预填充和稀疏模式都是对此的回应，而 DeepSeek-V4 仍延续了架构主干基本不变、工程规模急剧增长的路线。

## 值得关注的方向

### 1. 从 Transformer 到 DeepSeek-V4 的未完成空白

小团队可对照里程碑论文的设计差异定位尚未工程化的组合。[[Transformer-NeurIPS17|Transformer]] 提到局部或受限注意力与多模态扩展，[[DeepSeek-V4-arXiv26|DeepSeek-V4]] 只在文本上实现 100 万上下文；可进一步研究复杂度为 $O(r·n·d)$ 的受限注意力如何与 CSA、HCA 组合，以及旋转位置编码、线性偏置注意力（Attention with Linear Biases，ALiBi）和 mHC 在百万词元尺度的外推边界。

### 2. 将里程碑结果做成可复现基准

复现关键结果和建立对比基准适合小团队。DeepSeek-V4 的完整训练不可复现，但 mHC、CSA 和 HCA 可在 10 亿至 100 亿参数的压缩版本上验证；Transformer 表 3 的严格消融实验在前沿论文中日渐少见。具体问题包括 mHC 相对普通残差的质量增益、CSA 与 HCA 的最优混合比例，以及 FP4 量化感知训练在非 DeepSeek 架构上的精度边界。

### 3. 将前沿方法反向验证于小模型

Muon、mHC、CSA 和全词表在策略蒸馏（full-vocabulary on-policy distillation，OPD）可分别在 10 亿至 80 亿参数模型上验证，适合拆解 DeepSeek-V4 未报告的小模型规模效应。可测试 Muon 的 Newton–Schulz 系数能否随任务调整、使用两至三个教师模型的简化 OPD，以及 mHC 约束在小模型上是否可以放松。

### 4. 统一预填充内核与解码缓存

单张 H100 或 A100 即可对 FlashAttention 内核和分页键值加载的重叠做微基准。FlashAttention-3 明确指出短查询解码应走其他路径，而 vLLM 与 SGLang 的集成假设不同；可测量预填充使用 FlashAttention-3、解码使用拆分键值计算时的最佳切换点，并探索基数树缓存与分页块共享同一内存池的设计。
