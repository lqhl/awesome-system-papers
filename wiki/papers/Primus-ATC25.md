---
type: paper
name: Primus
full_title: "Primus: Unified Training System for Large-Scale Deep Learning Recommendation Models"
authors: [Jixi Shan, Xiuqi Huang, Yang Guo, Hongyue Mao, Ho-Pang Hsu, et al.]
venue: ATC
year: 2025
tags: [dlrm, training-system, recommendation, online-learning, bytedance]
source_pdf: "[[atc2025-shan-jixi.pdf]]"
source_md: "[[atc2025-shan-jixi]]"
---

# Primus: Unified Training System for Large-Scale Deep Learning Recommendation Models (ATC 2025)

> **一句话总结**：字节跳动生产级 DLRM 统一训练系统，5 年部署、10M+ CPU core / 万级 GPU；动态扩缩降本 17.1%、CPU 利用率 50%→80%、广告收入提升 0.4%–2.4%。

## 问题

字节内部 DLRM 训练 5 年内 daily job 增长 10×，单模型日数据 20→160 TB，daily CPU vcore 1.5M→9M。训练系统需同时跨 YARN 与 Kubernetes 多调度系统、混合 batch + stream 多源数据、并平衡 offline 鲁棒性与 online 时效性（catastrophic forgetting + delayed feedback）。现有方案要么只支持单一调度系统、要么不感知 stream，要么在线训练与离线训练割裂。

## 核心方法

三层「统一」设计：

- **Unified Resource Scheduling**：JobCRD 屏蔽 YARN/Kubernetes 差异；Dynamic Scaling Manager 用 metric-driven 公式 $L_u = \mathbf{w}\cdot\mathbf{u}$ 决定数据/训练 executor 比例（horizontal），并按 $D(N_R)$ 加权平均预测资源变化做 vertical 扩缩。
- **Unified Data Orchestration**：三层数据抽象 dataset / data stream / data source；Data Task Graph Generation (DTGG) 用 Timer / Source / Joiner / Sink 四种 OP 并行生成 batch + stream task，把 4M task 生成从 58 分钟（单线程 baseline）压到 42 秒（4 线程）。
- **Unified Training Paradigm**：Mixture Training Recommendation Model (MTRM) 拆出 memory tower（学 24h 延迟 batch，对抗 catastrophic forgetting）+ adapt tower（学 stream，保时效），通过参数更新逻辑分离避免信息泄露；mixture data prioritization 用 sigmoid 加权优先级 $p_i = w_i \cdot \frac{1}{1+e^{-q_i}}$ 在限资源下保 stream 优先。

开源：https://github.com/bytedance/primus

## 关键结果

- 横向扩缩：cluster ROI 从 30.26 提到 35.44（+17.1%），单 job CPU 节省 23.33%。
- 纵向扩缩：CPU 利用率 50%→80% 同时不影响吞吐与 AUC；PS 内存动态扩 1984 GB 避免 OOM，吞吐 275→496 minibatch/s。
- DTGG 单线程相比 PyTorch baseline 加速 23×，4 线程到 42s。
- MTRM 在 4 个生产 CVR/CTR 模型 A/B 测试中：AUC 提升 0.03%–0.07%，广告收入提升 0.397% / 0.806% / 1.045% / 2.438%。

## 相关

- **相关概念**：DLRM、Online Learning、Catastrophic Forgetting、CRD、Elastic Training
- **同会议**：[[ATC-2025]]
