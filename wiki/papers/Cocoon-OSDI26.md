---
type: paper
name: Cocoon
full_title: "Cocoon: A System Architecture for Differentially Private Training with Correlated Noises"
authors: [Donghwan Kim, Xin Gu, Jinho Baek, Timothy Lo, Younghoon Min, Kwangsik Shin, Jongryool Kim, Jongse Park, Kiwan Maeng]
venue: OSDI
year: 2026
tags: [differential-privacy, ml-training, correlated-noise, cxl, near-memory-processing]
source_pdf: "[[osdi26-kim-donghwan.pdf]]"
source_md: "[[osdi26-kim-donghwan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 面向相关噪声差分隐私训练的系统架构（OSDI 2026）

> **原题**：Cocoon: A System Architecture for Differentially Private Training with Correlated Noises

> **一句话总结**：相关噪声可以让训练中的噪声相互抵消、改善模型效用，却要保留约 `(b̂−1)×模型参数量` 的历史并每步做 GEMV；Cocoon 把历史分到 GPU、CPU 和 CXL-NMP，就地并行计算，并为稀疏 embedding 预计算、合并未来噪声，非平凡 DLRM 配置相对较好基线快 2.33–10.82 倍、含 NMP 的大模型配置快 1.23–2.32 倍，但 embedding 优化采用更弱的攻击者模型，NMP 端到端结果也把原型的低速 memcpy 分析缩放到 22 GB/s，并非全部直接实测。

## 问题与动机

[[Differential-Privacy|差分隐私]]训练通过裁剪每个样本的梯度，再加入 Gaussian noise，限制单条训练数据对最终模型的影响。传统 [[DP-SGD]] 每轮加入独立噪声；新一类方法让后续噪声与过去噪声相关，使它们跨轮次部分抵消，从而在相同隐私预算下得到更好的模型效用。Cocoon 采用 BandMF 作为代表机制，关注的不是改变隐私算法，而是让这种算法在有限硬件上跑得动（§2、§3）。

系统代价来自一份很大的“噪声历史”。若模型有 `m` 个可训练参数、相关带宽（band size）为 `b̂`，每轮要保存前 `b̂−1` 份、每份大小为 `m` 的噪声，并用 mixing vector 对历史做 GEMV。历史可能挤占训练所需 HBM，甚至超过 CPU DRAM；只保存随机种子再从头生成又有 `O(n²)` 的递归成本（图 2–3、§3.1）。

推荐系统（DLRM）的 embedding table 更棘手：一个 batch 只访问少量 row，所以有用训练计算随表大小增长较慢；但差分隐私仍需给零梯度 row 加噪声，噪声工作和存储接近随整张表线性增长。对于普通 dense 模型，若历史能留在 DRAM，CPU-GEMV 常可与 GPU 训练重叠；一旦溢出到 [[CXL]] 内存，搬完整历史回 CPU/GPU 才成为主要瓶颈（图 4–6）。

## 关键观察 / 隐含假设

- **观察 1：相关噪声的历史状态可能比训练本身更占内存。** 即使历史勉强放进 HBM，也会迫使训练缩小 microbatch、降低 GPU 利用率；递归重生成则随训练步数变成二次复杂度（图 2–3、§3.1）。
  - **依赖假设**：较大的 `b̂` 确实是目标隐私/效用点，而不是可直接减小的超参数。
  - **可能失效场景**：小模型、小 `b̂` 或拥有大量 HBM/TPU 时，历史完全留在 accelerator，Cocoon 的复杂度没有回报。
- **观察 2：历史放在哪一层，决定了应该在哪一层做 GEMV。** GPU-GEMV 算得快，却要跨 [[PCIe|PCIe]] 搬整段历史；CPU-GEMV 算得慢，但只需把结果送 GPU，且可与训练并行。小模型历史在 DRAM 时 CPU 开销几乎可隐藏，历史进 CXL 后两者都明显变慢（图 5–6、§3.2）。
  - **依赖假设**：GPU 训练、CPU GEMV 和 NMP GEMV 能真正并行，且没有其他作业抢占 CPU 核、PCIe 或 CXL。
  - **可能失效场景**：CPU 只得到 4%–7% 核时，论文测到 1.52–2.77 倍 slowdown；共享节点上静态 profile 很容易过时。
- **观察 3：embedding row 在两次访问之间不必每轮都物化噪声。** 只要在下一次被读取前加入数学上等价的累积噪声，就能把多份记录合成一份；频繁访问的少量热 row 反而不适合这样存（图 8–11、§4.2）。
  - **依赖假设**：预计算阶段能用相同随机种子准确重现未来 batch 顺序，并且中间梯度不会交给攻击者。
  - **可能失效场景**：adaptive sampling、在线数据、动态过滤、失败恢复或数据顺序改变都会让预计算 schedule 失效。
