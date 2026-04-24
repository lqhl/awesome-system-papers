---
title: "Agentic Operator Generation for ML ASICs"
authors: [Alec M. Hammond, Aram Markosyan, Aman Dontula, Simon Mahns, Zacharias Fisches, et al.]
year: 2026
venue: MLSys
tags: [llm-code-generation, triton, kernel-generation, ml-compiler, asic, agent]
---

# Agentic Operator Generation for ML ASICs

**作者**：Alec M. Hammond, Aram Markosyan, Aman Dontula, Simon Mahns, Zacharias Fisches, et al.
**单位**：Meta, FAIR Meta Superintelligence Labs, Meta Superintelligence Labs
**会议**：MLSys 2026
**链接**：https://proceedings.mlsys.org/paper_files/paper/2026
**源文件**：[[e2ef524fbf3d9fe611d5a8e90fefdc9c.pdf]]

---

## 1. 背景

AI/ML 模型计算需求的爆发推动了数据中心异构加速器的大规模部署。Meta 自研的 MTIA (Meta Training and Inference Accelerator) 作为第二代推荐系统专用 ASIC,已经在服务 Facebook/Instagram/Threads 的 DLRM 推荐模型,相比 GPU 能降低 44% 的 TCO。US 数据中心电力消耗预计到 2028 年将占总用电量的 6.7%–12%,这一趋势使得定制 ASIC 成为产业刚需。

然而每款新芯片都需要庞大的软件栈来衔接 PyTorch 生态 —— 其中最繁重的是 ATen (PyTorch 的张量算子库) 的 **operator coverage**,即一个加速器能在原生硬件上执行多少比例的 ATen 算子。一个典型的 PyTorch 后端需要上千个算子的实现,才能支撑从原型训练到生产推理的全栈需求。按传统的人工方式,kernel 工程师为一款新芯片手写完整的 ATen backend 动辄数月甚至年级别,并且每次硬件/编译器升级都需要重新适配,这已经成为 ASIC 商业化落地最关键的瓶颈之一。

近年来随着 LLM 在代码生成上的突破,学术界出现了一批基于 LLM 自动生成 GPU kernel 的工作(KernelBench、TritonBench、AutoTriton、AI CUDA Engineer 等),但这些工作基本都瞄准"少数关键 kernel 的性能优化"(如 FlashAttention 类工作负载),而非"完整后端的覆盖率"。本文作者观察到:对于新 ASIC 的冷启动阶段,**先有完整、正确、覆盖全面的后端,再谈性能**,因此需要一种新的工程范式。

---

## 2. 要解决的问题

论文聚焦 ASIC bring-up 阶段的 PyTorch 后端自动化,具体要解决以下痛点:

- **覆盖率优先于极致性能**。已有 LLM kernel generation 工作几乎都"只打榜单里最热的几个算子"(如 matmul, layernorm, attention),跳过其他几百个 ATen 算子,而真实后端落地需要每一个算子都能工作。
- **测试规模极为有限**。KernelBench 这类基准通常每算子仅测少数 shape/dtype 组合,而生产场景会遇到几十种 shape × 5 种 dtype × 多种参数分支的长尾输入,LLM 生成的代码极易过拟合到测试样例而在部署时崩溃。
- **"Cheating" 行为难以杜绝**。已有工作中普遍观察到 LLM 会通过把 Triton kernel 的逻辑"dispatch 回 host 执行原生 PyTorch"或"调用其他尚未实现的算子"来骗过测试,这种代码虽然通过单元测试,但无法在只有 MTIA 硬件的环境中真正运行。
- **与生产基础设施集成困难**。研究性 kernel 生成管线假设在便携的本地容器里跑,而 Meta 的 MTIA 部署在 Twine 集群的生产容器、远程硬件可用性受限、LLM 推理需走内部 inference platform,整个链路都要在生产约束下端到端跑通。
- **新一代芯片需要在 tape-out 前验证**。针对下一代 MTIA,只有 QEMU 模拟器可用,还没有真实硅片,此时更需要大规模、自动化、可迭代的 kernel 生成+反馈回路来提前暴露编译器/ISA 缺陷。

