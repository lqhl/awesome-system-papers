---
type: paper
name: Acumen
full_title: "Acumen: A Platform for Encrypted and Accountable Collaborative Editing"
authors: [Ryan Cottone, Darya Kaviani, Conor Power, Will Giorza, Evelyn Koo, Natacha Crooks, Raluca Ada Popa]
venue: OSDI
year: 2026
tags: [collaborative-editing, crdt, cryptography, consistency, privacy]
source_pdf: "[[osdi26-cottone.pdf]]"
source_md: "[[osdi26-cottone]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 加密且可问责的协同编辑平台（OSDI 2026）

> **原题**：Acumen: A Platform for Encrypted and Accountable Collaborative Editing

> **一句话总结**：去中心化加密 CRDT 难以同时让新用户验证当前 snapshot、隐藏已删除历史并限制状态增长；Acumen 用 history hash、operation/Treedoc accumulator、placeholder 与二阶 causal-stability garbage collection 提供 confidentiality、fork-causal consistency 和 strong snapshot consistency，并支持 25 用户各 60 WPM、额外 latency 平均少于 1 ms。

## 问题与动机

端到端加密让 cloud server 无法理解或合并 edit；客户端本地维护 CRDT 并广播 encrypted operation 可以保密，却把 malicious client、malicious relay 和新成员 onboarding 变成核心问题。新用户若只收到当前文档，如何确认它确实来自一致 edit history？若收到完整 history，又会泄露已经删除的内容；若永不删 tombstone，storage 和 snapshot size 又随历史无限增长。

Acumen 面向 op-based Treedoc，要求同时满足 confidentiality（含隐藏 edit access pattern）、integrity（fork-causal consistency, FCC）、real-time performance 与 secure dynamic membership。相比 Snapdoc，它将 snapshot consistency 加强为新用户不依赖任何 honest user 在线也可验证，且 snapshot/storage 随当前 document size 而非 edit history length 扩展。

## 关键观察 / 隐含假设

- **观察 1**：Treedoc 把 root-to-node path 放进 operation 会让 ciphertext size 泄露访问位置；连续尾插形成线性 path，Snapdoc 约 1000 edits 时单 update 已达 7 MB（§5.1、图 7）。
  - **依赖假设**：network observer 看不到 plaintext，但能看 message size；timing leakage 明确不在 threat model。
  - **可能失效场景**：若 transport 做全局 padding/batching，path-size side channel 的优先级下降，但带宽开销仍在。
- **观察 2**：constant-space accumulator 可承诺一个用户的 operation set 与 Treedoc node set；snapshot 可用 signed state descriptor 重建各用户历史前缀，而不发送每个 prefix 的原始内容（§5.2.2）。
  - **依赖假设**：collision-resistant hash、signature、PKI 与 secure group messaging 成立。
- **观察 3**：被当前 snapshot 删除、但某旧用户状态尚未看到删除的字符，其原始 data 对最终 `exec` 结果无关，可用 placeholder 验证结构而不泄露字符（§5.2.3）。
  - **依赖假设**：对应 delete operation 必然包含在 missing execution 中，并由 protocol 验证。
- **假设 1**：最多 `n-1` malicious clients，但 snapshot 中至少有一个 honest user 的 state descriptor。
  - **证据强度**：模型前提；若所有当前成员串通，新成员无法区分任意伪造 snapshot。

## 核心方法

每个 operation 带 version vector 与按用户维护的 history hash chain。receiver 检查 causal dependency、sender chain prefix 和 signature，使诚实用户在共同历史上同意状态；恶意 equivocation 会形成永久可检测 fork，即 FCC，而非强制所有 fork 自动合并（§4）。

Acumen 把 Treedoc address 改成固定长度 parent disambiguator，依赖 reliable causal broadcast 保证 parent 先到，消除 variable path size 泄漏。character data 用随机 nonce 与 PRF commitment 绑定，network adversary 只看到固定结构（§5.1）。

snapshot 包含当前 operation/node set、version vectors、history hashes，以及每个用户签名的 state descriptor。descriptor 内的 operation-set accumulator 与 Treedoc accumulator 让新用户从不可信 snapshot 数据重建各用户状态，验证 history hash prefix、missing partial execution 的 well-formedness，并重放到同一 final state（图 3、§5.2）。

为兼顾 edit-history privacy，snapshot 对“旧状态见过 insert、当前状态已 delete”的 node 放无 data/nonce 的 placeholder；verification 证明 missing delete 会消掉它。secure [[Garbage-Collection|GC]] 只有在 operation 对所有用户 causally stable 后才删除 tombstone，并通过第二阶 GC version vector 处理“用户对别人的 stability knowledge 尚不同步”的循环；snapshot verification重放同一 GC 规则（§5.3）。

## 设计取舍

- **恶意安全换 fork permanence**：FCC 能检测并隔离 equivocation，但不会自动修复 fork，成员可能永久无法再协作。
- **snapshot 可验证性换按用户成本**：load time 与 snapshot metadata 近似随 user count 线性增长，因为要验证每个 state descriptor。
- **当前大小扩展换 protocol 复杂度**：GC 不再只是删 causally stable tombstone，还需证明所有 snapshot reconstruction 会得出相同删除集。
- **confidentiality 边界**：不防 DoS 和 timing attack；relay 可任意阻断消息，系统只保证 safety，不保证 availability。
- **适用边界**：实现针对 tombstone-based op CRDT/Treedoc；推广到 rich-text、嵌套 object 或非 tombstone CRDT 仍需新证明。