- **观察 4：CXL 的主要问题不是容量，而是把大矩阵反复搬出来。** 若在内存旁做 GEMV，只需传 mixing vector 和结果；原型 NMP 的 GEMV 峰值为 47.9 GB/s（图 12–13、§4.3）。
  - **依赖假设**：商用 [[Near-Memory-Processing|近内存计算]]设备提供足够容量、带宽、可靠性和多租户隔离。
- **假设 1：BandMF 的系统形态能代表其他相关噪声算法。**
  - **证据强度**：中。论文认为它们只在 mixing matrix 的推导上不同、计算上都是历史 GEMV；若未来矩阵更稀疏、可流式化或历史结构不同，结论会改变。

## 核心方法

**1. 先 profile，再按参数维切分噪声历史。** Cocoon 不沿时间维拆历史，而是把参数维切为 GPU、CPU、NMP 三段 `m_G`、`m_C`、`m_N`。它先测一个分配单位 `m_u` 在各设备上的 GEMV 延迟，再选择整数个单位，使三条并行路径中的最长者最短，同时满足各层内存容量和 GPU 接收缓冲区约束（图 7、§4.1）。

**2. 让计算靠近数据，并与训练重叠。** GPU 处理留在 HBM 的历史，CPU 处理 DRAM 中的历史，NMP 处理 CXL 内存中的历史，最后只把各段 GEMV 结果合回 GPU。以 OPT-1.3B、`b̂=64`、4×A5000 为例，模型被分成 20 个约 7100 万参数的单位：GPU 放 1 份、CPU 放 5 份、NMP 放 14 份；训练本身已使用约 72 GB HBM 和 22 GB DRAM（§4.1）。

**3. 对 embedding 提前生成未来相关噪声。** 训练开始前，空闲 GPU 按 tile 处理 embedding。一个 tile 的 `b̂−2` 行复用历史可以一直留在 HBM，系统连续计算这个 tile 的所有未来轮次，再处理下一个 tile，避免普通 GPU-GEMV 每轮把历史 spill 到 DRAM（图 8–9、§4.2）。预计算每个训练 job 都必须重做，不能跨 job 复用，否则会破坏隐私。

**4. 只在下一次访问前保存一份合并噪声。** Cocoon 用相同 sampler seed 提前知道每个 row 的下一次访问，把中间各轮噪声相加，只在访问前写入，并用压缩稀疏列（CSC）保存。频繁访问 row 的合并机会少，因此系统以访问次数阈值做 hot/cold split：Criteo 上阈值 3 把 7% row 标为热，将平均每轮噪声条目从 23.8 万降到 10.5 万，即减少 2.3 倍；热 row 继续在线 GEMV（图 10–11）。

**5. CXL-NMP 原型在内存侧执行 GEMV。** 原型板卡使用 Xilinx Versal VP1502 FPGA、CXL controller 和 DDR4，CPU 通过 CXL.io 发命令、通过 CXL.mem 访问数据。历史以 ring buffer 更新，mixing vector 预归一化并按环形位置重排；NMP 做乘加，GPU 生成新的 Gaussian noise，再更新模型和历史。多 job 命令采用先来先服务，每轮末尾 flush coherence（图 12–13、§4.3）。

**6. 隐私边界随 embedding 优化改变。** 普通 Cocoon 沿用相关噪声算法的强攻击者：攻击者可看到最终模型和所有中间梯度。预计算与合并 embedding 噪声时，论文只保证面对“能看到最终模型、看不到中间梯度”的较弱攻击者。这个变化是方法成立的前提，不只是实现细节（§4 Threat model）。

## 设计取舍

- **低 step time 换巨量持久状态。** 噪声历史被分层处理而不是消失；embedding 合并后仍占模型大小的 4.3–31.6 倍。
- **预计算换固定数据顺序。** 它把在线 GEMV 移出关键路径，却要求未来访问可预测，并增加启动时间、checkpoint 与恢复复杂度。
- **合并噪声换更弱威胁模型。** 最终模型攻击者仍被覆盖，但能观察中间梯度的攻击者不再属于 embedding 优化的保证范围。
- **异构并行换拓扑相关调优。** profile 在独占节点上有效；CPU 核、PCIe、CXL 或 NMP queue 被其他 tenant 占用时，原切分不一定平衡。
- **低成本容量换新硬件依赖。** NMP 避免大量数据移动，但依赖尚未普及的 CXL compute device；原型的 memcpy 路径还没有达到论文假设的成熟速度。
- **适用边界。** 大模型、大 `b̂`、历史溢出 HBM/DRAM且训练计算不足以掩盖噪声开销时最合适；小模型、小 `b̂`、大 batch 或高配 GPU 集群收益有限。

