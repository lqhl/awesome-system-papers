---
type: paper
name: CSLE
full_title: "CSLE: A Reinforcement Learning Platform for Autonomous Security Management"
authors: [Kim Hammar]
venue: MLSys
year: 2026
tags: [security, reinforcement-learning, digital-twin, emulation, platform]
source_pdf: "[[6c8349cc7260ae62e3b1396831a8398f.pdf]]"
source_md: "[[6c8349cc7260ae62e3b1396831a8398f]]"
---

# CSLE: A Reinforcement Learning Platform for Autonomous Security Management (MLSys 2026)

> **一句话总结**：Cyber Security Learning Environment（CSLE）把 Docker Swarm 数字孪生（emulation）+ MDP 仿真（simulation）结合，在仿真里跑 RL 学策略、到孪生里评估迭代，包含 15 套 digital twin 配置、50+ 仿真场景、34 个 RL 算法实现，四个真实 use case（flow/replication/segmentation/recovery control）验证接近最优。

## 问题

网络系统安全管理（incident response、风险分析、威胁狩猎）目前主要靠人工专家——全球缺 400 万安全专家。用 [[Reinforcement-Learning]] 自动学防御策略看起来有希望，但现有 RL 安全研究大多停在 simulation，不清楚是否能泛化到实际运营系统。主要系统级挑战：

1. 运营网络里 attack/response 展开时间尺度长，直接交互做 RL 不现实（需要成千上万次 action）
2. 系统行为太复杂，simulation dynamics 必须从测量数据识别出来
3. 学到的策略必须在接近真实目标系统的环境里被验证

## 核心方法

CSLE 架构是「emulation + simulation」双系统闭环：

**Emulation System（数字孪生）**：
- 目标系统的虚拟副本，跑一样的软件和配置，但在 Docker 容器上
- Hosts/switches 用 Docker 容器，switch 跑 OVS 走 OpenFlow
- 网络链路用 Linux bridges + network namespace，跨物理机时 VXLAN 隧道
- 网络条件用 Linux NetEm 模块控制 bitrate/delay/loss/jitter
- Actors（attacker、defender、client）都通过 gRPC 管理 API 编程控制；client 用 Poisson arrival + exponential service + Markov 服务调用序列
- 自动运行攻击场景、收集 traces 和 metrics

**Simulation System**：
- 用 emulation 采集的 traces 做 system identification，得到 MDP 或 Markov game：$s_{t+1} \sim f(s_t, a_t^{(D)}, a_t^{(A)})$
- 仿真里单步 ms 级，比在孪生里（分钟级）快几个数量级
- 内置 34 种 RL 算法实现，用 simulation 学 defender 策略

**RL 方法论（7 步闭环）**：定义 target system → 建 digital twin → 采数据 → 系统辨识（MDP）→ RL 训练 → digital twin 评估 → 部署到 target system；不满意则回到采数据步骤迭代。

**Infrastructure**：分布式 $N \geq 1$ 服务器，Docker Swarm 做 virtualization，Citus 做分布式 metastore（leader-follower、quorum election，容忍 $\lfloor (N-1)/2 \rfloor$ 失效），Ansible 自动化部署；接口包括 Python/gRPC/REST/CLI。实现 275K 行 Python + 40K 行 JS + 5K 行 Bash。

## 关键结果

- 与 18 个同类平台（CyberBattleSim、CyBorg、NaSim、Yawning Titan、PenGym、CyberWheel 等）对比：CSLE 独有 **open source + emulation + simulation + RL 库 + management 系统 + 分布式部署 + 实验验证 + 持续维护** 全部 checkmark
- 四个 use case 都达到接近最优防御性能：
  - **Flow control**
  - **Replication control**
  - **Segmentation control**
  - **Recovery control**
- 初始配置：15 种 digital twin、50+ 仿真场景、34 个 RL 算法、4 个 system identification 算法
- 数字孪生 deploy/cleanup 时间、client load 下的 CPU/memory 资源使用都给了测量曲线
- 与 LLM-based 运营平台（ITBench、AIOpsLab）的差异：CSLE 专为 RL 安全管理、包含 system identification + sim-to-real transfer

## 相关

- **相关概念**：[[Reinforcement-Learning]]、Digital-Twin、MDP、System-Identification、Sim-to-Real
- **同类系统**：CyberBattleSim、CyBorg、NaSim、Yawning Titan、CyberWheel
- **相关领域**：ITBench、AIOpsLab（LLM-based，不同 scope）
- **同会议**：[[MLSys-2026]]
