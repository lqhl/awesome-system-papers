---
type: paper
name: gigiprofiler
full_title: "Diagnosing Performance Issues in Application-Defined Resources"
authors: [Yigong Hu, You-Liang Huang, Haodong Zheng, Yicheng Liu, Dedong Xie, Baris Kasikci]
venue: OSDI
year: 2026
tags: [profiling, performance-debugging, llm, static-analysis, observability]
source_pdf: "[[osdi26-hu-yigong.pdf]]"
source_md: "[[osdi26-hu-yigong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 诊断应用自定义资源的性能问题（OSDI 2026）

> **原题**：Diagnosing Performance Issues in Application-Defined Resources

> **一句话总结**：gigiprofiler 观察到 buffer pool、UNDO log、query cache 等应用资源的争用不会表现为 OS memory/lock pressure，却可统一为 WAIT/ACQUIRE/USE/RELEASE 事件；它让 LLM 从语义线索提候选、static/dynamic validation 校验并按 request 归因，在五个大型应用的 15 个已知案例中全部把根因排第一，另发现两个获确认的 MariaDB bug。

## 问题与动机

传统 profiler 看 CPU、memory、lock、hot loop，却看不到应用内部的逻辑 resource。MySQL buffer pool 即使被 temporary table/UNDO purge 占满，OS 只看到预分配内存仍正常；受害 query 后续走慢 eviction/I/O path，因果跨 request 传播，热点往往只是症状。

作者研究 45 个真实 issue，resource 分为 memory-like resource、shared state 与 internal queue；根因虽有 contention、policy、allocation、inconsistent state、unbounded growth、leak 六类，87% 可由少量 interaction pathology 表达。诊断工具需要恢复应用语义，同时以代码/运行时证据约束 LLM 猜测。

## 关键观察 / 隐含假设

- **观察 1：四种事件足以表达大多数 resource pathology。** WAIT 暴露慢获取，ACQUIRE/RELEASE 差值反映 size/leak，USE 揭示谁消费；45 cases 中 87% 匹配（表 1、§3.2）。
  - **依赖假设**：resource ownership/quantity 可由事件 count/parameter 近似，异步转交和层级 resource 不会打断 attribution。
  - **可能失效场景**：复杂 admission/priority policy、probabilistic cache、eventual cleanup 或一个 event 同时涉及多资源。
- **观察 2：[[LLM|LLM]] 擅长名字/comment/documentation 的语义召回，static analysis 擅长验证 data/control flow。** LLM 单独 FP 45%–60%，static validation 平均再降 22%，post-profile validation 再降 24%（图 12–13）。
  - **依赖假设**：code metadata 足够描述 resource；validation rule 覆盖实际 API idiom。
- **观察 3：瓶颈应从 aggregate request-resource interaction 统计推断，不应依赖固定完整 event pattern。** 这样可容忍部分 missing/misclassified event（§3.5）。
  - **依赖假设**：profiling workload 触发 bug 且 request ID 能贯穿 thread/async boundary。
- **假设 1：root-cause ranking 第一等价于实用诊断。**
  - **证据强度**：中；15/15 与两个新 bug 很强，但 benchmark 由已知 issue构造，缺少盲测开发者时间。

## 核心方法

offline analyzer 将 file→class/struct→member→function→source 组织成带 comment/name/type/data-dependency 的 DAG。LLM agent 分阶段识别 exclusive/shared application resource 及候选 WAIT/ACQUIRE/USE/RELEASE site；static analysis 用 alias、data flow 与 control flow 检查 candidate 是否真正获取、使用、释放或走 slow path，避免让 LLM 直接修改/判断代码（图 7、9–10）。

LLVM pass 在确认 site 注入轻量 probe，runtime 为每个 request 记录 resource ID、event type、数量/时长和 code path。post-profiling validation 删除从未呈现合理 lifecycle 的候选。diagnoser 从 WAIT duration、ACQUIRE/RELEASE imbalance、resource dominance 与 request correlation 找 bottleneck，再沿 responsible request 的 event/code path 回溯造成资源耗尽或慢 path 的源请求。

MySQL UNDO 案例中，系统看到 purge thread 的 buffer-pool USE 占主导，并由 UNDO ACQUIRE−RELEASE 差值重建持续增长，连接“长事务→巨大 UNDO→purge 占满 buffer pool→其他 query eviction”的跨资源链（图 5–6）。

## 设计取舍

