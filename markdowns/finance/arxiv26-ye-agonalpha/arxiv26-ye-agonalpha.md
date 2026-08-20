# AgonAlpha: Autonomous Alpha Discovery via Prompt Economy and Scalable Agentic Search

Weicheng Ye<sup>1,\*,‡</sup>, Youran Sun<sup>2,\*</sup>, Xingyu Ren<sup>1,\*</sup>, Shunyao Yu<sup>1</sup>, Chugang Yi<sup>2</sup>, Haizhao Yang<sup>2,3,†</sup>

<sup>1</sup>Department of Physics, The Chinese University of Hong Kong, Hong Kong SAR, China <sup>2</sup>Department of Mathematics, University of Maryland, College Park, MD, USA <sup>3</sup>Department of Computer Science, University of Maryland, College Park, MD, USA

## Contents

1 Introduction 2   
2 Related Work 4   
2.1 Axis I: The Unit of Search . 4   
2.2 Axis II: The Verification Regime 5   
2.3 Axis III: Budget Allocation 5   
3 Minimal Instance of the Agon Philosophy 5   
4 The AgonAlpha System 7   
4.1 Problem Formalization . 7   
4.2 The Two-Role Contract 7   
4.3 Adversarial Verification Protocol 7   
4.4 Two-Level Budget Allocation 8   
5 Evaluation and Artifact Release 11   
5.1 Protocol 11   
5.2 Overview 11   
5.3 Reviewer Interventions (Q2) 14   
5.4 Allocation and Concurrency (Q3) 14   
5.5 Artifact Completeness 14   
Discussion and Limitations 14   
7 Conclusion 15   
Deployment summary 18

<sup>∗</sup>Equal contribution.   
<sup>†</sup>hzyang@umd.edu.   
<sup>‡</sup>victoryeofphysics@gmail.com.

Representative sample run 25   
What the reviewer found 25   
Alpha constructions and economic interpretation 25   
Detailed node-by-node account 26   
What this typical run demonstrates 34   
Behavior across calendar regimes 34   
Evidence index 36   
Artifact completeness 36

## Abstract

Language models can propose many plausible trading factors, but an autonomous research system must also allocate its evaluation budget, verify its own evidence, and preserve how each candidate was produced. We present AgonAlpha, an architecture that searches over frozen research artifacts—hypotheses, executable expressions, platform evidence, rationales, and review status—rather than formulas alone. To our knowledge, AgonAlpha is the first alpha-mining system to combine verified artifact search, a fresh-context adversarial reviewer with re-execution and veto authority, and pending-aware parallel budget allocation, together with a complete public evidence trail. Independent deployments on WorldQuant BRAIN produced SPECTACULARgrade alphas across five users and six model backends, with Fitness reaching 9.50 and Sharpe reaching 3.48, while retaining prompt-to-expression provenance for every submission.

## 1 Introduction

With the increasing adoption of agentic workflows, autonomous alpha discovery is not merely about generating plausible formulas by large language models (LLMs), but also designing a comprehensive system of evaluation and self-improvement. The system should go beyond systematically and consistently generating plausible alphas: it should decide which families of alpha ideas deserve the limited number of expensive platform evaluation opportunities, ensure that the recorded evidence corresponds to the evaluated candidates, and maintain suficient state to enable reliable reconstruction of results after each run. AlphaBench shows that language models still struggle with zero-shot factor ranking, even though they are relatively efective at generating executable factors Luo et al. [2026]. Meanwhile, the performance of published anomalies has also weakened substantially over time. In the post-2005 non-micro-cap sample analyzed by Chen and Welch, the median return is only around 7 basis points per month—an efect size small enough to be explained away by statistical luck or modest transaction costs Chen and Welch [2026]. Moreover, a systematic review of 30 LLM-based trading papers reveals a recurring gap in research practice: while model architectures are often described in detail, crucial aspects such as point-in-time data controls, train-test splits, out-of-sample evaluation, transaction costs, turnover assumptions, execution details, and artifact availability are frequently underreported Yao and Zheng [2026]. Together, these findings locate the central challenge at the level of the automated alpha-discovery loop: preserving evidence, allocating costly evaluations across competing ideas, and separating proposal from verification.

For this purpose, we apply the artifact-level discovery; compared with previous works, many of which are at the formula-level, there are four distinctive architectural choices, as shown in Figure 1.

• Search unit. Existing systems typically treat a formula as the basic unit of discovery. However, a formula alone does not preserve the hypothesis that motivated it, the alternative directions that were explored and rejected, or the objections that were addressed along the way. We instead treat discovery as a lineage of research decisions, preserving the context needed to understand why a candidate was generated and how it evolved.

![](images/608b1172307d24adfa9d7412c8da4132bc15cfbdb2f376ac7aaab6a6173b2a57.jpg)  
Figure 1: Two paradigms for LLM-driven alpha mining. Left: formula-level search with self-scoring and a closed trail. Right: AgonAlpha searches over research artifacts subject to fresh-context review with a pending-aware scheduler validated under 10 concurrent workers.

• Verification mechanism. Existing systems often rely on self-evaluation procedures or scalar performance thresholds. While these mechanisms are efective for ranking candidates, they do not independently verify whether the supporting evidence is consistent with the evaluated candidate. We introduce explicit verification procedures to audit the correspondence between generated candidates, evaluation records, and reported results.

• Resource allocation. Existing systems commonly allocate search budgets according to fixed schedules. However, when external platform evaluations require substantial time and multiple research directions proceed concurrently, static allocation cannot adaptively redirect resources toward promising research lineages or account for evaluations already in progress. We instead treat evaluation budget allocation as an active decision-making problem, allowing the system to prioritize promising directions while coordinating ongoing experiments.

• Evidence preservation. Existing systems often provide incomplete evidence trails. The audit of 30 LLM-based trading papers shows that critical execution and evaluation details needed to interpret reported results are frequently less accessible than descriptions of the agent architecture itself Yao and Zheng [2026]. We therefore emphasize the preservation of complete research artifacts and execution history, enabling results to be reproduced and independently assessed.

Together, these diferences highlight a broader distinction: these are not merely limitations of individual factor-generation methods, but missing interfaces required for building a fully autonomous discovery system.

AgonAlpha implements these interfaces through three coordinated components: a proposer, a fresh-context reviewer, and a pending-aware scheduler. The proposer commits each candidate as an evidence-bearing artifact; the reviewer independently checks the artifact, may rerun the associated platform evaluation, and can reject unsupported or fabricated claims; and the scheduler allocates each subsequent invocation to a research lineage while accounting for evaluations already in progress. This architecture follows the Agon philosophy and the Prompt Economy principle Sun et al. [2026a,b]. Five co-authors deployed AgonAlpha on WorldQuant BRAIN using multiple model backends, producing 60 submissions, of which 17 received SPECTACULAR grades; the best observed Fitness and Sharpe ratio were 9.50 and 3.48, respectively. We present detailed analyses of five representative cases and release the prompts, decisions, reviews, platform evidence, and factor expressions for all 60 submissions, with the complete collection provided in the supplementary material.

On top of the design of the system, the design of the evaluation is itself a key systems consideration. Existing approaches, including AlphaForge, AlphaJungle, and FactorMiner, evaluate generated factors through author-controlled academic pipelines, even when they introduce temporal or crossmarket holdouts Shi et al. [2025, 2026], Wang et al. [2026]. Such protocols improve the separation between discovery and evaluation data, but the evaluator remains part of the system being designed. Our approach instead adopts WorldQuant BRAIN as an external evaluation environment: a platform that independently determines the data, simulation rules, metrics, submission constraints, and final scores, with an incentive mechanism for qualifying research consultants WorldQuant [2026]. Therefore, our results measure not only factor discovery capability but also the ability of an autonomous research system to operate under a fixed, externally governed evaluation regime.

• C1 — An integrated architecture for auditable alpha discovery. To our knowledge, AgonAlpha is the first alpha-mining system to combine verified artifact search, adversarial review authority, pending-aware parallel budget allocation, and a complete public evidence trail. Its compact realization applies the six Agon principles—Prompt Economy, Minimal Prompts, Future-Facing, Zero-Code, OmniDisciplinary, Massive Parallelism—through two roles and 101 lines of role prompt Sun et al. [2026a,b].

• C2 — Trajectory-level search over evidence-bearing artifacts. The search unit is a frozen research artifact containing a hypothesis, executable expression, platform evidence, economic rationale, and review status. The scheduler therefore allocates work across research lineages rather than isolated formula edits.

• C3 — Adversarial review with re-execution and veto authority. The reviewer is separately routed and invoked in a fresh context, may re-run platform evidence, and can set the scheduler reward to zero when it verifies fabrication. Other risk findings remain attached to the artifact as inspectable warnings.

• C4 — Pending-aware parallel budget allocation. Across lineages, a pending-aware MCTS scheduler combines progressive widening, percentile rewards, backpressure, and a root fallback so that in-flight work afects subsequent allocation. Within each pipeline, a halving tournament concentrates simulations on surviving candidates (§4.4).

• C5 — Trace-complete multi-user deployment validation. Five users and multiple model backends produced 60 externally graded submissions, including 17 SPECTACULAR alphas and Fitness reaching 9.50. We release every prompt, search decision, platform record, review, and executable expression.

## 2 Related Work

## 2.1 Axis I: The Unit of Search

Most alpha-mining agents search over formulas. AlphaJungle applies Monte Carlo Tree Search (MCTS) to formula expression trees, using one LLM to generate and self-score candidates Shi et al. [2026]. It asks where to add the next operator ; we ask which lineage deserves the next budget. QuantaAlpha evolves trajectories as genetic material under a fixed five-round schedule; our artifacts are evidence units—frozen, adversarially gated, UCB-budgeted Han et al. [2026]. FAMA chains experiences linearly and reports hallucinations in its own evaluation Li et al. [2024], directly motivating C3.