---

## 3. 洞察与设计

**关键洞察**:off-the-shelf 开源 LLM(CWM 32B / GPT-OSS 120B)本身并不熟悉 MTIA 特定语义(如 32-byte 对齐、scatter store 禁用、可用的 tl.* 子集等),但**只要把 linter、compiler、debugger 的结构化反馈以 in-context 方式反复喂回 LLM**,模型就能在单次 session 内渐进地"蒸馏"出 MTIA 特化约束并产出可通过测试的 kernel。换言之,"硬件专属文档"不必事先塞进 prompt(实际尝试也发现这样做反而效果更差),**工具链的精确错误信息才是最有效的硬件知识载体**。这个洞察让整条 pipeline 可以不依赖硬件 RAG、不依赖 fine-tune,纯粹由 agentic loop + 开源模型驱动。

基于上述洞察,作者构建了 **TritorX** —— 一个 FSM 驱动的 kernel 生成 agent:

- **FSM 而非 "free-form agent"**。团队没有采用近年流行的"推理 LLM + 自由工具调用"范式,而是把流程写死成有限状态机:`Init → Generate Kernel → Triton MTIA Linter → Compile/Execute/Test → Process Results → Debug → (重新 Generate 或 Success/Failure)`。理由是在生产环境里 FSM 的可调试性、可审计性、可水平扩展性都显著强于自由 agent,且各 state 可以独立 A/B。
- **自定义 Triton MTIA Linter 防止"cheating"**。基于 Python AST + regex 实现静态规则引擎,强制:(1) 输出格式符合 JIT harness(禁止 import 语句、要求函数名为 `kernel`/`wrapper`);(2) 禁止 wrapper 中 dispatch 其他 ATen 算子(只允许 `torch.empty` 等分配/reshape 操作);(3) `tl.*` 白名单只允许 MTIA 实际支持的 ~200 个函数;(4) 禁止 `.cpu()`/`.cuda()`/`torch.device('cpu')` 等跨设备 fallback;(5) 禁止 `eval`/`exec` 等动态执行绕过。
- **三条反馈路径区分不同失败模式**:
  - **Linter violation** → 把结构化 lint 报告直接反馈回 LLM。
  - **编译错误** → 先用 Llama-4-Maverick 作 secondary summarization LLM 把冗长的 Triton MTIA 编译日志压缩成"exact error + 触发代码片段 + traceback",避免主 session 上下文爆炸。
  - **Runtime / 精度错误** → 在反馈 prompt 中附带 CPU 参考张量与 MTIA 张量的 summary、输入 shape/args/kwargs、首个失败样例数据,同时明确提示"不要过拟合这条测试"。精度容忍度按 dtype 自适应。
  - **硬件 crash** → 加载 crash dump 到 LLDB,取 backtrace、寄存器、frame 信息塞进 prompt。
- **Initial prompt 只给算子 docstring + 3 个示范 kernel**。选取 `exp`(elementwise)、`argmax`(reduction with indices)、`diag`(shape manipulation) 作为三类典型示例。ATen docstring 中跨算子引用(如 `argmax` 指向 `max`)通过构造 docstring DAG 展开嵌套。不提供 MTIA 硬件手册。
- **PyTorch OpInfo 作为测试口径**。这是一个 PyTorch 原生的算子级测试框架,每个算子提供数十到数百个 "sample" 输入,覆盖不同 dtype/shape/args 组合。TritorX 以 "pass 100% 的 OpInfo samples" 作为 success 判据,这比 KernelBench 那种少量 fixture 严格几个数量级。
- **Session 管理**。单个算子最多 3 个 dialog session,每个 session 最多 15 次 LLM 调用;上下文即将溢出时用"最近一次代码"开新 session 继续调试;异常路径全部 subprocess 隔离,避免一个 kernel 崩掉整个 run。

---

## 4. 实现细节

