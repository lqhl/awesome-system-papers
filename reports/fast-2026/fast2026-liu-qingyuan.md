# Sharpen the Spec, Cut the Code: A Case for Generative File System with SYSSPEC

**作者**：Qingyuan Liu, Mo Zou, Hengbin Zhang, Dong Du, Yubin Xia, Haibo Chen（上海交通大学并行与分布式系统研究所）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/liu-qingyuan
**源文件**：[[fast2026-liu-qingyuan.pdf]]

---

## 一、背景

文件系统是操作系统的核心组件，需要不断演进以适应新硬件特性和应用需求。传统文件系统开发遵循「实现功能 → 修 bug → 维护」的循环，开发者长期陷入低层 C 代码的编写和调试中。作者对 Ext4 从 Linux 2.6.19 到 6.15 的 3,157 个 commit 进行了纵向分析，发现 82.4% 的 commit 用于 bug 修复和维护，仅 5.1% 用于新功能开发。例如 fast-commit 特性初始实现只需 9 个 commit，却引发了约 80 个后续 commit 来修复新引入的 bug 和维护代码。

近年来 LLM 在代码生成领域取得了显著进展，但直接用自然语言 prompt 生成完整、功能正确的文件系统几乎不可能——文件系统的并发正确性、复杂文件结构管理等语义难以用自然语言无歧义地表达。

---

## 二、要解决的问题

1. **规约语义鸿沟**：自然语言 prompt 无法精确表达文件系统的功能正确性、磁盘布局选择、细粒度并发控制等多维语义，导致 LLM 生成的代码存在歧义和错误。
2. **复杂组件组合**：LLM 的有限上下文窗口无法一次性生成整个文件系统，需要模块化生成，但模块间的接口兼容性和演进时的级联效应难以管理。
3. **LLM 能力不可靠**：LLM 的代码生成具有非确定性（hallucination），相同规约可能产生不同且可能错误的输出，朴素的「生成并祈祷」方式不适用于系统软件。

---

## 三、洞察与设计

**关键洞察**：用借鉴自形式化方法的结构化规约（specification）替代模糊的自然语言 prompt，可以为 LLM 提供无歧义的蓝图，从而使生成和演进复杂文件系统成为可能。

基于这一洞察，作者提出 SYSSPEC 框架，包含三层规约和一套 LLM 工具链：

### 三层规约

- **功能规约（Functionality Specification）**：基于 Hoare logic 的前置/后置条件和不变量，定义每个模块的行为语义。根据模块复杂度分为三个层次：简单模块仅需前/后置条件；中等复杂度加上 intent 描述；高度优化的设计需要显式的系统算法描述。
- **模块化规约（Modularity Specification）**：将文件系统分解为满足上下文窗口约束的模块（≤500 LoC），通过 Rely-Guarantee 条件定义模块间接口契约——Rely 声明模块对其依赖的假设，Guarantee 声明模块对外提供的承诺。
- **并发规约（Concurrency Specification）**：将并发逻辑从功能逻辑中解耦，单独定义锁协议和并发行为。代码生成分两阶段：先生成正确的顺序实现，再根据并发规约插入锁操作。

### DAG 结构的 Spec Patch

用于文件系统演进。开发者通过编写对规约的补丁（而非直接修改 C 代码）来添加新特性。补丁组织为 DAG 结构：叶节点是自包含的局部变更，中间节点基于子节点的 guarantee 构建更复杂逻辑，根节点提供语义不变的 guarantee 以原子替换旧实现。

### LLM 工具链

- **SpecCompiler**：将规约翻译为 C 代码，采用两阶段 prompting（先功能后并发）和 retry-with-feedback 循环（CodeGen agent 生成 + SpecEval agent 审查）。
- **SpecValidator**：对完整实现进行全局验证，结合规约审查和传统测试套件。
- **SpecAssistant**：辅助开发者撰写规约，提供自动验证和细化循环。

---

## 四、实现细节

- **SPECFS**：基于 FUSE 的用户态并发内存文件系统，设计参考了经过形式化验证的 AtomFS。共 45 个模块，生成约 4,300 行 C 代码（在 Linux 6.1.10 的 82 个文件系统中排名第 42）。
- 规约使用结构化自然语言 + 类型注解表达（非纯数学逻辑），降低开发者门槛。
- 模块大小限制在 ≤500 LoC，推理 token 消耗约 30K tokens。
- 成功生成的模块实现会被缓存以复用，规约更新时异步触发重新生成。
- 支持外部代码（库）通过 Rely-Guarantee 框架集成。
- 开源地址：https://llmnativeos.github.io/specfs/

---

## 五、实验结果

### 生成准确率（AtomFS 45 模块）

| 模型 | Normal Baseline | Oracle Baseline | SPECFS |
|------|----------------|----------------|--------|
| Gemini-2.5-Pro | ~60% | ~82% | **100%** |
| DeepSeek-V3.1 Reasoning | ~45% | ~65% | **100%** |
| GPT-5-minimal | ~35% | ~55% | ~90% |
| Qwen3-32B | ~25% | ~40% | ~75% |

### Ablation Study（DeepSeek-V3.1）

| 模块类型 | Func only | +Mod | +Con | +SpecValidator |
|---------|-----------|------|------|---------------|
| 并发无关（40个） | 40% (12/40) | 100% | 100% | 100% |
| 线程安全（5个） | 0% (0/5) | 0% | 80% (4/5) | 100% (5/5) |

