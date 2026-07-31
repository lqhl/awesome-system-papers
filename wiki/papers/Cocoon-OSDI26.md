---
type: paper
name: Cocoon
full_title: "Cocoon: A System Architecture for Differentially Private Training with Correlated Noises"
authors: [Donghwan Kim, Xin Gu, Jinho Baek, Timothy Lo, Younghoon Min, Kwangsik Shin, Jongryool Kim, Jongse Park, Kiwan Maeng]
venue: OSDI
year: 2026
tags: [differential-privacy, ml-training, cxl, near-memory-processing, embeddings]
source_pdf: "[[osdi26-kim-donghwan.pdf]]"
source_md: "[[osdi26-kim-donghwan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 相关噪声差分隐私训练的系统架构（OSDI 2026）

> **原题**：Cocoon: A System Architecture for Differentially Private Training with Correlated Noises

> **一句话总结**：Cocoon 发现 correlated-noise DP 虽提高模型精度，却要保留 `band_size−1` 份完整模型大小的 noise history，在经济型 GPU 集群上可慢 14.49 倍；它按 CPU/GPU/CXL 分片计算历史，对 sparse embedding 预计算、tiling/coalescing，并用 FPGA CXL-NMP 原型执行 GEMV，端到端加速 1.23–10.82 倍。

## 问题与动机

DP-SGD 每 iteration 加独立 Gaussian noise，累积后伤害 accuracy。新机制让后续噪声与过去 `b̂−1` 份 noise相关并部分抵消，但生成第`t`份 noise需对 `(b̂−1)×m` history做 GEMV；每份 history 与全部 trainable parameter 同大。论文指出以1024 TPU等资源充足设置评估，会掩盖中小组织实际遇到的 capacity/data-movement bottleneck。

DLRM embedding尤其反常：每 iteration只访问少数 row，训练时间随table size次线性增长，但privacy仍要求所有 zero-gradient row加入noise，因此noise work比有用training更接近线性。大LLM则可能让history达到数百GB/数TB，必须越过[[PCIe|PCIe]]/CXL。

## 关键观察 / 隐含假设

- **观察 1：noise history 可超过GPU总HBM甚至CPU DRAM。** baseline最佳方案在`b̂=8/16`仍慢2.03–8.62/6.28–14.49倍（图2–6）。
  - **依赖假设**：选择较大band确有accuracy/privacy价值；若`b̂`小且history入HBM，Cocoon收益消失。
- **观察 2：embedding row在再次访问前，无需逐iteration materialize noise。** 可把多次noise合并，在next access前一次加入（图10）。
  - **依赖假设**：sampler可用相同seed预知完整access schedule，coalesced noise数学上等价且不改变[[Data-Parallelism|DP]] accountant。
  - **可能失效场景**：adaptive sampling、online data、dynamic batch或failure后随机序列偏移。
- **观察 3：CXL bottleneck是把history搬回CPU/GPU做GEMV，而非capacity本身。** NMP在memory side做GEMV，只传mixing vector/result（图12–13）。
  - **依赖假设**：未来商用CXL-NMP有足够GEMV throughput、capacity和multi-tenant isolation。
- **假设 1：BandMF的compute pattern代表其他correlated-noise mechanism。**
  - **证据强度**：中；mixing matrix不同但都是history GEMV，稀疏/online变体可能不完全等价。

## 核心方法

Cocoon 按GPU HBM、CPU DRAM和CXL memory的capacity/bandwidth把noise-history row/tile分布，GPU/CPU/NMP并行GEMV并与training overlap，目标是让最慢device不延长critical path。history以ring buffer更新，mixing vector预先reorder/normalize（图13）。

对embedding，Cocoon离线按tile预计算未来noise：一个tile的`b̂−2`可复用history始终留在GPU，连续产生该tile所有future iteration结果，避免每轮spill（图9）。coalescing只保存row两次access之间noise的sum，以CSC sparse format存储；hot/cold splitting对频繁row继续在线GEMV，稀疏row使用预计算，平衡storage与compute（图10–11）。

NMP原型是Xilinx Versal FPGA CXL card+DDR4，controller内MAC/ACC engine直接对resident history做GEMV。CPU发command/mixing vector，NMP回result，GPU并行生成fresh Gaussian、更新model/history。framework基于PyTorch。

## 设计取舍

