---
type: paper
name: SysSpec
full_title: "Sharpen the Spec, Cut the Code: A Case for Generative File System with SysSpec"
authors: [Qingyuan Liu, Mo Zou, Hengbin Zhang, Dong Du, Yubin Xia, Haibo Chen]
venue: FAST
year: 2026
tags: [generative-file-system, llm-code-generation, formal-methods, file-system, hoare-logic]
source_pdf: "[[fast2026-liu-qingyuan.pdf]]"
source_md: "[[fast2026-liu-qingyuan]]"
---

# Sharpen the Spec, Cut the Code: A Case for Generative File System with SysSpec (FAST 2026)

> **一句话总结**：提出"生成式文件系统"新范式，用 Hoare 逻辑 + rely-guarantee + 显式并发协议三段式 spec 替代模糊自然语言提示，让 [[LLM]] 自动生成完整 FUSE 文件系统 SpecFS；通过 spec patch 增量演化整合 Ext4 的 10 个真实 feature，其中 delayed allocation 在 xv6 编译场景实现 99.9% data write 削减。

## 问题

作者纵向分析 Ext4 自 Linux 2.6.19 至 6.15 全部 3,157 个 commit 发现：82.4% 是 bug fix + maintenance，仅 5.1% 是新 feature；fast commit 这类 4000 SLOC 的功能初始 9 个 commit 后又触发约 80 个后续修复。文件系统进入"长尾维护"状态，开发负担巨大。直接用 LLM 从自然语言生成完整 FS 的尝试都失败：(1) 自然语言难以无歧义表达 invariant、并发协议、on-disk layout；(2) 上下文窗口不够生成完整 FS，模块化又会引入接口失配；(3) LLM 幻觉无法保证生成代码遵循规范。

## 核心方法

SysSpec = 三层规约 + 三 LLM agent + spec-patch 演化。

**Spec 三段式**：
- **Functionality**：基于 Hoare logic 的 pre/post-condition + invariant + system algorithm（性能关键模块）+ intent（自然语言意图）。复杂度分 Level 1-3 决定写多深。
- **Modularity**：rely-guarantee 接口契约保证模块独立开发可组合。
- **Concurrency**：显式描述 locking protocol、ordering，绕开 LLM 难以推断的并发陷阱。

规约用结构化自然语言 + 类型注解书写（不是纯数学逻辑），可读性优于完整形式化方法但语义足够精确。

**Toolchain 三 Agent**：
- **SpecCompiler**：用 two-phase prompting（先 logic 后 concurrency）把 spec 编译成 C 代码。
- **SpecValidator**：rigorous 验证生成代码 + retry-with-feedback 循环自动纠错。
- **SpecAssistant**：辅助开发 spec 本身。

**Spec Patch DAG 演化**：开发者改 spec 而非 C 代码，patch 形成 DAG 结构，toolchain 自动重新生成受影响模块，避免人工管理跨模块 cascading 依赖。

案例 SpecFS：完整 FUSE 文件系统，无人工干预生成 C 实现；通过 spec patch 集成 Ext4 的 extent、delayed allocation、file encryption 等 10 个 feature。

## 关键结果

- SpecFS 在数百个回归测试中达到与手写 baseline 等价的正确性。
- 成功无人工干预重新生成已验证的 AtomFS。
- 复杂操作正确率比 naive prompting 提升至多 34.4%。
- 一条 delayed allocation spec patch 自动重生成相关模块，xv6 编译数据写入降低 99.9%。
- 顺利集成 Ext4 的 10 个真实 feature，验证可演化性。
- 项目开源：https://llmnativeos.github.io/specfs/

## 相关

- **相关概念**：[[Formal-Methods]]、[[Hoare-Logic]]、[[LLM-Code-Generation]]、[[Rely-Guarantee]]、[[FUSE]]
- **同类系统**：Clover（docstring + annotation）、AutoCodeRover（GitHub issue 驱动）、AtomFS（被重新生成的对照）
- **同会议**：[[FAST-2026]]
