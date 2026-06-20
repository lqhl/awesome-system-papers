---
type: paper
name: Libra
full_title: "Libra: Effective yet Efficient Load Balancing for Large-Scale MoE Inference"
authors: [Jaehoon Yang, Yushin Kim, Seokwon Moon, Yeonhong Park, Jae W. Lee]
venue: ICLR
year: 2026
tags: [moe, llm-inference, load-balancing, expert-parallelism, prefill]
source_pdf: "[[iclr26-yang-libra.pdf]]"
source_md: "[[iclr26-yang-libra]]"
---

# Libra: Effective yet Efficient Load Balancing for Large-Scale MoE Inference (ICLR 2026)

> **一句话总结**：Libra 的关键判断是现代 [[MoE]] 为了 expert specialization 放松训练期均衡后，prefill 阶段的 expert load imbalance 会变成 [[Expert-Parallelism]] 的主要 straggler；它用相邻 Transformer block hidden state 变化缓慢这一观察提前预测下一层 expert 激活，再用 Two-Stage Locality-Aware Execution 把 CPU token sharding 和 expert replication planning 藏进 `MoE_local` / `MoE_remote` 的执行窗口，在 8x H200 上对 Qwen3MoE 和 GLM-4.5 的 prefill throughput 最高提升 19.2%，并把动态 workload 下的 imbalance ratio 维持在接近 1.0。

## 问题与动机

这篇论文处理的是大规模 MoE 推理里的 expert load imbalance。MoE 层通过 gating network 为每个 token 选择少量 expert；当 serving 系统用 [[Expert-Parallelism]] 把 expert 分散到多张 GPU 上时，某些 hot expert 会让承载它们的 GPU 成为 straggler。同步 MoE 层要等最慢 GPU 完成，因而少量热门 expert 足以拉低整层吞吐和尾部延迟。

作者强调这个问题在新一代 MoE 上更尖锐：Qwen3MoE、GLM-4.5、DeepSeek-V3 等模型为了更强 expert specialization，不再依赖细粒度 auxiliary load-balancing loss 去强行平均 expert 使用率。训练目标的改变提升模型能力，但 inference 阶段会把 expert 分布的偏斜直接暴露给系统层。

已有 system-level 方案大多围绕 hot expert replication 和 token sharding。EPLB 基于历史 profiling 周期性复制 hot expert，简单但跟不上每个 request 或 dataset 的即时变化；Lina 通过历史 expert-selection-path 查表预测下一层，能把 replication 搬出关键路径，但预测精度在论文实验中很低；HarMoEny 等精确 routing 后决策的方法均衡效果好，却把复杂 planning 和 sharding 算法放进当前 MoE 层的关键路径。Libra 的目标是同时要这两件事：接近精确均衡的效果，以及几乎不暴露在关键路径上的机制开销。

## 关键观察 / 隐含假设

- **观察 1**：现代大 MoE 的 expert load imbalance 与模型能力追求绑定，而不是单纯实现瑕疵。
  - **证据**：论文用 Figure 1 比较 Qwen2MoE vs Qwen3MoE、DeepSeek-V2 vs DeepSeek-V3 的 layer-wise imbalance ratio；较新的模型在许多层出现 1.5-2.7 左右的 imbalance，而旧模型大多更接近 1.0。
  - **依赖假设**：未来高性能 MoE 仍会继续弱化训练期均衡约束，让 expert specialization 优先于推理均匀性。
  - **可能失效场景**：如果训练方法能同时保持 specialization 和严格 per-layer / per-request load balance，或者模型架构转向不需要 EP 的 dense / shared-expert 形式，Libra 解决的问题会变窄。

- **观察 2**：相邻 Transformer block 的 hidden states 演化慢，可以用当前 hidden states 提前运行下一层 gate，预测下一层 expert 激活。
  - **证据**：Table 1 显示 Libra predictor 在 Qwen3MoE 上达到 86.5-91.7% accuracy，在 GLM-4.5 上达到 72.7-79.6%；Lina lookup predictor 只有 37.5-47.3% 和 11.2-12.7%。
  - **依赖假设**：相邻层 representation 稳定性足以迁移到 router decision，且提前执行 gate 的计算/同步成本能被当前层 MoE 计算隐藏。
  - **可能失效场景**：router 对微小 hidden-state 变化高度敏感、模型使用更强 layer-wise specialization、routing 引入噪声或动态约束时，lookahead predictor 的精度可能下降。

