---
title: "LAPS: A Length-Aware-Prefill LLM Serving System"
authors: [Jianshu She, Zonghang Li, Hongchao Du, Shangyu Wu, Wenhao Zheng, Eric Xing, Zhengzhong Liu, Huaxiu Yao, Jason Xue, Qirong Ho]
year: 2026
venue: MLSys
tags: [llm-inference, prefill, scheduling, cuda-graph, disaggregation, multi-turn]
---

# LAPS: A Length-Aware-Prefill LLM Serving System

**作者**:Jianshu She, Zonghang Li, Hongchao Du, Shangyu Wu, Wenhao Zheng, Eric Xing, Zhengzhong Liu, Huaxiu Yao, Jason Xue, Qirong Ho
**会议**:MLSys 2026
**链接**:[MLSys 2026 proceedings](https://proceedings.mlsys.org/paper_files/paper/2026)
**源文件**:[[ec5decca5ed3d6b8079e2e7e7bacc9f2.pdf]]

---

## 1. 背景

现代 LLM 服务栈(vLLM、SGLang 等)广泛采用 **Prefill–Decode (PD) disaggregation** 架构,将算力受限的 prefill 阶段和带宽受限的 decode 阶段拆分到不同实例上,以避免相互干扰,并配合 continuous batching 提升吞吐。这种范式针对 prefill 与 decode 的本质差异已经做了较好的优化。

然而,作者指出:在多轮对话、agent、speculative decoding、token routing、RAG 等真实工作负载中,prefill 阶段本身存在严重的**异构性**——既有冷启动的长 prompt,又有 multi-turn 中追加几十个 token 的短 re-prefill。基于真实数据集 LMsys-Chat-1M 的统计:首轮约 63% 的 prompt 不足 256 tokens,后续轮次中这一比例上升到平均 81%。也就是说,生产环境中绝大多数 prefill 请求其实是**短的、内存受限的 re-prefill**,而非传统理解中的"长 prompt 一次冷启动"。

---

## 2. 要解决的问题

现有 PD disaggregation 隐含一个假设:**所有 prefill 都是 compute-bound 的长序列**。这与多轮对话工作负载的真实特征严重脱节,带来三个具体问题:

1. **Intra-prefill 干扰**:长 prefill(GEMM 主导,compute-bound)与短 (re-)prefill(KV-cache I/O 主导,memory-bound)在同一 batch 中相互拖累。短请求在长 GEMM 之后排队,TTFT 飙升;长请求受短请求大量 KV traffic 的带宽抢占,有效 FLOPs 下降。论文图 1 验证了在 H200 + Qwen2.5-32B 上,混合长短 prefill 时长 prefill 的 P90 TTFT 显著高于纯长 prefill 基线。
2. **HoL blocking 量化**:用 M/G/1 队列模型推导出 head-of-line blocking 项 $\Delta W_{\text{HoL}} = \frac{\lambda p(1-p)}{2(1-\rho)}(S_\ell - S_s)^2$,与并发度和服务时间方差成正比。
3. **CUDA Graph 在 prefill 阶段未被利用**:decode 阶段普遍用 CUDA Graph 减少 CPU 调度开销,但传统 prefill 由于输入长度高度动态,无法套用 Graph。短 re-prefill 实际上序列长度相对稳定,本应能从 Graph 中获益,却因为和长 prefill 共享队列而无法形成稳定的 batch shape。

现有的 length bucketing(Multi-Bin Batching、BucketServe)只优化 batch 内的 padding,不区分 prefill 与 re-prefill,也不解决 compute-memory 干扰。

---

## 3. 洞察与设计

**关键洞察**:

1. **Prefill 阶段不是同质的**:长 prefill 与短 (re-)prefill 在 compute/memory 资源占用上呈互斥关系——前者打满 tensor core,后者打满 HBM 带宽。两者之间是 compute-bound vs memory-bound 的张力,与传统 PD 之间的张力本质相同,因此可以**复用 PD disaggregation 的设计哲学,在 prefill 阶段内部再做一次拆分**。
2. **Re-prefill 的 token 长度天然适合 Graph 复用**:多轮对话中每轮新 token 数量稳定(常见几十个),用 power-of-two 的 (L, B) 桶化后,CUDA Graph 命中率高;而长 prefill 长度高度动态,Graph 无法摊销 capture 成本——这天然要求"短独立成池才能用 Graph"。
3. **存在解析的 compute-memory 边界**:用 $T_{\text{comp}} = \alpha L(L+2H) + \beta L$ 与 $T_{\text{mem}} = \gamma_w L + \gamma_r H$ 两个二次/线性式可以求出 prefill 与 re-prefill 各自的临界长度 $L_m^{\text{prefill}}$ 和 $L_m^{\text{re-prefill}}$,提供一个明确、可在线拟合的分类阈值。

**核心设计——LAPS 系统**:

LAPS 在 PD disaggregation 之上引入第四种调度模式:**prefill batch 的时间/空间 disaggregation**。整体由三层组成:

- **分类层**:每个请求按 $L_p > L_m$ 落入短队列 $Q_s$ 或长队列 $Q_l$。
- **执行层**:
  - **Temporal disaggregation**(单实例):一个 prefill 实例在某个时刻只处理一类请求(短或长),通过时分轮换避免共存。
  - **Spatial disaggregation**(多实例):将 N 个 prefill 实例划分为 $n_s$ 个短池和 $n_l = N - n_s$ 个长池,实例间专门化执行。
- **调度层**:
  - **AWD (Adaptive Wait-Depth) scheduler**(短 prefill):动态维护等待窗口 $W$ 和目标 batch 深度 $D$,直到时间窗到期或深度达标才 dispatch;dispatch 前对齐到最近的 captured Graph shape。SLA-aware 模式下还会取 $\min\{W_{\text{SLA}}, W_{\text{GR}}\}$ 平衡 deadline 与 Graph 复用。
  - **Lightweight Instance-Pressure Controller**(多实例):周期性测量每个实例的 queue backlog、SLA 偏差、GPU 利用率,聚合成池压力 $P_s, P_l$;若超过滞回阈值并过了 cool-down,则迁移一个实例。

```
Request → [L_p > L_m?] → Q_s / Q_l → PLA Scheduler → {Short Prefill Inst, Long Prefill Inst}
                                                ↑
                                       Dynamic allocation (Algorithm 2)
```

LAPS 与现有 PD disaggregation 完全兼容,作为 prefill 侧的"内嵌增强层"。

---

## 4. 实现细节

- **代码规模与基础**:基于 SGLang 扩展约 2K 行代码,部署在 NVIDIA H200 单卡及 8×H200 集群。
- **CUDA Graph capture 设计**:
  - 系统初始化时按 $L \in \{8, 16, 32, 64, 128, 256\}$、$B \in \{1, 2, 4, 8, 16, 32, 64\}$ 笛卡尔积捕获 Graph;
  - 推理时短 prefill 请求 padding 到最近的 (L, B) 桶;
  - 单 graph 大小:7B 模型 228 MB / 14B 240 MB / 32B 277 MB(尺寸对模型 scale 不敏感);
  - 单 graph capture 耗时 8–12 秒,启动开销不可忽略。
- **AWD Algorithm 1**:核心循环是"边累积边估算 deadline 风险",任一请求 slack 低于 $\sigma$ 立即 dispatch;dispatch 后根据实测 fill time 与实际 batch 深度反馈调整 $W, D$。
- **Pressure Controller Algorithm 2**:压力打分 $\psi_k = \alpha q_k + \beta e_k - \gamma u_k$,池间用 P90 robust aggregator,每周期最多迁移一个实例,带 cool-down 防抖。
- **边界系数在线拟合**:运行时采集 $(T_{\text{comp}}, T_{\text{mem}}, L, H)$ 样本拟合 $\alpha, \beta, \gamma_w, \gamma_r$,从而动态更新 $L_m$。

---

## 5. 实验结果

**评测设置**:

| 维度 | 设置 |
|------|------|
| 模型 | Qwen2.5-7B / 14B / 32B |
| 硬件 | 1×H200 (单实例) / 8×H200 (多实例) |
| 数据集 | LMsys-Chat-1M, ShareGPT-4 |
| Baselines | SGLang (PD disagg)、SGLang router (load-balanced)、vLLM (PD disagg) |
| 指标 | RPS、avg latency、P90 latency、SLO violation rate |

**主要结果**:

| 场景 | 指标 | LAPS 收益 |
|------|------|----------|
| 单实例 multi-turn (ShareGPT) | RPS | 比 SGLang 高 ~20% |
| 8 实例 spatial disagg | RPS | 比 SGLang 高 ~33% |
| 单实例 multi-turn | avg latency | 降低 ~20% |
| 单实例 SLO@0.4s | violation rate | 比 SGLang+router 降 ~10%,比 vanilla DP 降 ~30% |
| 8 实例 SLO@0.4s | violation rate | LAPS ~0%,SGLang+router 仍有 4.7% |
| 4P+4D PD 离线蒸馏 | end-to-end time | LMsys -7.3%, ShareGPT -8.3% |
| 高并发 Qwen2.5-32B | prefill RPS | 比 baseline 高 35%(摘要数字) |

**消融关键观察**:

- "仅开 CUDA Graph" 在某些配置下**反而退化**,因为 Graph 选择/启动开销不可忽略;
- "仅开 Disaggregation" 收益中等;
- 两者结合才是大头——disaggregation 让短 prefill 队列形状更均匀,Graph 命中率与 batch 大小双双提升,从而摊销掉 capture 成本。
- Mix-with-decode 模式下 RPS 显著退化,作者据此推断 LAPS 必须配合 PD disaggregated 架构。

**等待窗口 sweet spot**:实测在 6–8 ms 窗口附近,延迟达到最低、吞吐接近峰值;窗口过大反而增加 head-of-line latency。

---

## 6. 批判性分析

1. **摘要里的 "35% throughput 提升" 在正文中缺乏明确归因**。摘要写道"在高并发与混合请求场景下,Qwen2.5-32B prefill 实例 RPS 提升 35%",但 Figure 6 给出的数字是 20%(单实例)/33%(8 实例)RPS 增益。35% 这个数字很难在正文图表里精确对应,有 cherry-pick 单点最佳配置的嫌疑。

2. **离线蒸馏 8% 的收益相对于工程复杂度有些单薄**。Table 2 显示 PD 4+4 配置下 LAPS 仅快 7.3–8.3%,而离线场景没有 SLA 压力、调度复杂度本应更低,这反而暴露了"无 deadline 时 disaggregation 的边际收益偏小"——核心价值仍集中在 SLA-aware 的在线场景。

3. **静态 (L, B) bucket grid 的局限**。Bucket 上限 L=256, B=64,超出的请求 fall back 到普通 kernel。如果工作负载漂移(例如开始大量出现 300–500 token 的中等 prompt),Graph 命中率会显著下降。论文未讨论运行时动态扩展 bucket 集合的代价与策略。

4. **$L_m$ 边界的稳定性问题被略过**。系数 $\alpha, \beta, \gamma_w, \gamma_r$ 用 runtime 样本在线拟合,但论文没有给出:多久重新拟合一次?拟合期间用什么策略?温度/频率波动、并发模式切换会不会导致 $L_m$ 漂移得过快?

5. **Pressure Controller 的反应速度**。Algorithm 2 每个 control 周期最多迁移一个实例并带 cool-down,这意味着面对突发性 workload shift(例如 burst of long prompts)系统需要数个周期才能完成再平衡。论文用稳态多轮对话评测,刻意避开了 burst 场景。

6. **HoL blocking 模型的简化**。用 M/G/1 FCFS 推导 $\Delta W_{\text{HoL}}$ 的前提是 Markov 到达 + 独立服务时间。但多轮对话的请求间存在很强的 session-level 相关性(同一用户的连续 turn),这会改变排队分析的有效性,作者未做敏感性分析。

7. **Cold start 与 warm-up 成本被淡化**。系统初始化时 7×7=49 个 (L, B) Graph × 8–12s/graph ≈ 400–600 秒启动开销,在弹性扩缩容/AB 测试场景下不可忽略。论文一笔带过,未讨论 lazy capture 或预编译加速。

8. **与"智能 router + SLO awareness"的对比缺失**。LAPS 在多实例场景下与 SGLang router 比较,但 SGLang router 是 SLO-unaware 的;一个公平的对比应该是 LAPS vs. SLO-aware router(例如 IntelligentRouter 那条线),但论文没有做。

---

## 7. AI Infra / MLSys 视角

**对 AI Infra 研究的启发**:

1. **"Disaggregation 不止于 phase"**:这篇论文最大的方法论贡献是把 PD disaggregation 的范式从"phase 间"推广到"phase 内"。这个思路可以继续向下推:
   - **Decode 阶段内部** 是否也存在类似的异质性?例如 short-output(分类、tool-call)vs. long-output(CoT 推理),前者对延迟敏感、后者对吞吐敏感,是否值得 decode-side 的二次 disaggregation?
   - **Attention head 维度**:不同 head 的稀疏性、计算密度差异显著,能否做 head-level 的 compute/memory 路由?
2. **L_m 边界的解析建模值得复用**。$T_{\text{comp}}$ 与 $T_{\text{mem}}$ 的二次/线性分解 + roofline 视角,是一个轻量、可在线拟合的"workload classifier"原语,适用于任何混合 compute/memory 工作负载的调度器设计(不限于 LLM)。
3. **CUDA Graph 在动态 workload 下的可用性**:论文证明了"通过限定输入空间(bucketization + 同质化)可以让 Graph 在传统认为不适用的场景里发挥作用"。这对 RAG、agent、tool-using LLM 这类"大量短请求"场景有直接价值。
4. **可迁移到异构硬件**:短 prefill 是 memory-bound,长 prefill 是 compute-bound——这暗示了**异构 GPU 集群的天然分工**:用低算力高带宽的 GPU(例如 GH200 的 LPDDR、AMD MI300 大 HBM)跑短 (re-)prefill,用高 FP8 算力的 GPU(B200)跑长 prefill。这是一个比"全用同型号 H200"更经济的 deployment 方向。

**值得跟进的具体研究方向**:

1. **在线学习的 $L_m$ 与 bucket grid**:用强化学习或 contextual bandit 在线优化分类边界与桶配置,以适应漂移工作负载。
2. **Re-prefill 与 prefix cache 的协同**:re-prefill 的核心特征是"附着于已有 KV 历史",这与 SGLang 的 RadixAttention、vLLM 的 prefix cache 强相关。LAPS 没有讨论 prefix cache hit/miss 对 $L_m$ 的影响——这是一个值得做的 evaluation。
3. **将 LAPS 思路迁移到 RL post-training 推理 rollout**:RLHF/RLAIF 的 rollout 阶段同样混合 short/long prompts,但缺乏 SLA 约束,disaggregation 收益模型会变化。
4. **Burst 工作负载下的快速重平衡**:替换 Algorithm 2 的 hill-climb 为前瞻性 controller(例如 MPC 或基于 forecast 的预测式分配)。
5. **与 chunked prefill 的正交化**:Sarathi-Serve 把长 prefill 切块,LAPS 把长短 prefill 拆开;两者结合时,长 prefill 池内是否还需要 chunked prefill?切块粒度怎么选?

---

## 8. 总结

LAPS 把 PD disaggregation 的设计哲学下沉到 prefill 阶段内部,基于"短 (re-)prefill 是 memory-bound、长 prefill 是 compute-bound"这一可量化的边界,提出双队列 + 时空双模式的 disaggregation 架构,并通过 bucketized CUDA Graph + Adaptive Wait-Depth 调度器把短 prefill 的 batch 效率拉到新高度。在多轮对话工作负载下,LAPS 相比 SGLang 在单实例上获得约 20% RPS 与 20% latency 改进,在 8 实例上把 SLO violation 压到接近零。该工作适用于**真实多轮对话占比高、PD 已 disaggregate**的生产环境;主要局限在于必须配合 PD disaggregation 才能发挥价值、对 burst 工作负载和 workload drift 的鲁棒性论证不足、bucket grid 与 $L_m$ 的在线调整策略仍有打磨空间。