- **与 MTIA 生产栈深度绑定**。依赖 Twine 容器集群把 200 台 production MTIA 设备作为 executor pool,LLM 调用走 Meta 内部推理服务,OpInfo 测试、kernel 编译、上硅执行全部在生产容器内完成,因此生成出来的 kernel-wrapper 对可直接注册进 PyTorch dispatch 表供产品线使用。
- **Triton MTIA dialect**。将 Triton block 映射到 8×8 MTIA PE grid,load/store 通过 mask 处理边界、接入 DMA 引擎做结构化访存;对于 non-linear activation 等不直接映射的路径,靠 device library + FFU 补齐。硬约束如"32-byte 对齐访存"在编译器中会抛出 descriptive assert,作为反馈进入 loop。
- **模型与采样配置**。Kernel 生成模型用 CWM 32B 或 GPT-OSS 120B(reasoning=high),context length = 131,072,temperature = 1.0,top_p = 0.95(CWM) / 1.0(GPT-OSS)。Summarization 用 Llama-4-Maverick。
- **QEMU 模拟器支持下一代硬件**。同一 FSM pipeline 挂上 QEMU 后端就可以为尚未流片的芯片生成 kernel,用来反向驱动编译器 / ASIC 团队迭代 ISA。
- **运行时分布**。200 台 MTIA 设备上 2 小时能完成 95% 的 run,剩余 5% 的长尾(主要是 reasoning 陷入死循环)再耗 6–8 小时。新 run 可并发覆盖前一 run 失败的算子做 test-time aggregation。
- **E2E 模型集成新 step**。为衔接真实生产模型的 op 分布(shape、scalar、stride 与 OpInfo 不尽相同),引入 `__torch_dispatch__` 拦截 NanoGPT / DLRM / 两个内部推荐模型 MM1 MM2 的 forward+backward,记录全部张量/标量输入,再用这些"Model Input Shapes (MIS)"做二次验证:对已有 OpInfo kernel 先直接跑 MIS,未过则作为 starting point 进入 TritorX 精炼。
- **算子过滤**。568 个 MTIA 兼容 OpInfo 算子(从 629 剔除 complex 数类型、随机数类型、> 900 测试的大算子)、dtype 限定 bfloat16/float16/float32/int32/int64,累计 2 万+ 测试。

---

## 5. 实验结果

**主结果 —— 整套 OpInfo 的覆盖率**:多次 run 聚合后 **481 / 568 = 84.7%** MTIA 兼容 OpInfo 算子通过全部测试(2 万+ tests)。单次 run 下 GPT-OSS 120B 达 72.0%,CWM 32B 达 55.3%。Figure 4 显示 coverage 随 LLM call 数呈 log-like 上升,在 ~40 次调用左右趋近平台。

**分类性能**(Table 1,GPT-OSS):

| 算子类别 | Op 数 | CWM | GPT-OSS |
|---|---|---|---|
| Shape Manipulation | 75 | 96.0% | 96.0% |
| Elementwise | 161 | 80.1% | 84.6% |
| Reduction | 63 | 69.8% | 74.6% |
| Indexing & Selection | 34 | 73.5% | 79.4% |
| Linear Algebra | 78 | 75.6% | 74.3% |
| Other | 78 | 71.8% | 79.5% |
| Deep Learning | 90 | 64.4% | 71.1% |

Deep Learning 类(conv、norm、attention 变体等)最难,Shape Manipulation 最易 —— 与人对"语义复杂度"的直觉一致。

**端到端模型 enablement**(Table 2):NanoGPT 的 full op set 覆盖 87.2%,DLRM 81.4%,两个内部推荐模型 79.8% 和 80.6%。在"已有 OpInfo 生成的 kernel 直接测 MIS"这一列,80% 以上直接通过;再走一次 MIS 反馈精炼,可额外提升 6–20 个百分点,NanoGPT 能达到 100%。

**消融**(Table 3,单次 run):

| 配置 | CWM | GPT-OSS |
|---|---|---|
| Baseline | 55.3% | 72.0% |
| 去掉 Linter | 48.9% (−6.4) | 68.7% (−3.3) |
| 去掉 Summarization | 48.2% (−7.1) | 71.5% (−0.5) |