- **观察 3**：token sharding 的复杂均衡逻辑不一定必须在 GPU critical path 上完成。
  - **证据**：Libra 把 MoE 拆成 `MoE_local` 和 `MoE_remote`，让 CPU token sharding、metadata transfer、planning 与本地 MoE 计算重叠；Table 2 中 Libra 虽有 0.57 token sharding、0.26 replication planning、metadata transfer 等开销，但标注为 hidden，整层 total 为 9.07，低于 Lina 11.33 和 SGLang 13.61。
  - **依赖假设**：每层有足够多 local token 形成遮蔽窗口，CPU 端 sharding 算法和 GPU/CPU metadata 往返不会超过该窗口。
  - **可能失效场景**：短序列、小 batch、locality 不足、CPU 忙、PCIe/NVLink/NVSwitch 拓扑变化或跨节点通信都会压缩这个隐藏窗口。

- **假设 1**：prefill 是值得单独优化的主战场。
  - **证据强度**：中。论文采用 prefill-decode disaggregation，只评估 prefill throughput 和 TTFT；Appendix D 说明长上下文、batch 较大时 TTFT 降幅更明显，但 decode 阶段并不是 Libra 的主要对象。

- **假设 2**：单机 8x H200 + NVSwitch 上观察到的 overlap 和 AllGather 代价可以代表重要部署。
  - **证据强度**：中偏弱。硬件很强，P2P bandwidth 高，AllGather 增加通信量但在该环境中影响小；跨节点 EP、较弱互联或异构 GPU 没有被直接覆盖。

## 核心方法

Libra 的第一步是保持 proactive replication 的形态：在 Block i 处理当前 MoE 时，为 Block i+1 复制 hot experts。它不等 Block i+1 的真实 routing 结果，而是提前用当前 block 的 hidden states 运行下一层 gate，得到下一层 top-k expert 的预测。这个 lookahead predictor 继承了 Lina “提前准备下一层”的优点，但用 runtime hidden states 替代离线 lookup table，因此能适应 dataset 和 request 变化。

expert replication planning 不是只复制全局最热 expert。Libra 把每个 GPU 可额外容纳的 expert 数量记为 N，并用超参 alpha 划分两类目标：第一阶段为每个 GPU 复制本地 token 最常请求的 remote expert，扩大 `MoE_local` 窗口；第二阶段再从最重载 GPU 上选 hottest expert，复制到还没满额且负载最低的 GPU 上，为后续 token sharding 提供可选 replica。这个设计直接回应观察 3：复制决策不仅服务均衡，也服务“创造可隐藏开销的本地计算窗口”。

执行流的核心是 Two-Stage Locality-Aware Execution。普通 MoE load balancing 往往是 gate 后先做 token sharding，再 dispatch token，再做 MoE compute；Libra 则在 gate 后立即启动 `MoE_local`，同时 CPU 端运行 token sharding，通信层做 dispatch，GPU 端随后执行依赖 sharding 结果的 `MoE_remote`。因此复杂 sharding 的收益接近 HarMoEny，但它的成本尽量不落在 GPU MoE 的可见路径上。

token sharding 使用类似 HarMoEny 的 iterative greedy strategy，但只作用于 remote tokens。算法先计算每张 GPU 的 total load，如果某张 GPU 超过目标负载，就选最重载 GPU 上贡献最大的 remote expert，再找已经持有该 expert replica 且当前负载最低的 GPU，把一定数量 token 转移过去。每次转移后重新评估全局状态，直到负载接近平衡或没有可行迁移。

实现上，Libra 基于 [[SGLang]] v0.4.10。planning 和 token sharding 用 Cython 做成 SGLang 原生模块；hot expert replication 通过 PyTorch SymmetricMemory 做 copy-engine P2P transfer；even/odd layer 使用 double buffer，把当前层 Grouped-GEMM 和下一层 expert loading pipeline 起来。Dispatch 选择 AllGather 而非 All2All：这增加了原始通信量，但在论文的 NVSwitch 单机环境下让 dispatch 不必等待 sharding 决策，从而更容易被 overlap 掉。

## 设计取舍