- **预计算换未来access可预测性与storage**：coalesced history仍为model的4.3–31.6倍，且依赖deterministic sampler。
- **异构并行换topology tuning**：split比例需按GPU/CPU/CXL bandwidth、model和batch人工调，设备竞争会改变最优点。
- **NMP capacity/cost换新硬件依赖**：真实FPGA原型支持claim，但尚非通用商用品，DLRM更因throughput不足未获益。
- **DP accuracy换system cost**：Cocoon不改变privacy/accuracy mechanism，只降低实现overhead；若independent noise已足够则无采用理由。
- **边界条件**：large `b̂`、大embedding/[[LLM|LLM]]、少GPU和history溢出HBM时最好；大batch或小model training主导时收益下降。

## 实验与结果

- 8×A5000/双Xeon/256GB characterization中，history offload后最佳CPU/GPU baseline在`b̂=16`慢6.28–14.49倍；小ViT/OPT history入DRAM时CPU-GEMV几乎可隐藏，明确了适用边界（图3–6）。
- DLRM、`b̂`大于8时，Cocoon较最佳baseline快2.46–4.87倍；A100非平凡配置下为2.33–10.82倍（图14–16）。model加倍时`b̂=32` speedup由3.51升至6.27–6.35倍；batch增大则降至2.57倍（图15）。
- coalesced noise在1800 iterations下仅model size的4.3–31.6倍，而未优化最坏为1800倍；其overhead不随`b̂`增长（图17）。
- GPT2-L/XL、OPT-1.3B且超过200GB history置于CXL时，真实NMP原型较最佳baseline快1.23–2.32倍；OPT-1.3B大band最高2.26倍（图18–19）。
- NMP对DLRM因prototype GEMV throughput不足没有实测收益；额外2.4倍仅基于TB/s future device分析projection（§5.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| correlated noise在经济型硬件有严重system overhead | 图2–6：最佳baseline最高慢14.49倍 | BandMF、A5000、所选DLRM/LLM | 强 |
| embedding预计算/coalescing可大幅加速 | 图14–17：2.33–10.82倍、history 4.3–31.6×model | deterministic Criteo/synthetic access | 强 |
| memory-side GEMV能消除CXL transfer bottleneck | 图18：真实FPGA-NMP加速1.23–2.32倍 | LLM、prototype、超过200GB offload | 强 |
| 方法适用于未来DLRM NMP | §5.5：projection额外2.4倍 | 假设TB/s device，非实测 | 弱 |

## 批判性分析

### 论证链条

论文先刻画capacity/compute，再分别针对sparse embedding和dense large model给algorithm/hardware路径，boundary说得很清楚；小model/batch大时承认无收益。核心新意是把privacy mechanism的“历史状态”视为跨memory tier的系统data structure，而不是普通optimizer tensor。

### 假设压力测试

adaptive DP训练可能根据loss、privacy budget或user participation改变batch/order，破坏预计算schedule。checkpoint/restart必须同步sampler、coalesced noise和ring history，否则可能破坏privacy guarantee而非只影响performance。multi-GPU distributed optimizer/sharding与NMP command queue竞争也未充分覆盖。

### 实验可信度

真实A5000/A100、真实FPGA CXL-NMP、DLRM/LLM、model/batch/skew/band sensitivity与breakdown证据很强。大模型规模到约1.3B且多结果依赖特定prototype；成本/功耗用相似设备估值并刻意有利baseline，不是实测TCO。accuracy/privacy equivalence主要依赖数学机制，未展示end-to-end utility curve。

### 系统性缺陷

系统需管理超大privacy-critical history、checkpoint和device failure；NMP engine/driver错误可能悄然生成错误noise并使DP保证失效。FPGA first-come-first-served queue缺少tenant isolation/QoS。coalesced CSC本身可泄露embedding access pattern，若threat model包含infrastructure observer需审查。

## 局限与后续工作

- **局限 1**：precompute依赖deterministic future sampling，dynamic/online训练未支持。
- **局限 2**：NMP仍是FPGA原型，DLRM收益与更大band部分为projection。
- **后续工作 1**：设计可恢复的noise-history checkpoint protocol，以crash injection后privacy accountant一致性和bitwise noise replay验证。
- **后续工作 2**：在[[FSDP|FSDP]]/[[ZeRO|ZeRO]]式multi-node LLM上共同优化parameter/noise sharding，报告network、HBM、CXL与step-time breakdown。
- **后续工作 3**：对adaptive sampler开发windowed/on-demand coalescing，用相同epsilon/accuracy下的throughput与peak memory比较。

## 相关

- **相关概念**：[[Differential-Privacy]]、[[DP-SGD]]、[[CXL]]、[[Near-Memory-Processing]]、[[Embedding-Table]]
- **同类系统**：[[PyTorch]]、[[BandMF]]
- **同会议**：[[OSDI-2026]]
