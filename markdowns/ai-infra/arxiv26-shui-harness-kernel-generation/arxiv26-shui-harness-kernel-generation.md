# HARNESS ENGINEERING FOR LLM-DRIVEN GPU KERNEL GENERATION

Yue Shui Chenyu Ma Hangfei Xu Shengzhao Wen Yanpeng Wang

Baidu, Inc.

GitHub: github.com/syhya/mlsys26-flashinfer-contest

## ABSTRACT

Large language models (LLMs) can assist GPU kernel generation, but their practical effectiveness depends on whether generated code can be reliably constrained, validated, profiled, and selected. This paper presents a harness-centered system for LLM-driven GPU kernel optimization in the MLSys 2026 FlashInfer AI Kerne Generation Contest on NVIDIA Blackwell B200 GPUs. The system separates an evaluation harness from a profilebacked optimization controller: the harness enforces compilation, correctness, official-aligned timing, and artifact archival, while the controller turns profiler and workload evidence into bounded candidate-generation decisions. Human-authored skills capture operator constraints, references, profiling procedures, and promotion rules, while Codex and Claude Code agents generate candidate kernels inside those constraints. Across five operator definitions, the retained official-aligned artifacts achieved mean-latency speedups over supplied FlashInfer baselines of 1.62×, 18.05×, 29.68×, 1.12×, and 13.70×. The Agent-Assisted kernels outperform the Full-Agent artifacts across the evaluated definitions, indicating that expert-provided optimization directions, high-quality references, and workload context remain critical for reliable AI-driven kernel optimization.

## 1 INTRODUCTION

Efficient LLM serving is increasingly determined by specialized runtime and kernel decisions rather than by the model graph alone, as illustrated by structured generation runtimes, paged key-value (KV) cache serving systems, IO-aware attention kernels, and production GPU inference stacks (Zheng et al., 2024; Kwon et al., 2023; Dao et al., 2022; NVIDIA, 2026b). Operators such as MoE routing, sparse attention, top-k index construction, and recurrent state updates expose irregular shapes, mixed precision, short decode regimes, and long-context regimes. The contest definitions reflect mechanisms used in DeepSeek-MoE, DeepSeek-V3.2 sparse attention, and Gated Delta Networks (Dai et al., 2024; DeepSeek-AI, 2025; Yang et al., 2025). The FlashInfer AI Kernel Generation Contest turns these pressures into a controlled systems benchmark by evaluating submitted kernels for correctness and latency on NVIDIA B200 GPUs against FlashInfer baselines (Ye et al., 2025; Xing et al., 2026; FlashInfer Contest, 2026).

LLM-based coding agents can broaden the implementation search space, as KernelBench and KernelEvolve show for efficient GPU or accelerator kernel generation (Ouyang et al., 2025; Liao et al., 2026). Closed-loop algorithm and program-search systems such as AlphaTensor, AlphaEvolve, OpenEvolve, LoongFlow, ShinkaEvolve, and AVO further motivate generate-evaluate-select loops with evolutionary memory (Fawzi et al., 2022; Novikov et al., 2025; Sharma,

2025; Wan et al., 2025; Lange et al., 2026; Chen et al., 2026). GPU kernel optimization, however, remains a constrained systems problem: a candidate must satisfy the contest packaging contract, compile in the target container, preserve layout and numerical semantics, and improve mean latency over the full workload distribution rather than a single representative case. Failures therefore often arise from the surrounding engineering loop: stale baselines, incomplete workload coverage, packaging drift, noisy promotion, and loss of profiler or provenance information.

This paper studies harness engineering (OpenAI, 2026d; Anthropic, 2026a) as the mechanism for making LLM-driven kernel generation reliable. Prior agent work shows that interface design, interleaved reasoning and action, and verbal feedback memory can materially affect coding-agent behavior (Yang et al., 2024; Yao et al., 2023; Shinn et al., 2023). In this setting, humans define objectives, resources, feedback loops, and promotion rules, while coding agents perform bounded implementation search. The paper evaluates this design across all FlashInfer contest tracks using officialaligned B200 artifacts. The transferable claim is not that a particular model autonomously solves kernel optimization, but that profile-backed controller state, workload-grounded gates, and artifact memory make LLM search auditable enough to improve real contest kernels.

Our approach instantiates this claim through several key designs that make agent-assisted kernel optimization reproducible rather than prompt-only trial and error.

Skill-Grounded Optimization Harness. We encode expert optimization practice as reusable skills rather than one-off prompts. The generic CUDA skill defines the candidate contract, evaluation, profiling, and two-stage search, while the FlashInfer B200 skill adds reference-first reconnaissance, workload discovery, paired gates, official-aligned evaluation, and latency-first promotion.

Profile-Backed Optimization Controller. Beyond measuring candidate code, the workflow separates the evaluation harness from the optimization controller. The controller converts NCU and Torch Profiler evidence into bottleneck state, selects one bounded optimization direction, supervises plateaus or regressions, and records accepted and rejected evidence for later rounds.

Workload-Grounded Shape Dispatch. The system derives optimization regimes from contest workload UUIDs, JSON workload axes, and measured latency distributions rather than from a single hand-picked input. Shape-specialized routes are introduced only when profile and latency evidence show distinct limiting factors.

Human-Guided Plateau Recovery. Human effort remains central: humans design the harness, curate references, decide evaluation budget, and make final promotion decisions. When agents plateau, humans steer the search by switching GPT and Claude model families, requesting sub-agent review, supplying reference kernels or documentation, and changing implementation languages.

Hardware-Aware Language Selection. The workflow treats CUDA C++, Triton (Tillet et al., 2019), and CuTe/CUTLASS (NVIDIA, 2026a) as alternative control surfaces, with DeepGEMM used as FP8 GEMM reference material (DeepSeek-AI Team, 2025). Triton supports rapid specialization, CUDA C++ exposes low-level launch and memory control, and CuTe/CUTLASS provides explicit tensor-core layouts and Blackwell-specific kernels.

Noise-Resistant Promotion and Artifact Memory. Candidates are promoted by all-workload latency evidence, paired baselines, correctness pass rate, and repeated validation where needed rather than by an isolated speedup. Rejected probes, profiler reports, shape matrices, and promotion decisions are archived as negative or positive trajectory memory, reducing repeated exploration of failed routes.

The paper covers all three contest tracks and five definitions: FP8 Fused MoE, DSA, and GDN.

The definitions are summarized in Table 1. The retained runs used an official-aligned environment consistent with FlashInfer-Bench: CUDA 13.2, PyTorch 2.12, Triton 3.6, cupti-python timing, isolated runners, and B200 GPUs. Correctness and latency were both mandatory. Latency was the promotion metric; PyTorch reference latency was used as supporting context. This paper does not propose a new serving runtime, model architecture, or autonomous optimizer; it studies the agent-assisted harness and controller needed to generate correct and fast drop-in contest kernels.

Table 1. Contest definitions covered by this Agent-Assisted paper. Workload denotes the number of official-aligned workloads evaluated for each definition.  
![](images/f999dc8fc8c142c2d0bc09cd11cedbdfae139fa392d61fc4c38174993288a4c7.jpg)

## 2 HARNESS SYSTEM DESIGN

OpenAI describes harness engineering as a shift from humans writing every line of code to humans designing environments, constraints, and feedback loops that let agents do reliable work (OpenAI, 2026d). Anthropic makes a similar argument for long-running application development harnesses (Anthropic, 2026a). In this project, the environment was a CUDA kernel optimization loop rather than an application repository. The harness made the task legible to agents by turning workloads, profiles, rejected variants, and retained baselines into structured context. The architecture used the closed loop in Figure 1.

