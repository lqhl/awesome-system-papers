# Smart Casual Verification of the Confidential Consortium Framework

**作者**：Heidi Howard, Markus A. Kuppe, Edward Ashton, Amaury Chamayou (Azure Research, Microsoft); Natacha Crooks (Azure Research, Microsoft & UC Berkeley)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/howard
**源文件**：[nsdi2025-howard.pdf](../../papers/nsdi-2025/nsdi2025-howard.pdf)

---

## 一、背景

分布式共识协议是构建可靠云服务的基石，但其正确性极难保证。即便是 Raft、PBFT、Egalitarian Paxos、Zyzzyva 等知名协议，事后也被发现存在微妙的 bug。在工业实践中，真实系统往往需要对原始协议进行大量修改（如添加重配置、签名事务、性能优化等），这些修改的组合效应使得正确性验证更加困难。

Confidential Consortium Framework (CCF) 是微软开源的可信云应用平台，驱动 Azure Confidential Ledger 等生产服务。CCF 结合了 TEE（可信执行环境）和状态机复制（SMR），其共识协议从 Raft 演化而来，但已经过大量修改，本质上是一个未经证明的新算法。CCF 的 C++ 实现已有 63 kLoC，持续演进（平均每周合并 16 个 PR），对其进行正确性验证是一个实际而紧迫的需求。

传统的完全形式化验证（如 IronFleet、Verdi）虽然提供最强保证，但要求从头实现，对已有大型代码库不现实。另一方面，传统测试（单元测试、端到端测试）虽然实用，但难以覆盖分布式协议的巨大状态空间。

---

## 二、要解决的问题

1. **未经验证的自定义共识协议**：CCF 的共识协议虽基于 Raft，但经过签名事务、单向消息传递、乐观确认、Express catchup、Check Quorum、自定义重配置等大量修改，已不能简单依赖 Raft 的正确性证明。
2. **形式化文档缺失**：CCF 提供的客户端一致性保证（结合 strict serializability 和 fork-linearizability）相当微妙，缺乏精确的形式化定义，连论文审稿人都容易混淆。
3. **规约与实现脱节**：即使存在 TLA+ 规约，也无法保证 C++ 实现与规约一致。不同团队成员分别编写规约和实现，两者反映了对协议的不同理解。
4. **验证需要融入工程流程**：任何验证方法必须能集成到 CI 流水线中，随代码持续演进，且门槛足够低，让普通开发者也能参与维护。
5. **不能重写已有代码**：63 kLoC 的 C++ 代码库不可能为了验证而重写，验证方法必须适配现有实现。

---

## 三、洞察与设计

**关键洞察**：将形式化规约通过 trace validation 绑定到实际实现上，可以在不重写代码的前提下，系统性地发现规约与实现之间的差异和 bug——这种"smart casual"的混合方法能以合理的工程成本获得接近形式化验证的收益。

基于此洞察，作者提出了 **smart casual verification** 方法，核心架构包含三层：

1. **TLA+ 形式化规约**：
   - **共识规约**（1134 LoC）：17 个 action、13 个变量，描述 CCF 共识协议的所有状态转换，检验 State Machine Safety 等 27 个不变量/性质。
   - **客户端一致性规约**（375 LoC）：2 个变量（HISTORY 和 LOGBRANCHES），高层次描述客户端可观察行为，独立于节点内部状态。

2. **多层次验证**：
   - **穷举模型检查**：对有限状态空间进行完整检查，发现如 election quorum tally 的 bug。
   - **加权模拟**（Simulation）：通过手动降低故障 action 的权重，引导状态探索向前推进，在有限时间内覆盖更多有意义的行为。
   - **Trace Validation**：将实现运行产生的 trace 与 TLA+ 规约进行交叉验证，检查 T ∩ S ≠ ∅。

3. **与 CI 集成**：trace validation 集成到 CCF 的 CI 流水线中，每次提交自动验证，确保规约和实现持续同步。

---

## 四、实现细节

### Trace 收集
- 利用 CCF 已有的场景测试驱动（scenario driver），通过全局时钟确定性地序列化跨节点执行。
- 在实现中添加 15 条日志语句，在无副作用的 linearization point 记录一致状态（消息收发、状态转换）。
- 仅记录空间上恒定的值（如日志长度而非日志内容），编译时可禁用，不影响生产性能。

### Trace Validation 规约（Trace spec, ~400 LoC）
- 复用高层共识规约的 action 定义，但每个 action 仅在 trace 中当前事件匹配时才启用。
- 用 trace 中的值约束后继状态，有效缩小搜索空间。

### 原子性粒度对齐
- **Action 组合**：当实现将多步操作合并为一步（如 piggyback term update on AppendEntries），使用 TLA+ 的 action composition（A·B）使其原子执行。
- **消息丢失建模**：因 trace 不记录消息丢失，将 IsFault action 与 Trace 的 next-state relation 组合。
- **有限 stuttering**：当一个高层 action 对应多个实现事件时，引入不改变高层变量的 stuttering step。
- 将网络模型从 set 改为 multi-set，以处理消息重发。