- **取舍 1**：为了把 sharding 从关键路径移走，Libra 用 AllGather 替代 All2All，牺牲通信量换执行依赖更简单。在 8x H200 NVSwitch 上这个选择成立；在跨节点或较弱互联中，它可能从“被隐藏的小代价”变成主瓶颈。
- **取舍 2**：为了提高预测精度，Libra 额外执行下一层 gate。论文显示这个 predict 成本很小并可重叠，但该结论依赖 router/gate 成本远小于 MoE compute，且当前层有足够 work 可遮蔽。
- **取舍 3**：locality-aware replication 把一部分 replica 配额用于扩大本地窗口，而不是全给全局 load balance。这让 overhead hiding 更稳，但 alpha 选择会影响 locality 和 balance 的边界；论文采用 N=8、alpha=0.5，没有系统展示不同 memory budget 下的完整敏感性。
- **边界条件**：Libra 在长上下文、大 batch、prefill-heavy、单机高速互联、load imbalance 强的场景最自然；在短序列、小 batch、decode-heavy、跨节点 EP、CPU 侧资源紧张或 memory budget 很小的部署里会变脆。

## 实验与结果

- **主结果**：在 8x NVIDIA H200-SXM5、Qwen3MoE 235B 和 GLM-4.5 355B 上，Libra 相比 SGLang / EPLB / Lina 都有最高 prefill throughput，最高提升 19.2%。
- **基线设置偏友好**：EPLB 和 Lina 都被允许使用与 evaluation 相同的数据集做 profiling / lookup table；EPLB 静态复制每层 8 个 hot experts，Lina 和 Libra 均允许每 GPU 额外持有 8 个 expert，Libra 设 N=8、alpha=0.5。
- **动态 workload**：Figure 9 的 mixed-dataset 负载下，SGLang 和 Lina 的 throughput 会随 imbalance ratio spike 明显波动；Libra 将 imbalance ratio 长期压在约 1.0 附近，吞吐曲线也更平稳。
- **预测精度**：Qwen3MoE 上 Libra 为 86.5-91.7%，Lina 为 37.5-47.3%；GLM-4.5 上 Libra 为 72.7-79.6%，Lina 为 11.2-12.7%。GLM-4.5 的结果尤其说明离线 expert-selection-path 查表泛化很差。
- **MoE layer breakdown**：Qwen3MoE、seq=1024、batch=32 下，Libra 总 MoE layer latency 为 9.07，Lina 为 11.33，SGLang 为 13.61；Libra 的 local/remote MoE compute 为 2.77 + 4.55，并把 metadata transfer、token sharding、部分 planning 标为 hidden。
- **端到端 TTFT**：Appendix D 显示 Libra 更适合长上下文和较大 batch。短序列如 1K tokens 时收益可能接近或略低于 baseline，因为 `MoE_local` 窗口不足以完全隐藏 CPU 侧开销；长输入下 Qwen3MoE TTFT 最高降低 27%，GLM-4.5 最高降低 12.7%。

## Critical Analysis

### 论证链条

论文的主链条基本闭合：新 MoE 训练策略导致 inference imbalance 更严重；历史或 lookup-based replication 无法捕捉动态请求；精确 sharding 会把均衡决策放入关键路径；Libra 用 lookahead gate 提高预测质量，用 locality-aware execution 隐藏复杂 sharding 的成本。Figure 9 也很好地把“动态 workload 下稳定性”与 imbalance ratio 连接起来，不只是报告平均吞吐。

比较容易被外推的是“virtually zero overhead”。Table 2 证明了在指定 Qwen3MoE、seq=1024、batch=32、8x H200 上 Libra 的多个额外步骤被 overlap，但这更准确地说是“在足够 local MoE 窗口下可隐藏”，而不是机制本身没有成本。Appendix D 其实已经显示短输入时窗口不足会削弱收益。

### 假设压力测试

最关键压力来自 workload 和模型。Libra 需要两个条件同时成立：routing 结果足够不均衡，值得做 replication/sharding；相邻层 hidden states 又足够稳定，能提前预测下一层 hot expert。如果未来 MoE router 更随机、更稀疏、更受 task-specific prompt 影响，预测精度可能掉到 Lina 之外但仍不足以支撑 near-optimal balance。

第二个压力来自部署拓扑。论文环境是单机 8x H200 + NVSwitch，AllGather 的“多发 token”成本很容易被高速互联和 local compute 吞掉。跨节点 expert parallelism 中，AllGather 的带宽放大会更明显，expert P2P copy 也可能跨越网络边界；这时 Libra 可能需要回到 All2All 或分层通信，执行流就不再这么干净。

