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
last_reviewed: 2026-08-14
---

# Acumen：加密、可问责的协同编辑平台（OSDI 2026）

> **原题**：Acumen: A Platform for Encrypted and Accountable Collaborative Editing

> **一句话总结**：Acumen 在不信任 relay、最多 `n−1` 个客户端恶意的模型下，用 history hash、签名 state descriptor、Merkle accumulator、placeholder 和基于因果稳定性的二阶 [[Garbage-Collection|GC]]，让新成员不拿完整明文历史、只靠当前 snapshot 的状态与证明元数据，就能验证它精确来自某个 fork-causally consistent execution，同时不看到已删除字符；代价是 fork 不会自动修复、GC 依赖成员推进，以及 snapshot 验证成本随成员数增长。

## 问题与动机

端到端加密（end-to-end encryption）让服务器看不到文档内容，也就不能像传统 Google Docs 那样在服务器端合并编辑。一个自然方案是：客户端各自维护 operation-based CRDT，编辑操作加密后经 relay 广播，所有合作者本地执行。这能处理并发，却留下三个互相牵制的问题：

1. **恶意参与者可以 fork。** Relay 或客户端可以把互相矛盾的更新发给不同人；普通 CRDT 的 eventual consistency 不保证面对 Byzantine 行为仍安全。
2. **新成员不能盲信 snapshot。** 邀请者可能只发文档的一部分或伪造当前状态。若新成员下载并重放完整历史，虽然能验证，却会看到已经删除的草稿内容，成本也随历史长度 `E` 增长。
3. **Treedoc tombstone 不能随便删。** 旧客户端可能还会引用已删除节点为 parent。永久保留 tombstone 又会让 local state、edit 和 snapshot 越来越大。

Acumen 选择单字符 Treedoc 作为底层 operation-based CRDT。每个插入节点有 `(user ID, counter)` disambiguator，文档是树的 inorder traversal；删除先把节点变成 tombstone。系统目标是同时提供内容与在线 edit access-pattern confidentiality、fork-causal consistency（FCC）、strong snapshot consistency、邀请后的 edit-history privacy，以及按当前文档大小 `D` 而非累计历史 `E` 扩展的 storage/snapshot。

## 威胁模型与保证边界

- Relay 是主动恶意的，可以丢弃、延迟、重排或选择性转发消息；最多 `n−1` 个客户端也可以任意偏离协议。
- 系统假设可信公钥基础设施（PKI）和安全 group messaging 已经存在。Acumen 是其上的文档一致性层，不负责设计组密钥协议。
- 系统不防拒绝服务（DoS），也不防“某人在什么时候编辑”的 timing attack。Relay 能阻断进展，恶意成员也能拖住 GC。
- FCC 的含义是：诚实用户在共同因果历史上的状态一致，且不会同时接受同一恶意用户产生的两个冲突分支。发现 equivocation 后，两边会永久拒绝对方分支；这是安全隔离，不是自动 reconciliation。
- Strong snapshot consistency 要求 snapshot state **精确等于** 从空状态执行某个 FCC execution 的结果。Snapdoc 的 weak notion 允许 adversary 给正确状态的任意子集，Acumen 不允许这种遗漏。
- Edit-history privacy 只保证新邀请者看不到 snapshot 前已删除字符，除非它与一个早先已有访问权的客户端串通。它不隐藏 snapshot 前 Treedoc 结构所泄露的因果/访问模式。

## 关键观察 / 隐含假设

- **观察 1：每个用户一条 history hash chain 足以约束部分有序 DAG。** Operation 携带 version vector 和各用户当前 history hash；接收者只有在已处理所有 causal dependency、sender counter 正好连续且所有 hash prefix 相符时才接受（§4.1–4.2、图 2）。
  - **设计含义**：同一用户 equivocate 会形成不可合并的 hash 分支，诚实用户不会跨分支接受操作。
  - **边界**：FCC 阻止 silent merge，不负责决定哪一支是“正确历史”，也不提供恢复协议。
- **观察 2：强 snapshot 不需要把完整历史都发给新用户。** 每个旧用户已经签名的 state descriptor 可以承诺它见过的 operation set、Treedoc set、version vector 和 history hash；新用户从不可信 snapshot 重建这些状态，再对 accumulator root，即可检查是否漏项或改项（§5.2）。
  - **依赖假设**：signature、collision-resistant hash、PRF、PKI 与 secure group messaging 都安全；snapshot 列出的用户中至少有一个诚实用户。