## 2.2 Axis II: The Verification Regime

FactorMiner Wang et al. [2026], the nearest competitor, has the same role count but the opposite organizing principle. Its roles divide labor functionally (generator plus deterministic tool evaluation); ours divide adversarially (proposer plus attacker). Its Ralph Loop is a linear cycle with no tree, no UCB, and no cross-lineage allocation. Its validation is a tool—deterministic thresholds on IC and correlation—while ours is an authority with re-run and veto rights. FactorMiner publishes its factor library but keeps code and prompts closed. FactorMAD’s debate is cooperative with no veto, and admission returns to a deterministic cutof FactorMAD [2025]. Agora’s panel disperses power, so no single verifier holds both re-run and veto rights. Its own analysis concludes that adding agents merely relocates rather than resolves the failure of self-confirmation Agora [2026]. CogAlpha fields 21 agents at roughly 500 H100-hours per run with same-model quality control and closed prompts CogAlpha [2025]. Beyond Prompting’s fixed threshold gate fails in public Huang and Fan [2026], and AlphaCrafter documents the backtest-to-live clif AlphaCrafter [2026], ATLAS [2025]. AlphaBench is not a competing system. Its finding that LLM factor evaluation is near-random provides the strongest published motivation for C3 Luo et al. [2026].

## 2.3 Axis III: Budget Allocation

R&D-Agent-Quant alternates factor and model development under a two-arm bandit—arms, not tree nodes, with no notion of in-flight work Li et al. [2025]. AlphaGen reports exploration stagnation, while QF-REINFORCE’s algorithm-layer patch leaves its CSI500 RankIC below AlphaGen’s without explaining the gap Yu et al. [2023], Zhao et al. [2025]. AlphaForge instead runs a hardcoded pipeline over a frozen factor pool Shi et al. [2025]. QuantEvolver addresses the same problem by encoding experience in model weights through GRPO Zhang et al. [2026]. AgonAlpha instead searches at inference time, which is the only option available to platform users without weight access. Table 1 maps the field onto the four failure axes of §1. The F4 column shows the domain norm: no system releases prompts, search decisions, review text, and exact executable expressions together—most expose code only. C5 addresses this gap with a release that covers all five dimensions of the 30-paper audit (§5).

## 3 Minimal Instance of the Agon Philosophy

The Agon philosophy Sun et al. [2026a] defines six design principles for autonomous research systems and grounds them in Prompt Economy Sun et al. [2026b]. Under this view, a multi-agent system is a reusable prompt surface whose invocations must repay their cost. AgonAlpha is the first system to instantiate all six outside of the original Agon factory.

Prompt Economy. Every agent invocation costs tokens and coordination. Systems should maximize artifact value per prompt line and per handof. AgonAlpha reuses two role prompts across every node of the search tree. The halving tournament reserves later, more expensive simulations for survivors. The tournament schedule in §4.4 measures this directly.

Minimal Prompts. Shorter, fewer prompts reduce maintenance surface and coupling to specific models. AgonAlpha’s entire discovery workflow runs on 101 physical lines of role prompt: 57 for the proposer, 44 for the reviewer, plus a short dispatcher. The full prompt set is released.

![](images/652a4df1da842ebd1ea0ab39834eb11259dbbf29f1532926507129ff3969230b.jpg)  
Table 1: Representative formulaic alpha-mining systems on the four failure axes of §1 (F1 search unit, F2 verification regime, F3 budget allocation, F4 open evidence trail). <sup>✓</sup> = present, = partial/indirect, – = absent or unconfirmed. Performance numbers are excluded: universes, delays, and evaluation windows difer across studies.

Future-Facing. Prompts should describe stable roles and procedures, not patch current model weaknesses, so systems benefit from model upgrades without prompt changes. AgonAlpha’s role prompts name artifacts, checks, and stopping rules. No prompt mentions a specific model.

Zero-Code. Research logic lives in prompts, not in hardcoded pipelines. AgonAlpha’s deterministic code handles only platform I/O and tree bookkeeping. No human wrote a factor expression or factor-specific program.

OmniDisciplinary. Core agents remain domain-agnostic. Domain knowledge enters at runtime through manuals, readings, and schemas. AgonAlpha’s role prompts contain no market-specific tokens: no “stock,” no “equity,” no “option.”

Massive Parallelism. The same prompt set should instantiate concurrently across independent research threads, limited only by platform quotas. AgonAlpha’s proposer–reviewer pipelines occupy independent worker slots; only scheduler selection and update are serialized. The pending-aware UCB in §4.4 accounts for this concurrency. A validated 10-worker deployment demonstrates concurrent operation. Platform account quotas, rather than the architecture, set the ceiling.

These six principles operate through a producer–critic adversarial loop. The proposer freezes the artifact, a separately routed fresh-context reviewer attacks it, and only then does the verified score enter the search tree (§4.3).

Two roles form the fixed point. A single role must grade its own work, relying on the selfevaluation that AlphaBench has already shown to fail. Adding more than two roles redistributes adversarial pressure rather than increasing it, as Agora’s own analysis concluded. Two opposed roles are the smallest structure in which an adversary can exist. Sections 4–5 demonstrate that this minimal instance produces SPECTACULAR-grade alphas on WorldQuant BRAIN.

## 4 The AgonAlpha System

## 4.1 Problem Formalization

AgonAlpha searches for cross-sectional equity alphas expressed in WorldQuant BRAIN’s expression language (FASTEXPR), a domain-specific language for formulaic alpha construction. The unit of search is an artifact A = (h, f, E, r, v): a hypothesis h, an executable expression f, evidence records E (simulation inputs, metrics, annual results, submission state), an economic rationale r, and a verdict v from the adversarial review. A lineage is a chain of artifacts linked by ancestry; the single search operator is extend(ℓ), which invokes one proposer–reviewer pipeline to append a new artifact to lineage ℓ. Node scores enter the tree only after verification. The scheduler’s problem is budget allocation: given a budget B of platform simulations and a utility u(·) over verified artifacts, choose extensions maximizing <sup>E</sup>- P u(A<sub>i</sub>) subject to P cost(A<sub>i</sub>) ≤ B. The scheduler never generates expressions, runs simulations, or judges evidence; it only decides which lineage receives the next pipeline invocation.

## 4.2 The Two-Role Contract

The proposer receives ancestor reports, a work directory, two sampled readings, and the platform interface. It writes a hypothesis, generates 16 candidate formulas, and runs a halving tournament (§4.4). Every candidate is simulated, and near-duplicates above the self-correlation gate are removed. Survivors are ranked by absolute platform composite score |Score|; each pass eliminates the bottom half. A negative-scoring finalist is sign-reflected rather than re-simulated. For dollar-neutral crosssectional alphas, negation reverses the signs of returns and Sharpe while leaving turnover unchanged, so the flipped candidate’s metrics are derived exactly rather than re-simulated. A monotone target constraint requires the submitted formula to beat the best ancestor score. After the final pass, the proposer considers every eligible simulation, including eliminated candidates. It submits the winner and freezes the full search as an alpha report. The reviewer receives only the work directory and platform documentation. It runs in a fresh context on a diferent model route and has a single task: find grounds for rejection. It may re-run any simulation, and verified fabrication sets the score to zero. The two role prompts total 101 physical lines (57 proposer, 44 reviewer) in the current release. A short dispatcher prompt connects them to the scheduler. Reference manuals and platform documentation are runtime reading materials, not role prompts. The full prompt history is part of the released trail. The proposer and reviewer are routed through separate API endpoints with independent contexts; deployments used various backend combinations (see supplement for per-user configurations).

## 4.3 Adversarial Verification Protocol

The reviewer is not another score threshold: it must audit the evidence even when a candidate already clears every passive screen. Table 2 states the five audit dimensions and their recorded actions. The authority boundary is explicit: only verified fabrication—mismatched expressions, leaked or look-ahead inputs, invented records—changes the scheduler’s score, to zero. Sign, constant, regime, and redundancy findings remain advisory records attached to the artifact. Rules for blocking submission based on combinations of warnings are deferred to a stricter release. The released prompt history also records one boundary migration. Self-correlation began as a reviewer warning and moved into the proposer as a hard pre-ranking gate, currently at 0.85. Near-duplicates are removed before ranking rather than after review.

![](images/b106017625540fbe83cdda2d51b4daaaf8ac9750a201f9774ce7c2f614f165c0.jpg)  
Table 2: The five-dimensional audit of a frozen alpha report. Evidence failures can zero the scheduler’s score; risk warnings remain visible but advisory; the correlation gate rejects near-duplicates in search.

The division of labor directly addresses the AlphaBench result. The reviewer never estimates alpha quality—quality is scored by the platform. The reviewer audits evidence integrity: re-execution, record consistency, and look-ahead. This is a consistency-checking task, not the quality-prediction task at which AlphaBench found LLM agents near-random Luo et al. [2026]. The division-of-labor argument extends only this far. The sign and constant dimensions are judgmental; their reliability is evaluated through the reviewer audit record in §5.

![](images/d254dd31aadfb2ed5bb2154d5b281d0687a1e256ef5220c72e14f5e26d408e13.jpg)  
Figure 2: AgonAlpha separates trajectory-level search (scheduler), candidate production (proposer), BRAIN (platform), and independent verification (reviewer), which audits the frozen report before its score is recorded.

## 4.4 Two-Level Budget Allocation

Evaluation in this domain is expensive and asynchronous: each simulation is billed by the platform and takes minutes, and several pipelines may be in flight at once. AgonAlpha therefore allocates budget at two levels (Algorithm 1, Figure 3).

Upper level: pending-aware PW-MCTS across lineages. Write v(n) and π(n) for a node’s completed and in-flight (pending) counts. When a pipeline starts, it is credited to π for every node on its ancestor chain and cleared when it completes. Thus, π(n) tracks all in-flight work beneath n. A node is eligible for expansion when its completed-child count satisfies progressive widening Chaslot et al. [2008b],