The loop has four main responsibilities: grounding candidates in operator definitions, reference code, workload JSON files, baselines, and target-environment constraints; discovering shape axes such as sequence length, batch size, page count, and outlier regimes; closing the baseline-profilegenerate-evaluate-archive feedback cycle; and producing an explicit promotion decision with latency evidence and profiler artifacts.

Evaluation harness vs. optimization controller. The evaluation harness is the measurement layer: it packages candidates, compiles them in the target environment, runs correctness checks, measures official-aligned B200 latency, and stores benchmark and profiler artifacts. The optimization controller is the decision layer: it converts profile evidence into a reusable state, selects the next optimization hypothesis, carries supervisor constraints across rounds, and writes outcomes into memory. The unified CUDA optimization skill codifies this controller role, while the FlashInfer contest harness provides workload, environment, and promotion discipline.

The harness used conservative acceptance rules. Representative gates first compared a candidate against the same-round baseline on selected workloads drawn from the measured workload axes. Full sweeps then evaluated the entire distribution. For large definitions such as DSA top-k and GDN prefill, the multi-workload runner launched one evaluation worker per workload up to a worker limit, wrote incremental JSON, and retried transient infrastructure failures. A candidate was promoted only if the full distribution improved without correctness regressions. Rejected probes were archived because negative evidence prevents repeated exploration of failed launch-bound, fusion, or tile-size hypotheses.

![](images/e1bda6806142667d40eae9c0845b09dd28c829f3b241b91abe242c7671a62623.jpg)  
Figure 1. Closed-loop harness/controller workflow used for CUDA kernel optimization. The harness measures, archives, and promotes candidates, while the controller structures prompt construction, candidate generation, profiling feedback, and trajectory memory.

## 3 OPTIMIZATION WORKFLOW

## 3.1 Agent and Prompting Workflow

The optimization workflow used Codex and Claude Code as coding agents. The primary model families were GPT-5 variants, especially GPT-5.3-Codex (OpenAI, 2026c), together with Claude Opus 4.6 (Anthropic, 2026c) for independent reasoning and code review. Humans supplied the harness, contest-specific references, evaluation policy, and final promotion criteria. Agents generated candidate patches, diagnosed profiles, proposed route changes, and summarized failures.

Skills were used as reusable execution playbooks. Codex skills package instructions, references, and optional scripts behind SKILL.md, while Claude Code skills provide analogous project or personal workflows (OpenAI, 2026a; Anthropic, 2026b). The harness is described through three complementary skill layers. The generic CUDA kernel optimizer standardized the Model/ModelNew contract, correctness and performance evaluation, NCU/NSYS profiling, two-stage search, and export of reusable candidates. The FlashInfer B200 contest optimizer specialized this loop to reference-first search, real workload-shape discovery, sameround paired gates, B200/CUDA 13.2 tactics, official-parity evaluation, and artifact archival. The unified CUDA optimization controller codifies a profile-backed round contract: state extraction, state matching, one-direction optimization selection, candidate generation, trajectory supervision, knowledge-base update, and manifest-based resumption. This reduced prompt drift and made repeated optimization rounds reproducible across operators, model sessions, and implementation languages.

Sub-agents were used for parallel exploration, debate, and review (OpenAI, 2026b). In practice, this enabled independent review of shape regimes, profiler interpretations, and candidate routes when the primary agent stopped finding measured improvements. The harness still kept promotion centralized, so sub-agent outputs were treated as proposals rather than authority.

The main workflow studied in this paper is Agent-Assisted:

Algorithm 1 Agent-Assisted Harness Loop   
Input: definition D, workloads W , languages L, hardware H   
FlashInfer baseline B, round budget N, promotion gate G   
Output: retained solution Sol<sup>∗</sup> and artifact archive A   
A ← ∅   
M ← InitializeMemory(D, W, L, H, B)   
Sol ← B   
for i ← 0 to N − 1 do   
∆ ← ∅   
s<sub>i</sub> ← Controller.State(M, Sol<sub>i</sub>)   
C<sub>i</sub> ← Agent.Generate(Sol<sub>i</sub>, s<sub>i</sub>, L)   
for each candidate c ∈ C<sub>i</sub> do   
r ← Harness.RepGate(D, W, c, Sol<sub>i</sub>, H)   
if r.status = PASSED then   
p ← Profiler.Summarize(c, r)   
A ← A ∪ {(c, r, p)}   
end if   
end for   
c<sup>+</sup><sub>i</sub> ← SelectBestPassed(A, i)   
if c<sup>+</sup> exists then   
R<sub>i</sub> ← Harness.FullSweep(D, W, c<sup>+</sup>, H)   
∆<sub>i</sub> ← R<sub>i</sub>   
if Promote(R<sub>i</sub>, Sol<sub>i</sub>, G) then   
Sol<sub>i+1</sub> ← IntegrateOrDispatch(Sol<sub>i</sub>, c<sup>+</sup>, R<sub>i</sub>)   
else   
Sol<sub>i+1</sub> ← Sol<sub>i</sub>   
end if   
else   
Sol<sub>i+1</sub> ← Sol<sub>i</sub>   
end if   
M ← UpdateMemory(M, A, ∆<sub>i</sub>)   
if Supervisor.Plateau(M) then   
M ← HumanSteer(M)   
end if   
end for   
Sol<sup>∗</sup> ← BestCorrectFullSweep(A)   
return Sol<sup>∗</sup>, A

humans author the harness, curate references, steer plateau recovery, and approve promotions under measured gates. We also ran Full-Agent experiments with LoongFlow PES as same-protocol autonomous-search baselines (Wan et al., 2025). Their matched final evaluations are reported in Section 4; Appendix A summarizes the search traces that produced those artifacts.

Algorithm 1 summarizes the loop. Agents propose candidates; the harness handles compilation, correctness, profiling, full sweeps, and promotion. The controller is humanauthored evidence memory, not autonomous; plateau steering updates context without bypassing measured gates.

## 3.2 Human vs. Agent Contributions

The collaboration followed an AlphaEvolve closed loop: humans defined the objective, constraints, evaluation surface, and acceptance policy, while agents searched within that engineered environment (Novikov et al., 2025). The primary objective was to minimize average latency over all contest shapes; reported speedups use the normalizations stated in Section 4. Secondary signals included per-shape regressions, median latency, 95th-percentile (P95) latency, and outlier regimes that required separate dispatch.

Human effort focused on the design and orchestration of the optimization harness. We designed CUDA kernel optimization skills and developed serial and parallel B200 evaluation scaffolds. We integrated Torch Profiler and NVIDIA Nsight Compute (NCU) analysis scripts, and curated documentation and local references from FlashInfer, DeepGEMM, TensorRT-LLM, and contest-relevant GPU inference repositories (DeepSeek-AI Team, 2025; NVIDIA, 2026b). To address gaps in local code, we directed web and GitHub reference searches. To overcome optimization plateaus, we switched GPT and Claude model families, changed implementation surfaces, and used sub-agent debate. We also designed shape-aware dispatch strategies, but only promoted dispatch routes when profiler and latency evidence showed that the relevant shape regime had a distinct limiter.

Agent work centered on implementation search under those controls. Codex and Claude Code generated CUDA, Triton, and CuTe candidates; produced multiple parallel samples across different optimization directions; adapted reference kernels; proposed route and dispatch changes; interpreted profiler output; and suggested follow-up experiments. Candidate code was not accepted by assertion: it had to pass harness-controlled correctness, compilation, profiling, and latency gates. Appendix B summarizes the contribution split.

## 3.3 Iterative Refinement Loop

Each round instantiated Algorithm 1 with a fixed sequence: identify the bottleneck and workload regime from retained runs and NCU data; generate a bounded candidate family around one hypothesis; pack and preflight-compile the candidate; run a paired representative gate against the sameround baseline; profile correct and promising candidates; integrate the best candidate behind a cheap dispatch rule if the win is shape-local; run a full sweep and retry transient infrastructure failures; and promote only if the full distribution improves without correctness regressions.

