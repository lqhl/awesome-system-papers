---
type: paper
name: DISAGG
full_title: "DISAGG: Distributed Aggregators for Efficient Secure Aggregation in Federated Learning"
authors: [Haaris Mehmood, Giorgos Tatsis, Dimitrios Alexopoulos, Karthikeyan Saravanan, et al.]
venue: MLSys
year: 2026
tags: [federated-learning, secure-aggregation, privacy, secret-sharing, cross-device]
source_pdf: "[[a3c65c2974270fd093ee8a9bf8ae7d0b.pdf]]"
source_md: "[[a3c65c2974270fd093ee8a9bf8ae7d0b]]"
---

# DISAGG: Distributed Aggregators for Efficient Secure Aggregation in Federated Learning (MLSys 2026)

> **一句话总结**：one-shot SA（如 OPA）降轮次但密码学开销随维度爆炸；DISAGG 让客户 secret-share 更新给少量 Aggregator 委员会做部分和，服务器仅重构聚合，消除 pairwise mask 与 HE，在 **100k 维×100k 5G 客户端** 上比 OPA **4.6×** 加速，分析模型预测 M=N=1M 时可达 **~25×**。

## 问题与动机

Cross-device [[Federated-Learning]] 需 secure aggregation（SA）防 honest-but-curious server 反演个体更新。SecAgg 多轮 O(N²) 代价；OPA 单轮但 LWR/packed Shamir 重。目标：保留 one-shot/异步参与，降低 client 与 server 密码学负担。

## 关键观察 / 隐含假设

- **观察 1：mask-cancel 类协议把求和留在 server，client 端 mask 与 dropout recovery 成本高；把求和下沉到委员会可在保持 T-privacy 下减掉 local masking。**
  - **依赖假设**：γ 比例勾结、δ dropout、Byzantine 界限下阈值 tr/tc 可选（扩展 LCC 分析）。
  - **可能失效场景**：Aggregator 被攻破比例超模型；恶意 Aggregator 篡改部分和。

- **观察 2：Lagrange Coded Computing 加法同态 secret share 适合向量求和；仅 Aggregator 收 share（非全员广播）降带宽。**
  - **依赖假设**：域大小 p≥2³² 量化误差可忽略；PKE（DH）建通道。
  - **可能失效场景**：极高维稀疏更新 packing 策略不当仍贵。

- **观察 3：三 round（选 U、regular client→share、Aggregator→partial sum→server reconstruct）与 OPA 同属 one-shot 异步类。**
  - **依赖假设**：足够 |U0|、|A0| 到达即可重构，无全局 barrier。
  - **可能失效场景**：Aggregator 掉线率高于模型假设时延迟重构。

## 核心方法

每轮：server 广播模型；regular client 量化 Δw 并 secret-share 给 A 个 Aggregator（Algorithm 1）；Aggregator 本地加总 share；server 用 Algorithm 2 重构 ΣΔw。威胁模型：T-privacy，含 server + ≤γN 勾结 client。

相比 LIGHTSECAGG/OPA：无 homomorphic mask；Aggregator 额外通信由小委员会规模控制。

## 设计取舍

- **Aggregator 委员会 vs 纯 server**：client 计算降，引入高权限角色与额外 hop。
- **Secret-sharing vs HE**：更快，依赖阈值与 dropout 分析正确性。
- **量化 vs 浮点**：标准 SA 做法，略损 utility。
- **边界条件**：cross-device 大规模 N；datacenter FL 不同威胁模型未强调。

## 实验与结果

- 100k 维、100k 客户端：**4.6×** vs OPA（摘要/实验节）。
- 解析 timing framework：M=N=1M 配置预期 **~25×** vs OPA。
- 对比 SecAgg、SecAgg+、LIGHTSECAGG、OPA 等（复杂度与仿真）。

## Critical Analysis

### 论证链条

one-shot 痛点 + committee sum 直觉 → 协议 + 阈值分析 + timing，逻辑清楚。25× 来自分析外推，需生产流量验证。

### 假设压力测试

Aggregator 成为新攻击面；5G client 计算/电量是否真能承担 share+encrypt；与 DP 组合的开销。

### 实验可信度

大规模维度仿真强；真机百万 client 未演示。Baseline OPA 代表 one-shot SOTA。

### 系统性缺陷

运维委员会选举、轮换、审计；straggler Aggregator 尾延迟；论文对 mobile 网络抖动讨论有限。

## 局限与 Future Work

- **局限**：Aggregator 信任与可用性；极端 dropout 下延迟；与生产 FL 栈（TFF）集成成本。
- **Future work**：动态委员会规模；与压缩梯度结合；形式化 composable 安全在 DP-SGD 全流程。

## 相关

- **相关概念**：[[Federated-Learning]]、[[Secure-Aggregation]]
- **同会议**：[[MLSys-2026]]