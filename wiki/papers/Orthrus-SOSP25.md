---
type: paper
name: Orthrus
full_title: "Orthrus: Efficient and Timely Detection of Silent User Data Corruption in the Cloud with Resource-Adaptive Computation Validation"
authors: [Chenxiao Liu, Zhenting Zhu, Xiangyun Deng, Youyou Lu, Harry Xu, Quanxi Li, Yanwen Xia, Yifan Qiao, Tao Xie, Huimin Cui, Zidong Du, Chenxi Wang]
venue: SOSP
year: 2025
tags: [silent-data-corruption, cloud-reliability, mercurial-cores, validation, fault-detection]
source_pdf: "[[3731569.3764832.pdf]]"
source_md: "[[3731569.3764832]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Orthrus：通过资源自适应计算验证有效、及时地检测云中的静默用户数据损坏（SOSP 2025）

> **原题**：Orthrus: Efficient and Timely Detection of Silent User Data Corruption in the Cloud with Resource-Adaptive Computation Validation

> **一句话总结**：mercurial CPU 可在不崩溃情况下静默 corrupt 用户数据；Orthrus 对 cloud app **data path** 闭包异步重执行验证（versioned memory + 采样调度），生产级开销 2–6%、1 核验证即可检测 87% 注入 SDC，4 核达 96%。

## 问题与动机

Google/Alibaba 等报告 **mercurial cores**：安装后仍可能出现 instruction-level 静默错误，导致 **silent user data corruption (SDC)**——比 crash 更糟（违反 SLA、监管风险）。离线 fleet test 无法实时保护用户数据；[[RBV]]（>100% 资源）与 [[ILV]]（~50× 慢）不适合生产。

Insight：典型 cloud app 有清晰 **control path vs data path** 分离；data path（map/reduce、KV insert/read）逻辑简单，可 selective re-execute 验证。

## 关键观察 / 隐含假设

- **观察 1**：SDC 多发生在 data path 算子；control path 可用 checksum 在进出 data path 时验证用户对象完整性。
  - **依赖假设**：开发者愿用 annotation 标注 user-data types 与待验证 closures。
  - **可能失效场景**：业务逻辑与 data path 边界模糊时 annotation 负担高或漏检。
- **观察 2**：静默错误 **高度可复现** 且与特定指令类型相关，使采样验证仍有效。
  - **依赖假设**：同一 operator 多次执行结果应一致；fp/vector 等指令优先验证。
  - **可能失效场景**：真随机或 intentionally nondeterministic 算子不适用。
- **观察 3**：异步 out-of-order validation + versioned memory 可 decouple APP/VAL，维持 ~4% 开销。
  - **依赖假设**：versioned shared user-data space 开销可控；多核 dedicatable 给 VAL。
  - **可能失效场景**：极高 write churn 下 version chain 内存膨胀——论文未充分公开上限。

## 核心方法

1. **Annotations + compiler**：标记 user-data class 与 data-path closures；编译器插入 logging primitives。
2. **Versioned memory**：APP/VAL 分进程，共享 versioned user-data；写产生新版本。
3. **Validation log**：记录 input/output/版本地址；VAL 在不同 core 重放 closure 并比对。
4. **Sampling scheduler**：按可用 core 动态调采样率；优先久未验证算子与高 risk 指令；队列化 logs。
5. **Detection policy**：SDC 检测到即 **abort application**，防止坏数据返回客户端。

## 设计取舍

- **Best-effort detection vs guaranteed coverage**：生产可行，非形式化验证。
- **Sampling vs full validation**：资源自适应，但低 core 时漏检 13%+。
- **Abort on detect vs repair**：简单安全，但可用性冲击。
- **Annotation burden vs transparency**：需开发者参与，非完全自动。

## 实验与结果

- 四 real-world cloud applications；LLVM 注入 mercurial-style faults。
- Time overhead **~4%**（abstract 亦报 2–6%）；比 RBV **1.9×** faster；validation latency **40μs** vs RBV 高三数量级。
- SDC detection：**87%**（1 VAL core）→ **91%**（2）→ **96%**（4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Orthrus replays annotated data-path closures | APP/VAL split and versioned shared data (§3) | annotated data paths, not full control-path replay | high |
| End-to-end overhead is low in four app tests | abstract 2–6%; Phoenix under 2%, LSMTree 95% vanilla (§4.2, Fig.6) | LLVM-instrumented four applications | high |
| Validation latency is lower than RBV in listed workloads | Memcached 1.6µs vs 90µs; Phoenix 234 vs 513ms (§4.3, Fig.8) | completion-to-validation metric, four apps | high |
| Sampling detects most injected errors on one validator core | average 86.7%, 1.41× random (§4.4, Fig.9) | LLVM injected SDC coverage, not fleet error rate | high |
| Resource-sufficient coverage remains below RBV | 97.2–98.9% vs RBV 98.3–99.8% (Table 2) | production-unrealistic core-equivalent upper bound | high |

## 批判性分析

### 论证链条

「data path 可重放 + 错误可复现 → 异步 VAL + 采样」→ 注入 fault 检测率，在 annotated apps 上闭合。到未标注 legacy monolith 的外推需重新设计 data path 提取。

### 假设压力测试

- 只覆盖 annotated operators；control path bug corrupt 用户数据的路径可能漏检。
- 检测后 abort 在在线服务可能过于激进——论文未讨论降级模式。
- 注入 fault 基于历史 pattern，未知 fault model 可能逃逸。

### 实验可信度

- 四应用 + 与 RBV/ILV 对比合理；注入方法可追溯文献。
- 缺少真实 mercurial core 现场 case study（伦理/隐私可理解）。
- 4% overhead 在极端 QPS 下是否仍成立需更多点。

### 系统性缺陷

- 论文未讨论 VAL 自身运行在 mercurial core 上的信任问题。
- Multi-tenant 下 VAL core 分配公平性未讨论。
- 与 ECC/芯片级 RAS 特性协同未述。

## 局限与后续工作

- **局限**：annotation 必要；best-effort 覆盖；detect-then-abort；注入评估为主。
- **Future work**：自动 data path 提取；分级响应（quarantine vs abort）；与硬件 RAS 联动。

## 相关

- **相关概念**：Silent-Data-Corruption、Mercurial-Cores、Cloud-Reliability、Replication-Based-Validation
- **同类系统**：RBV、ILV、checksum-only 方案、Google fleet testing
- **同会议**：[[SOSP-2025]]