第三个压力来自 SLO。论文关注 prefill throughput 和 TTFT，对 decode 阶段、continuous batching、multi-tenant fairness、tail latency、failure recovery 讨论较少。如果 serving 系统的瓶颈是 decode memory bandwidth、KV cache 管理或 admission control，Libra 的改善会被其他模块稀释。

### 实验可信度

实验选择有几个强点。模型是 Qwen3MoE 235B 和 GLM-4.5 355B 这种近现代大 MoE；数据覆盖 BookCorpus、Codeforces、DeepSeek-Prover、FineWeb、GSM8K、HellaSwag、HumanEvalPlus、LMSYS-Chat-1M；baseline 还拿到偏有利的 profiling 条件，因此 Libra 的优势不是因为基线完全缺信息。

但仍有边界。Lina 是作者自研复现，因为没有 public implementation；EPLB 静态设置和实际生产重配置策略可能不同；HarMoEny 只在动机里作为强效果/高开销参照，没有完整系统级结果并列。更重要的是，实验没有跨节点、多机、异构 GPU、不同互联带宽或多租户 trace，因而“large-scale”主要是大模型单机 serving，而不是数据中心规模。

### 系统性缺陷

Libra 增加了 serving runtime 的状态和调度复杂度：每层要维护 predicted expert IDs、expert placement map、double buffers、metadata transfer、CPU sharding worker 和 GPU compute/communication overlap。论文说明这些模块能隐藏延迟，但没有深入讨论错误观测、调试、回退路径或生产可观测性。

资源隔离也是未充分讨论的风险。动态复制 expert 会占用额外 HBM，CPU token sharding 会占用 host compute，AllGather 会增加通信量；如果多个 model replica 或 tenants 共用节点，Libra 的“隐藏成本”可能从局部 latency 变成全局资源干扰。

正确性层面，Libra 不改变 routing 语义，只改变 expert replica 和 token assignment，因此模型输出应保持等价。论文没有重点讨论极端情况下的 replica consistency、copy failure、buffer reuse bug、或者与 quantization / kernel fusion / speculative serving 组合时的工程风险。

## 局限与 Future Work

- **局限 1**：评估集中在 prefill-decode disaggregation 下的 prefill 阶段；decode-heavy 服务、mixed prefill/decode 调度和 continuous batching 下的收益边界没有被系统测量。
- **局限 2**：所有主要实验在单机 8x H200 + NVSwitch 上完成；跨节点 expert parallelism、PCIe-only 机器、H100/A100 或异构 GPU 上 AllGather 与 P2P replication 是否仍可隐藏未知。
- **局限 3**：lookahead predictor 的失败模式没有展开。论文报告 top-k accuracy，但没有给出预测错误如何影响 imbalance ratio、复制浪费、HBM 占用和尾延迟。
- **Future work 1**：做 topology-aware Libra：在单机 NVSwitch、跨节点 InfiniBand、PCIe-only 三类拓扑上比较 AllGather、All2All、hierarchical dispatch 的临界点，输出可复现的带宽/窗口模型。
- **Future work 2**：把 predictor accuracy 与系统收益解耦测量：人为注入不同错误率和偏差类型，测 throughput、imbalance ratio、replica waste、TTFT tail，判断 Libra 对 router drift 的鲁棒性。
- **Future work 3**：扩展到 production-like scheduler：在 continuous batching、多租户、prefix cache / [[KV-Cache]] pressure、prefill/decode 混部下测 Libra 的资源干扰和 SLO tradeoff。
- **Future work 4**：把 replication planning 从固定 N/alpha 变成在线控制问题，用当前 HBM headroom、CPU load、communication queue depth 和 observed local-window length 动态调参。

## 相关

- **相关概念**：[[MoE]]、[[Expert-Parallelism]]、[[Disaggregation]]、[[Speculative-Decoding]]、[[KV-Cache]]
- **同类系统**：[[SGLang]]、[[Lina]]、[[EPLB]]、[[HarMoEny]]
- **同会议**：[[ICLR-2026]]
- **相关论文**：[[SGLang-NeurIPS24]]、[[PrefillOnly-SOSP25]]、[[MoE-Serving-Tax-MLSys26]]、[[LatencyOptimal-MoELB-INET4AI25]]、[[fabric-lib-MLSys26]]、[[MoE-nD-arXiv26]]