Profile-backed state and trajectory control. The unified controller codifies the stateful version of the loop. A closed round can produce a profiler-derived state signature, a statematch decision, one selected optimization, a candidate and evaluation result, a supervisor decision, and a knowledgebase update. The supervisor detects stalling, cycles, regressions, plateaus, and diminishing returns, then carries blocked or recommended directions into the next round. This loop follows the same structure as closed-loop program search: the model proposes code, the evaluator returns a scalar signal and diagnostics, and the system retains only measured improvements (Novikov et al., 2025). The contestspecific difference is that the evaluator must also enforce packaging, correctness, target-environment compilation, and workload-distribution coverage.

Table 2. Implementation artifacts referenced by this paper. These repositories are reproducibility artifacts, not official leaderboard claims.  
![](images/73245b4383ad45e8cc35b429f8d056cc6d6f9a52cd210aae021869480772c02d.jpg)

## 4 EXPERIMENTAL EVALUATION

The primary results in this paper are the Agent-Assisted retained official-aligned B200 measurements from archived artifacts. They are not undisclosed final official leaderboard scores. We also built Full-Agent implementations using LoongFlow PES and evaluated the selected Full-Agent artifacts on the same official-aligned workload sets, evaluation protocol, and supplied FlashInfer baselines used for the Agent-Assisted artifacts (Wan et al., 2025). Following the efficiency-table style used in LoongFlow, Table 3 reports common mean-latency speedup normalizations. The Py-Torch column uses the PyTorch reference mean recorded in the corresponding Agent-Assisted retained evaluator artifact, while the FlashInfer column is normalized to the supplied FlashInfer baseline; higher speedup and lower latency are better. The DSA top-k entry preserves the lowtrial retained artifact for comparability, while Appendix E separately records the high-trial replay evidence and conservative fallback tag.

Under the matched final-evaluation setting, the Agent-Assisted retained kernels are faster than the Full-Agent artifacts. The selected Full-Agent artifacts are 1.35–13.25× slower than the Agent-Assisted retained artifacts under the same FlashInfer-relative normalization, and two remain below the supplied FlashInfer baseline: MoE FP8 at 0.27× and GDN Decode at 0.83×. Section 5 analyzes the retained Agent-Assisted kernels, whose stronger results depended on human harness design, reference selection, and conservative promotion gates.

Following the FlashInfer-Bench evaluation protocol (Xing et al., 2026; FlashInfer Contest, 2026), speedup is correctness-gated and computed over workload-level latency ratios. For a definition d with workload set W , FlashInfer baseline latency b<sub>d,w</sub>, retained kernel latency ℓ<sub>d,w</sub>, and definition-level correctness indicator c<sub>d</sub> ∈ {0, 1}, the official per-kernel and per-track scores are

![](images/7967330fb9461277c473e1760d58b1d637374cf0a4509b7e23f4f2c3c39d34f5.jpg)  
Figure 2. Final retained mean-latency speedup over the supplied FlashInfer baseline.

![](images/66e30cc1beb1f6363f3577d341224c3ddeb1a5b7e380c943de3af2e49fe8d179.jpg)

where E<sub>MoE</sub> = 1, E<sub>DSA</sub> = 2, and E<sub>GDN</sub> = 2. If any workload fails correctness, then c<sub>d</sub> = 0; a missing definition in DSA or GDN contributes zero and effectively halves a single-definition submission. Table 3 and Figure 2 instead use a simpler ratio-of-means latency summary to compare FlashInfer, Full-Agent, and Agent-Assisted methods; this is a reporting normalization, not the official contest score. With mean FlashInfer baseline latency <sup>¯</sup>b<sub>d</sub> and mean retained latency <sup>¯</sup>ℓ<sub>d</sub>, the reported speedup is

![](images/560a4ed060eab1c9a4fec88774c7315ac87288748a8eb593e6a1c797e7478b55.jpg)

For example, the MoE summary speedup is 0.463874/0.286342 = 1.62×. Higher values indicate lower average latency relative to the supplied FlashInfer baseline.

Figure 2 visualizes the final mean-latency speedup of each retained operator over the supplied FlashInfer baseline. The largest FlashInfer-baseline speedups occurred on sparse attention and DSA top-k, where structural route changes reduced work at dominant regimes. GDN prefill also showed a large speedup by replacing the main algorithmic path. GDN decode had the smallest speedup because the supplied FlashInfer baseline was already close to the retained route.

## 5 FINAL KERNEL ANALYSIS

## 5.1 Per-Operator Case Studies

Having established the retained results, this section analyzes the final kernels rather than the search chronology. The final kernels were not produced by a single universal optimization. The effective pattern was shape-aware dispatch combined with full-workload promotion: each candidate route was retained only when it improved the measured distribution without breaking correctness. This policy is important because the contest workloads mix launch-bound regimes, tensor-core regimes, irregular sparse-memory regimes, and recurrent state updates.

Table 3. Efficiency comparison sorted by retained FlashInfer-relative mean-latency speedup. Latencies are mean milliseconds; lower is better. PyTorch speedup uses the retained Agent-Assisted PyTorch reference mean for each definition; FlashInfer speedup uses the supplied FlashInfer baseline. Full-Agent rows are matched final-evaluation baselines evaluated on the same official-aligned workload sets.  
![](images/f9a45c858e16854385745de817e4fb1e21285ea645ad99bb8d6c6a017fdd5ec1.jpg)

For MoE FP8, the bottleneck is the transition from top-k routed tokens to expert-major matrix multiplications and then back to token order. The selected design uses a CUDA helper to fuse routing, local-expert filtering, counting, prefix construction, and FP8 packing into a compact workspace. Triton persistent grouped general matrix multiply (GEMM) kernels then execute the two expert matrix products while handling block-scale dequantization and stable accumulation. The retained variant kept the expert-major mainline, used a shape-local epilogue path for the single-token regime, and preserved a routing and packing specialization for the long but structured sequence-length regime. Forced rerouting of additional shapes was rejected because it improved some local cases but regressed the full sweep (Tillet et al., 2019; DeepSeek-AI Team, 2025; Shui, 2026c).

For the DSA top-k indexer, the optimization separates score generation from top-k selection. The scorer is a CUDA/CuTe tensor-core kernel over FP8 query and key inputs, with vectorized memory access and a tile shape chosen to reduce launch count while improving query reuse in the mediumband workloads. The selector preserves the top-k semantics through three regimes: a vectorized filtered path for common cases, a histogram fallback for wider candidate ranges, and a short-row pass-through path when the scoring work is already small. This separation made it possible to tune the high-throughput scoring path without destabilizing correctness-sensitive selection logic (Shui, 2026d).

Trial-sensitive correctness. A post-submission DSA top-k check exposed a trial-sensitive numerical issue that was not consistently surfaced by the low-trial validation used during fast agent iterations. The source of this inconsistency is that FlashInfer-Bench evaluates randomized per-trial inputs and states, while the resolved default budget used by the harness is only n = 3 trials (Xing et al., 2026); rare top-k boundary cases can therefore be missed by one low-trial sweep and exposed by another. This is a practical limitation of kernel-search harnesses: repeated high-trial evaluation over every candidate and workload is often too expensive on B200, so the loop uses representative gates and low-trial full sweeps to preserve iteration speed. The follow-up evidence in Appendix E shows that targeted high-trial replay can expose rare selector-boundary failures and identify a more conservative fallback tag. We therefore treat high-trial replay as a final validation gate for suspicious or high-impact DSA top-k shapes rather than as the default inner-loop gate.

