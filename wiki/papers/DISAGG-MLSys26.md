---
type: paper
name: DISAGG
full_title: "DISAGG: Distributed Aggregators for Efficient Secure Aggregation in Federated Learning"
authors: [Haaris Mehmood, Giorgos Tatsis, Dimitrios Alexopoulos, Karthikeyan Saravanan, Jie Xu, Anastasios Drosou, Mete Ozay]
venue: MLSys
year: 2026
tags: [federated-learning, secure-aggregation, privacy, secret-sharing]
source_pdf: "[[a3c65c2974270fd093ee8a9bf8ae7d0b.pdf]]"
source_md: "[[a3c65c2974270fd093ee8a9bf8ae7d0b]]"
---

# DISAGG: Distributed Aggregators for Efficient Secure Aggregation in Federated Learning (MLSys 2026)

> **一句话总结**：用少量 client Aggregator committee 做 secret-share 局部求和，消除 pairwise masking 与 homomorphic encryption 开销；100k 维 × 100k 5G clients 比 one-shot OPA **4.6×** 更快，M=N=1M 场景理论 **25×** speedup。

## 问题

Secure aggregation（SecAgg/OPA）保护 client update 隐私，但 SecAgg 需 O(N²) 消息、多轮交互；OPA 单轮上传却 burden 重密码学（LWR masking + packed Shamir），client/server 成本随维度和 committee 规模膨胀。

## 核心方法

**DISAGG**：regular client 把 model update secret-share 给 Aggregator committee；Aggregators 本地加 partial sums，server 用 Lagrange Coded Computing 重建 aggregate。无 local masking、无 HE。

三轮 per FL iteration；支持 dropout（δ）与 collusion（γ）阈值下的 T-privacy。

## 关键结果

- 100k-dim update、100k 5G clients：**4.6×** vs OPA
- 解析 timing model：M=N=1M 时预期 **25×** over OPA
- 保留 one-shot/async 参与优势，client 端计算显著降低

## 相关

- **相关概念**：[[Quantization]]（quantize 后 field 上聚合）
- **同类系统**：SecAgg、SecAgg+、OPA、FASTSecAgg、LIGHTSecAgg
- **同会议**：[[MLSys-2026]]