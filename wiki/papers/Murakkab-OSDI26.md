---
type: paper
name: Murakkab
full_title: "Murakkab: Resource-Efficient Agentic Workflow Orchestration in Cloud Platforms"
authors: [Gohar Irfan Chaudhry, Esha Choukse, Haoran Qiu, Íñigo Goiri, Rodrigo Fonseca, Adam Belay, Ricardo Bianchini]
venue: OSDI
year: 2026
tags: [agentic-workflow, cloud-orchestration, resource-management, slo, llm-serving]
source_pdf: "[[osdi26-chaudhry.pdf]]"
source_md: "[[osdi26-chaudhry]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 云平台中的资源高效 Agent Workflow 编排（OSDI 2026）

> **原题**：Murakkab: Resource-Efficient Agentic Workflow Orchestration in Cloud Platforms

> **一句话总结**：现有平台把 workflow logic、model 选择和硬件部署割裂，Murakkab 用 declarative DAG 暴露跨层 knob，并以离线 profile、SLO-aware optimizer 和在线 reconfiguration 联合选择执行配置，在三类 workflow 与生产规模 trace 下最多减少 2.8 倍 GPU、3.7 倍能耗和 4.3 倍成本且保持所设 SLO。

## 问题与动机

Agentic workflow 往往串并联多个 [[LLM|LLM]]、多模态模型和工具，同一逻辑可使用不同 model、采样参数、agent 数、round 数、tensor parallelism 和 accelerator。LangGraph 等框架却把这些选择与 application logic 写在 imperative program 中，cloud model deployment 又把每次 agent call 当普通独立 API request，workflow、agent 和 hardware 三层各自优化。

这种 silo 让平台无法回答 end-to-end 问题，例如“满足 accuracy 与 latency SLO 的最低成本配置”，也难以在 traffic、resource availability 或 model 更新后联动调整。Murakkab 将 workflow 表达为只含逻辑 task 与 dependency 的 declarative graph，由统一 control plane 决定 component、model、parameter 与 hardware mapping。

## 关键观察 / 隐含假设

- **观察 1**：workflow configuration 的 accuracy、latency、throughput、energy 和 cost 呈强烈非单调 trade-off；放松 accuracy tier 可通过换小 model 或减少 agent/round 带来数量级资源差异（§2.5、图 2–3、§4.2）。
  - **依赖假设**：离线 profile 覆盖的 configuration 与线上 input distribution 足够稳定，profiled accuracy 能代表 deployment quality。
  - **可能失效场景**：prompt/domain drift、tool failure、新模型上线或 dynamic graph 生成超出 profile space。
- **观察 2**：不同 workflow/SLO 的 model request 可被 multiplex 到共享 instance，且 DAG parallelism、CPU offload 与 heterogeneous GPU 选择必须联合考虑（§3、§4.3–4.6）。
  - **依赖假设**：平台同时管理 model、agent 与 infrastructure，有权跨 tenant 合批、迁移和重新 provisioning。
  - **可能失效场景**：第三方 API、数据隔离要求、不同安全域或独立组织拥有各层控制权。
- **假设 1**：用户能把 quality 约束归纳为可离线测量的 accuracy tier，把 latency/cost 约束写成数值 SLO。
  - **证据强度**：中。三种 benchmark 可量化，但开放式 agent task 的 correctness/quality 常缺少可靠 oracle。
- **假设 2**：以历史 trace 预测下一 optimization epoch 的 peak/average load，并保留统一 buffer，足以避免 SLO violation。
  - **证据强度**：中。trace-driven 实验覆盖 load shift，真实 burst、cold-start 与 failure 的尾部更复杂。

## 核心方法

开发者用 logical task、dependency、input/output 和可调 knob 描述 workflow，不固定 model 或 resource。Murakkab 将静态 Video Q/A、multi-round debate 以及按 request 动态构造的 coding pipeline 都转换成可优化 graph；候选配置包含 frame 数、是否 speech-to-text、agent/round 数、model、batch、parallelism 与 CPU/GPU placement。

离线 profiler 测量每个 component/configuration 的 quality、latency、throughput、resource、energy 和 cost，并组合出 end-to-end workflow operating point。optimizer 先按 request 的 accuracy/latency/cost SLO 过滤不可行配置，再以 load、model instance capacity、GPU inventory 和 multiplexing 约束求解 MILP，为每个 workflow–SLO 类别选择配置与 instance 数，最小化 cost 或 energy。

在线 runtime 根据 declarative DAG 调度 ready component，跨 workflow 共享相同 model deployment，监控 demand 与 SLO，并在固定 epoch 重新优化。它优先保留容量 buffer，load 增长时 scale out 或切换配置，resource availability 改变时在 A100/H100 间重映射；对 CPU/GPU 混合组件则利用 DAG overlap，把适合 offload 的 Whisper 放 CPU，同时保留 latency-critical detector 在 GPU。

## 设计取舍

- **profile-guided search**：把巨大 online search 化为可解的配置表与 MILP，代价是 profiling 成本、配置离散化和 stale profile 风险。
- **统一 control plane**：获得 cross-layer/global optimum 和 multiplexing，代价是更大 trust domain、tenant isolation 与 blast radius。
- **周期性 reconfiguration**：短 epoch 更能跟上 demand，却增加 VM/model transition cost；长 epoch 更稳定，却导致 prediction error 和 over-provisioning。实验中 60–180 分钟是所测 trace 的折中区，而非普适常数（§4.7、图 13）。
- **SLO 优先**：保留 buffer 降低 violation，意味着不会总达到理论最低 resource；quality 也仅由 benchmark accuracy 近似。

