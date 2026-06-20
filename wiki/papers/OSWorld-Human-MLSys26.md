---
type: paper
name: OSWorld-Human
full_title: "OSWorld-Human: Benchmarking the Efficiency of Computer-Use Agents"
authors: [Reyna Abhyankar, Qi Qi, Yiying Zhang]
venue: MLSys
year: 2026
tags: [computer-use-agent, benchmark, latency, osworld, efficiency]
source_pdf: "[[6364d3f0f495b6ab9dcf8d3b5c6e0b01.pdf]]"
source_md: "[[6364d3f0f495b6ab9dcf8d3b5c6e0b01]]"
---

# OSWorld-Human: Benchmarking the Efficiency of Computer-Use Agents (MLSys 2026)

> **一句话总结**：首次在 [[OSWorld]] 上量化 computer-use agent 延迟瓶颈——planning/reflection 大模型调用占 **75–94%** 总时间、后期 step 因历史 prompt 膨胀可达早期 **3×**；据此构建 369 任务人工最短轨迹基准 **OSWorld-Human** 与 **WES** 效率指标，16 个 SOTA agent 比必要步骤多 **1.4–2.7×**，OSWorld 最高 **41.4%** 成功率在 grouped-action WES+ 上仅 **17.4%**。

## 问题与动机

Computer-use agent（CUA）在 [[OSWorld]] 等 benchmark 上 task success rate 快速提升，但端到端延迟与轨迹冗余几乎未被系统研究。作者观察到典型落差：改两段行距 agent 需 **12 分钟**，熟练用户 **<30 秒**；创建 SSH 用户等 OS 任务 Agent S2 跑满 **50 步、40+ 分钟**。现有 leaderboard 与论文几乎只优化准确率，忽视 **时间效率**——而交互式编辑、频繁视觉调整、实时应用操作等场景要求响应接近人类水平，数十分钟延迟使 agent 难以进入真实 workflow。

论文目标不是再提一个新 agent，而是 **(1) 首次剖析 CUA 延迟从何而来**、**(2) 建立人类效率金标准**、**(3) 用新指标量化「成功但极慢」与「快速失败」**。深度测量与表格细节回 [[6364d3f0f495b6ab9dcf8d3b5c6e0b01]] 或 [[6364d3f0f495b6ab9dcf8d3b5c6e0b01.pdf]]。

## 关键观察 / 隐含假设

- **观察 1：planning + reflection 的大模型调用主导端到端延迟，占 75–94%。**
  - **证据**：在 Agent S2 + GPT-4.1 的 37 个 [[OSWorld]] 子集上，按应用分解（Table 1）；OS 任务 timeline（Fig. 1）显示 50 步任务 **40+ 分钟** 几乎被 planner/reflector 填满。Grounding（[[UI-TARS]]-7B-DPO + [[SGLang]] on A6000）与 screenshot/action 占比极小。
  - **依赖假设**：agent 采用「每步 observe → plan → ground → act → reflect」循环，且 prompt 含完整历史；该架构与 InfantAgent、Jedi 等 leaderboard 前列系统同构（§3.4）。
  - **可能失效场景**：单模型端到端（如 UI-TARS-1.5 单次调用）延迟结构不同；无 reflection 的轻量 agent；或 prompt 压缩 / 滑动窗口截断历史后，后期 step 3× 放大效应减弱。

- **观察 2：轨迹越长，单步 LLM 延迟越高——prompt 随 step 数线性累积历史截图与规划文本。**
  - **证据**：Fig. 3 对 37 任务按每 5 步滑动平均，后期 step 的 latency 与 prompt token 同步上升；作者归因于「step 10 的 prompt 含 step 1–9 的截图与规划/反思」。
  - **依赖假设**：CUA 不把历史外置到独立 memory 结构，而是全量塞进 context；prefill 阶段主导 planning/reflection 延迟（Fig. 2 CDF）。
  - **可能失效场景**：[[KV-Cache]] 复用、摘要化历史、分层 planner（子任务级重规划）可打破「越跑越慢」；论文未实验这些缓解手段。

- **观察 3：A11y tree 显著抬高 per-step token 与任务延迟；Set-of-Marks（SoM）在部分应用上减少步数。**
  - **证据**：每应用抽 1 任务（§3.3），A11y 树生成 **3–26 s**，LibreOffice 等可达数千 token/step；Fig. 5 相对 screenshot-only 延迟大幅上升。Table 2：SoM+A11y 在 Writer/VLC/Thunderbird/GIMP 等达最少步数，但 VS Code/Chrome 反而更多步。
  - **依赖假设**：「更少步数 ≈ 更低总延迟」；tree 内容对 grounding 有足够增益才值得代价。
  - **可能失效场景**：仅 9 应用各 1 任务采样，结论 task-dependent 成分大；10k token cutoff 外的巨型 tree 行为未测；SoM 标注开销在 Fig. 5 中被省略。