- **观察 3：将来必被删除的旧字符不影响最终 `exec` 结果。** 若旧用户见过 insert、尚未见到 delete，而当前 snapshot 已见到 delete，新用户验证旧状态时只需保留位置和 commitment，不需要原字符（§5.2.3）。
  - **设计含义**：用 placeholder 代替字符，再验证 missing execution 中确实存在相应 delete。
- **观察 4：Treedoc 不必在每个 edit 中发送完整 root-to-node path。** 因为协议本来就要求 reliable causal broadcast，parent 必须先到；edit 只带固定长度 parent disambiguator 即可（§5.1）。
  - **效果**：消除 ciphertext size 随 path depth 变化的 side channel，也避免 worst-case `O(E)` edit。
- **观察 5：内节点 tombstone 可以无共识异步 flatten，但条件很严格。** 只有 node 与 parent 都是 causally stable tombstone（CST）时，未来 insert 才不会再引用 parent，压平边才不会改变并发插入位置（§5.3.2）。
- **假设 1：成员数可视为常数。** 表 1 的 `O(D)` storage/snapshot 明确把用户数当作 `O(1)`；实际 metadata 和 verification 仍随 user count 近似线性增长。
- **假设 2：所有成员最终推进 version vector。** 离线或恶意成员若长期不确认，local causal stability barrier 不前进，tombstone 与 secondary state 无法及时回收。

## 核心方法

### 1. 用 version vector 与 history hash 实现 FCC

每个用户维护 operation set、Treedoc、version vector 和“每个用户一条”的 history hash。用户 `u` 的第 `n` 个 operation 把 operation hash 与 `HH(u,n−1)` 再哈希，得到 `HH(u,n)`。接收 operation 时，客户端验证：

1. 非 sender 分量的 causal dependency 都已处理；sender counter 恰好比本地多 1；
2. sender 的上一项 history hash 与本地一致；
3. operation 携带的其他用户 history hash 都等于本地对应 prefix；
4. operation 的认证信息有效。

Operation hash 不是直接哈希字符。每条操作带随机 `rand` 和 `hdata = PRF(rand, data)`，hash 绑定 metadata 与 `hdata`。字符被删除后可以清掉 `data` 与 `rand`，仍用 `hdata` 验证原 commitment；这为后面的 placeholder 隐私打基础（§4.1.1）。

### 2. 固定长度 Treedoc address

原始 Treedoc operation 序列化从 root 到 node 的完整 path。连续在末尾插入会形成线性树，最后一个 edit 的 path 长度可达 `O(E)`；即使内容加密，packet size 也暴露编辑位置。Acumen 只发送 parent 的固定长度 disambiguator，依靠 causal broadcast 保证 parent 已存在。于是 balanced 和 worst-case edit size 都是 `O(1)`（表 1、§5.1）。

这不等于隐藏所有访问模式：network observer 不再从单条 ciphertext size 看 path；新成员收到 snapshot 后，仍会从当前 Treedoc 结构看出过去操作的一部分因果形状，timing 也不在保护范围内。

### 3. Merkle accumulator 与签名 state descriptor

Acumen 使用固定高度的 sparse Merkle-tree accumulator。集合元素哈希到 leaf，root 是常数大小的承诺；加入或删除 `k` 个元素可在 `O(h+k)` 更新。每个用户分别对 operation set 和 Treedoc node set 维护 accumulator。

用户最近 operation 中的前七个字段组成签名 state descriptor：user ID、operation accumulator、Treedoc accumulator、version vector、该用户看到的最小 version vector、history hashes 和 signature。Snapshot 带当前 operation/Treedoc 数据、全局 metadata，以及每个用户的 descriptor（表 3、表 5）。

新成员对 snapshot 中 **每个用户** 执行以下检查（图 3）：

1. 验签，并按该用户 version vector 从 snapshot 数据重建它当时的 operation/Treedoc state；
2. 重算两个 accumulator，和签名 descriptor 比较；
3. 检查该用户 history hash 是 snapshot history 的 prefix；
4. 找出它尚未处理的 operation，验证这些操作构成 well-formed FCC partial execution；
5. 从重建状态执行 missing operations，要求每个用户都到达同一个 final snapshot state。

最多 `n−1` 用户恶意意味着至少一个 descriptor 来自诚实用户。Verifier 不知道是哪一个，所以全部检查；只要所有检查通过，就存在至少一个 honest state 可以沿 FCC execution 到达 snapshot。整个过程不要求某个诚实旧用户当时在线响应。

