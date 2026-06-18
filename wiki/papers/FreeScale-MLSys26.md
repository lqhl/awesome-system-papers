---
type: paper
name: FreeScale
full_title: "FreeScale: Distributed Training for Sequence Recommendation Models with Minimal Scaling Cost"
authors: [Chenhao Feng, Haoli Zhang, Shakhzod Ali-Zade, Yanli Zhao, Liang Luo, "et al."]
venue: MLSys
year: 2026
tags: [recommendation-system, distributed-training, load-balancing, embedding, rdma]
source_pdf: "[[2838023a778dfaecdc212708f721b788.pdf]]"
source_md: "[[2838023a778dfaecdc212708f721b788]]"
---

# FreeScale: Distributed Training for Sequence Recommendation Models with Minimal Scaling Cost (MLSys 2026)

> **一句话总结**：序列推荐训练里用 UIH 负载均衡消 straggler、优先更新 collision embedding 行、CPU-[[RDMA]] SM-Free 通信避免 overlap 抢 SM，256×H100 生产 workload 上 exposed communication 降 **90%**、bubble 最高降 **90.3%**。

## 问题

工业 **DLRM 序列模型** 的用户交互历史（UIH）长度高度不均：padding 到 batch 内最长样本带来 >20% straggler idle；embedding lookup 的 blocking AllToAll 又把 GPU 空转放大。Prefetch 下一迭代 ID 可与计算 overlap，但会导致 embedding row collision（虽仅 ~低个位数 %，生产上 0.1% 指标回归也不可接受）。LLM 的 length bucketing / context parallel 不能直接搬——推荐训练样本时序敏感，且 embedding 通信模式不同。

## 核心方法

**FreeScale** 三件套（PyTorch + TorchRec 上 ~8.6K LOC）：

1. **Sequence load balancing**：按 UIH 长度/候选数估计算力，三阶段 AllGather+AllToAll 重排样本（FBS zig-zag 或 VBS 按 L^α 加权 + autotune）；hook 注入 forward/backward/optimizer，与 prefetch buffer overlap 通信。
2. **Prioritized embedding updates**：区分 collision vs exclusive row；exclusive 行异步 prefetch+更新，collision 行强制 write-read 顺序；封装进自定义 autograd.Function，与 dense 计算并行。
3. **SM-Free communication**：AllGather/AllToAll 走 D2H → CPU [[RDMA]] ring → H2D，不占 SM；避免与 Triton embedding kernel overlap 时 NCCL 抢 SM（kernel 执行快 **~10%**）。

配套 Triton kernel 处理 jagged ID tensor（world size 512 时比 PyTorch eager 快 **600×+**）。

## 关键结果

- Straggler：UIH max 21K、64 GPU 时 straggler 从 >20% 降到约 **1/9**（相对 TorchRec）。
- Exposed embedding communication：合成数据上降约 **9×**；collision 率越高 FreeScale 优势越线性体现。
- 256 H100 生产模型：exposed communication **90%** 削减，端到端 QPS 随集群放大收益更明显；数值与 TorchRec 收敛曲线一致（NE 对齐）。
- 高带宽 IB 集群已显著；更慢网络预期收益更大。

## 相关

- **相关概念**：[[RDMA]]、embedding parallelism、AllToAll
- **同类系统**：TorchRec、DMT、PLink、LB-BSP
- **同会议**：[[MLSys-2026]]