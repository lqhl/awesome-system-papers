---
type: paper
name: AgenticCache
full_title: "AgenticCache: Cache-Driven Asynchronous Planning for Embodied AI Agents"
authors: [Hojoon Kim, Yuheng Wu, Thierry Tambe]
venue: MLSys
year: 2026
tags: [embodied-ai, llm-agents, caching, multi-agent, planning]
source_pdf: "[[98f13708210194c475687be6106a3b84.pdf]]"
source_md: "[[98f13708210194c475687be6106a3b84]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# AgenticCache：具身 AI 智能体的缓存驱动异步规划（MLSys 2026）

> **原题**：AgenticCache: Cache-Driven Asynchronous Planning for Embodied AI Agents

> **一句话总结**：具身任务存在强 **plan locality**（如 GoGrasp→Transport 占 **59.7%**），同步 [[LLM]] 规划占仿真 **>70%** 延迟；AgenticCache 用 2-gram 计划转移缓存 + 后台 Updater 异步校验/纠错，在 4 benchmark × 3 模型上平均 SR **+22%**、延迟 **-65%**、token **-50%**（GPT-5 TDW-COOK 延迟 **7.4×**、成本 **4.8×**）。

## 问题与动机

[[LLM]] 驱动的 embodied agents（perceive-plan-act）避免手工 pipeline，但每步同步调用 [[LLM]] 造成高延迟与 token 成本。并行规划（plan-while-act）与 speculative planning 仍**每步依赖 LLM**。

作者观察到 **plan locality**：下一高层计划常可由当前计划与任务元数据预测（Fig. 4 2-gram 分布）。纯模式跟随会因环境变化失效，需 hybrid：缓存快路径 + 选择性 LLM 推理。

## 关键观察 / 隐含假设

- **观察 1：多 agent 具身 benchmark 中 LLM/VLM 查询占端到端仿真时间 majority（>70%）。** 四环境 latency breakdown 支持。
  - **依赖假设**：规划粒度为离散高层 plan（GoGrasp、Transport 等），非低层 motor control；API 延迟主导非物理仿真。
  - **可能失效场景**：本地小模型亚秒级规划时缓存收益缩小；连续控制无离散 plan 边界。

- **观察 2：2-gram 转移高度偏斜，但纯缓存无 LLM 校验时 SR 显著低于 GPT-5 同步基线（Fig. 5）。** 环境动态（他 agent 先抓取）使 stale transition 失效。
  - **依赖假设**：metadata 范围过滤（步数、持物数、房间访问等）足以剔除多数无效转移。
  - **可能失效场景**：长 horizon 后 metadata 范围过宽，错误转移仍 feasible；多 agent 协调冲突需 plan replacement。

- 假设 1：异步 Updater 延迟 k 步的 LLM 确认/纠错 + confirmation/correction suppression 可在不阻塞执行下维持 84–100% SR（GPT-5/mini）。
  - **证据强度**：**强**——Table 2 12 配置；ablation 显示 update + replacement 协同（静态缓存仅 **24%** SR）。

- 假设 2：缓存 footprint 极小（0.1–1.0 KB/agent），增长约 1500 步后饱和，无 unbounded blow-up。
  - **证据强度**：**中**——Table 5/6；长 episode 行为需更多生产级任务验证。

## 核心方法

**Cache planner**：每 agent 维护 ⟨P_i→P_j⟩ 2-gram 条目，含转移计数 C、LLM 确认率衍生的 importance I、metadata 范围；score S=C×I，先 metadata 过滤再 argmax。

**Cache Updater**（后台）：周期性发 LLM 查询；k 步后若预测 plan 已在轨迹中则 reinforce（confirmation suppression）；否则 correction——更新转移、降错误计数、**立即替换**当前 plan（correction suppression）。

**Warm-start**（可选）：OOD 成功轨迹预填缓存；cold-start 仍 **1.4–1.9×** 降延迟。

## 设计取舍

- **2-gram vs 更长 context**：实现简单、KB 级内存，但无法表达多步依赖；复杂任务靠 Updater 纠错。

- **Per-agent cache vs 全局**：适配 decentralized multi-agent，但跨 agent 协调冲突需 LLM 层（BEHAVIOR-1K 合并每步单次 LLM 调用）。

- **立即 plan replacement vs 等当前 plan 结束**：降低 stale hit 伤害，但可能中断进行中动作增加仿真复杂度。

- **API 依赖（GPT-5 系列）**：结果难直接迁移开源本地模型；成本数字绑定 OpenAI 定价（2025-10）。

- **边界条件**：TDW-MAT/COOK/GAME + BEHAVIOR-1K COHERENT；RTX 4090 工作站；非真实机器人 deploy。

## 实验与结果

- **SR**：12 配置平均 **+22%**；TDW-GAME AgenticCache **100%** vs parallel **0–22%**、speculative **11–33%**。
- **效率**：平均延迟 **-65%**、token **-50%**；TDW-COOK GPT-5：**12.86h→1.75h**、**$21→$4.4**。
- **Cold-start**：延迟仍 **1.4–1.9×** 优于同步；长 horizon GPT-5 SR 略降 **82.2%→80.6%**。
- **Hit rate**：TDW-GAME **>66%**、BEHAVIOR **≥73%**；COOK **39–46%**（多样性高）。
- **Ablation**：仅 update **+12%** SR；仅 replacement **+35%**；完整 **70.7%** vs 静态 **24%**。

## 批判性分析

### 论证链条

Plan locality 测量 → 纯缓存失败 → hybrid cache+async LLM 设计 → 四环境三模型全面胜出，链条完整。与 [[KV-Cache]]/[[vLLM]] serving 优化正交互补的 claim 合理。

### 假设压力测试

- **已证明**：高规律性环境 hit 高；Updater 纠错对动态环境必要。
- **可能失效**：开放世界新 plan 词汇冷启动 miss 多（fallback 9–29s VLM）；真实部署网络抖动对异步 k 步对齐的影响未测。
- **未覆盖**：与 [[SGLang]]/[[vLLM]] prefix cache 叠加、多 tenant 缓存隔离。

### 实验可信度

Baseline 含 CoELA/COMBO/COHERENT 同步、parallel、speculative，覆盖较全。COMBO 为简化复现。成本来自 API 计费，可复现性依赖模型版本。

### 系统性缺陷

安全性：缓存投毒/恶意 transition 论文未讨论。可观测性：何时 trust cache vs LLM 对运维不透明。多 agent 协调错误在长 horizon 仍出现（GPT-5 SR 微降）。

## 局限与后续工作

- **局限 1**：依赖闭集高层 plan 词汇与仿真器离散动作；迁移真实机器人需新 plan ontology。
- **局限 2**：GPT-5 系列 API，开源模型 plan locality 分布未知。
- **Future work 1**：在 production robot fleet trace 上测 hit rate vs 环境熵的回归曲线。
- **Future work 2**：与 speculative decoding 结合——缓存提供 draft plan，LLM 验证合并。

## 相关

- **相关概念**：[[LLM]]、embodied-ai、multi-agent-systems
- **同类系统**：CoELA、COMBO、[[vLLM]]
- **同会议**：[[MLSys-2026]]