For DSA sparse attention, the principal challenge is that the sparse index set induces different bottlenecks depending on token count and page-table representability. Short decode workloads are best served by a small specialized route or an upstream-derived helper route. Larger workloads use split key-value (KV) flash-decoding with asynchronous sparse key gathers, shared-memory layouts chosen to reduce bank conflicts, and a separate merge phase for partial outputs. The accepted final change targets padded tail work in the large split route: it avoids unnecessary attention and value accumulation on empty upper-half tiles while keeping the same output contract for downstream merging (Kwon et al., 2023; Shui, 2026d).

![](images/f68963cd80d19236ae1d855bd78c95bbf84b70b4682094760569362ef6c4f667.jpg)

![](images/010c78e09affbfc8fa7966402e12197df173d54f0614d339a4d9fcd6bcbb36e2.jpg)

![](images/232c23c04b990c148039ed8944176385564d3f79709f9de6aa83c37b4505fec3.jpg)

![](images/c61f14784612005b231f1179d793789c057bf62995dab4be712708c11c19aaab.jpg)

![](images/9caf789c99e445be498300a448678d288553471963eadeed95377a04cfee33ee.jpg)  
Figure 3. Retained speedup trajectories over the supplied FlashInfer baseline. The y-axis is log-scale speedup versus FlashInfer; the x-axis uses effective tag versions after collapsing retained tags with unchanged latency. Open circles mark the two largest non-final jumps, stars mark the best retained points, and dashed lines mark the 1.0× FlashInfer baseline.

For GDN decode, the retained implementation is explicitly dispatch-driven. A single recurrent kernel did not generalize across batch regimes, because small batches are dominated by launch and state-access overhead while larger batches need different pretranspose and value-tile behavior. The final dispatcher therefore combines a Triton recurrent route for small batches, a one-warp specialization for the batch-eight regime, a CuTe pretranspose route for mid-sized batches, and a larger-value route for the highest measured batch regime. This explains why GDN decode shows the smallest final speedup: the supplied baseline was already strong, and the remaining wins were batch-local rather than global (Shui, 2026b).

For GDN prefill, the key improvement is algorithmic routing rather than a narrow micro-optimization. The final implementation makes a Blackwell chunked CuTe-DSL kernel the default path, replacing a broader dispatch table that was difficult to tune consistently. The chunked path uses SM100 tensor memory, Tensor Memory Accelerator (TMA) movement, and warp specialization to separate matrix products, gate loading, recurrence correction, and output storage. A scalar preprocessing helper prepares the gate and beta inputs for the chunked kernel, while a narrow recurrent fallback handles tiny shapes where the chunked path is not yet favorable (Shui, 2026b).

## 5.2 Implementation Stack

Language selection as part of the search policy. The implementation used multiple authoring surfaces because each operator exposed a different limiting factor. Triton was most effective where rapid specialization and maintainable grouped matrix kernels mattered, as in MoE and the smallbatch GDN decode path (Tillet et al., 2019). CUDA C++ was used where direct control over shared memory, launch attributes, vectorized memory access, and low-level conversion instructions determined performance, especially in DSA top-k and DSA sparse attention. CuTe and CUTLASS provided explicit tensor-core layouts for DSA top-k and the Blackwell chunked GDN prefill path (NVIDIA, 2026a). Python remained the orchestration layer for dispatch, packaging, caching, and harness-controlled exclusion of variants that were correct but not globally beneficial. Language switching was therefore a controlled response to profiler evidence and implementation constraints, not an aesthetic preference.

## 5.3 Profile-Guided Analysis

Profiler output as decision evidence. Torch Profiler and NCU outputs were compressed into decision records: dominant kernel, workload regime, bottleneck class, limiting resource, occupancy, throughput, waves per SM, and candidate headroom. This made profiling actionable for dispatch and promotion. A route could win a local UUID or shape band and still be rejected when the full sweep showed that its benefit did not survive workload mixing.

The condensed largest-shape evidence used for these decisions is reported in Appendix G, especially Table 10. Across the five operators, the profiler evidence supports the same policy: keep route changes only when Torch Profiler and NCU identify a distinct limiting regime, such as GEMMplus-packing cost in MoE, low-wave sparse launches in DSA, and resource pressure in the GDN prefill chunk kernel.

## 6 LIMITATIONS AND FUTURE DIRECTIONS

The main limitation is that this paper evaluates an Agent-Assisted engineering workflow, not an isolated LLM. Human harness design, budget decisions, reference selection, and final promotion were central. The workload distributions are contest-specific, and the reported timings remain local official-aligned B200 evidence rather than final leaderboard scoring.

Future work should move more controller state, memory, and model orchestration into the harness while preserving measured promotion discipline. Longer-running research agents and kernel-specific systems suggest how to increase candidate diversity (Karpathy, 2026; Jaber & Jaber, 2026; Yu et al., 2026; Liao et al., 2026). Evolutionary memory systems and agentic variation operators offer another route for broadening candidate search (Novikov et al., 2025; Sharma, 2025; Wan et al., 2025; Lange et al., 2026; Chen et al., 2026), but the DSA top-k replay shows that stronger automation must also strengthen final validation gates.

## 7 CONCLUSION

This paper presented an Agent-Assisted workflow for Flash-Infer contest kernel optimization on NVIDIA B200 GPUs. The central result is a measurable systems loop rather than a prompt template: reusable CUDA optimization skills, a contest-specific evaluation harness, a profile-backed controller, workload-grounded shape dispatch, and artifact memory convert agent output into compile, correctness, profiling, full-sweep, and promotion decisions. Across five definitions, the retained low-trial official-aligned artifacts achieved FlashInfer-baseline mean-latency speedups from 1.12× to 29.68×, with the DSA top-k high-trial fallback evidence separated in Appendix E.

The results show that reliable LLM-driven kernel generation still depends on harness engineering. The largest gains came from structural, hardware-aware changes such as sparseattention route specialization and the Blackwell chunked GDN prefill path, while matched Full-Agent final evaluations remained slower than the retained Agent-Assisted artifacts. This gap suggests that near-term kernel agents are most useful when paired with human-curated references, profiler interpretation, conservative promotion gates, and persistent trajectory memory; future autonomous systems should move more of this controller and memory into the harness without weakening measured validation.

## ACKNOWLEDGMENT

We are grateful to Wanping Zhang, Bowen Ren, Zejia Liu, Bo Pang, Yalu Ouyang, and Shiyong Li for helpful discussions, technical feedback, and project support. We also acknowledge the FlashInfer team for organizing the AI Kernel Generation Contest, defining the benchmark tasks, and maintaining the FlashInfer-Bench evaluation infrastructure. Access to NVIDIA B200 GPUs was provided by Modal and enabled the contest-aligned evaluation, profiling, and repeated validation reported in this paper.

## REFERENCES

Anthropic. Harness design for long-running application development. Anthropic Engineering Blog, 2026a. URL https://www.anthropic.com/ engineering/ harness-design-long-running-apps.

Anthropic. Claude code skills. Claude Code Documentation, 2026b. URL https://code.claude.com/ docs/en/skills.

Anthropic. Claude opus 4.6. Anthropic News, 2026c. URL https://www.anthropic.com/news/ claude-opus-4-6.

Chen, T. et al. AVO: Agentic variation operators for autonomous evolutionary search. arXiv preprint arXiv:2603.24517, 2026.

Dai, D. et al. DeepSeekMoE: Towards ultimate expert specialization in mixture-of-experts language models. In Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), pp. 1280–1297. Association for Computational Linguistics, 2024. doi: 10.18653/v1/2024.acl-long.70.

Dao, T., Fu, D. Y., Ermon, S., Rudra, A., and Re, C. FlashAttention: Fast and memory-efficient exact attention with IO-awareness. Advances in Neural Information Processing Systems, 35:16344–16359, 2022.