### 4. Placeholder 隐藏已删除字符

难点是：旧用户 descriptor 可能承诺一个当时还活着、现在已删除的字符；若 snapshot 为重建旧状态发送原字符，就泄露 edit history。Acumen 把这种节点改成 placeholder：`data=null`、`rand=null`、`tombstone=False`，保留 `hdata` 和结构 metadata。由于 placeholder hash 被定义为与原 live node hash 相同，重算 accumulator 仍能匹配旧 descriptor。

协议只允许对“旧用户见过 insert、但对应 delete 不在其 version vector 内”的节点这样替换。Verifier 还必须确认 missing operations 里有对应 delete，并要求最终状态没有 placeholder。删除 placeholder 与删除原字符得到相同 final state，因此不需要知道字符内容（§5.2.3、定理 1）。若 snapshot sender 随便把未删除字符变成 placeholder，缺少合法 delete，最终检查会失败。

### 5. 因果稳定 GC

Operation 只有在所有用户都处理后才是 causally stable。单个客户端不知道全局状态，就使用“自己看到的每个用户最新 version vector 的逐分量最小值”作为保守的 local barrier；local stable 一定 global stable，反向不一定（§5.3.1）。

GC 先删除 causally stable 的 delete operation 和它对应的 insert；Treedoc 中，leaf CST 可以直接 prune，inner CST 只有在 parent 也为 CST 时才 flatten。每个新 operation 携带 sender 的 local-min version vector，receiver 用同一个 barrier 执行 GC，保证并发到达顺序不同的诚实用户仍得到相同状态。附录给出 GC 与 insert/delete、GC 与 GC 可交换的 proof sketch。

### 6. 二阶 GC 解决 snapshot 的循环依赖

Snapshot 验证要重建每个用户过去的 descriptor；若只保留已经被所有过去状态删掉的数据，几乎什么都不能回收。Acumen 因此保留两份对象：

- **primary object** 按当前 operation 携带的 `VV_min` 正常 GC，日常 state descriptor 对它做 accumulator；
- **secondary object** 保留用于重建各用户 descriptor 的更老数据，只按 `GCVV_min` 回收。`GCVV_min` 是“每个用户最近声明的 local-min VV”再取一次逐分量最小值，因此是二阶 stability barrier（§5.3.4）。

Snapshot 发送 secondary 数据，verifier 为每个 descriptor 用其 barrier 重建 primary state，最后把验证后的 final state 设为新 primary/secondary。这个设计换来 `O(D)` asymptotic claim，但前提仍是 user count 为常数且 stability 能推进。

## 设计取舍

- **Safety 胜过 fork repair。** FCC 防止两个冲突分支静默重新合并，但 honest clients 一旦分叉就永久互拒；论文没有 leader、仲裁或人工选择分支的流程。
- **强 snapshot 换按用户验证。** 不需要在线 honest user，代价是 snapshot 带每个用户 descriptor，并逐个重建和 replay；成员越多越慢。
- **隐私不是全隐私。** Fixed-length edit 隐藏 packet-size path，placeholder 隐藏已删除内容；edit timing、snapshot 前 Treedoc structure 和与旧成员串通都不在保证内。
- **异步 GC 换保守进度。** 不跑 distributed consensus，但 offline/malicious member 会让 barrier 停住。论文排除 DoS，因此没有解决 storage exhaustion。
- **当前文档大小换双份状态。** Primary 适合日常执行，secondary 为 snapshot proof 保留更多数据；实现与 correctness proof 比普通 CRDT 复杂得多。
- **Treedoc 简化证明。** 单字符、tombstone-based tree 很适合说明机制，rich text、nested object、comment/attachment 的操作和 GC 关系需要重新设计与证明。

## 实验设计

Local 实验使用原 Automerge 论文的顺序编辑 trace，共 182,315 次单字符 insert 和 77,463 次 delete。5 个用户轮流产生第 `k mod 5` 条 edit，并让其他用户立即处理，运行在 GCP c2-standard-16（16 vCPU、64 GB）。Baseline 是无恶意安全保证的 Automerge，以及最接近 Acumen 安全目标的 Snapdoc。