## 实验设置

- 主机主要为双 Xeon Gold 6330、256 GB DRAM 和 8×RTX A5000；补充实验用双 EPYC 7763、1 TB DRAM 和 8×A100 80 GB。DLRM 通常单 GPU、无 NMP；语言模型通常 4 GPU、带 NMP（§5.1）。
- DLRM 使用 Criteo Kaggle 与合成 Zipf 数据；其他模型用 ImageNet 大小的 dummy data 或 E2E 数据，模型覆盖 ResNet、ViT、GPT2、OPT 和 DLRM。batch 为视觉/语言 1024、DLRM 65536，`b̂` 扫描 2–256。
- 基线是把外置历史拉回 GPU 做 GPU-GEMV，或在 CPU 做 CPU-GEMV，并以两者中更快者报告主要 speedup；训练实现基于 Amazon fastDP、[[PyTorch|PyTorch]] 2.4、MKL/OpenBLAS。
- NMP 原型实测 memcpy 只有 5–7 GB/s。涉及 NMP 的端到端实验把这部分分析缩放到另一块同类内部 CXL 内存实测的 22 GB/s，并运行独立进程把估算开销加进训练；GEMV 与其他开销是真测，但整体不是原型原速的直接端到端结果（§5.1）。

## 实验与结果

- **问题规模**：DLRM 在 `b̂=8/16` 时，即使选 GPU-GEMV 与 CPU-GEMV 中较好的一个，相对独立噪声 [[Data-Parallelism|DP]]-SGD 仍慢 2.03–8.62/6.28–14.49 倍。普通模型若历史完全在 DRAM，GPU-GEMV 只慢 0.6%–18.2%、CPU-GEMV 几乎可隐藏；GPT2-L 把 63% 历史放 CXL 后则慢 2.83–3.75 倍（图 4–6、§3.2）。
- **DLRM 端到端**：A5000 上，非平凡的 `b̂` 大于 8 配置相对较好基线快 2.46–4.87 倍；A100 上更大 DLRM 的非平凡配置快 2.33–10.82 倍。`b̂` 为 2–4、历史全在 GPU 时，Cocoon 的 embedding 优化反而是额外负担，系统应关闭它（图 14、图 16、§5.2）。
- **规模敏感性与内存**：在 `b̂=32` 下，模型加倍使 speedup 从 3.51 倍增到 6.27–6.35 倍，减半后只剩 1.37 倍；batch 从 64K 降到 32K 时升到 4.79 倍，增到 128K 时降到 2.57 倍。1800 轮训练中，合并噪声占模型的 4.3–31.6 倍，而未合并的最坏情况是 1800 倍（图 15、图 17、§5.2–5.3）。
- **NMP 端到端**：当每个配置有超过 200 GB 历史置于 CXL 时，Cocoon 相对较好基线快 1.23–2.32 倍；OPT-1.3B 增大 `b̂` 后最高快 2.26 倍。这里使用真实 NMP GEMV 加 22 GB/s memcpy 模型；图 19 的 `b̂=128` 还因容量不足而是未来大容量设备的分析投影（图 18–19、§5.4）。
- **成本与功耗估算**：GPT2-XL、`b̂=64`、约 413 GB 历史下，表 1 估算 GPU-only/CPU-GEMV/Cocoon 分别需 10/3/1+NMP 个硬件单元，成本约 11.3/3.39/1.83 万美元，峰值功耗 11.6/3.5/1.2 kW；但 Cocoon 归一化吞吐只有 0.13，CPU 方案为 0.33、GPU 为 1，所以 Cocoon 与 CPU 的单位成本/功耗效率接近，而不是全面胜出。
- **未实测边界**：当前 NMP 吞吐不足以帮助低迭代延迟 DLRM；论文所说额外 2.4 倍来自假设 TB/s 内部带宽的分析投影。[[LLM|LLM]] 实验最大约 OPT-1.3B/GPT2-XL、4 GPU，未做多节点训练（§5.5、§6.1）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 相关噪声在经济型硬件上会形成容量和数据移动瓶颈 | 图 2–6：较好基线最高慢 14.49 倍，历史进 CXL 后慢 2.83–3.91 倍 | BandMF、A5000、DLRM 与最多 1.3B 参数语言模型 | 强 |
| embedding 预计算与合并能显著降低关键路径 | 图 14–17：非平凡配置快 2.33–10.82 倍，状态为模型的 4.3–31.6 倍 | 固定 sampler、Criteo/合成访问、最终模型攻击者 | 强 |
| 在 CXL 内存侧做 GEMV 能减少外移数据 | 图 18：相对较好基线快 1.23–2.32 倍 | 真实 47.9 GB/s GEMV，memcpy 按 22 GB/s 分析缩放 | 中到强 |
| Cocoon 能保持原相关噪声算法的全部攻击者保证 | §4：embedding 优化明确排除能看到中间梯度的攻击者 | 非 embedding 路径保持原模型；embedding 路径威胁模型变弱 | 弱 |
| NMP 对 DLRM 和更大 band 仍会继续加速 | §5.4–5.5：2.4 倍与部分 `b̂=128` 点为分析投影 | 假想 TB/s 或更大容量设备 | 弱 |