- **semantic recall 换 LLM 成本/不确定性**：不同模型候选覆盖不同，后续 validation 是必要组成而非可选优化。
- **全量事件换诊断分辨率**：平均 runtime overhead 3.7%、最高 7.8%；高频 resource 需 sampling/batching。
- **统一四事件换复杂 policy 覆盖**：87% study case 适配，剩余 13% 无法归入。
- **源码 instrument 换部署便利**：需可编译 LLVM IR 与 request propagation，closed-source/plugin/JIT code 不易覆盖。
- **边界条件**：C/C++ 大型 server、明确 request context 和稳定复现 workload 最适合；async actor、dynamic language 与 distributed resource 会更难。

## 实验与结果

- MySQL、MariaDB、PostgreSQL、Apache HTTP Server、llama.cpp 的 15 个真实 issue 上，gigiprofiler 全部把真实 root cause 排第一，包括三个 multi-root case；平均检测+诊断 95.15s（表 3–4）。
- 额外发现两个此前未知的 MariaDB application-resource issue，均获 developer 确认（§4.2）。
- 五项目 resource-event identification FP 较低，最大 MySQL 为 13.6%；LLM alone FP 45%–60%，static/post-profile validation 分别平均减少 22%/24%（图 11–13）。
- MySQL 与 SyncFinder+PCatch cross-check 中，gigiprofiler 154 events、漏23，FNR 13.0%；对方漏约100个 gigiprofiler event、FNR 66.7%。buffer-pool 339 events/200 functions 的多模型 study 平均漏约23% events和12% functions（表 5）。
- 九个可测案例中 throughput overhead 平均 3.7%、最高 7.8%，来自每 event 写 ring buffer（图 14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 四事件模型能诊断多类应用资源问题 | 表 1/4：45-case study覆盖87%，15/15根因第一 | 五个C/C++应用、复现已知issue | 强 |
| LLM+static analysis 比任一单独阶段更精确 | 图 11–13：LLM FP45%–60%，两级各降22%/24% | 五项目、有限模型与人工ground truth | 强 |
| 工具能发现未知问题 | §4.2：两个MariaDB bug获确认 | 单一项目、数量2 | 中 |
| runtime tracing overhead 可接受 | 图 14：平均3.7%、最高7.8% | 九个case、全量trace、非production长期负载 | 中 |

## 批判性分析

### 论证链条

empirical study→四事件 abstraction→hybrid discovery→runtime attribution 的链条完整，且 LLM ablation 明确证明 symbolic validation 的必要性。15/15 看似完美，但 case selection 都是能复现且属于定义范围的 application-resource bug；不能外推到普通 performance issue 的 overall diagnostic recall。

### 假设压力测试

缺少 comment/naming 时 LLM 漏 event；实际 buffer-pool study 多模型仍漏23%。request 跨 thread pool、callback、message queue 或 background compaction 后，attribution ID 可能断裂。ACQUIRE−RELEASE 长期为正未必是 leak，可能是 intended cache warming；统计需要 workload phase 与 policy 上下文。

### 实验可信度

五个成熟大型应用、15 个 issue、两个新 bug、cross-tool coverage、multi-model ablation 与 overhead，证据扎实。ground truth 主要人工构造/审核，未给 profiler operator blinded diagnosis、误报 triage time 或在无 bug production trace 中的 alert rate。平均95s不含 LLM API成本/编译准备的完整人力。

### 系统性缺陷

源码层 instrumentation 与 LLM hierarchy build 会随版本变化；event schema/agent output 需缓存、审计和 reproducibility。持续全量 tracing 可产生大量数据，ring-buffer drop 对诊断影响未量化。LLM 输入私有 code 还引入模型部署与数据治理风险。

## 局限与后续工作

- **局限 1**：13% empirical case 超出四事件 pathology，dynamic language/distributed resource 未覆盖。
- **局限 2**：event coverage 仍有约23%漏项，正确诊断依赖 workload 恰好经过已 instrument path。
- **后续工作 1**：在 async/distributed server 中传播 causal request ID，以 known-bug recall、misattribution rate 和 trace volume 验证。
- **后续工作 2**：实现 adaptive sampling/batching，在少于1% overhead下比较 root-cause top-1 与 event-loss sensitivity。
- **后续工作 3**：做 blinded developer study，测从报告到确认/修复的 wall time、false-alert dismissal 与对 system profiler 的增量价值。

## 相关

- **相关概念**：[[Performance-Profiling]]、[[Application-Level-Resource]]、[[Causal-Profiling]]、[[Static-Analysis]]
- **同类系统**：[[MySQL]]、[[PCatch]]、[[pBox]]
- **同会议**：[[OSDI-2026]]