Snapshot sweep 使用 1–10 用户，operation 数为 0、10、50、100、200、400、1000，然后从文档末尾删除 0% 或 90% 字符。因为 Snapdoc 内存需求很高，这部分改用 n2-highmem-48（48 vCPU、384 GB）。Network benchmark 中，每个 client 是 c2-standard-8，central relay 是 c2-standard-30；用户反复输入再删除约 800 字符的论文摘要。网络 baseline 只收发 200-byte edit，不做本地 CRDT/security processing。表 7 的 round-trip latency 在 5 ops/s 下测量；maximum throughput 则是单个用户每秒处理的 operation 数，二者不是同一负载点。

## 实验与结果

- **Local operation 保持亚毫秒，但比普通 CRDT 贵。** Trace index 50/250/425/850 时，Acumen insert 为 0.29/0.32/0.34/0.44 ms，delete 为 0.30/0.30/0.33/0.34 ms；Automerge 都少于 0.01 ms。Snapdoc insert 为 5.63/23.81/37.5/193.7 ms，delete 为 11.3/22.3/42.9/190.7 ms（表 6）。
- **Remote overhead 主要来自 accumulator。** 5 用户轮流执行前 40K edits 时，每个 remote operation 约做 `2λ` 次 hash 与 hashmap insertion；GC 只占小部分，后期增长主要来自 Treedoc 及其 list insertion（图 6）。这个结果来自用户都及时跟进的环境，不能说明 lagging user 下 GC backlog 很小。
- **Fixed-length edit 避免随历史膨胀。** Acumen 和 Automerge update size 基本保持常数；Snapdoc 因携带 Treedoc path 线性增长，在约 1,000 edits、约 200 个英文词时，单条 update 已约 7 MB（图 7）。
- **Snapshot 的优势在删除多、历史长时最大。** 0% deletion 时 Acumen load time 比 Snapdoc 约快一个数量级；90% deletion 且用户少时接近两个数量级。1,000 edits、90% deletion 时，snapshot size 相差约三个数量级（图 8）。但 sweep 只到 1,000 operations，远小于 local trace 的 259,778 operations。
- **25 用户交互延迟仍低，但 throughput 随人数反比。** 2/5/10/25 用户时，Acumen round-trip latency 是 1.03/1.17/1.38/2.7 ms，network-only baseline 是 0.37/0.465/0.51/1.5 ms；论文按所有点平均后称额外 latency 少于 1 ms，但 25 用户这个点的差值是 1.2 ms。最大 throughput 是 1,340/645/402/270 ops/s，仍足以支持 25 人各 60 WPM（表 7）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| Acumen 同时满足 FCC、strong snapshot consistency 与 edit-history privacy | §4–§5、图 2–4、附录 proof sketch；完整 proof 在 supplemental | 依赖 PKI、secure group messaging、hash/PRF/signature、至少一个 honest descriptor | 中 |
| Storage/edit/snapshot 从 `E` scaling 改为 `D` scaling | 表 1、fixed path 与二阶 GC 构造 | 表 1 把 user count 当 `O(1)`；GC 必须持续前进 | 中 |
| 相对 Snapdoc，edit 不随历史快速变大/变慢 | 表 6、图 7：850 edits 约 190 ms；1000 edits 约 7 MB | 单字符 Treedoc、一个 Automerge trace | 强 |
| Snapshot 在历史远大于当前文档时明显更小更快 | 图 8：90% deletion 时最多约 2 个数量级 load、3 个数量级 size 差异 | 1–10 users、最多 1000 operations、high-memory VM | 强 |
| 25 人实时协作可用 | 表 7：2.7 ms、270 ops/s | central relay；每个 sender 等待其余 `N−1` 个 update；没有 WAN/churn/failure | 中 |

## 批判性分析

### 论证链条

论文把难点拆得很清楚：history hash 解决恶意 fork，accumulator/state descriptor 解决“不信 snapshot sender”，placeholder 解决“验证旧状态却不能泄露旧字符”，二阶 GC 解决“证明旧状态与回收历史的循环依赖”。每个机制都对应一个具体的安全或 scaling gap，表 1 也明确比较 Acumen、Snapdoc 和普通 CRDT 的功能及复杂度。

不过，系统实验只能证明实现开销可接受，不能替代安全证明。正文和附录给出定义、theorem 与 proof sketch，完整 formal proof 在 supplemental；页面未见 machine-checked proof 或 adversarial implementation testing。因此“协议在模型内安全”的置信度主要来自密码学论证，不来自表 6/7 的性能数字。

### 假设压力测试

“最多 `n−1` malicious”看起来很强，但保证仍依赖 snapshot 中至少一个 honest descriptor。若邀请时列出的所有旧成员都恶意，新成员没有外部 anchor，无法区分任意自洽伪造。即使有诚实成员，它也不必在线；可验证性来自过去签名，但成员身份、撤销和 key rotation 必须由假设中的 group messaging/PKI 正确处理。