### 生产力提升

| 任务 | 手动实现 | SPECFS | 加速比 |
|------|---------|--------|-------|
| Extent 特性 | 4.5h | 1.5h | 3.0× |
| Rename 模块 | 13h | 2.4h | 5.4× |

### 特性演进

成功集成 10 个 Ext4 特性（Extent、Inline Data、Multi-block Pre-allocation、Delayed Allocation、rbtree Pre-allocation、Metadata Checksums、Encryption、Logging/jbd2、Timestamps、Indirect Block），均通过 spec patch 实现。

### 性能优化效果

- **Inline Data**：QEMU 源码存储减少 35.4%，Linux 源码减少 21.0%
- **Multi-block Pre-allocation**：不连续读写比例下降约 30%
- **rbtree**：20MB 文件 1000 次写入时 block pool 访问频率下降 80.7%
- **Delayed Allocation**：xv6 编译场景数据写入减少 99.9%

---

## 六、批判性分析

1. **FUSE 用户态限制了评估说服力**：SPECFS 基于 FUSE 运行在用户态，没有存储栈（无直接磁盘访问）、不考虑 crash consistency。论文承认无法与内核态文件系统进行「苹果对苹果」的性能对比，但这也意味着 SYSSPEC 在真实生产环境中的适用性仍未验证。Crash consistency 是文件系统最核心的正确性要求之一，缺失这一维度使得框架的实用价值大打折扣。

2. **准确率评估方法存在偏差**：「生成模块通过所有功能测试 + 人工审查逻辑等价」作为正确性标准，但人工审查的主观性和测试覆盖率的局限性未被讨论。对于声称替代形式化验证的系统，这一评估标准偏弱。

3. **规约编写成本被低估**：论文强调从「写代码」转向「写规约」提升了效率，但 45 个模块的三层规约（功能 + 模块化 + 并发）本身的编写和调试成本未被量化。生产力评估（Tab. 4）只比较了「给定规约后」的开发时间，没有包含规约编写的时间。

4. **AtomFS 作为基准的局限**：SPECFS 复用了 AtomFS 的高层设计和部分 Coq 规约中的条件，本质上是已有形式化工作的「降级重实现」。如果没有 AtomFS 这样的参考设计，从零撰写规约的难度和正确性保障如何，论文未回答。

5. **模型依赖性风险**：在 Gemini-2.5-Pro 和 DS-V3.1 上达到 100% 准确率，但在 Qwen3-32B 上仅约 75%。这说明框架的效果高度依赖模型能力，随着模型更新换代，规约和工具链可能需要持续调整。

6. **10 个 Ext4 特性的代表性**：这些特性被选择性地归为四类，但跳过了 Ext4 中更复杂的特性（如 journal recovery 的完整实现、online resize、quota management）。论文未讨论哪些类型的特性是 SYSSPEC 当前无法支持的。

7. **SpecEval 的验证边界**：论文将 LLM 作为 SpecEval 的验证器，声称「验证比生成简单」，但未提供这一假设的实证支持。LLM 验证器本身也可能 hallucinate，尤其在涉及微妙的并发 bug 时。

---

## 七、AI Infra / MLSys 视角

1. **LLM-driven 系统软件生成范式的启示**：SYSSPEC 展示了用结构化规约引导 LLM 生成复杂系统软件的可行路径。这一思路可迁移到 AI Infra 中的算子编译器（如 Triton kernel 生成）、分布式通信库（如 NCCL 的新 collective 实现）等场景——通过规约定义算子语义和性能约束，让 LLM 生成优化实现。

2. **两阶段生成（功能 → 并发）的通用性**：AI 推理系统（如 vLLM、TensorRT-LLM）中也面临功能正确性和并发性能的双重挑战。将功能逻辑与并发调度解耦的规约思路，可用于自动生成 serving 系统中的 batch scheduler 或 KV cache manager。

3. **Spec Patch 的演进机制**：AI Infra 系统演进速度极快（新模型架构、新硬件），DAG 结构的 spec patch 提供了一种管理系统演进复杂性的方法。可以探索将其应用于 AI 编译器的 pass pipeline 管理或分布式训练框架的并行策略演进。

4. **值得跟进的方向**：
   - 将 SYSSPEC 的规约框架扩展到 GPU kernel 生成，用 Hoare logic 定义 kernel 的正确性约束（如 shared memory 不越界、warp 同步正确性）
   - 探索 spec-guided 的 AI 系统自动调优：用规约定义性能目标（延迟/吞吐 SLO），让 LLM 在规约约束下搜索最优配置

---

## 八、总结

SYSSPEC 提出了「生成式文件系统」这一新范式，通过三层结构化规约（功能、模块化、并发）替代自然语言 prompt 引导 LLM 生成和演进文件系统代码。其原型 SPECFS 在强模型上达到 100% 模块生成准确率，并成功集成 10 个 Ext4 特性。核心贡献在于将开发者角色从编写低层代码提升到设计高层规约，展示了 LLM + 形式化方法思想结合的潜力。主要局限在于仅验证了用户态 FUSE 文件系统、缺乏 crash consistency 支持、规约编写成本未被充分评估，距离替代真实内核文件系统开发还有较大差距。
