---
type: paper
name: DISAGG
full_title: "DISAGG: Distributed Aggregators for Efficient Secure Aggregation in Federated Learning"
authors: [Haaris Mehmood, Giorgos Tatsis, Dimitrios Alexopoulos, Karthikeyan Saravanan, Jie Xu, Anastasios Drosou, Mete Ozay]
venue: MLSys
year: 2026
tags: [federated-learning, secure-aggregation, secret-sharing, privacy]
source_pdf: "[[a0a080f42e6f13b3a2df133f073095dd.pdf]]"
source_md: "[[a0a080f42e6f13b3a2df133f073095dd]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# DISAGG：用于联邦学习中高效安全聚合的分布式聚合器（MLSys 2026）

> **原题**：DISAGG: Distributed Aggregators for Efficient Secure Aggregation in Federated Learning

> **一句话总结**：DISAGG 将跨设备联邦学习的安全聚合从服务器和普通客户端移到一个小型 Aggregator committee：客户端把更新 secret-share 给 committee，committee 只返回部分和，服务器重构总和。论文在参数化 timing analysis 和单机模拟中报告相对 OPA 的加速；这些不是 production deployment 测量。

## 问题与动机

传统 secure aggregation 需要多轮密钥/掩码恢复；OPA 将每轮客户端交互压缩为一次，但其加密和重构代价随模型维度与 committee 参数增长。DISAGG 的目标是保留低交互特性，同时让 Aggregator 对 shares 求和，减少普通客户端 masking 和服务器重构工作。

## 关键观察 / 隐含假设

- **观察 1**：将求和移到小型 committee 可以减少普通客户端与服务器端的加密/重构工作，但会把流量和计算转移给 Aggregator。
- **观察 2**：协议性能主要由模型维度、参与人数、committee 参数以及上下载带宽共同决定；论文的主要验证是参数化 timing analysis。
- **隐含假设**：参与客户端按论文的 honest-but-curious server、随机 corruption/dropout 威胁模型运行，且 Aggregator 的可用性和流量预算可接受。

## 核心方法

每轮中服务器选定参与客户端和 Aggregator。普通客户端把量化后的模型更新按 Lagrange coded secret sharing 切成 shares，加密后经服务器转发给 Aggregator；Aggregator 解密并累加 shares，服务器收集足够的 aggregate shares 后重构总更新。论文采用 honest-but-curious server 模型，参数化容忍恶意比例 γ、dropout 比例 δ，并以 reconstruction/corruption thresholds 控制可恢复性和隐私。

## 设计取舍

- **委员会求和 vs OPA 的加密聚合**：普通客户端和服务器工作下降，但 Aggregator 的通信、存储和计算上升，效果依赖 committee 大小 A 与 packing ratio ρ。
- **参数化性能模型 vs 端到端部署**：论文用通信/计算时延模型比较协议，并用单机进程模拟部分验证；它不提供百万真实移动设备或生产网络上的端到端训练测量。
- **安全边界**：安全性针对论文定义的 honest-but-curious server、随机 client corruption/dropout；不覆盖恶意服务器或实现漏洞。

## 实验与结果

- 5G timing model（metric：总协议时间；baseline：OPA；boundary：M=N=100k、2 MB/s uplink、20 MB/s downlink）：DISAGG 的最优配置报告 4.56× 加速（830 s vs 461 s，§4.2、Fig. 5）。这是参数化 timing analysis，不是实测设备 fleet。
- 大规模 extrapolation（metric：预测总时间；baseline：OPA；boundary：M=N≤1,000,000，k=0.3、k_comp=0.66）：模型估计 3.1–29.8× 加速（§4.2、Fig. 6）；作者明确把这一项作为 analytical estimate。
- 单机模拟（metric：相对运行时间；baseline：OPA；boundary：M=1k/10k，模拟 clients 和 committee processes）：M=1k 时约高 10%，M=10k 时报告 3.2× 加速（§5、Fig. 6）。该模拟不代表跨设备网络行为。
- 百万维成本（metric：Aggregator download；baseline：OPA；boundary：M=N=1,000,000、A=1607、ρ=1331）：原始 Aggregator 下载大于 12 GB；作者估计调整参数可降到约 269 MB 并维持至少 3× 对 OPA 的优势（§4.2）。这暴露了性能与 committee 流量的权衡。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| committee aggregation can reduce modeled protocol time | 4.56× vs OPA，830 s vs 461 s（§4.2，Fig. 5） | 100k-dimensional updates、100k clients、5G timing model | high |
| speedup depends strongly on deployment parameters | modeled 3.1–29.8× vs OPA（§4.2，Fig. 6） | M=N up to 1M、specified k/k_comp；analytical extrapolation | high |
| small simulation shows the predicted crossover | M=1k about 10% overhead；M=10k 3.2× vs OPA（§5，Fig. 6） | single-machine simulated client/committee processes | high |
| committee traffic can be large at scale | more than 12 GB raw download; adjusted estimate about 269 MB（§4.2） | M=N=1M、A=1607、ρ=1331; parameter model | high |

## 批判性分析

### 论证链条

论文的主要实证是 timing model，加上有限的单机模拟；它支撑“在给定计算/带宽假设下可能更快”，不支撑 production FL 中的端到端延迟、掉线恢复成本或训练收敛改善。

### 假设压力测试

性能对 A、ρ、client upload、Aggregator 下载高度敏感；为改善协议时间而增加的 committee 流量也可能是移动网络的实际瓶颈。安全证明的有效性还依赖威胁模型与参数选择，不能外推为对恶意服务器或实现层攻击的保护。

### 实验可信度

模型比较明确给出了参数边界，且单机模拟展示了小规模 crossover；但缺少同实现、真实跨设备网络和 failure injection 的端到端比较。

## 局限与后续工作

- 用真实跨设备网络、异构上传速率和掉线模式验证模型结论，并报告 p50/p95 round latency。
- 与 OPA 在同一实现、同一加密库和同一 failure injection 下对比。
- 量化 Aggregator 选择、能耗和流量成本，特别是百万客户端配置。

## 相关

- **相关概念**：[[Federated-Learning]]、[[Secure-Aggregation]]、[[Secret-Sharing]]
- **相关系统**：OPA、SecAgg、SecAgg+