DeepSeek-AI. DeepSeek-V3.2: Pushing the frontier of open large language models. arXiv preprint arXiv:2512.02556, 2025.

DeepSeek-AI Team. DeepGEMM: Clean and efficient FP8 GEMM kernels with fine-grained scaling. GitHub repository, 2025. URL https://github.com/deepseek-ai/ DeepGEMM.

Fawzi, A. et al. Discovering faster matrix multiplication algorithms with reinforcement learning. Nature, 610: 47–53, 2022. doi: 10.1038/s41586-022-05172-4.

FlashInfer Contest. FlashInfer AI kernel generation contest. MLSys 2026 Competition, NVIDIA Track, 2026. URL https://mlsys26.flashinfer.ai/.

Jaber, J. and Jaber, O. AutoKernel: Autonomous GPU kernel optimization via iterative agent-driven search. arXiv preprint arXiv:2603.21331, 2026.

Karpathy, A. Autoresearch. GitHub repository, 2026. URL https://github.com/karpathy/ autoresearch.

Kwon, W. et al. Efficient memory management for large language model serving with PagedAttention. In Proceedings of the 29th ACM Symposium on Operating Systems Principles, pp. 611–626, 2023. doi: 10.1145/3600006.3613165.

Lange, R. T., Imajuku, Y., and Cetin, E. ShinkaEvolve: Towards open-ended and sample-efficient program evolution. In International Conference on Learning Representations, 2026.

Liao, G. et al. KernelEvolve: Scaling agentic kernel coding for heterogeneous AI accelerators at Meta. arXiv preprint arXiv:2512.23236, 2026.

Novikov, A. et al. AlphaEvolve: A coding agent for scientific and algorithmic discovery. arXiv preprint arXiv:2506.13131, 2025.

NVIDIA. CUTLASS: CUDA templates and Python DSLs for high-performance linear algebra. GitHub repository, 2026a. URL https://github.com/NVIDIA/ cutlass.

NVIDIA. TensorRT-LLM. GitHub repository, 2026b. URL https://github.com/NVIDIA/ TensorRT-LLM.

OpenAI. Codex skills. OpenAI Developers, 2026a. URL https://developers.openai.com/ codex/skills.

OpenAI. Codex subagents. OpenAI Developers, 2026b. URL https://developers.openai.com/ codex/concepts/subagents.

OpenAI. Introducing GPT-5.3-Codex. OpenAI Blog, 2026c. URL https://openai.com/index/ introducing-gpt-5-3-codex/.

OpenAI. Harness engineering: Leveraging Codex in an agent-first world. OpenAI Blog, 2026d. URL https://openai.com/index/ harness-engineering/.

Ouyang, A., Guo, S., Arora, S., Zhang, A. L., Hu, W., Re, C., and Mirhoseini, A. KernelBench: Can LLMs write efficient GPU kernels? In Proceedings of the 42nd International Conference on Machine Learning, volume 267 of Proceedings of Machine Learning Research, pp. 47356–47415. PMLR, 2025.

Sharma, A. OpenEvolve: An open-source evolutionary coding agent. GitHub repository, 2025. URL https://github.com/algorithmic superintelligence/openevolve.

Shinn, N., Cassano, F., Gopinath, A., Narasimhan, K., and Yao, S. Reflexion: Language agents with verbal reinforcement learning. In Advances in Neural Information Processing Systems, volume 36, 2023.

Shui, Y. mlsys26-flashinfer-contest: Open-source harness and artifacts for the MLSys 2026 FlashInfer contest. GitHub repository, 2026a. URL https://github.com/syhya/mlsys26- flashinfer-contest.

Shui, Y. mlsys26-flashinfer-solution-gated-delta-net. GitHub repository, 2026b. URL https://github.com/syhya/mlsys26- flashinfer-solution-gated-delta-net.

Zheng, L. et al. SGLang: Efficient execution of structured language model programs. In Advances in Neural Information Processing Systems, volume 37, pp. 62557–62583, 2024.

Shui, Y. mlsys26-flashinfer-solution-fused-moe. GitHub repository, 2026c. URL https://github.com/syhya/mlsys26- flashinfer-solution-fused-moe.

Shui, Y. mlsys26-flashinfer-solution-sparse-attention. GitHub repository, 2026d. URL https://github.com/syhya/mlsys26- flashinfer-solution-sparse-attention.

Tillet, P., Kung, H.-T., and Cox, D. Triton: An intermediate language and compiler for tiled neural network computations. In Proceedings of the 3rd ACM SIGPLAN International Workshop on Machine Learning and Programming Languages, pp. 10–19, 2019. doi: 10.1145/3315508.3329973.

Wan, C. et al. LoongFlow: Directed evolutionary search via a cognitive plan-execute-summarize paradigm. arXiv preprint arXiv:2512.24077, 2025.

Xing, S. et al. FlashInfer-Bench: Building the virtuous cycle for AI-driven LLM systems. arXiv preprint arXiv:2601.00227, 2026.

Yang, J., Jimenez, C. E., Wettig, A., Lieret, K., Yao, S., Narasimhan, K., and Press, O. SWE-agent: Agent-computer interfaces enable automated software engineering. In Advances in Neural Information Processing Systems, volume 37, 2024. doi: 10.52202/079017-1601.

Yang, S., Kautz, J., and Hatamizadeh, A. Gated delta networks: Improving Mamba2 with delta rule. In The Thirteenth International Conference on Learning Representations, 2025.

Ye, Z. et al. FlashInfer: Efficient and customizable attention engine for LLM inference serving. In Proceedings of Machine Learning and Systems, volume 7, 2025.

Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K. R., and Cao, Y. ReAct: Synergizing reasoning and acting in language models. In International Conference on Learning Representations, 2023.

Yu, Y. et al. Towards automated kernel generation in the era of LLMs. arXiv preprint arXiv:2601.15727, 2026.

## APPENDIX

This appendix provides the Full-Agent trajectory artifacts, human/agent contribution matrix, core skill and prompt excerpts, ablation notes, DSA top-k repeated-validation evidence, operator background, largest-shape NCU/Torch Profiler evidence, and per-workload shape tables used to support the main paper.

## A FULL-AGENT TRAJECTORY DETAILS

In addition to the Agent-Assisted workflow studied in the main text, we also ran Full-Agent experiments with LoongFlow PES (Wan et al., 2025). Table 4 summarizes the Full-Agent search traces that produced the selected artifacts. The Full-Agent rows in Table 3 use those selected artifacts evaluated under the matched final-evaluation protocol; the trace-workload counts below describe the search logs, not Table 3 final-evaluation coverage. The LoongFlow trace-local best-score checkpoint can differ from the FlashInfer-relative best-latency checkpoint because the trace score is normalized by a run-local PyTorch reference latency.

Table 4. Full-Agent search trace summary. FI speedup is normalized to the supplied FlashInfer baseline; trace workloads describe trace logs rather than Table 3 final-evaluation coverage.  
![](images/2bc4153fe81e01acbc090d0026e2c12783705fb54906420faed1b70aaf00bf27.jpg)

![](images/ed34fa7d64a1bed0d26373b30c260b8652257aae82be1fe283f1752d8018cffe.jpg)

![](images/b91787b1f9a2869de956ae88bf833c02bf214a7c0c26323785e1fd5cedc04d45.jpg)

![](images/4856e3def4e21378556843491b7bfb545fa4321e9775bc618923253ccb092989.jpg)

![](images/bc05db7090a8fb057e2aecd020ac27145866554acf692db6f908fafad097e6fa.jpg)

