---
type: paper
name: NetKeeper
full_title: "NetKeeper: Enhancing Network Resilience with Autonomous Network Configuration Update on Traffic Patterns and Anomalies"
authors: [Zhaoyang Wan, Rongxin Han, Haifeng Sun, Qi Qi, Zirui Zhuang, et al.]
venue: ATC
year: 2025
tags: [network-configuration, intent-based-networking, llm, multi-agent-rl, autonomous-network]
source_pdf: "[[atc2025-wan.pdf]]"
source_md: "[[atc2025-wan]]"
---

# NetKeeper: Enhancing Network Resilience with Autonomous Network Configuration Update on Traffic Patterns and Anomalies (ATC 2025)

> **一句话总结**：双向 intent 接口（自然语言 + 异常日志 → DSL → API）+ 多智能体 RL 自治更新网络配置，平均策略一致性 99.6%，性能提升 5.3%、流量迁移降低 8.7%。

## 问题

企业网络运维面临频繁变更（半数网络月均 ≥10 个变更事件），现有 intent-based 工具用 DSL/SMT/监督学习写配置：要么仅支持单一 intent 形式（DSL 或自然语言），无法处理管理平台的异常日志；要么仅满足 forwarding policy 不感知 traffic pattern，导致拥塞或负载失衡；要么基于静态 snapshot 不能适应 dynamic network。

## 核心方法

- **Intent Translation（双向）**：northbound 接收 operator 自然语言，southbound 接收平台异常日志；统一形式化为 IT={ND, NP, PO, NR, AT, FP}（设备/协议/选项/规则/属性/转发策略）。LLM 用 P-tuning 微调 + LangChain 部署，把 intent 翻译为 DSL（带 `assignIp`、`pathConstraint`、`bgpPolicy` 等 operation），再经 DSL interpreter 做语法/参数/逻辑校验，错误反馈通过 LLM 自然语言回给 user 形成闭环。
- **Configuration Update（多智能体 RL）**：3 个 agent 分管 OSPF（α 权重）、BGP（γ1 LP / γ2 AS path / γ3 MED）、链路属性（β1 带宽 / β2 容量 / β3 队列长度）。State 用 network sketch + Graph Transformer 编码为 (V, E)；Reward 综合策略一致性 π、最大链路利用率 ρ（递归计算 ECMP load + lossy link）、流量迁移 τ（路由表 next-hop 改变比例），并加 stationary/dynamic 子项防局部最优。模型用 Actor-Critic 架构（中心化 critic + 去中心化 actor），训练算法用 COMA（Counterfactual Multi-Agent），通过 baseline + advantage 评估每个 agent 贡献。

## 关键结果

- 平均策略一致性 99.6%；网络性能（含 latency、throughput）提升 5.3%；流量迁移降低 8.7%。
- 多智能体设计相比单智能体显著降低 solution space 复杂度，收敛更快。
- 双向 intent 接口同时支持 5 类 operator intent + 3 类异常日志，DSL 类型化校验 + LLM feedback 解决 LLM hallucination。

## 相关

- **相关概念**：Intent-Based Networking、Multi-Agent Reinforcement Learning、Network Configuration Synthesis、OSPF、BGP
- **同会议**：[[ATC-2025]]
