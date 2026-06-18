---
type: paper
name: CSLE
full_title: "CSLE: A Reinforcement Learning Platform for Autonomous Security Management"
authors: [Kim Hammar]
venue: MLSys
year: 2026
tags: [reinforcement-learning, security, emulation, digital-twin, platform]
source_pdf: "[[6c8349cc7260ae62e3b1396831a8398f.pdf]]"
source_md: "[[6c8349cc7260ae62e3b1396831a8398f]]"
---

# CSLE: A Reinforcement Learning Platform for Autonomous Security Management (MLSys 2026)

> **一句话总结**：CSLE 用 Docker 数字孪生 emulation + MDP simulation 闭环学安全策略，含 15 种 twin 配置、50+ 场景、34 种 RL 算法，在 flow/replication/segmentation/recovery 四类管控任务上达到近最优且可迁移到近似生产环境。

## 问题

RL 用于自主网络安全管理（incident response、APT 防御等）的结果多限于 simulation，与真实系统行为 gap 大。直接在运营系统上交互学策略不现实（慢、危险）；纯 simulation 又难建模复杂动态。

## 核心方法

**CSLE**（Cyber Security Learning Environment）双系统闭环：

1. **Emulation**：Docker Swarm 数字孪生复刻目标网络（hosts、switches、攻击者/防御者/客户端），可控延迟与 workload；收集 trace 做 system identification（MDP/Markov game）
2. **Simulation**：毫秒级 MDP 仿真 + 34 种 RL 算法学策略
3. **Management**：分布式 metastore（Citus）、Ansible 部署、Python/gRPC/REST/CLI 接口

七步方法论：定义目标系统 → 建 twin → 采集数据 → 辨识模型 → RL 学策略 → twin 评估 → 部署/迭代。

## 关键结果

- 四类用例（flow、replication、segmentation、recovery control）均学到 **near-optimal** 策略
- 15 digital twin 配置、50+ 模拟场景、34 RL + 4 system ID 算法
- 对比 CyberBattleSim、CyBorg 等 20+ 平台：唯一同时支持 **emulation 评估 + simulation 优化 + 开源维护 + 分布式部署**
- ~275K LOC Python；CC-BY-SA 4.0 开源

## 相关

- **相关概念**：reinforcement learning、digital twin、MDP
- **同类系统**：CyberBattleSim、CyGym、Gym-FlipIt、Yawning Titan
- **同会议**：[[MLSys-2026]]