## 实验与结果

- 在 GCP c2-standard-16、5 用户交替执行 Automerge 论文 trace（182,315 inserts、77,463 deletes）时，Acumen local insert/delete 均少于 1 ms；Snapdoc 到约 850 edits 已接近 200 ms（表 6）。
- Acumen remote processing 主要成本是每 operation 约 `2λ` 次 hash/hashmap accumulator update；GC 占比较小，update size 随历史保持常数，而 Snapdoc 约 1000 edits 后达 7 MB（图 6/7）。
- snapshot sweep 覆盖 1–10 users、0–1000 ops、0%/90% delete；0% delete 时 Acumen load time 相对 Snapdoc 改善约一个数量级，90% delete/低用户时接近两个数量级，1000 edits/90% delete 的 snapshot size 改善三个数量级（图 8）。
- 网络 benchmark 的 2/5/10/25 users latency 分别为 1.03/1.17/1.38/2.7 ms，baseline 为 0.37/0.465/0.51/1.5 ms；扣 baseline 后平均增加少于 1 ms（表 7）。
- 最大 throughput 随用户数从 1340 ops/s（2 users）降到 270 ops/s（25 users），仍远高于 25 users 各 60 WPM 的交互输入需求（表 7）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 固定长度 edit 与 GC 避免随 history 膨胀 | 图 7/8 | Automerge text trace、最多 1000-op snapshot sweep | 强 |
| cryptographic protocol 仍满足 real-time local processing | 表 6、图 6 | 5 users、GCP、单字符 Treedoc edits | 强 |
| 25-user interactive collaboration latency 可接受 | 表 7 | central relay、c2-standard clients、5 ops/s latency test | 强 |
| strong snapshot consistency 与 edit-history privacy 同时成立 | §5.2、图 3、supplemental proofs | formal model、至少一个 honest descriptor、secure PKI/group messaging | 中 |
| storage/snapshot 主要随 current document size 扩展 | 表 1、§5.3、图 8 | tombstone-based Treedoc 与协议 GC | 中 |

## 批判性分析

### 论证链条

论文把 security gap 具体化为 snapshot verification、history privacy 与 GC 的三角冲突，再用 accumulator/placeholder/second-order stability 分别闭合，设计论证清晰。形式安全证明在 supplemental material，正文提供构造与 proof sketch；系统结果支持性能，却不能替代 cryptographic proof audit。

### 假设压力测试

最多 `n-1` compromised 看似强，但 snapshot safety 仍需要 snapshot 中至少一个 honest user。长期离线 user 会拖慢 causal stability 和 GC；malicious user 可保持在线身份却拒绝推进 version vector，形成 storage DoS，论文又明确不防 DoS。大量 churn、revocation 和数百/数千成员会放大 per-user descriptor 成本。

### 实验可信度

与 Snapdoc 和 Automerge 比较、使用真实 edit trace、拆 local/remote/snapshot/network，证据维度合理。不过 snapshot scale 只到 1000 ops，远小于 local trace 的 259k operations；只测 plain character Treedoc 和最多 25 concurrent users，无法代表长文档 rich-text、图片/评论或大型组织。throughput protocol让每用户等待 `N-1` updates，天然随 N 反比，百人规模可能迅速退化。

### 系统性缺陷

系统没有 availability：relay 可 drop/reorder，恶意 member 可 fork 或阻塞 GC。FCC 在检测分歧后缺少 reconciliation、审计归责和成员踢出流程。secure group messaging、key rotation、membership revoke 与 offline device recovery 被作为下层假设，实际集成时可能改变 snapshot/history privacy 语义。

## 局限与后续工作

- **局限 1**：不防 DoS 与 timing leakage，恶意 relay/用户可阻止进展或延迟 GC（§3.1）。
- **局限 2**：snapshot 与 throughput 的 user-count scaling 仍是线性/反比，未覆盖大群组。
- **局限 3**：Treedoc 单字符模型未验证 rich-text CRDT、嵌套对象和 attachment。
- **后续工作 1**：在离线/恶意不确认成员比例、membership churn 与 1–1000 users 上测 tombstone backlog、snapshot size 和 verification p99。
- **后续工作 2**：设计 fork evidence、member eviction 与 safe rejoin protocol，并机器验证不会破坏 history privacy。
- **后续工作 3**：将 accumulator/placeholder GC 移植到 Yjs/Automerge rich-text schema，比较 metadata、merge latency 与兼容性。

## 相关

- **相关概念**：[[CRDT]]、[[Fork-Causal-Consistency]]、[[Cryptographic-Accumulator]]、[[End-to-End-Encryption]]、[[Causal-Stability]]
- **同类系统**：[[Snapdoc]]、[[Automerge]]、[[SUNDR]]、[[Depot]]
- **同会议**：[[OSDI-2026]]