GC 对成员活性敏感。一个长期离线设备、被遗忘的成员或故意不推进 version vector 的恶意客户端，都可能让 `VV_min/GCVV_min` 停住。由于 DoS 是 non-goal，论文可以保持 safety，却无法保持 `O(D)` 的实践空间上界。成员越多，这种最慢成员效应越严重。

Edit-history privacy 也有明确缝隙：新成员与任何旧成员串通就能得到旧内容；snapshot 的 Treedoc 结构仍泄露过去的 causal/access pattern；网络 timing 仍显示何时编辑。它保护的是“已删除字符内容”，不是全历史不可区分性。

### 实验可信度

实验分为 local creation、remote processing、message size、snapshot 和 network，能把密码学 accumulator、Treedoc list 和 GC 的成本分开。原 Automerge paper trace 比纯随机 edit 更真实，表 6/7 给了完整原始数字而不是只报最大 speedup。

边界也很明显：snapshot 只到 1,000 operations 和 10 users，network 只到 25 users；没有 WAN、offline device、membership churn、malicious equivocation 或 relay failure。Local trace 虽有 259,778 operations，但 snapshot sweep 没有用到这个规模。为了跑 Snapdoc，snapshot 使用 384 GB high-memory VM；这说明 baseline 的 scaling 差，也让绝对 latency 与普通部署不易比较。

Network throughput 测试让每个用户等到来自其余 `N−1` 人的更新后才发下一条，因此测得的 inverse-`N` scaling 部分来自 benchmark protocol。这种做法可能保守，但也说明百人规模未验证。论文没有用 Automerge 做 network baseline，理由是 edit-history degradation 使 steady state 难以测；因此表 7 只能分解 Acumen 相对 network-only framework 的额外成本，不能做主流 CRDT 的端到端对比。

### 系统性缺陷

FCC 只给出 permanent fork，没有证据格式、归责 UI、成员驱逐、branch choice 或 safe rejoin。现实协作文档不能在一次 malicious equivocation 后永远分裂，恢复协议还必须保持 snapshot consistency 和 history privacy。

论文把 membership change 视为 AddUser operation，但大量 churn、RemoveUser、设备丢失、key rotation、history key erasure 和 offline recovery 没有完整评测。Relay 虽不被信任安全性，却仍是 availability 集中点。底层 Treedoc 是单字符模型；rich text span、comment、table、image、undo 和 nested object 的 operation semantics 可能让 placeholder 与 GC theorem 不再直接成立。

## 局限与后续工作

- **局限 1**：不防 DoS 和 timing attack；offline/malicious member 可以阻止 GC 前进，也能让 relay availability 消失。
- **局限 2**：FCC 发现冲突后形成永久 fork，没有 reconciliation、归责、eviction 或 safe rejoin。
- **局限 3**：`O(D)` claim 把 user count 视为常数，且依赖因果稳定性持续推进；snapshot/verification 仍随用户数增长。
- **局限 4**：snapshot 最多只测 1,000 operations/10 users，network 最多 25 users；没有 churn、WAN、长期离线和 adversarial execution。
- **局限 5**：单字符 Treedoc 尚未覆盖 rich text、nested CRDT、attachment、undo 和评论。
- **后续工作 1**：让 1–1000 用户按真实在线/离线分布运行数月 trace，报告 tombstone backlog、secondary-state size、snapshot p50/p99 和恢复时间。
- **后续工作 2**：设计可转交的 fork evidence、成员投票/驱逐与 branch reconciliation，并机器验证不会破坏 FCC 或泄露 deleted content。
- **后续工作 3**：把 RemoveUser、key rotation、device recovery 与 snapshot protocol 联合建模，测试恶意旧设备持有旧 key 时的边界。
- **后续工作 4**：移植到 Automerge/Yjs rich-text 或 nested-object schema，重新证明 placeholder/GC 的交换性并测 metadata。
- **后续工作 5**：加入 packet padding/batching 选项，分别量化 message-size、timing 和 snapshot-structure 三类 leakage 的带宽代价。

## 相关

- **相关概念**：CRDT、fork-causal consistency、cryptographic accumulator、causal stability、[[Garbage-Collection]]
- **同类系统**：Snapdoc、Automerge、Treedoc、SUNDR、Depot、SPORC
- **同会议**：[[OSDI-2026]]
