---
type: paper
name: Atropos
full_title: "Mitigating Application Resource Overload with Targeted Task Cancellation"
authors: [Yigong Hu, Yile Gu, Zeyin Zhang, Shuangyu Lei, Yicheng Liu, et al.]
venue: SOSP
year: 2025
tags: [overload-control, slo, resource-contention, cancellation, cloud]
source_pdf: "[[3731569.3764835.pdf]]"
source_md: "[[3731569.3764835]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Atropos：通过有针对性的任务取消来缓解应用程序资源过载（SOSP 2025）

> **原题**：Mitigating Application Resource Overload with Targeted Task Cancellation

> **一句话总结**：Atropos 在 application-resource overload 前取消占用关键资源的 culprit task；在六个 large-scale applications 的 16 个复现场景中，平均 normalized throughput 为 96%，平均 request drop 少于 0.01%，平均 normalized P99 latency 为 1.16（相对各自 no-overload baseline，§5.1–5.3，Fig. 9–11）。

## 问题与动机

云应用常在峰值附近运行，短 spike 可触发 **receive livelock** 或内部资源争用（MySQL table lock、buffer pool）。传统 **admission control**（队列延迟信号）不知哪条请求是 long-hold culprit，误杀大量 victim；**performance isolation**（pBox 等）静态分区在可变 workload 下利用率低、尾延迟高。

研究问题：overload 时如何 **maximize SLO attainment** 且 **minimize drops**？

## 关键观察 / 隐含假设

- **观察 1**：overload 常由少数 long-running culprit 占据关键 application resource，而非总 QPS 超限。
  - **依赖假设**：可度量 per-cancelable-task 的 contention level 与 cancellation **resource gain**。
  - **可能失效场景**：大量中等长度请求集体累积无单一 culprit 时，cancel 策略退化。
- **观察 2**：151 个 surveyed OSS applications 中 115 个（76%）支持 cancellation，其中 109/115（95%）提供 cancellation initiator。
  - **依赖假设**：cancel 语义正确释放锁/缓冲区；无 initiator 的应用需改造或使用粗粒度、默认关闭的 fallback。
  - **证据强度**：中。151 apps survey 支撑，但六案例集成仍手工。
- **观察 3**：cancel culprit 比 deny admission 更少损害 usability，因多数请求仍被服务。
  - **依赖假设**：culprit 识别足够早，在 SLO 大幅恶化前。
  - **可能失效场景**：识别延迟时 cancel 与 admission 效果趋同。

## 核心方法

1. **Cancelable task abstraction**：请求与后台任务统一为可取消单元；归因资源使用。
2. **Application resource abstraction**：统一 contention level + resource gain 指标。
3. **Proactive cancellation**：检测资源将过载时，选 **最大 resource gain** 的 task 取消。
4. **Language hooks**：C/C++/Java/Go；接 MySQL、PostgreSQL、Apache、Elasticsearch、Solr、etcd 现有 cancel API。

## 设计取舍

- **Cancellation vs admission**：保留更多请求进入系统，但牺牲部分进行中工作。
- **Resource-agnostic framework vs app-specific policy**：通用性换精准度，依赖 gain 估计质量。
- **No universal safe cancel**：需应用已有或实现 cancel 逻辑——非透明 kernel 方案。

## 实验与结果

- **Throughput**：16 个复现场景中平均 normalized throughput 为 96%，Protego / pBox / DARC / PARTIES 分别为 50.7% / 53.9% / 36.3% / 37.8%（§5.1–5.2，Fig. 9–10；six applications、Azure VM 16 vCPU/64GB/160GB SSD）。
- **Drop**：平均 request drop 少于 0.01%，Protego 约 25%（§5.2，Fig. 11；同一实验定义与场景）。
- **Latency SLO**：20% latency-increase threshold 下，16 例中 14 例满足；平均 increase 为 10.2%，c3/c12 仍为 23%/26%，且没有策略满足该 threshold（§5.3）。
- **Tracing overhead**：五个 applications 的 normal workload 下 throughput 平均降 0.59%、P99 平均升 0.21%；禁用 cancellation 的 overload workload 下分别为 7.09%/8.12%（§5.5，Fig. 14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Atropos 在复现 overload 场景中保留 96% normalized throughput | §5.1–5.2, Fig. 9–10 | 6 apps；16 scenarios；Azure VM；no-overload baseline | strong |
| Atropos 平均 request drop 少于 0.01% | §5.2, Fig. 11 | 同一 16 scenarios；依论文 drop metric 定义 | strong |
| 20% latency SLO 下仍有两例不达标 | §5.3 | 16 scenarios；c3/c12；cancellation interval 限制 | strong |
| Normal-path tracing overhead 低于 overload-path overhead | §5.5, Fig. 14 | 5 applications；overload test 禁用 cancellation | strong |

## 批判性分析

### 论证链条

「culprit vs victim」motivation case study → resource gain cancel → 16 scenarios metrics，链条在集成应用上闭合。survey 76% 有 cancel API 不等于生产启用质量高——hook 可靠性依应用而定。

### 假设压力测试

- 错误 cancel 可能丢关键写请求——业务可接受性未用户研究。
- resource gain 估计错误会 cancel victim，重演 admission 问题。
- 分布式跨节点锁 overload 需全局视图——论文 focus 单应用实例为主。

### 实验可信度

- 16 real-world scenarios 丰富；六应用跨三语言。
- Baseline 选 Protego/pBox/DARC 合理；需读者查每场景配置公平性。
- 0.01% drop 惊人，需确认是否包含 overload 前已入队请求。

### 系统性缺陷

- 论文未讨论 cancel 后客户端重试风暴。
- Multi-tenant 公平 cancel（同一 culprit 模式）未讨论。
- 对无 cancel API 应用的通用 bytecode 注入未提供。

## 局限与后续工作

- **局限**：依赖 cancel API；gain 估计可能错；分布式全局 overload 有限。
- **Future work**：自动 infer cancel points；跨实例 coordinated cancel；与 admission 混合策略。

## 相关

- **相关概念**：Overload-Control、SLO、Admission-Control、Resource-Contention
- **同类系统**：Protego、pBox、DARC、SIGALRM-based shedding
- **同会议**：[[SOSP-2025]]