![](images/13bf5cc30f720687b70566174124160c9b11cddda86ba78108c174624998f6fb.jpg)

(1)

where k=1.0 and α=0.5, so the branching factor grows only as a lineage accumulates evidence. An eligible node must also have no in-flight direct child. One design axiom exempts the root ρ from this second condition, so ρ always satisfies the backpressure condition. Equation (1) still governs its routine expansion. Selection descends from ρ to the completed child maximizing a pending-aware upper-confidence bound Kocsis and Szepesv´ari [2006] that counts in-flight candidates in both parent and child visits:

![](images/8bed153b4ed61baf02f3ecffbfd055a9af904257b21874b9f33f62add346c438.jpg)

(2)

where Q<sub>sub</sub>(c) is the sum of rewards over all completed artifacts in the subtree rooted at c, and v(c) is that node’s completed visit count. The exploitation term values entire lineages using only completed evidence. Pending counts in the exploration term prevent over-allocation to branches whose workers are still busy. The descent stops at the first eligible node, which is expanded by creating one in-flight child. Re-expanding a completed node forms siblings, so progressive widening bounds per-node fan-out while depth remains UCB-driven. Under a single worker, the root becomes eligible again at v = 2, 5, 10, 17, . . .. When the UCB descent reaches a busy dead end, the fallback unconditionally expands the root ρ, preventing pipeline starvation. This fallback also handles cold start: at t=0, Eq. (1) is false for the root, so the first expansion always uses the fallback. The eligibility rule thus gives each non-root node at most one in-flight child (backpressure). C=10.0 matches the [0, 10] reward domain; all three constants appear verbatim in the released configuration. Write S(A) = Score(A). Raw scores are non-stationary, so rewards are population percentiles via mid-rank,

![](images/be0ccb2a43707b018cc6d40b237d5a5f737c93604b5b8c203459103dada616b8.jpg)

(3)