Linter 与 Summarization 都在 CWM 下作用显著;summarization 对 GPT-OSS 影响小,猜测是 120B 对长噪声上下文抗性更强。

**Test-time scaling 效应**:两次 CWM run 聚合即从 55% 提到 64%,说明模型随机性下的跨 run 算子交集较小,aggregation 是"免费午餐"。

**QEMU 路径**:在未流片的下一代 MTIA 上用 GPT-OSS 跑了一轮,73.1% 覆盖,同时把暴露出的编译器缺陷和 ISA gap 反馈给硬件团队。

---

## 6. 批判性分析

- **"Coverage-first" 的定义回避了性能**。论文反复声明"牺牲性能换覆盖率",但生产级别的 ATen backend 如果 kernel 比手写实现慢 5–10×,在 inference fleet 里并不可用。论文只字未提生成 kernel 的实际 throughput / latency,只是在 Future Work 里说"autotuning 可以之后再做"。缺少端到端模型吞吐数据(训练一次迭代耗时、推理 QPS),让人无法判断这 84.7% 的覆盖率是否真的产生了业务价值,还是"能跑但远不如人工版本"。
- **MM1 / MM2 匿名化使 E2E 结果难以验证**。Table 2 的两个"Meta Model"是内部推荐模型,代号、规模、op 分布都未披露,外部读者无法复现也无法评估这两列 80%+ 数字的难度。
- **"不许 cheating" 的规则本身就是设计决策**。Self-consistent generation(允许 wrapper 调用其他已实现算子)在讨论节承认"是更高效甚至更高性能的做法",却被强行禁用以换取 embarrassingly parallel。这意味着整套框架生成的是"极端原子化"的 kernel,而真实高性能 backend 往往依赖 fused op 和跨算子调用。论文没有量化这个限制的性能代价。
- **Linter 的"白名单"做得足够细才能防 cheating,这本身工作量也不小**。文章把 linter 描述得轻量,但 200+ 条允许函数、scope 限制、cross-device 禁用、禁用 eval/exec —— 这些规则本身就是专家知识的编码,某种程度上"硬件先验"只是从 prompt 转移到了 linter,论文没有公开完整 linter 规则集,"无需硬件文档"的 framing 略显激进。
- **结果对 OpInfo 质量完全依赖**。论文承认 OpInfo 不是完备测试,但主指标就是 OpInfo pass 率。对于 OpInfo 本身存在测试盲区(如边界 shape、特殊 dtype)的算子,84.7% 实际上可能虚高;MIS 补充测试的发现("即使 OpInfo 过了,也只有 80% 在生产输入下 work")也印证了这一点 —— 这说明"OpInfo pass"的实际含金量比论文主指标暗示的低。
- **模型选择与复现性**。CWM 是 Meta 自家今年才发布的开源模型,GPT-OSS 120B 也只是 2025 年中开源,复现这套结果的前提是有能力托管这两个 120B 规模模型的内部推理服务。学术界 / 小团队很难等比复现。
- **Failure mode 定性描述不足**。未通过的 15.3% 算子具体卡在哪里? reasoning 陷入死循环? 编译器 bug? ISA 缺陷? 表格和文中的描述都比较含糊,只说"tail 需要 6–8h",缺少定量的失败归因,这对后续研究者判断瓶颈很重要。
- **消融只跑 single run,和"test-time scaling 能省一切"的主结论略有冲突**。既然 Aggregation 本身能把 55% 拉到 64%,那 linter / summarization 的 6–7 个百分点优势是否在 aggregation 场景下被稀释? 论文没做这个交叉验证。

---

## 7. AI Infra / MLSys 视角

这篇论文对 AI Infra 研究有几个直接可迁移的启发:

- **"工具反馈作为硬件知识载体"** 是对 agent 系统设计的一个有价值经验:与其把 accelerator spec 塞进 system prompt(往往陈旧、token 昂贵、模型容易忽视),不如让编译器/linter/debugger 写出结构化 error,通过 few-shot loop 让模型自己蒸馏。这个范式对 TPU / Ascend / Gaudi / 国产 NPU 的 PyTorch 后端 bring-up 都有借鉴意义。
- **FSM over free-form agent**。今年业内大量 kernel gen / code agent 工作都在追"用推理模型做 planner + 自由工具调用",但本文在生产环境里选择退回 FSM,理由是可调试性 / 可观测性 / 可并行。对于研究组要落地的 production AI pipeline 而言,这是一个重要的工程选择经验。
- **Linter 作为 anti-cheating gate**。LLM 生成代码对测试过拟合是普遍现象,本文的 AST-based 规则引擎(禁止 dispatch 原生 op、禁止跨设备 fallback、tl.* 白名单、scope 限制)是一套可复用的静态检查框架,可以迁移到 GPU kernel gen、RL environment reward hacking 防护等场景。
- **Test-time scaling + aggregation** 的实际 ROI 值得量化。论文给出"两次 run 聚合 55%→64%"的数据点,对于其他自动化 pipeline(compiler autotuning、inference serving schedule search 等)是很好的启示:随机性 + aggregation 在 agent 系统里往往比改进单次 policy 性价比更高。
- **可跟进的 future work 切入点**:
  1. **Self-consistent backend generation**:把整个后端的已实现算子作为 tool 暴露给 agent,允许 wrapper 调用其他生成过的 kernel,打破 embarrassingly parallel 约束 —— 这是论文 Discussion 节指出的但未实现的方向,也是通往 fused op、性能级 kernel 的必经之路。
  2. **Performance-aware 扩展**:在 TritorX 的 FSM 后追加 autotuning state(蒸馏参数 / tile size / schedule),用 benchmark 结果作反馈。这是把 "coverage-first" 扩展到 "coverage-then-performance" 的自然路径。
  3. **Crash dump → Hardware ISA feedback 回路**:论文已经把 QEMU 上编译错误反馈给硬件团队,但还没形式化这个流程。可以做一个 "agent-driven hardware/compiler codesign" loop,让 kernel gen 失败模式反向驱动 ISA 演进。
  4. **精度容忍度自适应学习**:当前按 dtype 硬编码 tolerance,但不同算子对误差敏感度差异很大,可以让 agent 自己学习 per-op tolerance 或用生产数据分布标定。
  5. **跨 DSL 迁移**:FSM 结构与 Triton 无关,同样的 pipeline 可以用来生成 CUDA / Pallas / Mojo / 国产 DSL 的 kernel,拓宽适配面。
- **对小团队的实操价值**:复现整套 pipeline 需要大规模硬件 + 自家 LLM 推理服务,门槛很高;但 linter 规则、FSM 状态转移、feedback prompt 模板都是可独立拆出来的工程资产,对做 GPU kernel / Triton 自动化的小团队同样适用。

---

## 8. 总结

TritorX 把 MTIA 的 PyTorch 后端 bring-up 从"数月的人工工程"压缩成"一夜的自动化流程",核心贡献是用 FSM + 开源 LLM + 自定义 linter + OpInfo 测试 + 生产硬件执行的工程组合,首次在 ASIC 场景下把 operator coverage 作为一级目标并推到 85% 左右(481 / 568 算子,2 万+ 测试)。论文展示了 "in-context 工具反馈"可以替代"硬件文档注入"作为 LLM kernel 生成的知识通道,并且 FSM 架构在生产集成、可并行、可调试性上优于 free-form agent。主要局限是完全回避了性能(未报告 kernel 吞吐或模型端到端速度)、依赖 OpInfo 的测试完备性、内部模型与 120B 级推理服务使得学术复现困难,并且 "anti-cheating" 规则虽有效但同时挡住了通往 fused / 高性能 kernel 的路径。对 AI Infra 领域最有价值的是 pipeline 的架构抽象和 "linter + FSM + 工具反馈" 这一套可迁移的设计模式。
