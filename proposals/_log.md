# Proposals Log

记录每个 proposal 的生成 / review / status 变化的时间线。倒序,最新在上。

---

## [2026-04-27] SpeculativeAsyncRL (review)

- target: `proposals/SpeculativeAsyncRL.md`
- 模式: inline
- deep: false
- 引用核验: 5 篇内部 paper(全部存在,1 处 framing stretch 已在 Critic 标注)/ 14 个外部 URL(13 篇 first-author 写错,已 inline 修正)/ 1 个 GitHub repo(mnoukhov/async_rlhf ✓)
- 新增 critic: 0 dealbreaker / 5 serious / 8 minor
- 新发现 prior work: 0 篇(`created` = `currentDate` 同日;但 Step 4d 把 TBA v2 的 4× 加速、Stabilizing RL 的 staleness 形式化、TensorHub 的 19× cross-DC 等关键数字补回相关工作节)
- 一致性问题: 3 处(proof milestone 缺失 / wall-clock 阈值 15-25% gap / benchmark 2 个 vs 3 个表述)
- 谬误: 5 处(cherry-pick baseline + speculation-as-fact 各 1 serious;假设变结论 / 假二分 / 术语漂移 / 数字外推 / 10x vs 2x 是 minor)
- AI 推荐: revise(若团队仍要做)/ archive(proposal 自评 novelty: low,已自荐"低优先级备选,sister proposal 优先级更高")
- counter-defense: 13/14 作者错无合理 reading,必须修(已修);TBA / Stabilizing RL scoop-risk 可通过 Reframing A(理论保证 first-order)分流投算法会议;cherry-pick baseline 与 speculation-as-fact 通过"≥25% 降级为 aspirational + 增加 ROLL Flash / TBA 直接对比"修补,但需要 proposal 显式 framing
- 关键风险: 13/14 作者写错是学术诚信下限警报,审稿人易当作"未真读论文"信号;若不彻底修这一项,投稿命中率近零
- report file: 无(inline 模式)

## [2026-04-27] LiveSessionMigration (review + rewrite)

- target: `proposals/LiveSessionMigration.md`
- 模式: rewrite(用户明确要求按 review 意见整体重写 proposal,不在文档内保留 Critic/Reframings/Verdict/Review Log 节)
- deep: false
- 引用核验: 8 篇内部 paper(全部存在)/ 9 个外部 URL(8 verified + 1 推测,ServerlessLLM §5.2 引用未在 abstract 中确认)/ 2 个 repo(pplx-garden ✓ MIT、blitz-serving/blitz-scale ✓——proposal 原写错为 `blitzscale` 已修)
- 修正:5 处 mischaracterization(AnchorTP 第一作者 Liu→Xu、BanaServe Qiu→He、ReviveMoE Chen→Li、LMCache Cheng→Liu、BlitzScale repo URL `blitzscale`→`blitz-scale`)+ NanoFlow 分类标签(prefill-side → intra-device parallelism)+ BlitzScale strawman 措辞软化为 ZigZag layer-pipeline split 描述
- 关键发现(已吸收到 proposal):
  - **BanaServe scoop-risk(serious)**:其 abstract 明确做 module + KV migration on load rebalance trigger,直接占据 "non-failure trigger 上 KV-preserving migration" 的相当空间。proposal novelty thesis 已重写为 "三角差异化(decentralized + session-grain + 4-trigger 协议复用)";原"首个"主张删除
  - **TL;DR vs M4 metric inconsistency(serious)**:TL;DR 80%/90% absolute vs 原 M4 30% relative,数量级差距。已 harmonize 为 absolute 同 metric(R2 Option A)
  - **Baseline 工程量超预算(serious)**:4 个 baseline 全部无开源,3 周复现不现实。M4 收窄到 AnchorTP + BanaServe-style 两核心 baseline 严格做,Tarragon / ReviveMoE 仅引用 paper 数字 narrative;M4 时长扩到 5 周
- 一致性问题: 1 处 → 已 harmonize
- 谬误: 2 处 minor → 措辞已修正
- AI 推荐: revise(已通过 rewrite 落地;novelty / feasibility frontmatter 字段不动,留给原作再判断)
- 关联问题: `wiki/papers/BlitzScale-OSDI25.md` 同样 URL 错(`blitzscale` vs `blitz-scale`),后续 wiki maintenance 顺手修
- 流程变更:本次 review 被用户要求改为 "rewrite" 模式;同时确认 `wiki/log.md` 不接收 proposal/review 内容(skill + CLAUDE.md 已更新)
- report file: 无

## [2026-04-27] OnlineExpertMigration (review)

- target: `proposals/OnlineExpertMigration.md`
- 模式: inline
- deep: false
- 引用核验: 12 篇内部 paper(全部存在)/ 9 个外部 URL(5 verified、4 abstract-only 因 WebFetch 偶发超时)/ 2 个 repo;**5 处 mischaracterization 已 inline 修正**
- 新增 critic: 0 dealbreaker / 3 serious / 6 minor
- 新发现 prior work: 5 篇(LLEP scoop-risk / HybridEP partial-overlap / SGLang Elastic EP code-path-conflict / UCCL-EP 底座替代 / Rewiring Experts parallel)
- 一致性问题: 3 处(effort vs timeline / go-no-go threshold gap / TL;DR-vs-Plan 复杂度)
- 谬误: 3 处(continuous-vs-batch 假二分 / speculation as fact / 复杂度藏在小字)
- AI 推荐: revise(strong)
- counter-defense: LLEP 反例部分成立,本提案的 "continuous background + decoupled hot-swap + decentralized" 三条**联合**仍是真 delta;不致命但 novelty 折半
- report file: 无(inline 模式)