- **观察 4：即使 OSWorld 上最成功的 agent，轨迹仍比人类必要路径长 1.4–2.7×。**
  - **证据**：对 leaderboard 16 个已公开轨迹的 CUA，与 OSWorld-Human gold 对比；Agent S2 w/ Gemini 2.5 OSWorld **41.4%** → single-action WES+ **28.2%**、grouped-action WES+ **17.4%**（Table 4）。
  - **依赖假设**：人工标注的 single/grouped trajectory 代表「典型熟练用户」的最短合理路径；步数比 $t_{exp}/t_{actual}$ 能代理效率。
  - **可能失效场景**：人类路径忽略思考时间、环境差异（坐标变化已刻意不写）；专家可用 CLI/脚本捷径而标注刻意限制（LibreOffice 禁用脚本等）；不同 S 值（最大步数）影响 WES− 跨 agent 可比性。

- **假设 1**：减少 planning/reflection 调用次数或降低其单次延迟，是加速 CUA 的两条主杠杆（§1 结论）。
  - **证据强度**：**强**——延迟分解与 token 增长测量直接支持；但论文 **未实现** 任何加速系统验证该杠杆的端到端收益。

## 核心方法

工作分两条线：**延迟剖析**（§3）与 **OSWorld-Human 基准 + WES 指标**（§4–5）。

### 延迟剖析（Agent S2 代表框架）

在 [[OSWorld]] 提供的 **37 任务（10%）** 子集上跑 Agent S2：planner/reflection/retrieval 用 **GPT-4.1**，grounding 用 **UI-TARS-7B-DPO**，单卡 **NVIDIA A6000** + [[SGLang]] serving；最多 **50 步/任务**。逐步计时分类：**retrieval**（任务初一次）、**planning**（每步 + 子任务后）、**grounding**、**screenshot**、**action**、**reflection**（每步）。

关键机制结论：
- Planning 总时间 > reflection，因 planning 频率更高。
- Retrieval 仅占 **0.7–8.9%**（只发生一次）；grounding 小模型 + 高效 serving 相对廉价。
- Planning/reflection 的 **prefill** 因超长 prompt 主导；retrieval 延迟主要在 **decoding**（整合文档进计划）。
- 对比三种 perception：**screenshot only**、**+A11y tree**、**+SoM**——量化 token 与步数 tradeoff。

作者论证 Agent S2 可代表 broader agentic CUA（InfantAgent、Jedi 等同循环），也适用于单模型 UI-TARS 式「observe-call-act」——整体趋势仍向多模型 agentic 系统倾斜。

### OSWorld-Human 金轨迹构建

为全部 **369** 个 [[OSWorld]] 任务人工构造 **gold trajectory**：
1. 优先用 benchmark 自带「source」（论坛回答等）映射到 OSWorld action space；无 source 则手工推导并与官方 gold file 对照。
2. 不写精确坐标（跨环境易变）；可用键盘快捷键等「典型用户」知识。
3. 两名 CS 研究生各做一遍 + 交叉验证；在 OSWorld VM 中手工复现直至 evaluator 通过。

产出两种粒度：
- **Single-action**：每个原子动作算一步。
- **Grouped-action**：同一视觉观察下可连续执行的动作组（如 click → type → enter）合并为一步，步数 ≤ single-action，为「单次 LLM 调用输出多动作」提供上界参考（Table 3 按应用汇总平均步数）。

### Weighted Efficiency Score (WES)

在步数效率之外兼顾成功率，避免「少步但失败」优于「多步但成功」：
- 成功任务 $r_t=1$：按 $t_{exp}/t_{actual}$ 加权（越少步越好）。
- 失败任务 $r_t=0$：惩罚 $t_{actual}/S$（$S$ 为该 agent 允许的最大步数，快速失败优于耗尽预算）。
- **WES+** ∈ [0,1]：高表示既成功又高效；**WES−** ∈ [−1,0]：高（接近 0）表示成功或快速失败，低表示又慢又失败。
- Single-action 与 grouped-action 共用 WES−；WES+ 分别用两种 $t_{exp}$，后者更严格（步数更少）。