with midrank = (#below + #at or below)/2 over the N completed artifacts at assignment time. A fabrication-zeroed artifact receives reward 0 regardless of its raw Score and does not enter the percentile population N. Each artifact’s percentile reward is computed at completion and frozen; historical rewards are not recomputed as the population grows, keeping backed-up values stable. The percentile reward is a distribution-adaptive choice; complete scheduler logs are released for analysis.

Our selection rule extends the parallel MCTS lineage Coulom [2006], Kocsis and Szepesv´ari [2006], Liu et al. [2020] with deterministic pending-count penalties rather than virtual-loss correction Chaslot et al. [2008a], Segal [2010], and composes five mechanisms for asynchronous evaluation: progressive widening, percentile rewards, backpressure, root fallback, and lineage-granularity expansion. Together these guarantee the pipeline never starves and every lineage receives unbounded visits asymptotically Kocsis and Szepesv´ari [2006], Chaslot et al. [2008b], Liu et al. [2020].

Lower level: elimination tournaments within a pipeline. Each proposer starts with 16 candidates and eliminates half per pass (16 → 8 → 4 → 2 → 1). This elimination tournament follows the spirit of successive halving Jamieson and Talwalkar [2016] and Hyperband Li et al. [2018]. Because candidates are revised between passes, the tournament refines candidates rather than resampling fixed arms. The platform’s simulator is deterministic for a fixed expression and settings, so the planned 16+8+4+2+1 = 31 simulations measure 31 distinct candidate versions. The counterfactual 16×5 = 80 runs all 16 starting candidates through all five revision passes. The ratio 2.6× is an allocation count, reported as such rather than as a measured claim about tokens, money, or wall-clock time.

![](images/589495e7d202b4e7ea4e565709d9c096550018685f042825ae57ec2072362cb9.jpg)

Algorithm 1 Two-Level Budget Allocation   
Require: tree T rooted at ρ; worker pool W ; C=10.0, k=1.0, α=0.5   
1: eligible(n): Eq. (1) holds and (n = ρ or n has no in-flight direct child) ▷ ρ always satisfies   
backpressure (design axiom)   
2: while budget remains and a worker is free do   
3: n ← ρ   
4: while not eligible(n) and n has a completed child do   
5: n ← arg max<sub>c</sub> UCB(c) over completed children of n (Eq. (2))   
6: end while   
7: if eligible(n) then   
8: expand n: assign worker tournament 16→8→4→2→1 on lineage of n; create one in-flight   
child   
9: else   
10: expand ρ: open a new lineage ▷ root fallback at a busy dead end; pipeline never starves   
11: end if   
12: on completion (asynchronous): reviewer audits the frozen artifact (Table 2); if fabrication   
is verified, r(A) ← 0 (Eq. (3)); otherwise compute and freeze r(A); backpropagate; clear   
pending along the ancestor chain   
13: end while  
Figure 3: Two-level budget allocation. (a) A pending-aware PW-MCTS selects which lineage receives the next pipeline; dashed nodes are in-flight. (b) A halving tournament concentrates 31 simulations on survivors versus the 80-simulation all-candidates schedule.

## 5 Evaluation and Artifact Release

## 5.1 Protocol

We chose WorldQuant BRAIN WorldQuant [2026] as an external evaluator. On this production platform, consultants submit alphas for potential compensation, giving the platform economic stakes beyond our paper. An academic holdout changes scored rows while authors retain control of the pipeline, costs, metrics, and disclosure Shi et al. [2025, 2026], Wang et al. [2026]. BRAIN instead controls the data, simulator, checks, and grades; we cannot alter its implementation, recompute grades locally, or relax failed gates. We designed the protocol around this separation: external adjudication is stronger for our end-to-end claim than another date split inside a self-administered backtest.

We fixed one deployment protocol across all users: U.S. TOP3000 equities, delay one, and the platform evaluation window January 1, 2019 through December 31, 2023. The proposer chooses neutralization, decay, truncation, data fields, and expression structure. Humans supplied the system and launched the evaluation, but wrote no factor expression or factor-specific program. BRAIN computes metrics from its own data and assigns grades after submission. Its SPECTACULAR grade—the highest of four tiers—requires clearing the platform’s gates with a strong composite score. We report the returned values without re-estimation and release the submitted expressions, platform records, and complete generation trail.

We organize the evaluation around four questions.

• Q1: Does AgonAlpha reproduce platform-validated discovery across independent users?

• Q2: Does artifact-level review detect defects that formula-level records cannot represent?

• Q3: Does the allocator operate under real concurrency and concentrate simulations as specified?

• Q4: Can every headline result be reconstructed from the public trail?

The evidence index in the supplement maps each claim to a specific artifact.

## 5.2 Overview

Five co-authors independently deployed AgonAlpha on WorldQuant BRAIN using separate accounts and diferent model backends. Each ran the same two-role prompt surface and MCTS scheduler without human-written factor code. Collectively they produced 60 submissions, of which 17 received SPECTACULAR grade. All submitted alphas entered BRAIN’s out-of-sample (OS) tracking stage. We feature five SPECTACULAR-grade submissions representing distinct economic mechanisms; complete per-user deployment trees for all 60 submissions appear in the supplementary material. Table 3 reports the platform benchmark for the five featured alphas. All five passed BRAIN’s Fitness, Sharpe, turnover, weight-concentration, sub-universe, self-correlation, and competition-matching checks.

A17q5RdR: aligned six-month option demand. The construction is

![](images/6ec5f0a9ae5e1e4f02a58e5adb88f3775d50d4224b01a3a72d72a7309a911216.jpg)

(4)

where B backfills only the contemporaneously aligned call–put spread. A relatively expensive six-month call indicates stronger demand for upside optionality, whereas a negative spread indicates stronger demand for downside protection; the 40-day mean treats that imbalance as persistent positioning rather than a one-day shock. Computing the aligned spread before backfilling prevents stale observations from diferent dates from creating an artificial spread. With industry neutralization, no simulation decay, and 8% truncation, the alpha attains Fitness 3.93, Sharpe 2.52, turnover 5.92%, and self-correlation 0.1827. Annual Fitness is 2.49, 1.13, 3.94, 10.59, and 2.98 from 2019 to 2023. Every year is positive, with the strongest contribution from the 2022 option-demand regime.

![](images/381dc3d47732fb546435241910a4653e1d02b31272dd964f7c030e1053a87af1.jpg)  
Table 3: Comprehensive BRAIN benchmark for five representative validated alphas. Return, turnover, drawdown, and margin are platform-assigned values. Sub-universe Sharpe and self-correlation show the observed value followed by the applicable passing boundary.

88er8JAl: relative-volume stability. This alpha is

![](images/75024085a65f6aedb319637f3dcbe2f675c5ad8cea43919e2bdc153d39bf5712.jpg)

(5)

Dividing daily volume by its 20-day average makes participation comparable across stocks; the negative 40-day dispersion then buys stocks with steady relative participation and sells stocks dominated by episodic, attention-driven volume. The mechanism is consistent with temporary speculative demand unwinding more strongly among stocks with unstable volume. With industry neutralization, decay two, and 5% truncation, the alpha records Fitness 2.55, Sharpe 1.76, return 26.24%, and turnover 9.58%. Annual Fitness is 2.71, 1.76, 1.15, 5.34, and 3.48, and turnover stays between 9.21% and 9.92% in every year. Annual Fitness and turnover are stable across regimes, with 2022 strongest.

LL1mdWz6: persistent short interest with reversal timing. The construction is

![](images/59010b278886c073b33a43edef7adfe7f2f82b89b6242817ffdeefdcbfdb80c0.jpg)

(6)

where B<sup>sub</sup> 60 is a 60-day subindustry backfill. The slow market normalization makes short interest comparable through time without a unit warning. Subindustry backfill and hold-on-missing logic preserve breadth, while the small five-day reversal sleeve times entry after temporary price pressure. The expression has no arbitrary centering ofset and only one explicit blend coeficient, 0.1, whose role is to keep the timing sleeve secondary to the persistent-short signal. Its Fitness 2.82, Sharpe 2.32, turnover 7.82%, drawdown 6.91%, and low self-correlation of 0.4173 jointly show that the result is not obtained by excessive trading or duplication of an existing alpha. Annual Fitness is positive in every year and equals 1.02, 7.08, 2.57, 3.83, and 0.95 from 2019 to 2023. The positive sign on high short interest is an empirical open question.

pwlL71Ex: multi-tenor downside-insurance disagreement. Let IV <sup>put</sup><sub>τ</sub> − IV <sup>call</sup> measure put– call implied-volatility disagreement at tenor τ . The alpha is

![](images/192bdd50e2a2ab648fba78e9fc643df1c4d515f54198ae1d1e072b6c2c5e5a66.jpg)

(7)

Persistent demand for downside protection is interpreted as bearish private information, distress, or crowded insurance demand; low or reversed disagreement is bullish relative to sector peers. The three tenors enter with equal weight, so the expression does not rely on fitted cross-tenor coeficients or an unexplained additive constant. Its Fitness 4.73 and Sharpe 3.03 are accompanied by low turnover of 5.08%, self-correlation of 0.4968, and passage of the sub-universe check. Annual Fitness is 2.76, 3.77, 4.96, 9.92, and 2.39, remaining above 2 in every year even though 2022 is strongest. The 48-day mean is the main localized tuning risk.

## KPE0LnN1: state-conditioned option confirmation. Define

![](images/4619da07fb4ebf4de3b5dec4ebff6314d9e7cb7ad9168c62199d45f44b58552c.jpg)

The final expression is

![](images/b5ed8f2de0b716bfe31423c36fe6fc7f4d9dcac20d95b3c7814b497aa2d6ef2c.jpg)

(8)

The multi-tenor skew supplies direction, while industry-level skew magnitude and the option-forward curve supply confidence only when long-dated positioning is call-dominant. The gate at one is the economically natural put/call balance point rather than a fitted additive ofset. This alpha attains Fitness 9.50 and Sharpe 3.48, passes the sub-universe Sharpe check at 1.76 versus 1.51, and remains below the self-correlation ceiling at 0.6321. Annual Fitness is 8.43, 2.59, 18.28, 17.19, and 4.15; the weakest year exceeds 2.5.

## Good properties of the obtained alphas.

• Clear and diverse economic mechanisms. The five alphas express distinct hypotheses involving option demand, relative-volume stability, short-interest persistence with reversal timing, multi-tenor downside-insurance demand, and state-conditioned option confirmation.

• Strong performance under comprehensive checks. All five receive BRAIN’s SPEC-TACULAR assessment, with Fitness from 2.55 to 9.50 and Sharpe from 1.76 to 3.48, while passing the platform’s turnover, weight-concentration, sub-universe, self-correlation, and competition-matching checks.

• Low redundancy, moderate turnover, and transparent constants. Self-correlation is below 0.70 for every alpha; turnover is between 5.08% and 9.58%; and none of the five contains an unexplained additive shift.

## 5.3 Reviewer Interventions (Q2)

The reviewer audited 24 frozen reports across the full trace and exercised its zero-score authority twice. One intervention addressed a semantic mismatch between a claimed mechanism and its executed operator. The other addressed metrics copied from a diferent candidate into a final report. Eleven additional artifacts carry persistent risk findings for regime concentration or redundancy. Because every proposer report is frozen before review, the trace records an exact pre-review and post-review state for every node, making each intervention directly inspectable.

## 5.4 Allocation and Concurrency (Q3)

Within each pipeline, tournament elimination evaluates 16 + 8 + 4 + 2 + 1 = 31 candidate versions—a 61% reduction from the 80 simulations required to carry all 16 candidates through five passes. A validated deployment instantiated ten concurrent proposer–reviewer pipelines under one pending aware search tree. Scheduler logs retain every dispatch, pending-count update, completion, and backpropagation event.

## 5.5 Artifact Completeness

The accompanying release contains the proposer, reviewer, and dispatcher prompts; prompt history; scheduler code and complete MCTS state; all candidate reports; simulation inputs and responses; rankings; correlation records; submission checks; and final submission responses. The released reports preserve the literal executable FASTEXPR strings and the detailed formula records for every discussed alpha.

The 30-paper audit provides a fixed comparison boundary [Yao and Zheng, 2026]. No audited study is complete across its five reproducibility fields, even though 18 expose some artifacts. AgonAlpha releases the complete prompt-to-factor trail and exact production formulas for all submissions. This is the first complete prompt-to-factor release in the audited LLM trading literature.

## 6 Discussion and Limitations

Every deployment used the same controlled BRAIN benchmark: U.S. TOP3000 equities, delay one, and a 2019–2023 evaluation window. Under identical externally administered rules, all five users obtained platform-validated alphas, 17 of 60 submissions received SPECTACULAR grade, and every featured submission passed BRAIN’s full gate suite.

A chronological holdout and an external evaluator address diferent failure modes. A holdout tests later rows under the same author-configured pipeline; BRAIN instead removes the data, simulation, metric, gate, and grade implementations from our control. The platform’s proprietary operation separates the method from its evaluator, while our open trail lets readers inspect every submitted expression, returned record, and search decision. For our central claim, evaluator independence is the stronger test of whether autonomous artifacts survive production research gates. Every submission also entered BRAIN’s OS tracking stage under the same external authority. Academic backtests remain useful for algorithmic comparisons, but provide weaker evidence for this end-to-end claim.

Across the five deployments, the reviewer audited frozen reports and exercised zero-score authority for verified fabrication. The selection-risk audit dimension records search pressure, and the data-snooping literature provides the framework for interpreting selection efects White [2000], Hansen [2005], Harvey et al. [2016], Bailey and L´opez de Prado [2014], Bailey et al. [2014]. Table 1 compares 15 systems on architectural axes; AgonAlpha is the only system that satisfies all four. The released trail contains all prompts, search decisions, platform records, review text, and executable expressions.

## 7 Conclusion

AgonAlpha suggests that the core principles of the Agon philosophy can be compressed into a minimal yet complete discovery architecture: two roles and a 101-line prompt are suficient to support an adversarially verified research workflow. The fundamental search unit is not a formula, but a verified artifact containing the evidence and reasoning behind a candidate. The verifier is granted the authority to independently reproduce evaluations and veto unsupported claims, while the scheduler converts concurrent exploration into a structured search over research lineages. By releasing the complete execution trace, AgonAlpha enables inspection rather than blind trust of every reported result. Because these mechanisms operate independently of the underlying domain, the same two-role interface and MCTS-based scheduling framework can be applied to any setting with a well-defined objective evaluation metric.

## References

Agora. Ai trading’s alpha singularity: Emergent market reasoning through agent-to-agent selfevolution. arXiv:2606.29194, 2026. URL https://arxiv.org/abs/2606.29194.

AlphaCrafter. Alphacrafter: A full-stack multi-agent framework for cross-sectional quantitative trading. arXiv:2605.05580, 2026. URL https://arxiv.org/abs/2605.05580.

ATLAS. Atlas: Adaptive trading with llm agents through dynamic prompt optimization and multi-agent coordination. arXiv:2510.15949, 2025. URL https://arxiv.org/abs/2510.15949.

David H. Bailey and Marcos L´opez de Prado. The deflated sharpe ratio: Correcting for selection bias, backtest overfitting, and non-normality. Journal of Portfolio Management, 40(5):94–107, 2014. URL https://doi.org/10.3905/jpm.2014.40.5.094.

David H. Bailey, Jonathan M. Borwein, Marcos L´opez de Prado, and Qiji Jim Zhu. Pseudomathematics and financial charlatanism: The efects of backtest overfitting on out-of-sample performance. Notices of the AMS, 61(5):458–471, 2014. URL https://doi.org/10.21314/JCF.2016. 311.

G. Chaslot, M. Winands, and H. van den Herik. Parallel monte-carlo tree search. In Proceedings of the 6th International Conference on Computers and Games (CG), pages 60–71, 2008a. URL https://doi.org/10.1007/978-3-540-87608-3 6.

G. Chaslot, M. Winands, H. van den Herik, J. Uiterwijk, and B. Bouzy. Progressive strategies for monte-carlo tree search. New Mathematics and Natural Computation, 4(3):343–357, 2008b. URL https://doi.org/10.1142/S1793005708001094.

Andrew Y. Chen and Ivo Welch. What useful alphas? arXiv:2607.06502, 2026. URL https: //arxiv.org/abs/2607.06502.

CogAlpha. Cognitive alpha mining via llm-driven code-based evolution. arXiv:2511.18850, 2025. URL https://arxiv.org/abs/2511.18850.

R. Coulom. Eficient selectivity and backup operators in monte-carlo tree search. In Proceedings of the 5th International Conference on Computers and Games, 2006. URL https://doi.org/10.1007/978- 3-540-75538-8 7.

FactorMAD. Factormad: Multi-agent debate for alpha factor mining. In Proceedings of the ACM International Conference on AI in Finance (ICAIF), 2025. URL https://doi.org/10.1145/3768292. 3770377.

Jun Han, Shuo Zhang, Wei Li, Zhi Yang, Yifan Dong, Tu Hu, Jialuo Yuan, Xiaomin Yu, Yumo Zhu, Fangqi Lou, Xin Guo, Zhaowei Liu, Tianyi Jiang, Ruichuan An, Jingping Liu, Biao Wu, Rongze Chen, Kunyi Wang, Yifan Wang, Sen Hu, Xinbing Kong, Liwen Zhang, Ronghao Chen, and Huacan Wang. QuantaAlpha: An evolutionary framework for LLM-driven alpha mining. arXiv:2602.07085, 2026. URL https://arxiv.org/abs/2602.07085.

Peter Reinhard Hansen. A test for superior predictive ability. Journal of Business & Economic Statistics, 23(4):365–380, 2005. URL https://doi.org/10.1198/073500105000000063.

Campbell R. Harvey, Yan Liu, and Heqing Zhu. . . . and the cross-section of expected returns. The Review of Financial Studies, 29(1):5–68, 2016. URL https://doi.org/10.1093/rfs/hhv089.

Huang and Fan. Beyond prompting: An autonomous framework for systematic factor investing via agentic ai. arXiv:2603.14288, 2026. URL https://arxiv.org/abs/2603.14288.

K. Jamieson and A. Talwalkar. Non-stochastic best arm identification and hyperparameter optimization. In Proceedings of the 19th International Conference on Artificial Intelligence and Statistics (AISTATS), 2016. URL http://proceedings.mlr.press/v51/jamieson16.pdf.

L. Kocsis and C. Szepesv´ari. Bandit based monte-carlo planning. In Proceedings of the 17th European Conference on Machine Learning (ECML), 2006. URL https://doi.org/10.1007/11871842 29.

L. Li, K. Jamieson, G. DeSalvo, A. Rostamizadeh, and A. Talwalkar. Hyperband: A novel banditbased approach to hyperparameter optimization. Journal of Machine Learning Research, 18(185): 1–52, 2018. URL https://arxiv.org/abs/1603.06560.

Y. Li, X. Yang, X. Yang, M. Xu, X. Wang, W. Liu, and J. Bian. R&D-agent-quant: A multiagent framework for data-centric factors and model joint optimization. In Advances in Neural Information Processing Systems, 2025. URL https://arxiv.org/abs/2505.15155.

Z. Li, R. Song, C. Sun, W. Xu, Z. Yu, and J.-R. Wen. LLMFactor: Extracting profitable factors through prompts for explainable stock movement prediction. In Findings of the Association for Computational Linguistics: ACL 2024, pages 3891–3902, 2024. URL https://arxiv.org/abs/2406. 10811.

Anji Liu, Jianshu Chen, Mingze Yu, Yu Zhai, Xuewen Zhou, and Ji Liu. Watch the unobserved: A simple approach to parallelizing monte carlo tree search. In International Conference on Learning Representations, 2020. URL https://arxiv.org/abs/1810.11755. arXiv:1810.11755.

Haochen Luo, Ho Tin Ko, Jiandong Chen, David Sun, Yuan Zhang, and Chen Liu. Alphabench: Benchmarking large language models in formulaic alpha factor mining. In The Fourteenth International Conference on Learning Representations, 2026. URL https://openreview.net/forum? id=d97Q8r7ZKZ.

R. B. Segal. On the scalability of parallel UCT. In Proceedings of the 7th International Conference on Computers and Games (CG), pages 36–47, 2010. URL https://doi.org/10.1007/978-3-642- 17928-0 4.

H. Shi, W. Song, X. Zhang, J. Shi, C. Luo, X. Ao, H. Arian, and L. A. Seco. Alphaforge: A framework to mine and dynamically combine formulaic alpha factors. In Proceedings of the AAAI Conference on Artificial Intelligence, volume 39, pages 12524–12532, 2025. URL https://arxiv.org/abs/2406.18394.

Y. Shi, Y. Duan, and J. Li. Navigating the alpha jungle: An LLM-powered MCTS framework for formulaic factor mining. In Proceedings of the AAAI Conference on Artificial Intelligence, volume 40, pages 997–1005, 2026. URL https://arxiv.org/abs/2505.11122.

Y. Sun, X. Ren, C. Yi, J. Guo, K. Zhang, J. Du, and H. Yang. Agon: An autonomous large-scale omnidisciplinary research system built on prompt economy. arXiv:2606.24177, 2026a. URL https://arxiv.org/abs/2606.24177.

Y. Sun, X. Ren, C. Yi, J. Guo, K. Zhang, J. Du, and H. Yang. Perspectivegap: A benchmark for multiagent orchestration prompting. arXiv:2606.08878, 2026b. URL https://arxiv.org/abs/2606.08878.

Wang et al. Factorminer: A self-evolving agent with skills and experience memory for financial alpha discovery. In International Conference on Learning Representations, 2026. URL https: //arxiv.org/abs/2602.14670.

Weng et al. Alphalogics: A market logic-driven multi-agent system for scalable and interpretable alpha factor generation. arXiv:2603.20247, 2026. URL https://arxiv.org/abs/2603.20247.

Halbert White. A reality check for data snooping. Econometrica, 68(5):1097–1126, 2000. URL https://doi.org/10.1111/1468-0262.00152.

WorldQuant. Worldquant brain platform, 2026. URL https://worldquant.com/brain. Accessed 2026-07.

Junyi Yao and Zihao Zheng. Beyond agent architecture: Execution assumptions and reproducibility in LLM-based trading systems. arXiv:2606.08285, 2026. URL https://arxiv.org/abs/2606.08285.

Yu et al. Alpha-GPT: Human-AI interactive alpha mining for quantitative investment. In Proceedings of the 29th ACM SIGKDD Conference on Knowledge Discovery and Data Mining, 2023. URL https://arxiv.org/abs/2308.00016.

Zhang et al. From feedback loops to policy updates: Reinforcement fine-tuning for llm-based alpha factor discovery. arXiv:2605.15412, 2026. URL https://arxiv.org/abs/2605.15412.

Zhao et al. Quantfactor reinforce: Mining steady formulaic alpha factors with variance-bounded reinforce. arXiv:2409.05144, 2025. URL https://arxiv.org/abs/2409.05144.

# Supplementary Material for AgonAlpha: Autonomous Alpha Discovery via Prompt Economy and Scalable Agentic Search

Weicheng Ye, Youran Sun, Xingyu Ren, Shunyao Yu, Chugang Yi, and Haizhao Yang

## Deployment summary

Multiple co-authors independently deployed AgonAlpha on separate WorldQuant BRAIN accounts, each using the same two-role prompt surface and MCTS scheduler without modification. We deliberately fixed U.S. TOP3000 equities, delay one, and the platform evaluation window from January 1, 2019 through December 31, 2023 so that every deployment faced identical externally administered rules. Table 4 summarizes the outcomes across deployments. All submitted alphas entered BRAIN’s out-of-sample tracking stage.

![](images/8b6b5e8ba706d32375c636b94f2f13678fc5eefc8e18749518d8a295474f2488.jpg)  
Table 4: Per-user deployment outcomes. All values are platform-assigned metrics; Best Sharpe is the full-universe value.

Tables 5–9 expose the recorded search topology of every deployment rather than only the submitted winners. Indentation and the Parent column specify tree edges, v records MCTS scheduler visits, and a BRAIN ID identifies an alpha that was submitted and entered OS tracking. A parent– child edge therefore records search lineage, not a requirement that the parent itself was submitted. Self-correlation is platform-computed against previously submitted alphas, with 0.70 as the ordinary passing boundary. Across the tables, identifiers are set in monospace, “–” denotes unavailable or inapplicable data, and SPECTACULAR grades are bold. The Sharpe headings distinguish full-universe Sharpe from the sub-universe Sharpe used in a submission check.

The realized trees difer substantially in size and selectivity. After excluding the virtual roots, Users A–E have 15, 24, 11, 26, and 19 recorded nodes, respectively, of which 15, 23, 7, 6, and 9 were submitted. These counts describe the realized traces rather than a normalized eficiency comparison: the deployments end with diferent visit allocations, and some trees retain nodes marked no record, discarded, not submitted, or pending.

## Tree-specific patterns.

• User A: complete submission with concentrated late gains. All 15 non-root nodes were submitted. The two SPECTACULAR alphas, nodes 0012 and 0015, terminate sibling refinement paths under node 0004; node 0015 attains the deployment maxima of 2.87 Fitness and 3.25 Sharpe.

• User B: recovery beyond a failed parent. This tree submits 23 of 24 nodes and produces seven SPECTACULAR alphas, the largest count among the five deployments. Node 0018 fails four submission gates, yet its descendants produce four SPECTACULAR and two EXCELLENT alphas. The same lineage contains node 0021, which attains the overall maxima of 9.50 Fitness and 3.48 Sharpe. In this trace, a failed parent therefore does not terminate further refinement.

• User C: a compact tree with the highest top-grade share. Four of seven submitted alphas receive SPECTACULAR grade, the largest fraction among the deployments. All four descend from root child 0003 through the 0004 and 0005 branches, although several submitted descendants also exceed the ordinary 0.70 self-correlation boundary.

• User D: broad exploration with selective submission. This is the largest recorded tree, with 26 non-root nodes, but only six submissions and no SPECTACULAR grade. Its deepest successful path, 0003 → 0005→ 0008→ 0040, ends in an EXCELLENT alpha with Fitness 2.25. The tree consequently records substantially more rejection and continuation than final-grade concentration.

• User E: pruning with two successful lineages. The tree retains discarded, not-submitted, and pending nodes while submitting nine alphas, four of which are SPECTACULAR. Three SPECTACULAR nodes (0007, 0012, and 0010) descend from the 0004 branch, while node 0011 arises under the distinct 0008 branch.

![](images/0f08a99703765ef6d66187afef2420d6b52258fb686b9bde84c49576aca68b4a.jpg)  
Table 5: User A deployment MCTS tree. Indentation and the Parent column specify every edge. All submitted nodes entered BRAIN OS tracking. † BRAIN returned PASS despite scalar values above the 0.70 limit.

![](images/662e0b355116e59579681defae0add39064f0c32406c674f3e17fb6510751404.jpg)  
Table 6: User B deployment MCTS tree. A BRAIN ID indicates submission and OS tracking entry. Nodes marked vetoed were submitted but received reviewer score zero. Node 0018 failed submission gates and was not submitted.

![](images/4829a431e1f25b67ff3d0c7b0c9fc213ac01f1dfad804a6ccb8a14e92c978c9e.jpg)  
Table 7: User C deployment MCTS tree. Reviewer: DeepSeek V4 Pro, Kimi K3. Indentation indicates parent-child edges. All submitted nodes entered BRAIN OS tracking. The Sharpe column reports sub-universe submission-check Sharpe. † marks submitted alphas with reported self-correlation above 0.70.

![](images/6f6826f5083383763ff7b1f89840cb706d08f4c4bd7e6afe5ad20e30e34aae9f.jpg)  
Table 8: User D deployment MCTS tree. Indentation indicates parent-child edges. A BRAIN ID indicates submission and OS tracking entry. † BRAIN marks 0.9546 as PASS against a 0.70 limit; the Alpha is ACTIVE/OS.

![](images/3e499013015c145687be2bf3ef2b3683548baf6a55e04d1c6d9ca742dc10b049.jpg)  
Table 9: User E deployment MCTS tree. Reviewer: gpt-5.6-sol. Indentation indicates parent-child edges. All submitted nodes entered BRAIN OS tracking. The Sharpe column reports sub-universe submission-check Sharpe; full-universe Sharpes for featured alphas appear in the main paper.

## Representative sample run

We present one continuous AgonAlpha trace on WorldQuant BRAIN as a representative execution from User B. Here, “representative” refers only to the execution protocol: the run uses the same scheduler, proposer–reviewer contract, tournament elimination, platform checks, and artifact logging used in an ordinary AgonAlpha execution. It does not mean that this single trace estimates the distribution of results over repeated independent runs. The trace is instead a fully inspectable example of how the program expands, critiques, selects, and submits alpha hypotheses from end to end.

Every submitted alpha uses U.S. TOP3000 equities, delay one, and an evaluation window from January 1, 2019 through December 31, 2023. The proposer could choose industry or subindustry neutralization, decay, truncation, data fields, and expression structure. Humans supplied the system and started the trace, but wrote no factor expression or factor-specific program.

BRAIN computes metrics from its platform data and assigns grades after submission. We report the platform values without re-estimating them. These values are deterministic records for the submitted expressions, so confidence intervals do not apply to individual table cells.

The trace contains 24 evaluated alpha nodes under a virtual root. Twenty-three nodes passed the platform gates and were submitted, for a yield of 23/24. Node 0018 was retained in the tree but not submitted because it failed Fitness, turnover, concentration, and sub-universe checks. The best raw platform Fitness and Sharpe are both attained by node 0021, at 9.50 and 3.48, respectively. The OS tracking stage stores out-of-sample metrics separately; all submitted alphas entered this stage.

Table 6 is a preorder traversal of the complete tree from a User B deployment. Nodes marked vetoed were submitted but received reviewer score zero. Node 0018 failed submission gates and was not submitted.

## What the reviewer found

All 24 node reports contain reviewer blocks. The reviewer found no cheating in 22 reports and set review Fitness to zero for two. For node 0017, the report repeatedly described ts regression(..., rettype=2) as a residual, whereas the live operator documentation defines return type 2 as the regression slope. Tables 10–12 and the detailed account below therefore use the evaluated slope interpretation. For node 0018, the final expression and headline Fitness matched the platform, but its reported drawdown, margin, and long count came from other candidates. The same node also failed four platform submission gates and was not submitted.

Eleven reports received regime-dependence warnings. Node 0014 was additionally flagged for buying high short interest without an adequate ex ante justification; node 0020 was flagged for both the contrarian sign on the composite-revision term and the unexplained centering constant 0.35. These warnings are retained rather than repaired after seeing performance. They separate raw platform success from the reviewer’s assessment of whether the claimed economic story matches the evaluated expression.

## Alpha constructions and economic interpretation

Tables 10–12 cover all 24 MCTS nodes. They use compact operator notation so that the entire search can be inspected in the paper. R is a cross-sectional rank, while R<sub>g</sub> and Z<sub>g</sub> are within-group rank and z-score. M , D , ∆ , and σ denote a d-day mean, linear decay, diference, and standard deviation, respectively. H(c, x) holds the last value when condition c is false, and sp<sub>p</sub>(x) = sign(x)|x|<sup>p</sup>. Subscripts s, i, and G denote subindustry, industry, and the stated relationship group. The released node reports retain the literal executable FASTEXPR strings; the tables expose their operator-level construction and economic content without truncating the tree to a few winners.

## Detailed node-by-node account

The compact tables make the topology and formulas comparable. This subsection records additiona node-level information from the released alpha reports. Each entry names the production artifact, explains what changed relative to its direct parent, gives the main platform settings and raw metrics, and preserves the principal search or review limitation. Fitness and Sharpe below are raw BRAIN values unless a review score is explicitly stated.

## Branch rooted at 0001: price reversal and earnings yield

Node 0001. Artifact: 0001-4-group-multi-horizon; BRAIN ID: mLbg8jVx; Parent: root. This root child combines a 20-day return z-score reversal with a smoother three-day return reversal, scales both by recent volatility, and ranks the result within subindustries. The economic hypothesis is that temporary liquidity demand and overreaction reverse, while volatility scaling makes shocks comparable across stocks. With market neutralization, decay 8, and 5% truncation, the node records Fitness 1.02, Sharpe 2.00, turnover 56.50%, and drawdown 5.07%. Its report documents a four-round tournament and notes that the Fitness margin over the submission threshold is only 0.02.

Node 0002. Artifact: 0002-4-earnings-yield-decay6; BRAIN ID: 9qrWzY8e; Parent: 0001. The child leaves the parent’s price-reversal family and instead ranks the 252-day time-series zscore of consensus EPS divided by price. It therefore buys firms whose forward earnings yield has risen relative to its own annual history, then compares the result within subindustries. Market neutralization, decay 6, and 5% truncation produce Fitness 1.73, Sharpe 2.07, turnover 6.42%, and drawdown 4.39%. The much lower turnover reflects the slower analyst-estimate channel, but the exact 252-day standardization window remains a search choice rather than independent evidence of a one-year mechanism.

Node 0005. Artifact: 0005-4-balanced-multifactor-multihorizon; BRAIN ID: 9qrEoNno; Parent: 0001. This sibling retains the parent’s multihorizon price reversal but makes its strength increase with volume relative to ADV20 and adds a contrarian rank of static and accelerating multifactor-model scores. Economically, the model component captures slow overvaluation while high relative volume is treated as confirmation that a large price displacement is informative enough to rank strongly. With market neutralization, decay 10, and 5% truncation, the node reaches Fitness 1.33, Sharpe 1.87, turnover 22.86%, and drawdown 8.67%. The report treats the blend as a diversification exercise rather than evidence that every model subscore has a distinct causal channel.

## Branch rooted at 0003: model, customer, news, and product-group reversal

Node 0003. Artifact: 0003-4-balanced-revision-reversal; BRAIN ID: N1rV29p8; Parent: root. This root child combines a slow contrarian analyst-revision-acceleration term with a five-day price decline divided by 20-day average volume. The low-volume scaling emphasizes price moves that may reflect temporary pressure, while subindustry ranking and neutralization reduce structural industry diferences. Decay 18 and 5% truncation yield Fitness 1.38, Sharpe 1.60, and turnover 12.34%. The report shows that neither sleeve was independently strong enough to submit; the result comes from their horizon complementarity.

Node 0004. Artifact: 0004-12-customer-acceleration-weight-thirteen; BRAIN ID: 0mEjq6AK; Parent: 0003. The child replaces the analyst term with a broader multifactor-acceleration reversal, lengthens the low-volume price leg to seven days, adds a 1.3-weight contrarian customer-return sleeve, and adds a half-weight five-day return reversal. The customer term tests whether relationship-linked returns overshoot rather than difuse positively. With subindustry neutralization, decay 18, and 5% truncation, the alpha records Fitness 1.40, Sharpe 1.79, and turnover 15.06%. Its maximum self-correlation exceeds the ordinary cutof, but BRAIN passes the submission because Sharpe improves by more than 10% over the most correlated submitted alpha.

Node 0009. Artifact: 0009-20-impact-w15-price-eight-customer-twelve; BRAIN ID: KP9Vvgvj; Parent: 0004. Node 0009 retains the parent’s four sleeves, changes the price horizon to eight days, reduces the customer weight to 1.2, and adds a 1.5-weight RavenPack business-news-impact rank. Crucially, missing news is set explicitly to zero so that a sparse news field does not make the entire additive signal missing and force event-driven turnover. Subindustry neutralization, decay 22, and 5% truncation give Fitness 1.84, Sharpe 2.06, and turnover 14.30%. The final self-correlation check passes only because its Sharpe improvement over the relevant correlated alpha is approximately 10.16%, leaving little margin around the exception boundary.

Node 0010. Artifact: 0010-10-sales-recent-180-book-080; BRAIN ID: qMlOMKGE; Parent: 0004. This child adds a 2.3-weight, 180-day-backfilled sales-growth rank and a 0.8-weight, 252- day-backfilled book-to-price rank to the parent’s model, customer, and price-reversal core. The stronger fundamental weights were selected after a weaker version remained too correlated with the parent; filter=true preserves the parent signal when a fundamental sleeve is missing. With subindustry neutralization, decay 10, and 3% truncation, the node reaches Fitness 1.81, Sharpe 2.13, and turnover 12.31%. Its maximum self-correlation falls to 0.6841, so submission does not rely on the Sharpe-improvement exception.

Node 0007. Artifact: 0007-12-product-cluster-reversal; BRAIN ID: MPQ6V0L6; Parent: 0003. Rather than extending the analyst-revision core, node 0007 moves to product-relationship groups. It buys stocks that lag the five-day return of their product cluster and combines that difusion gap with a low-volume five-day reversal ranked within the same relationship group. Subindustry neutralization, decay 44, and 5% truncation produce Fitness 1.11, Sharpe 1.40, turnover 14.78%, and a maximum self-correlation of 0.4809. The report records two failed terminal attempts before the third workflow cleared both the Fitness and correlation gates, making this node informative about the cost of deliberate decorrelation.

## Branch rooted at 0006: relationship breadth, short interest, and option overlays

Node 0006. Artifact: 0006-10-competitor-breadth-risk-balanced; BRAIN ID: GrLm3d8o; Parent: root. The core signal ranks decayed competitor returns inside relationship groups and multiplies them by the log-ranked number of competitor links, then adds a small long-minus-short systematicrisk-horizon term. The hypothesis is that competitor information is more reliable when it is supported by a broader network, while changing systematic exposure identifies a diferent risk regime. Subindustry neutralization, decay 15, and 8% truncation yield Fitness 1.05, Sharpe 1.32, turnover 10.13%, and drawdown 7.10%. The modest Fitness level makes the node useful mainly as a structurally distinct parent for later expansions.

Node 0008. Artifact: 0008-5-impact-merger-risk-price-robust; BRAIN ID: qMl5v0zZ; Parent: 0006. This child replaces the direct competitor-breadth product with a composite of persistent broad news impact, M&A sentiment, two price-target news fields, and the systematic-risk term structure. The sleeves are intended to combine several channels of delayed information arrival rather than amplify one sparse event field. With subindustry neutralization, decay 16, and 6% truncation, it records Fitness 1.16, Sharpe 1.63, turnover 13.15%, and drawdown 3.95%. Its gain over the parent is real in the trace but small in absolute Fitness, so the report does not treat it as evidence that every news sleeve generalizes independently.

Node 0014. Artifact: 0014-25-persistent-short-reversal; BRAIN ID: LL1mdWz6; Parent: 0006. Node 0014 pivots to a market-scale-normalized level of news short interest, backfilled within subindustries, smoothed for 20 days, and held between valid updates; a small five-day return-reversal term times entry. The positive short-interest sign is interpreted post hoc as crowded-short covering or a securities-lending premium, but the reviewer marks this explanation inadequate because the standard directional prior is bearish. Subindustry neutralization, decay 20, and 2% truncation produce Fitness 2.82, Sharpe 2.32, turnover 7.82%, and drawdown 6.91%. The node also receives a regime warning because annual Fitness ranges from 0.95 to 7.08.

Node 0015. Artifact: 0015-10-fast-persistent-short-acceleration; BRAIN ID: N1rJzP0L; Parent: 0014. This child retains the persistent-short and five-day-reversal anchor, adds a small contrarian multifactor-acceleration sleeve, and changes portfolio controls to decay 8 and 0.75% truncation. The faster decay restores responsiveness, while the unusually tight cap limits the more concentrated composite. The result is Fitness 3.24, Sharpe 2.61, turnover 11.94%, and drawdown 6.59%. The report flags regime dependence: annual Fitness ranges from 0.91 to 6.87, so the in-sample improvement is not temporally uniform.

Node 0016. Artifact: 0016-35-gaussian-macro-fund-final; BRAIN ID: XgnMr2Aa; Parent: 0014. Node 0016 expands the persistent-short anchor with a capital-expenditure expectation surprise, a 720-day call-minus-put implied-volatility spread, and a 120-day call-implied-to-Parkinson-volatility ratio. A Gaussian quantile map emphasizes cross-sectional tails, while trade-on-update logic prevents stale analyst data from generating artificial daily changes. Subindustry neutralization, decay 36, and 0.455% truncation yield Fitness 3.44, Sharpe 2.91, turnover 4.95%, and drawdown 4.87%. The final truncation search is important to the passing Sharpe improvement, but annual Fitness still ranges from 0.97 to 7.04 and triggers a regime warning.

Node 0017. Artifact: 0017-10-resid-all-snt-d25; BRAIN ID: xAkpRWlw; Parent: 0006. The oficial name and report describe a relationship-return residual, but the evaluated rettype=2 operator returns the 20-day regression slope of all-relationship returns on competitor returns. The actual alpha therefore combines competitor-channel exposure, a social-sentiment z-score, and the systematic-risk term structure within relationship groups. Subindustry neutralization, decay 25, and 8% truncation produce raw Fitness 1.18, Sharpe 1.56, turnover 6.42%, and drawdown 4.24%. Because the report’s mechanism does not match the evaluated expression, the reviewer sets review Fitness to zero; annual Fitness from 0.05 to 2.46 also produces a regime warning.

## Branch rooted at 0011: event-conditioned close reversal

Node 0011. Artifact: 0011-8-raven-ratings-slower; BRAIN ID: rKl9GKXj; Parent: root. This root child uses the position of the close within the daily high–low range as a reversal signal and multiplies it by ranked absolute broad-news and analyst-ratings impact after 18-day backfill. The absolute news values measure event importance without trusting the provider’s direction, so the mechanism is a consequential-event filter on weak-close reversal. With subindustry neutralization, decay 12, and 3% truncation, the node records Fitness 1.02, Sharpe 2.21, turnover 54.81%, and drawdown 3.10%. Its self-correlation exceeds the nominal threshold but passes through the morethan-10% Sharpe-improvement exception.

Node 0012. Artifact: 0012-4-annual80-reported60; BRAIN ID: np2m5EXa; Parent: 0011. The child pivots from event reversal to two consensus-earnings-yield trends: a double-weight 80-day time-series rank of adjusted annual EPS over price and a 60-day rank of reported GAAP EPS over price. The second sleeve checks whether the adjusted-EPS trend is supported by reported earnings rather than accounting exclusions alone. Subindustry neutralization, decay 8, and 5% truncation yield Fitness 1.69, Sharpe 1.98, turnover 12.23%, and drawdown 4.35%. Annual Fitness ranges from 0.43 to 4.96, so the reviewer records regime dependence despite positive full-period metrics.

Node 0013. Artifact: 0013-3-news-accel-direction-blend; BRAIN ID: 2rL93WoJ; Parent: 0011. Node 0013 preserves the parent’s news-weighted weak-close reversal, increases its weight when multifactor acceleration has a large magnitude, and adds a contrarian rank of the 20-day mean acceleration direction. The additive 0.25 floor prevents the event-reversal channel from disappearing when model activity is low. With subindustry neutralization, decay 12, and 3% truncation, the node reaches Fitness 1.31, Sharpe 2.52, turnover 43.40%, and drawdown 3.68%. The result demonstrates that high Sharpe need not imply high Fitness when turnover remains materially above the denominator floor.

Branch rooted at 0018: failed news-volume seed and successful option/fundamental descendants

Node 0018. Artifact: 0018-6-lowvol-group-zs; Simulation ID: qMlJ7V0O; Parent: root; Submission: none. This retained root child standardizes the negative 30-day decay of news-day volume surprise within sectors, buying quiet names and shorting unusually active ones. The proposed mechanism is that quiet trading on news days signals lower information asymmetry and informed-trading risk. Subindustry neutralization, decay 10, and 8% truncation produce raw Fitness 0.45, Sharpe 1.40, and turnover 85.88%. The node is not submitted because it fails Fitness, maximum-turnover, concentration, and sub-universe checks; the reviewer also sets review Fitness to zero because its reported drawdown, margin, and long count do not match the final platform record.

Node 0019. Artifact: 0019-12-tenor-blend-mean48; BRAIN ID: pwlL71Ex; Parent: 0018. Node 0019 abandons news volume and sums put-minus-call implied-volatility disagreement at 30-, 60-, and 90-day tenors, averages it for 48 days, reverses the sign, and z-scores it within sectors. Persistent demand for downside protection is treated as bearish, while agreement across tenors reduces dependence on one expiry. Industry neutralization, decay 10, 8% truncation, and NaN handling yield Fitness 4.73, Sharpe 3.03, turnover 5.08%, and drawdown 11.15%. The 48-day window is explicitly tournament-selected and option-data coverage remains the main operational boundary, although all five in-sample years are positive.

Node 0021. Artifact: 0021-28-forward-pcr-low-quartic; BRAIN ID: KPE0LnN1; Parent: 0019. This child trades only when the 20-day mean of the 270-day put/call open-interest ratio is below one. Within that call-dominant state, multi-tenor IV skew supplies direction, while industry-level skew magnitude and a 90/30 option-forward-curve deviation enter as squared and fourth-power confidence terms. Industry neutralization, decay 12, and 8% truncation produce the trace maximum: Fitness 9.50, Sharpe 3.48, turnover 7.93%, and drawdown 19.50%. The threshold one has an economic interpretation, but the 48- and 60-day windows and the fitted powers create substantial selection risk; annual Fitness from 2.59 to 18.28 triggers a regime warning.

Node 0020. Artifact: 0020-41-forward-1080-30-w60-d30; BRAIN ID: E5e5LxqP; Parent: 0018. Node 0020 combines the sector-standardized diference between 1080- and 30-day synthetic option forwards with a contrarian composite-revision rank and activates a low-volatility tilt only in the smallest-capitalization 15%. The long-horizon forward curve is the principal information channel; the gated low-volatility term is designed to protect the higher-capitalization sub-universe check. With no portfolio neutralization, decay 30, and 3% truncation, the node records Fitness 2.24, Sharpe 1.69, turnover 2.01%, and drawdown 13.66%. The reviewer flags the contrarian revision sign, the unexplained 0.35 centering constant, and regime dependence.

Node 0022. Artifact: 0022-9-p8-s08; BRAIN ID: j2rExRxQ; Parent: 0020. This child replaces the option-forward structure with annual and quarterly consensus-EPS-yield deviations from their 126-day means, plus a contrarian 60-day social-sentiment sleeve. After z-scoring, an eighth signed power concentrates the book in the extreme tails and also reduces correlation with the earlier EPS-yield nodes. Subindustry neutralization, decay 10, and 3% truncation yield Fitness 2.77, Sharpe 2.23, turnover 8.76%, and drawdown 7.89%. The power ladder is search-selected and the node remains regime-dependent, with annual Fitness falling to 0.13 in 2023 and reaching 5.81 in 2020.

Node 0023. Artifact: 0023-10-quad-filter-dec20; BRAIN ID: gJ9Oz2Nv; Parent: 0018. Node 0023 builds four separately standardized relationship-group sleeves: volatility-scaled weekly reversal, standardized year-over-year operating-income surprise, volatility-scaled competitor momentum, and gross-margin contraction. Fine relationship groups are used for price sleeves and coarser groups for lower-coverage fundamentals; filter=true treats a missing sleeve as zero rather than removing the stock. Subindustry neutralization, decay 20, and 8% truncation produce Fitness 2.44, Sharpe 2.69, turnover 12.82%, and drawdown 4.17%. The missing-value union is the largest documented improvement in this search, but the sub-universe Sharpe passes exactly at its limit and annual Fitness from 0.84 to 6.15 triggers a regime warning.

Node 0024. Artifact: 0024-7-sept-cpiv-w100; BRAIN ID: 9q70L2mr; Parent: 0023. The final child retains all four parent sleeves and adds two option channels: a half-weight negative 500-day z-score of the 270-day put/call open-interest ratio and a full-weight 10-day decay of the 60-day callminus-put implied-volatility spread. Abnormally put-heavy positioning is bearish, while relatively expensive calls are interpreted as informed bullish demand that reaches the equity price with delay. Subindustry neutralization, decay 20, and 8% truncation yield Fitness 3.35, Sharpe 3.33, turnover 11.80%, and drawdown 3.31%. Self-correlation with node 0023 is 0.8422 but passes through the Sharpe-improvement exception; the sub-universe Sharpe again passes exactly at its limit, and annual Fitness from 1.45 to 7.36 produces a regime warning.

![](images/f09982588a37ba076c0ecd5b9e86d47c7ec13d58008b6a2dd2284d216d309a56.jpg)  
Table 10: Complete alpha catalog and economic interpretations, part 1 of 3. All constructions are faithful operator-level compressions of the released FASTEXPR strings.

![](images/31b156a3158ae9ed34864d3fd2fa96083964e94d87d9e06cc4c902714a832874.jpg)  
Table 11: Complete alpha catalog and economic interpretations, part 2 of 3.

![](images/8dc5add85de4eba0173662b8dc883e3eafd69ffb371721018bbeb1904081dfac.jpg)  
Table 12: Complete alpha catalog and economic interpretations, part 3 of 3. Daggers match the reviewer-invalidated reports in Table 6.

## What this typical run demonstrates

This trace shows how the program can move between genuinely diferent data families rather than merely retune one formula. Some branches improve by adding information to a parent, as in the business-news and option overlays, while others abandon the parent’s mechanism to escape a correlation or Fitness dead end. The retained failure at node 0018 and the reviewer-invalidated explanation at node 0017 are part of the evidence: the tree records failed gates and mismatched reasoning rather than presenting only submitted winners.

At the same time, a typical sample run is not a repeated-run benchmark. The high node-level submission rate, the best Fitness of 9.50, and all lineage-specific improvements describe this trace under one sequence of model states and platform responses. The trace demonstrates that the complete workflow operates as specified under a fixed protocol, producing externally graded artifacts with full provenance.

## Behavior across calendar regimes

Aggregate Fitness can conceal whether an alpha works steadily or earns most of its score in one market environment. We therefore examine all nine nodes whose full-period Fitness exceeds 2.0. For compactness, the five-number sequences below report annual Fitness in chronological order from 2019 through 2023. The calendar years provide descriptive regime slices: roughly pre-pandemic, pandemic shock and rebound, reopening, monetary tightening, and the subsequent rebound. They are not exogenous regime assignments. These slices diagnose temporal concentration within the platform-graded window; they are not an author-defined substitute test set.

Persistent-short branch (0014–0016). The three related alphas have strikingly similar annual profiles. Their annual Fitness sequences are

0014 : (1.02, 7.08, 2.57, 3.83, 0.95),

0015 : (0.95, 6.87, 3.56, 4.25, 0.91),

0016 : (1.81, 7.04, 4.32, 3.62, 0.97).

All three peak near Fitness 7 in 2020 and all fall to approximately 1 in 2023. The acceleration and option/fundamental overlays improve some middle years, but they do not remove the shared temporal shape inherited from the persistent-short anchor. Consequently, the rise in full-period Fitness from 2.82 at 0014 to 3.24 and 3.44 at its children should not be read as independent evidence of regime robustness. The branch appears especially suited to the cross-sectional dislocations of 2020, while the positive high-short-interest sign remains both economically under-explained and empirically state dependent.

Option disagreement and forward-curve branch (0019–0021). Node 0019 is comparatively broad-based: its annual Fitness sequence is (2.76, 3.77, 4.96, 9.92, 2.39), so every year exceeds 2 even though 2022 contributes about 41% of total in-sample PnL. Its descendant 0021 is stronger in every calendar year, at (8.43, 2.59, 18.28, 17.19, 4.15), but the very large 2021–2022 values dominate its full-period Fitness of 9.50. Thus, 0021 is not a one-year result, yet its nonlinear skew and forward-curve construction is clearly most efective in the 2021–2022 option regime. The minimum annual Fitness of 2.59 is reassuring within the sample; the 7.1-fold gap between its best and worst years is not.

Node 0020 provides a useful contrast within the same broad option-data family. Its annual Fitness sequence is

(3.14, 2.87, 3.46, 0.68, 2.31).

The long-horizon forward-curve, contrarian-revision, and small-cap low-volatility blend weakens precisely in 2022, when 0019 and 0021 are strongest. This opposite 2022 behavior suggests that the program did not merely rediscover one generic option-market exposure. It also shows why grouping alphas only by data source is insuficient: sign, tenor, conditioning, and the accompanying equity sleeves determine the regime profile.

Earnings-yield and sentiment tail signal (0022). Node 0022 records

(1.69, 5.81, 2.95, 5.01, 0.13).

It performs strongly in 2020 and 2022 but almost disappears in 2023. The eighth signed power concentrates positions in extreme combinations of earnings-yield change and depressed sentiment; this improves full-period separation and lowers correlation with earlier earnings-yield alphas, but it also makes the result depend on years in which the composite produces suficiently informative tails. The 44.7-fold best-to-worst annual Fitness ratio is the most severe regime imbalance among the stronger nodes.

Relationship-peer branch (0023–0024). The four-sleeve parent 0023 records

(1.45, 0.84, 6.15, 1.41, 3.54),

with its largest payof in 2021 and its weakest result in 2020. Adding abnormal put/call positioning and call–put implied-volatility spread produces 0024’s annual Fitness sequence:

(1.93, 1.45, 7.36, 3.22, 3.46).

The option overlay raises annual Fitness in 2019–2022 and is nearly neutral in 2023, where Fitness slips only from 3.54 to 3.46. It also reduces the best-to-worst ratio from 7.3 to 5.1. This is the clearest within-lineage evidence that a child improved temporal balance rather than merely increasing the best year, although 2021 remains dominant and the ratio still exceeds the reviewer’s regime-warning threshold.

Cross-branch interpretation. The peaks are staggered rather than universal: the persistentshort branch is strongest in 2020, the relationship-peer branch in 2021, and the option-disagreement branch in 2022; node 0020 is unusually weak in that same 2022 environment. This pattern is consistent with the tree discovering economically distinct exposures rather than variants of one hidden common score. It is not, by itself, proof of portfolio diversification, because a combined book was not evaluated and all formulas were selected on the same five-year interval. The main lesson is more modest: high aggregate Fitness should be read together with the annual path. Nodes 0019 and 0024 show the most balanced positive annual evidence among the stronger alphas, whereas 0014–0016 and 0022 depend much more heavily on particular calendar regimes.

Constants and selection risk. Several formulas contain numerical constants that serve diferent purposes but create a common overfitting concern. Some have an ex ante interpretation, such as the put/call threshold of one in 0021, which distinguishes call-dominant from put-dominant positioning, while others are portfolio weights or smoothing horizons chosen from tournament grids. The unexplained centering constant 0.35 in 0020 is the clearest warning case: it mechanically changes the book’s net exposure without an economic or calendar rationale. The squared and fourth-power confidence terms in 0021, the eighth signed power in 0022, and the tenor, lookback, and sleeve weights in 0024 can likewise improve in-sample separation by concentrating on a small set of observations. The program compared multiple nearby values before selecting these specifications; the selected constants are documented in the released reports so that every choice is inspectable. Evidence index

![](images/2d6f68346782d95314175f38e35f5fc5d169056e0ae800125d6b9eb6129b00f4.jpg)  
Table 13: Evidence index: every headline result links to a specific, inspectable artifact bundle.

## Artifact completeness

The accompanying release contains the proposer, reviewer, and dispatcher prompts; prompt history; scheduler code and complete MCTS state; all candidate reports; simulation inputs and responses; rankings; correlation records; submission checks; and final submission responses. The node reports provide the literal executable strings underlying the compact constructions in Tables 10–12. Together, these files connect each public result to the prompt that produced it, the candidates it beat, the reviewer text it received, and the platform record that supports its metrics.

The 30-paper audit provides a fixed comparison boundary [Yao and Zheng, 2026]. No audited study is complete across its five reproducibility fields, even though 18 expose some artifacts. AgonAlpha deliberately uses BRAIN’s external grading rather than substituting an author-defined holdout from a local engine. A chronological split tests temporal transfer conditional on the authors’ backtest implementation. BRAIN adds evaluator independence by controlling the data, simulator, metrics, gates, and grades. Every submitted alpha then enters platform-run out-of-sample tracking. On our side of that boundary, AgonAlpha releases the complete prompt-to-factor trail, exact production formulas, and returned platform records. This is the first complete prompt-to-factor release in the audited LLM trading literature.