![](images/baf5705a4a922183272ea1d3e3ba750ec689f0a38f26e3bf14bf4b0b52e4ac87.jpg)  
Observed correct candidate Running best FlashInfer baseline ★ Best FI-relative point  
Figure 4. Full-Agent optimization trajectories extracted from the LoongFlow trace logs. Gray dots are correctness-passing evaluated candidates, solid lines are the running best FlashInfer-relative speedup, dashed lines mark the supplied FlashInfer baseline, and stars mark the best FlashInfer-relative latency point from Table 4. The y-axes are logarithmic because the traces span sub-baseline and multi-× regimes.

## B HUMAN AND AGENT CONTRIBUTION MATRIX

Table 5. Human and agent contributions in the Agent-Assisted workflow.  
![](images/206b3bbd440978df1903ffc7a0f588a297a3c0d001b82302b61bb47274d11d8c.jpg)

## C CORE SKILL AND PROMPT TEMPLATE FOR ITERATIVE OPTIMIZATION

The core iterative playbook was encoded as a reusable optimization skill rather than an ad hoc prompt. The skill converted each optimization round into a constrained protocol: reference-first reconnaissance, workload-derived shape discovery, paired baseline gates, profiling-guided candidate generation, controller state update, artifact archival, and promotion by repeatable mean-latency improvement. Its purpose was to make agent outputs comparable across operators, model sessions, and implementation languages.

Table 6. Core skill controls used in the iterative optimization loop.  
![](images/2da4dff488003f86940dce5119643d0734f294b80293b7158617c73b6fd5d81c.jpg)

The full skill is longer than a paper appendix, so the excerpt below records the prompt-style core that was repeatedly exposed to the coding agent. This follows the artifact style of prompt appendices: it specifies the role, required inputs, hard gates, step order, and final decision contract rather than only describing the method in prose.

## C.1 FlashInfer B200 Optimization Skill Excerpt

![](images/22eae8df9bd566665d5d585b313a9cf79febff287a4fdb5329ba8adc8a0645d1.jpg)

The corresponding prompt template exposed the same controls to the coding agent. Each round specified: the active operator, correctness contract, packaging constraints, and current best latency; the reference and reconnaissance summary; the workload-derived regimes, paired baseline measurements, and latency-heavy outliers; the profiler bottleneck table and optimization hypothesis for the next candidate family; the permitted implementation surfaces, such as Triton, CUDA C++, or CuTe; the evaluation plan, including representative gates, repeat validation, optional full sweep, retry policy, and promotion threshold; and the archival requirement with a final decision label of archive only, promote globally, or reject and restore.

A typical instruction therefore asked the agent to generate a bounded candidate family around one bottleneck, run or prepare paired gates, interpret profiler output, and update the retained route only through the harness decision policy. This prompt design prevented a single-shape local win from being treated as a submission-ready result.

## D ABLATION NOTES

Table 7 records representative ablations that changed promotion decisions. Each row is backed by retained summaries or rejected probes; the purpose is to explain why a route was kept or rejected, rather than to enumerate every trial.

Table 7. Representative ablation evidence from retained summaries and rejected probes.  
![](images/f2f174a7cd0848dfd0d867bff25d41622e3c2aa156b777d02358339b3c961047.jpg)

## E DSA TOP-K REPEATED-VALIDATION EVIDENCE

This appendix records the follow-up checks used to understand the DSA top-k indexer numerical issue observed after submission. The contest-side validation is treated as the authoritative scoring signal. The local retained result is reported only as development-time harness evidence, and the repeated-validation runs are used to explain the failure mode and the resulting harness policy.

The issue is a trial-budget problem rather than a latency-path mismatch. During normal agent search, running many trials for every candidate and every workload would make B200 iteration too slow and expensive, so the loop used representative gates and low-trial full sweeps to keep search moving. In the public FlashInfer-Bench configuration checked for this paper, the resolved default evaluation budget is n = 3 trials and the DSA top-k definition does not have a separate trial-count override (Xing et al., 2026). Each trial regenerates or reloads a distinct input/state sample before correctness is checked, so the default budget observes only three draws from the workload distribution. That policy is effective for throughput exploration, but it can produce apparent inconsistencies: a low-trial run may not sample a near-tie top-k boundary case, while another run or a high-trial replay can sample it and trigger the exact matched-ratio gate.

The detection effect can be modeled directly. For a fixed workload w, let F<sub>w,t</sub> denote the event that trial t violates the exact matched-ratio correctness gate, and let

![](images/6d4a05ca05f48f228a42cabd2998d5c3d79c1c5d8410f0545d06117672f77174.jpg)

Under an independent-trial approximation, a validation run with n trials detects at least one such failure with probability

![](images/748908e677d73c0680a5c862c3116ea2ba74f3416b1eb6439b3a56d1173bb474.jpg)

For a set of workloads S, a low-trial full sweep misses all rare failures with probability approximately

![](images/d35edf6cf646fc0b8f1299648564337d6d4a112eefe8fb5b0955a1a193811293.jpg)

This explains why a low-trial gate can pass while a targeted high-trial replay of the same suspicious workload later exposes a rare failure.

The top-k selector also has a natural stability condition. Let s be the reference score for page j, T (s) the selected top-k set, and sˆ = s + δ the implemented score after FP8 arithmetic, tiling, and reduction-order perturbations. Define the top-k boundary margin

![](images/7fcb7a332ef9ea104c0ccf349b21520a2c6c94c4debcbb883e4f734bda77b945.jpg)

If max |δ | ≤ ϵ and γ(s) > 2ϵ, then the selected set is stable: T (ˆs) = T (s). Trial-sensitive failures concentrate in the boundary regime γ(s) ≤ 2ϵ, where small numerical perturbations can swap an in-set and out-of-set page while most trials remain exact. Figure 5 visualizes the observed mismatch rates and the resulting detection-probability curve under the high-trial rerun evidence.

![](images/2efc0b968cfc465be6a709fec0ac9b5495ddcdd41ca5e65a662ed815e708793d.jpg)

![](images/cad63cf393661d2f19d1d773aa625522b8c7be35eb7c7e0e25e15d967f48ce0c.jpg)  
Figure 5. Observed high-trial mismatch rates and trial-budget detection probability for DSA top-k. The labels v50, v48, and v37 denote repository git tags, not iteration numbers; the probability curve uses the observed git tag v50 mismatch rate pˆ = 3/200.

Table 8. Concern workloads and repeated-validation outcomes for DSA top-k. The rows summarize archived B200 reruns; max error is reported as max absolute / max relative error.  
![](images/579680c47806999788985d297ffa390c66c816966fa046d4ebae5d3fb8b7ea4c.jpg)

Table 9. DSA top-k latency consistency on contest-side timed rows. The two rows that failed correctness do not have contest-side latency rows, so this table compares only the reported timed rows.  
![](images/569019bc5a25e74fd12cf23b9df78e20955fcf18db06e7882e4bae97eb9afb14.jpg)

These checks changed the harness policy rather than the paper’s scoring interpretation. Low-trial validation remains appropriate inside the agent search loop because it preserves iteration speed, but suspicious DSA top-k regimes now require targeted high-trial replay before a tag is treated as the most conservative release artifact.

## F OPERATOR BACKGROUND AND MATHEMATICAL DEFINITIONS

The contest page defines the three tracks as FP8 Fused MoE, DeepSeek Sparse Attention from DeepSeek-V3.2, and Gated Delta Net used in Qwen3-Next (FlashInfer Contest, 2026). This appendix records the operator-level mathematical background used to interpret the benchmark definitions. The formulas are not new model contributions; they explain why the kernels stress routing, top-k selection, sparse memory access, and recurrent state updates.

## F.1 Fused MoE FP8

The MoE task is naturally described by top-k routed expert execution. In a Transformer block where a dense FFN is replaced by an MoE layer, DeepSeekMoE writes the token update as (Dai et al., 2024)