评估使用 leaderboard **16 个 CUA 的已发布轨迹**，按各 agent 的 grouped-action 定义对动作分组后算分。

## 设计取舍

- **测量论文 vs 系统论文**：聚焦 benchmark 与剖析，不提出新 agent 或 serving 优化；换完整问题定义空间（latency + efficiency）但无工程解法。
- **Agent S2 深剖 vs 16 agent 浅评**：37 任务上精细 timing/token trace，全量 369 任务仅步数效率对比——用代表性框架换可扩展评估成本。
- **人类 gold 路径**：刻意排除 LibreOffice 脚本等「超典型用户」程序化解法，换与 benchmark 意图一致的可比性；牺牲部分理论最短路径。
- **Grouped-action 轨迹**：给出「一次观察多动作」的理论下界，但多数现有 agent API 仍是一步一 LLM 循环——指标偏乐观，揭示潜力而非当前可达性能。
- **WES 用步数代理延迟**：假设每步 LLM 成本相近或步数与 wall-clock 单调相关；实际上后期 step 更慢（观察 2），**论文未在 WES 中按 per-step latency 加权**。
- **开源承诺**：将发布 OSWorld-Human 与原始 timing 数据，换社区可复现；发布时点论文中为 future release 表述。

## 实验与结果

**延迟剖析（37 任务，Agent S2 + GPT-4.1）**：
- Planning+reflection：**75–94%** 总延迟（全应用一致）。
- 后期 step LLM 延迟可达早期约 **3×**（Fig. 3）。
- Grounding（UI-TARS-7B + [[SGLang]]）token 数稳定、延迟远低于 planning/reflection。
- A11y tree：LibreOffice 等 token 爆炸，树生成最高 **26 s**；部分应用（OS/GIMP/Chrome）步数反而下降。
- SoM：LibreOffice Writer、VLC、Thunderbird、GIMP 等达最少步数；VS Code/Chrome 步数增加。

**OSWorld-Human 步数基线（369 任务）**：
- Grouped-action 相对 single-action 全应用降低步数；弹窗/新窗口频繁的应用（Chrome 等）分组收益小，同页编辑（Writer/Calc）收益大（Table 3）。

**16 CUA 效率评估（Table 4）**：
- 轨迹冗余：相对人类路径多 **1.4–2.7×** 步。
- **Agent S2 w/ Gemini 2.5**：OSWorld **41.4%** → single-action WES+ **28.2%**（约 **1.5×** 降幅）、grouped-action WES+ **17.4%**（约 **2.4×** 降幅）。
- Grouped-action WES+ 严格低于 single-action（全 baseline 一致）。
- **UI-TARS-72B-DPO**：WES− **−0.16**（最快失败/完成）但 WES+ 很差——「快但不对」典型案例。
- OSWorld 上相对排序与 WES+ 大体一致，但绝对值大幅下移。

**个案**：
- 行距修改：**12 min**（agent）vs **<30 s**（人类）。
- OS SSH 用户任务：**50 步 / 40+ min**（Agent S2 时间线示例）。

## Critical Analysis

### 论证链条

链条 **「准确率 benchmark 忽视延迟 → 测量发现 LLM plan/reflect 瓶颈 + 历史 prompt 膨胀 → 人类最短轨迹揭示 1.4–2.7× 冗余 → WES 量化 success×efficiency 双重失败」** 在诊断层面闭合良好。最强证据是 **37 任务逐步 timing/token 分解** 与 **369 任务逐步数金标准** 的组合：前者解释「为什么慢」，后者解释「慢了多少相对于合理路径」。

最弱环节：(1) 从 Agent S2 延迟结构 **外推** 到全部 16 agent——仅论证架构相似，未对其他 agent 做同等粒度 profiling；(2) WES 用 **步数** 聚合，与 wall-clock 延迟（观察 2 表明步间成本不均）脱钩；(3) grouped-action WES+ 隐含「agent 可一次输出多动作」，与多数生产 agent 接口不匹配，指标更像 **研究 upper bound** 而非当前产品 KPI。

### 假设压力测试