## 批判性分析

### 论证链条

论文先把相关噪声拆成容量、GEMV 和数据移动三个成本，再分别用跨层切分、embedding 合并与 NMP 回应，且小 `b̂`、大 batch、DRAM 可容纳历史时主动报告无收益，边界讲得较清楚。最重要的概念是把“隐私算法历史”看成需要分层、恢复和保护的系统状态。不过，摘要的 1.23–10.82 倍把直接 DLRM 实验与部分模拟的 NMP 实验合并成一个范围，阅读时必须拆开。

### 假设压力测试

embedding 路径依赖完整、确定的未来访问序列。真实训练中的过滤坏样本、动态采样、弹性 worker、数据重分片或 crash/restart 都可能改变顺序；若噪声与 sampler 状态没有原子恢复，后果可能是隐私保证失效，而不只是速度下降。若攻击者能看到中间梯度，或者能观察 CSC 中哪些 row 何时有噪声，论文的较弱 threat model 也不覆盖它。

### 实验可信度

A5000/A100、真实 CXL-NMP 板、DLRM/语言模型、`b̂`、模型、batch、skew 和内存分解提供了很强的内部证据。外部有效性较弱：NMP memcpy 被缩放到另一设备的 22 GB/s，成本/功耗来自相似设备的公开估值，`b̂=128` 容量点和 DLRM NMP 是投影；没有隐私预算 `ε`、模型 accuracy/utility 或数学等价的端到端复现实验。单机最大 4 GPU 的语言模型也不足以验证现代多节点 foundation model。

### 系统性缺陷

噪声历史、sampler RNG、预计算 CSC、ring-buffer 位置和 privacy accountant 都是必须一致恢复的安全关键状态，论文没有给 checkpoint protocol 或故障注入。NMP 使用先来先服务队列，没有 tenant 隔离、QoS、ECC/计算错误检测或错误噪声的 fail-stop 机制。即使合并后 4.3–31.6 倍模型大小的状态仍很大，也可能高于某些 `b̂=16/32` 基线；预计算启动延迟和重复 job 成本没有作为独立指标报告。

## 局限与后续工作

- **局限 1**：embedding 优化只承诺面对看不到中间梯度的攻击者，保证范围弱于普通相关噪声训练。
- **局限 2**：NMP 端到端时间部分依赖 22 GB/s memcpy 模型，成本、功耗、更大容量和 DLRM NMP 也含估算或投影。
- **局限 3**：预计算要求固定 sampler seed 和未来访问顺序，不支持动态/在线数据管线。
- **局限 4**：最大语言模型约 1.3B、4 GPU，未验证多节点通信、弹性训练和现代大模型 optimizer sharding。
- **后续工作 1**：设计原子 checkpoint，把 sampler RNG、privacy accountant、ring history 和 CSC 版本一起提交；用 crash injection 验证恢复后的噪声序列与无故障运行一致。
- **后续工作 2**：在相同 `ε`、相同 clipping 与相同随机种子下，对原 BandMF 和 Cocoon 比较逐步参数、最终 accuracy、membership inference 与中间梯度可见两种攻击者。
- **后续工作 3**：把 noise sharding 与 [[FSDP]]/[[ZeRO]] 放到 8–64 GPU 多节点上共同规划，分别报告网络、HBM、DRAM、CXL、预计算和 step time。
- **后续工作 4**：在 NMP 上加入 per-tenant queue、带宽配额、ECC 与结果校验，注入 bit flip、command timeout 和拥塞，测隐私安全回退与 P99 step time。

## 相关

- **相关概念**：[[Differential-Privacy]]、[[DP-SGD]]、[[CXL]]、[[Near-Memory-Processing]]、[[Embedding-Table]]
- **同类系统**：[[BandMF]]、[[fastDP]]
- **同会议**：[[OSDI-2026]]