## 实验与结果

- 在 Azure A100/H100 VM 上，使用 Video Q/A、multi-agent Code Generation、Math Q/A 与 Dynamic Coding Pipeline，并以 production-scale trace 驱动 load；baseline 包括静态 LangGraph 与 autoscaling 版本（§4.1）。
- 单 workflow 中，Video Q/A 在 good accuracy tier 下能耗从 10.6 MWh 降到 3.9 MWh；进一步降至 61.4% accuracy 时成本从最贵配置降至约 $6.9k，约 4 倍差异（§4.2、图 7）。
- Code Generation 从 best 放松到 good accuracy 时，optimizer 换 model/configuration，能耗约降 10.5 倍、成本约降 8.7 倍；这是 SLO trade-off，不是同质量下的纯系统 speedup（§4.2、图 8）。
- 多 workflow、混合 high-accuracy/low-latency SLO 下，per-SLO optimization 后再 multiplex，GPU 数、energy、cost 继续分别下降；相比 state-of-the-art 总体报告最高 2.8×、3.7×、4.3×，并保持指定 SLO（摘要、§4.3、表 2）。
- CPU offload case 中，把 Whisper 移到 CPU、OmDet 留在 1×A100、Gemma 用 4×A100，可用 5 GPU 满足 30 秒 SLO；两者都移 CPU 只需 4 GPU 但违反 SLO（§4.6、图 12）。
- optimization interval 从 20 分钟扫到 6 小时，60–180 分钟在所测 trace 上取得较好 cost/utilization/shortage 折中（§4.7、图 13）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| cross-layer optimization 能显著减少 workflow resource | 摘要、§4、表 2：最高 2.8× GPU、3.7× energy、4.3× cost | 三类 workflow、Azure A100/H100、trace-driven load | 强 |
| per-request SLO 分类优于 workflow-wide 固定配置 | §4.3、图 9：混合 high-accuracy/low-latency request 均满足各自约束 | 两个主 workflow、预定义 SLO tier | 中 |
| CPU/GPU placement 必须联合考虑 DAG critical path | §4.6、图 12：6/5 GPU 满足 30 s，4 GPU offload 违反 | 单 Video Q/A configuration | 中 |
| runtime 能适应动态 GPU inventory 与 load | §4.5、表 3、图 11：0–500 H100 约束下重映射 | trace replay、epoch-level adaptation | 中 |

## 批判性分析

### 论证链条

论文有效展示了 imperative/silo configuration 导致的全局 inefficiency，并让 declarative abstraction、profile database、MILP 与 adaptive runtime 一一回应。最大收益同时混合了系统 orchestration、硬件选择和允许的 SLO/accuracy 差异；其中“同 SLO 下优于 baseline”有意义，但跨 tier 的 8–10 倍数字不能解释为保持相同质量的系统改进。

### 假设压力测试

Murakkab 最适合 provider 拥有整个 stack、workflow 可枚举且 quality 可 benchmark 的 managed cloud。若使用闭源 API、tool latency 高度随机、graph 由 model 自由生成，或 tenant 禁止 multiplex，优化空间会收缩。model/prompt drift 会让 accuracy profile 失效，而平均/peak trace prediction 未必覆盖 correlated burst；错误 profile 可能选择低质量配置却在 telemetry 中不可见。

### 实验可信度

评测包含 multimodal、text、static 和 dynamic workflow、heterogeneous GPU、load/resource sensitivity，覆盖面强；数值也同时报告 GPU、energy、cost 与 SLO。局限是 baseline 主要为 LangGraph 的固定/auto-scaled deployment，缺少对成熟 model-serving autoscaler、workflow-specific hand tuning 与近似 online optimizer 的全面比较。production-scale trace 不等于 production deployment，profiling overhead 和 MILP solve tail 亦未成为主结果。

### 系统性缺陷

统一 control plane 掌握 prompt、data dependency、model assignment 与 tenant demand，论文未深入讨论 privacy、fault isolation、fairness 和 admission control。reconfiguration 涉及 model load/VM allocation，可能分钟级且造成 transient capacity loss；实验把它折算进 interval trade-off，却未给出 provider failure injection。declarative API 也可能限制包含 side effect、transaction 或人类交互的 workflow。

## 局限与后续工作

- **局限 1**：quality 被固定 benchmark accuracy/tier 代理，开放式 agent correctness 与 safety 未覆盖。
- **局限 2**：依赖完整 stack ownership 与跨 tenant multiplexing，第三方 API/隔离场景收益不明。
- **局限 3**：离线 profile 的生成成本、老化检测与新 configuration cold-start 未系统量化。
- **后续工作 1**：注入 model update、prompt drift、tool timeout 和突发 load，测量 profile error 到 SLO violation 的函数并建立自动 invalidation 阈值。
- **后续工作 2**：在相同 SLO 与 hardware budget 下和强 autoscaler/model server 做 head-to-head，分离 multiplexing、model choice、DAG scheduling 各自收益。
- **后续工作 3**：加入 tenant-level isolation/fairness 与 side-effect semantics，用 fault injection 验证 reconfiguration 期间不重复执行 tool action。

## 相关

- **相关概念**：[[Agentic-Workflow]]、[[SLO-Aware-Scheduling]]、[[Model-Multiplexing]]、[[Declarative-Programming]]
- **同类系统**：[[LangGraph]]、[[LlamaIndex]]、[[AutoGen]]
- **同会议**：[[OSDI-2026]]
