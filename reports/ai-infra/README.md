# AI Infra 论文索引

> 共 3 篇论文 | 最后更新: 2026-04-02

---

## 论文列表

#### [[2510.27656v1|pplx-garden: RDMA Point-to-Point Communication for LLM Systems]]
- **作者**：Nandor Licker, Kevin Hu, Vladimir Zaytsev, Lequn Chen（Perplexity AI）
- **会议/来源**：arXiv 2025
- **要解决的问题**：现有 LLM 框架依赖 collective 通信（NCCL），无法支持 disaggregated inference、MoE routing 等新范式所需的灵活 P2P 通信，且不同云厂商 RDMA 实现（ConnectX RC vs EFA SRD）导致厂商锁定。
- **核心贡献**：提出 TransferEngine，以"可靠无序交付"为最大公约数构建跨硬件 RDMA P2P 通信库，在 MoE token dispatch、KV cache transfer、RL weight sync 三大场景中验证有效性。
- **关键发现/观点**：P2P 通信范式比 collective 更适合新兴 LLM 工作负载——动态成员管理、异步操作、per-token scatter 等特性是 collective 库无法提供的。

#### [[16200_Libra_Effective_yet_Effi|Libra: Effective yet Efficient Load Balancing for Large-Scale MoE Inference]]
- **作者**：Jaehoon Yang et al.（Seoul National University）
- **会议/来源**：ICLR 2026
- **要解决的问题**：MoE 推理时 expert 负载不均导致 straggler effect，现有方案在 effectiveness（负载均衡效果）和 efficiency（均衡过程开销）之间存在矛盾。
- **核心贡献**：通过投机执行下一层 gating function 实现 70-80% 预测精度，结合 Two-Stage Locality-Aware Execution 将所有均衡开销隐藏在 MoE 计算中，在 8× H200 上实现 19.2% prefill throughput 提升。
- **关键发现/观点**：Transformer hidden states 在相邻层间缓慢演变，可用于投机预测 expert 激活；将 MoE 计算按 token locality 拆分为 local/remote 两阶段，可创造并行窗口隐藏负载均衡开销。

#### [[3769695.3771675|Latency-Optimal Load Balancing for Distributed MoE Inference]]
- **作者**：Venkata Pavan Kumar Miriyala et al.（AMD）
- **会议/来源**：INET4AI '25 (CoNEXT Workshop), December 2025
- **要解决的问题**：EPLB 等现有负载均衡算法只优化负载均衡效果，忽视均衡过程本身的数据搬运开销（占总 LB 延迟约 50%），导致 LB 的代价远超收益。
- **核心贡献**：提出联合优化负载均衡和搬运代价的 ILP 公式化及实用 heuristic 算法，expert 搬运量降低 57%，支持 2x 更频繁的 LB，MoE 延迟降低 12.5%。
- **关键发现/观点**：负载均衡的数据搬运开销是被忽视的主要瓶颈——EPLB 单次搬运 13036 个 expert，引入的延迟是其收益的 ~10 倍。联合优化搬运代价后，可以以更高频率执行 LB 并适应快速变化的 workload。

---

## 主题综述

AI 基础设施（AI-Infra）方向聚焦大模型训练和推理的系统级优化。当前收录的论文集中在 MoE 推理场景的两个关键挑战：

**通信层**：pplx-garden 代表了从 collective 通信向 P2P 通信的范式转移。MoE 的稀疏 routing 天然适合 P2P 模式——每个 token 直接发送给目标 expert，无需 all-to-all 的对称缓冲区。这一通信层的变革为上层调度策略（动态 expert placement、弹性扩缩）提供了基础能力。

**负载均衡**：Libra 和 INET4AI 分别从不同角度优化 MoE 推理时的 expert 负载不均。Libra 聚焦 prefill 阶段，通过投机执行 + locality-aware 两阶段执行实现高效均衡；INET4AI 聚焦均衡过程本身的搬运代价优化。两者互补：Libra 回答 "复制什么到哪里"，INET4AI 回答 "如何最小化搬运代价"。但两者都局限于单节点、prefill 场景，**decode 阶段 + 多节点**的负载均衡仍是开放问题。