### 性能优化
- 实现 DFS（深度优先搜索）替代 BFS 进行 trace validation，一致性规约验证从约 1 小时降到不到 1 秒。

### 工程投入
- Trace validation 核心工作约 2 个工程师月（分布在 4 个月内）。
- 一致性规约的 trace validation 仅需 1 个工程师周。
- 共识规约经历 107 次变更，Trace spec 88 次细粒度提交。

---

## 五、实验结果

### 规约规模与状态覆盖

| 组件 | LoC | 变量数 | 状态探索速率（/min） | 总状态数 |
|------|-----|--------|---------------------|---------|
| 共识规约 | 1134 | 13 | — | — |
| 模型检查（共识） | 158 | — | 10⁶ | 10⁸ |
| 模拟（共识） | 69 | — | 10⁶ | 10⁸ |
| Trace Validation（共识） | 369 | — | — | — |
| 实现代码 | 2174 | 25 | — | — |
| 功能测试 | 2579 | — | 10⁵ | 10³ |
| 端到端测试 | 2815 | — | 10³ | 10⁴ |
| 一致性规约 | 375 | 2 | — | — |
| 模型检查（一致性） | 70 | — | 10⁶ | 10⁵ |

规约验证的状态探索速率和覆盖量比实现测试高出数个数量级。

### 发现的 6 个 Bug

| Bug 名称 | 类型 | 发现方式 | 描述 |
|----------|------|---------|------|
| Incorrect election quorum tally | Safety | 穷举模型检查 | 选举 quorum 在配置联合上计数，而非每个活跃配置单独计数 |
| Commit advance for previous term | Safety | 规约对齐 + 模拟 | Leader 可在非当前 term 推进 commit index |
| Commit advance on AE-NACK | Safety | Trace validation + 模拟 | 变量复用导致 AE-NACK 时错误推进 commit index |
| Truncation from early AE | Safety | Trace validation | Follower 可能回滚已提交的日志条目 |
| Inaccurate AE-ACK | Safety | Trace validation | AE-ACK 报告的 index 超出实际 AE 范围 |
| Premature node retirement | Liveness | 模拟 | 节点过早退出共识导致容错能力下降 |

此外还发现只读事务不满足 linearizability（仅满足 serializability），通过一致性规约的 12 步反例在 4 秒内发现。

所有 6 个 bug 均在影响生产之前被发现和修复。

---

## 六、批判性分析

1. **Bug 的实际影响被高估的可能性**：论文声称所有 bug 在"影响生产前"被发现，但同时承认 incorrect election quorum tally bug 在生产中存在期间，运维恰好只执行单节点重配置所以未触发。这说明该 bug 在生产中长期存在但未暴露，验证的价值更多是"防患于未然"而非"紧急救火"。论文对此表述略显模糊，可能给读者一种"差一点就出事"的印象。

2. **Simulation vs. Model Checking 的对比不够充分**：论文提到穷举模型检查在 128 核机器上花费 48 小时才找到第一个 bug，而 simulation 通过加权在合理时间内也能找到 bug。但缺乏系统性对比：哪些 bug 只有穷举才能找到？加权模拟能覆盖多大比例？Q-Learning 自动加权失败的原因也未深入分析。

3. **工程投入的泛化性存疑**：2 个工程师月的 trace validation 投入建立在 CCF 已有完善的场景测试驱动和全局时钟的基础上。对于没有这些基础设施的系统，bootstrap 成本可能远高于此。论文未充分讨论这一前提条件的重要性。

4. **一致性规约的 trace validation 过于轻描淡写**："1 个工程师周"的成本看似很低，但这是在共识规约已充分对齐、TLC 已增强、团队已有丰富经验之后。论文给出的是边际成本而非全量成本，可能误导读者低估初始投入。

5. **缺乏性能影响评估**：论文完全没有讨论 trace validation 对测试执行时间的影响，也没有说明 CI 流水线中的验证耗时。对于"平均每周合并 16 个 PR"的项目，CI 时间是实际的工程约束。

6. **Trace validation 的覆盖率局限**：trace validation 只能验证测试生成的 trace，其覆盖范围受限于测试场景的设计。论文承认初始的 fuzz testing 因"failed to generate interesting behaviors"而被放弃，但未讨论如何系统性地提高 trace 的多样性。

---

## 七、总结

本文提出了 smart casual verification 方法，将 TLA+ 形式化规约通过 trace validation 绑定到 CCF 的 C++ 生产实现上，并集成到 CI 流水线中持续验证。该方法在不重写代码的前提下，以约 2 个工程师月的主要投入，发现了 6 个影响安全性和活性的微妙 bug，全部在生产事故之前修复。论文的核心贡献在于展示了一种务实的工业级分布式系统验证路径：不追求完全形式化证明，而是通过规约-实现的持续对齐来渐进式地提升正确性信心。该方法最适合已有成熟测试基础设施、具备确定性执行能力的系统，对于缺乏这些前提的项目，迁移成本可能显著增加。