![](images/49c7172982485ec03a5375d33ea751e2b8c4e337ab29fd5b19eaa102c8bbb701.jpg)

Here u<sup>ℓ</sup> is the token hidden state after attention, e<sup>ℓ</sup> is the router centroid for expert i, and only K expert FFNs are active per token. The contest definition specializes this pattern to a fixed top-8 routed FP8 MoE with block-scale quantization. At the kernel level, the mathematical sparsity becomes a systems problem: gather routed tokens, pack expert-major work, run two expert GEMMs with FP8 block scales, apply the activation/epilogue, and scatter weighted expert outputs back to token order.

For block-scaled FP8 inputs and weights, each tile is represented as a low-precision tensor and a scale. Abstractly, a GEMM tile computes

![](images/49f062949256e2fdc716d7c4a9958775ee0d5d9af389cef27695f75fcfb753f6.jpg)

where q<sup>x</sup>, q<sup>w</sup> are FP8 values and s<sup>x</sup>, s<sup>w</sup> are per-block scales. This is why the retained MoE implementation emphasized FP8 scale handling, expert-major packing, and epilogue fusion rather than only raw matrix multiplication throughput.

## F.2 DeepSeek Sparse Attention

DeepSeek-V3.2 introduces DSA to reduce long-context attention cost by learning a lightweight indexer and applying attention only to selected key-value entries (DeepSeek-AI, 2025). For query token h<sub>t</sub> and preceding token h<sub>s</sub>, the lightning indexer computes

![](images/21595019e2e77a7bfd8f0bd2759ad9548f8f1c1a3b2524f0cb3723d8ca06f694.jpg)

where H<sub>I</sub> is the number of indexer heads, q<sup>I</sup><sub>t,j</sub> and w<sup>I</sup><sub>t,j</sub> are query-derived indexer features, and k<sup>I</sup><sub>s</sub> is a key-derived indexer feature. The selected context set is

![](images/114e8d8675a6a3cf314c0cec78958dc1fab60ddec931cc57397d61ff4dbd803d.jpg)

The sparse attention output is then computed only over the selected entries:

![](images/05de82567533d352cdc172d2984f46e23bff5d880f5b5ed58d68ee2bfbbb4271.jpg)

In the contest, this decomposition appears as two definitions. The DSA top-k indexer kernel computes index scores and selected indices across batch\_size, max\_num\_pages, and fixed num\_pages. The DSA sparse attention kernel consumes those sparse indices and performs attention over the selected KV pages. In kernel notation, the attention route can be summarized as

![](images/7ded860c8c64d90abb6130c581ced492d2ad58d8390e634e9fc5bf6912d0c898.jpg)

where λ is the softmax scale, q<sup>nope</sup> and q<sup>pe</sup> are the non-positional and positional query components, and c<sup>K</sup>, c<sup>V</sup> , k<sup>pe</sup> denote the corresponding cached latent/value and positional-key components. The exact tensor layout is fixed by the contest reference implementation; the optimization challenge is to preserve the selected-set semantics while avoiding wasted work on padded pages and short-token regimes.

## F.3 Gated Delta Net

Gated DeltaNet belongs to the linear-recurrent attention family. A simple linear attention recurrence maintains a matrix state S<sub>t</sub> and emits

![](images/88a8447845a74027c78775a1cf405adfeb5559be4622b9c8dce64721a5a9031c.jpg)

DeltaNet replaces the additive write with a selective update that removes the old value associated with key k<sub>t</sub> before writing the new value:

![](images/bd282043374f82e4d4d200f6283ceed05466da57a0612a8b9de16456b220fd64.jpg)

Gated DeltaNet adds a data-dependent decay gate α<sub>t</sub> ∈ (0, 1), yielding the gated delta rule (Yang et al., 2025):

![](images/2411fdcac5166c2fb4478a028626855f0e90ab04ebee11d2c6f628f695715cd0.jpg)

The two contest definitions correspond to two execution regimes of this recurrence. Decode receives a prior state and computes a small number of new recurrent updates, so launch overhead, batch-size dispatch, and state layout dominate. Prefill evaluates a whole sequence and returns both outputs and the final state, so the key issue is parallelizing the recurrence through chunked matrix operations while applying the log-domain gate consistently, e.g. α<sub>t</sub> = exp(a<sub>t</sub>) when the reference exposes a natural-log gate. This explains why the retained GDN prefill solution benefited from a Blackwell chunked path, while GDN decode used batch-size-specific dispatch.

## G AGENT-ASSISTED PROFILING EVIDENCE

This appendix summarizes the largest-shape profiling evidence requested by the review committee. Each profile uses the final Agent-Assisted retained implementation for the selected workload. The table keeps only the Torch Profiler and NCU facts that affected optimization decisions: dominant CUDA time, kernel-level throughput, occupancy or wave count, and the resulting implication. The corresponding artifact archive contains the raw Torch Profiler tables, NCU reports, selected-workload metadata, evaluator outputs, and run logs; those raw logs are summarized here rather than inlined.

Table 10. Condensed largest-shape profiling evidence for the retained Agent-Assisted kernels. The table summarizes raw Torch Profiler and NCU reports from the artifact archive.  
![](images/6be3753472d361573a3add2e9ca28c4cc0e36df58da149a166f851b73f63d704.jpg)

## G.1 Detailed Per-Operator Analysis

The NCU kernel durations below describe individual profiled kernel passes; they are used as bottleneck evidence and are not summed into end-to-end latency.

MoE FP8. Workload: Selected stress workload (seq\_len=14107) covers the long seq (L=14107) regime. The retained latency is 1.189900 ms; the short profiling-run latency is 1.172120 ms.

Torch Profiler: Torch Profiler reports that gemm1\_kernel takes 627.519 us, or 50.78% of CUDA time, and gemm2\_kernel takes 380.639 us, or 30.80%. The two expert GEMMs therefore account for 81.6% of CUDA time. The remaining time is still meaningful: reduce\_add contributes 6.53%, fusedGating 4.21%, FP8 permute/pack 3.79%, and activation quantization 2.78%.

NCU: NCU shows that the two GEMM kernels launch one block per SM with 384 threads per block. Both use 168 registers per thread and roughly 216 KB of dynamic shared memory per block, which limits achieved occupancy to about 18.7%. GEMM1 reaches 50.2% SM throughput and 41.1% memory throughput, while GEMM2 reaches 37.8% SM throughput and 32.8% memory throughput. This is a mixed tensor-memory and movement bottleneck rather than a launch-only case.

Optimization implication: The profile supports keeping the long-sequence route and optimizing the expert-major GEMM path together with FP8 packing, scale movement, and reduction/epilogue work. Treating the epilogue as an isolated microkernel would miss the dominant cost structure.

DSA Top-k Indexer. Workload: Selected stress workload (batch\_size=30, max\_num\_pages=91, num\_pages=11923) covers the high page-count (B=30, Pmax=91) regime. The retained latency is 0.017546 ms; the short profiling-run latency is 0.015168 ms.

Torch Profiler: Torch Profiler shows only two meaningful CUDA kernels on the largest shape: the filtered single-row top-k selector takes 8.928 us, or 55.25% of CUDA time, and the CuTe scorer takes 7.232 us, or 44.75%. The final largest-shape profile is therefore no longer scorer-only.

NCU: NCU reports that the CuTe scorer launches 394 blocks, reaches 18.9% SM throughput and 31.3% memory throughput, and executes only 0.67 waves per SM. The selector is more extreme: it is a one-block launch with 0.01 waves per SM and near-zero device-wide compute and memory utilization. This explains why the selector can consume more CUDA time despite not saturating the device.

Optimization implication: The earlier scorer tile optimization remains justified, but the next largest-shape bottleneck is selector underfill and launch overhead. Promising follow-up directions are selector parallelization, reducing launch count, or fusing scorer and selector work where correctness permits.