- **人类路径代表性**：两名研究生 + 交叉验证，无多人群多样性研究；「典型用户」与 power user 路径差可能很大；禁止脚本/API 捷径使 gold 路径偏 GUI 冗长，可能 **低估** 人类效率上界，从而 **低估** agent 冗余比。
- **步数 ≈ 效率**：后期 step 延迟 3× 时，多 2× 步的实际耗时可能 >2×；WES 未按 step latency 加权，可能 **高估** 前期步数多的 agent 相对 **低估** 长轨迹 agent 的真实时间浪费。
- **环境绑定**：Grounding 在单卡 A6000 + [[SGLang]]；planner 用云端 GPT-4.1——换模型/API/硬件后 planning/reflection 占比可能变化；**无 sensitivity 曲线**。
- **Perception 实验规模**：每应用 1 任务对比 SS / A11y / SoM，**不能**支撑应用级普适结论，作者亦承认 task-dependent。
- **Leaderboard 轨迹复用**：依赖各团队自行发布的轨迹与 $S$ 值；版本漂移、重试策略、hidden tooling 未统一控制。

### 实验可信度

- **Workload**：[[OSWorld]] 369 任务覆盖 Ubuntu 等真实环境、9 类应用——比合成 GUI 更贴近部署，但仍是 **VM benchmark**，非生产用户会话 trace。
- **Baseline**：16 个 SOTA CUA 来自官方 leaderboard，覆盖多种 observation 类型分段（Table 4）——覆盖面好；**缺** 延迟维度的 head-to-head wall-clock 对比实验。
- **Metric**：WES 同时看成功与步数，比纯 success rate 更贴近「可用性」；**缺** TTFT/TPOT 式逐步延迟分位数、token 成本、GPU 占用、美元成本。
- **Ablation**：有 single vs grouped $t_{exp}$、三种 observation 对比；**无**「若砍掉 reflection」「若摘要历史 prompt」等干预实验验证瓶颈假设。
- **可复现性**：承诺开源 OSWorld-Human + raw timing；标注过程双人验证增强可信度。

### 系统性缺陷

- **无解决方案验证**：指出 planning/reflection 为主瓶颈，但未实现 batched actions、history compression、speculative grounding 等 prototype 量化收益。
- **尾延迟 / 交互体验**：未报告 per-step P95/P99 延迟或用户可感知 jitter；40 min 任务中失败恢复、重复 reflection 的开销 **未单独建模**。
- **多租户与成本**：单次任务数十分钟 GPT-4.1 调用的 **API 成本** 论文未讨论；无并发多任务场景。
- **正确性 vs 效率**：WES 对成功任务奖励少步，但未验证「抄近路」是否牺牲鲁棒性（如跳过确认对话框）。
- **运维与可观测性**：未给出 agent 运行时应暴露哪些 latency 分段指标的生产建议（论文定位 benchmark，**论文未讨论** 可观测性集成）。

## 局限与 Future Work

- **局限 1**：深度延迟测量仅 Agent S2 + 37 任务；其他 15 个 agent 只有步数效率，无同等 token/latency 分解。
- **局限 2**：WES 以步数为核心，未纳入 per-step 延迟差异、API 成本、GPU 时间——与真实「端到端分钟数」仍有距离。
- **局限 3**：人类 gold 轨迹主观且样本有限（2 人标注），grouped-action 分组规则基于「同一截图可执行」，与动态 UI（动画、加载）边界情况未系统讨论。
- **局限 4**：Perception 对比（A11y/SoM）每应用单任务，统计功效不足。
- **局限 5**：测量工作识别瓶颈但未验证缓解方案；读者知「plan/reflect 占 75–94%」，不知哪类工程改动能带来多少 × 加速。
- **Future work 1**：在固定 agent 栈上实现 **history 外置 / 摘要 / 分层规划 / 多动作单步输出**，用 OSWorld-Human 同时报 WES 与 wall-clock，闭合「诊断→处方→验证」。
- **Future work 2**：扩展 WES 为 **latency-weighted WES**（按 step 的 measured prefill+decode 加权），或引入 token-dollar 成本项，贴近生产 SLO。
- **Future work 3**：收集 **multi-user 人类轨迹分布**（而非单 gold path），报告 agent 相对人类 P50/P90 步数与时间，而非仅最短路径比。
- **Future work 4**：对 leaderboard 全 agent 做与 §3 同粒度的 **latency profiling**，验证 planning/reflection 占比是否跨架构稳定。

## 相关

- **相关概念**：computer-use agent、GUI agent、agentic loop、Set-of-Marks、accessibility tree
- **同类系统**：Agent S2、[[UI-TARS]]、InfantAgent、Jedi、OpenAI Operator、Claude Computer Use
- **Benchmark**：[[OSWorld]]、OSWorld-Human（本工作）
- **基础设施**：[[SGLang]]（grounding serving）
- **同会议**：[[MLSys-2026]]
- **互补论文**：[[OpenHands-SDK-MLSys26]]（agent SDK 产品化）、[[ADR-MLSys26]]（agent 安全）