DSA Attention. Workload: Selected stress workload (num\_tokens=8, num\_pages=8462, max\_pages=32) covers the T=8 sparse attention regime. The retained latency is 0.015115 ms; the short profiling-run latency is 0.015552 ms.

Torch Profiler: Torch Profiler attributes 8.416 us, or 71.86% of CUDA time, to attn\_split\_kernel and 3.296 us, or 28.14%, to attn\_merge\_kernel. The largest sparse-attention case is therefore a short two-kernel pipeline rather than a single dense attention kernel.

NCU: NCU shows the split kernel uses 126 registers per thread and 181 KB of dynamic shared memory per block, with 12.5% theoretical occupancy, 12.0% achieved occupancy, and 0.86 waves per SM. The merge kernel is even smaller, with 0.09 waves per SM and about 3.1% achieved occupancy. Both kernels show low device-wide throughput; the profile points to sparse-grid underfill and resource pressure rather than DRAM saturation.

Optimization implication: The retained half-width tail skip is supported because it removes real padded work in the large sparse route. The remaining headroom is more likely in split/merge scheduling, reducing merge overhead, or carefully fusing pipeline stages than in generic bandwidth tuning.

GDN Decode. Workload: Selected stress workload (batch\_size=64) covers the batch=64 decode regime. The retained latency is 0.012570 ms; the short profiling-run latency is 0.012352 ms.

Torch Profiler: Torch Profiler reports one CUDA kernel carrying the device work on the largest decode shape: the CuTe pretranspose decode kernel takes 9.952 us and accounts for 100% of CUDA time.

NCU: NCU measures the profiled decode kernel at about 12.8 us, with 44.0% SM throughput, 52.1% memory throughput, and 34.6% DRAM throughput. Achieved occupancy is high at roughly 82.9%, but the launch executes only 1.73 waves per SM and NCU flags a partial-wave tail effect. The limiter is therefore latency and wave shape, not a saturated tensor-core or DRAM kernel.

Optimization implication: The evidence supports the final dispatch design: batch-local routes are useful, but the larges batch already uses a strong CuTe path. A wholesale replacement is unlikely to dominate the full workload distribution unless it also improves state access and tail-wave behavior.

GDN Prefill. Workload: Selected stress workload (total\_seq\_len=8192, num\_seqs=57, len\_cu\_seqlens=58) covers the 8192-token prefill regime. The retained latency is 0.134540 ms; the short profiling-run latency is 0.141919 ms.

Torch Profiler: Torch Profiler shows that the retained Blackwell chunk kernel takes 130.111 us, or 98.47% of CUDA time.   
The fused gate helper takes only 2.016 us, or 1.53%, so the helper is not the largest-shape bottleneck.

NCU: NCU reports the chunk kernel at about 133.3 us, with 8.5% SM throughput and 24.0% memory throughput. The kernel uses 168 registers per thread and about 100 KB of dynamic shared memory per block; both registers and shared memory limit occupancy. Theoretical occupancy is 18.75% and achieved occupancy is about 16.2%. NCU also reports 976 local spilling requests and 3,382,832 excessive global sectors, about 50% of total sectors.

Optimization implication: This supports the current Blackwell chunk path as the right default for non-tiny prefill shapes, because the dominant work is the chunked recurrent kernel rather than gate preprocessing. Future tuning should focus on register/shared-memory pressure and global-memory coalescing before adding more dispatch cases.

## H PER-WORKLOAD STATISTICS AND SHAPE TABLES

The statistics in this appendix are computed from retained per-workload artifacts joined with contest workload axes. In Table 11, Workload denotes the number of retained evaluated workloads for each definition. The 95th percentile is computed across retained per-workload latency values, not trial-level variance. For DSA top-k, the promoted full-sweep summary records 0.006893 ms, while the available per-workload artifact used in this appendix has mean 0.007649 ms.

Table 11. Retained per-workload latency statistics from available artifacts. Workloads is the retained workload count; latency values are milliseconds; artifact mean is computed from the available per-workload artifact; PyTorch mean is the reference mean from the same evaluator output.  
![](images/0d2c410275b274038875994e41fe03a8fd785d005fb1940c5831f801799eeb49.jpg)

Primary-axis mean view. Figure 6 groups each definition by the shape axis that most directly changes its execution regime: sequence length for MoE and GDN prefill, maximum page count for DSA top-k, token count for DSA sparse attention, and batch size for GDN decode. Each bar reports mean retained latency for that bucket; the UUID-level tables below preserve the exact shapes and measurements.

![](images/907e5fbdff94e05b489ace3ef8402013c5e0adb919f7e06bef0e1353e40b0ec3.jpg)

![](images/386fee56348533929787aeed3629bf9db638abf4b70326a27b2b82c1ae8e000e.jpg)

![](images/7559d561db8ae2b12f5c0562fd12ec773c0676029f05b2d51ea2c1af26c4135e.jpg)

![](images/97aa74ae566e521e7811d4ffe6f56eb8d4569fae922734db2fb2d9f52e851780.jpg)

![](images/472c21df5a28b4259cb538ae5bae5d1dcc4a621b4842da22a7a7e865dcd88ba1.jpg)  
Figure 6. Mean retained latency by primary workload axis; high-cardinality axes are bucketed into workload-relevant ranges.

## I PER-SHAPE RETAINED RESULTS

Each table below corresponds to one contest definition. Each row is one retained workload joined with shape axes from the contest workload file; repeated shapes with different input data remain separate. The tables use full workload UUIDs and report retained latency, PyTorch reference latency, and speedup over PyTorch. Per-row PyTorch-reference speedups are diagnostic and are not the FlashInfer-baseline speedups reported in the main results.

## I.1 MoE FP8

Table 12: Per-workload retained results for MoE FP8. Latency and PyTorch reference are milliseconds; speedup is relative to PyTorch.  
![](images/754bb5f4f559b2285bfb436def61d262c5b467356cb8c01b40c122b3827ae367.jpg)

## I.2 DSA Top-k Indexer

Table 13: Per-workload retained results for DSA Top-k Indexer. Latency and PyTorch reference are milliseconds; speedup is relative to PyTorch. Fixed: page count = 11923.  
![](images/2f38860c60a3d24a543be3c8fe08d7052e305cbfdcdde8a225f4e1175d085d82.jpg)

Table 13 continued from previous page

![](images/e9a0fba6417b88869d3984189e7b71841d798265c6b7abe5809beb1439ff1f3b.jpg)

## I.3 DSA Sparse Attention

Table 14: Per-workload retained results for DSA Sparse Attention. Latency and PyTorch reference are milliseconds; speedup is relative to PyTorch. Fixed: page count = 8462.  
![](images/fad778cf3e7af8f8ef59f1730d01d8eb6fb27633dc2a0e6f27392f4776493c97.jpg)

## I.4 GDN Decode

Table 15: Per-workload retained results for GDN Decode. Latency and PyTorch reference are milliseconds; speedup is relative to PyTorch  
![](images/8beb90ae2cad7c8875ac81ebd0fe8b64d4176936a0fea370823891d54c72d2f9.jpg)

Table 15 continued from previous page  
![](images/69aadffeefcce00a3b34cd829b3f5f5a007a8e3233e5726514f5a254973a043b.jpg)

## I.5 GDN Prefill

Table 16: Per-workload retained results for GDN Prefill. Latency and PyTorch reference are milliseconds; speedup is relative to PyTorch.  
![](images/4734aec36b7d077322d8518f402026b2784236a01e316c02cde5fd71f3743a0d.jpg)

Table 16 continued from previous page  
![](images/71f14197b67d4726ad60b885f685ef96c0bb5653c4f9ac181b1fbb878f1e2e53.jpg)