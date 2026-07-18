# Wiki Repair Progress

## [2026-07-18] Needs-review batch 50

- Scope: `MPG-MLSys26`, `uEFI-ATC25`, `uFork-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 3 → 0; complete-candidate 440 → 443
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: MPG treated internal coverage and cited deployment data as fleet-wide gains; µEFI overextended boot-path evidence to tiny calls and added an unsupported LLM claim; µFork treated cross-paper Nephele data and a compute-only FaaS test as general comparisons
- Remaining: paper repair manifest complete; proceed to global lint, link-status, candidate decisions, and downstream synthesis rebuild

## [2026-07-18] Needs-review batch 49

- Scope: `DISAGG-MLSys26`, `FunSearch-Nature24`, `HexiScale-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer source verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 6 → 3; complete-candidate 437 → 440
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: DISAGG pointed to ProTrain rather than its verified raw source; FunSearch had abbreviated authors and overcompressed experiment context; HexiScale described simulated and UCloud boundaries too loosely
- Remaining: needs-review 3, complete-candidate 440; source/evidence recovery review remains for the final batch

## [2026-07-18] Needs-review batch 48

- Scope: `fabric-lib-MLSys26`, `pKVM-GhostShell-SOSP25`, `uCache-FAST26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 9 → 6; complete-candidate 434 → 437
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: fabric-lib generalized peak bandwidth and a single RL update; GhostShell attributed all bugs to dynamic specification execution; uCache generalized OOM/random-access benchmarks and hid worst IO overhead
- Remaining: needs-review 6, complete-candidate 437; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-18] Needs-review batch 47

- Scope: `WaferLLM-OSDI25`, `Weaver-ATC25`, `ZEN-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 12 → 9; complete-candidate 431 → 434
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: WaferLLM mixed GEMV microbenchmarks with E2E results; Weaver mixed dedicated and multiplexing baselines; ZEN combined maxima from different models, networks, and baselines
- Remaining: needs-review 9, complete-candidate 434; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-18] Needs-review batch 46

- Scope: `Trochilus-ATC25`, `Veritas-SOSP25`, `WASIT-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 15 → 12; complete-candidate 428 → 431
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Trochilus treated approximate data-plane matching as exact and throughput as measured line rate; Veritas conflated focused verifier bugs with total issues and understated cost evidence; WASIT presented a discovery campaign as ecosystem bug rate
- Remaining: needs-review 12, complete-candidate 431; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-18] Needs-review batch 45

- Scope: `TrainCheck-OSDI25`, `TrainVerify-SOSP25`, `TritorX-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 18 → 15; complete-candidate 425 → 428
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: TrainCheck generalized reproduced historical errors; TrainVerify omitted an author and understated its verification time; TritorX presented functional coverage as performance and omitted the long tail
- Remaining: needs-review 15, complete-candidate 428; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-18] Needs-review batch 44

- Scope: `Tigon-OSDI25`, `Tintin-OSDI25`, `Tock-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 21 → 18; complete-candidate 422 → 425
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Tigon hid single-partition regressions; Tintin misstated average overhead as an upper bound; Tock presented project-scale experience claims as performance benchmarks
- Remaining: needs-review 18, complete-candidate 425; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 43

- Scope: `TaiChi-SOSP25`, `Tempo-SOSP25`, `TickTock-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 24 → 21; complete-candidate 419 → 422
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: TaiChi generalized one CSP deployment and omitted nonzero DP cost; Tempo conflated peak results across attention/RL settings; TickTock reported a 36-second kernel check as sub-30-second full verification
- Remaining: needs-review 21, complete-candidate 422; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 42

- Scope: `SwiftGS-MLSys26`, `SysGPT-OSDI25`, `T2C-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 27 → 24; complete-candidate 416 → 419
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: SwiftGS generalized GPU/scene maxima and used nested bold; SysGPT treated label prediction and LLM judgement as system performance; T2C conflated checkers with tests and historical reproductions with production recall
- Remaining: needs-review 24, complete-candidate 419; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 41

- Scope: `Spira-MLSys26`, `SwCC-ATC25`, `Swift-ATC25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 30 → 27; complete-candidate 413 → 416
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Spira generalized kernel-map microbenchmarks; SwCC mixed FPGA, ASIC estimate, and 10Gbps Soft-RoCE results; Swift treated heuristic and ambiguous time claims as general guarantees
- Remaining: needs-review 27, complete-candidate 416; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 40

- Scope: `SoarAlto-OSDI25`, `Soze-OSDI25`, `Spars-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 33 → 30; complete-candidate 410 → 413
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: SoarAlto conflated predictor correlation with accuracy and mixed baselines; Soze used a single-hop signal and percentage interpretation incorrectly; Spars mixed distinct smartphone and virtual-screen experiments
- Remaining: needs-review 30, complete-candidate 413; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 39

- Scope: `Radical-SOSP25`, `SakuraONE-MLSys26`, `Skybridge-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 36 → 33; complete-candidate 407 → 410
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Radical conflated lower-bound fraction with measured latency; SakuraONE presented non-official benchmark results as official; Skybridge presented opt-in fail-closed consistency as default read behavior
- Remaining: needs-review 33, complete-candidate 410; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 38

- Scope: `QiMeng-Xpiler-OSDI25`, `Quilt-SOSP25`, `Quirk-Sparing-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 39 → 36; complete-candidate 404 → 407
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: QiMeng overstated unit-test accuracy and productivity results; Quilt generalized a synthetic workload and ignored resource-aware splitting; Quirk-Sparing presented parameterized model outputs as operational measurements
- Remaining: needs-review 36, complete-candidate 407; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 37

- Scope: `Proto-SOSP25`, `QBL-MLSys26`, `QOS-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 42 → 39; complete-candidate 401 → 404
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Proto conflated core and full kernel size and self-linked; QBL generalized complexity and benchmark trends; QOS misattributed a 9.6× fidelity result to utilization
- Remaining: needs-review 39, complete-candidate 404; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 36

- Scope: `PipeThreader-OSDI25`, `PoWER-OSDI25`, `ProfInfer-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 45 → 42; complete-candidate 398 → 401
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: PipeThreader conflated ChunkScan with ChunkState and a layer proxy with end-to-end serving; PoWER generalized modified YCSB comparisons; ProfInfer generalized device-specific tracing and diagnosis results
- Remaining: needs-review 42, complete-candidate 401; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 35

- Scope: `Picsou-OSDI25`, `Pie-SOSP25`, `PipeANN-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 48 → 45; complete-candidate 395 → 398
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Picsou attributed unqualified 24× and Kafka claims; Pie mixed incomparable workflow multipliers and self-linked; PipeANN inverted pipeline fullness and generalized SIFT1B/high-recall results
- Remaining: needs-review 45, complete-candidate 398; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 34

- Scope: `PLayer-FL-MLSys26`, `PMR-ATC25`, `Paralegal-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 51 → 48; complete-candidate 392 → 395
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: PLayer mixed rank summaries with individual-dataset accuracy; PMR mixed handset and fleet configurations; Paralegal did not initially state a lint-recognized latency metric and evaluation boundary
- Remaining: needs-review 48, complete-candidate 395; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 33

- Scope: `Orthrus-SOSP25`, `PASTA-ICLR24`, `PHOENIX-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 54 → 51; complete-candidate 389 → 392
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Orthrus generalized injected-SDC coverage; PASTA conflated format and content accuracy; PHOENIX mixed controlled injections, real bug cases, and distinct recovery-time measures
- Remaining: needs-review 51, complete-candidate 392; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 32

- Scope: `Omniglot-OSDI25`, `OpenCAS-Crash-ATC25`, `Orq-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 57 → 54; complete-candidate 386 → 389
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Omniglot generalized strong-runtime guarantees; OpenCAS overextended crash findings to untested modes/configurations; Orq combined incomparable privacy and protocol baselines
- Remaining: needs-review 54, complete-candidate 389; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-17] Needs-review batch 31

- Scope: `Mycroft-SOSP25`, `Nostor-OSDI25`, `Okapi-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 60 → 57; complete-candidate 383 → 386
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Mycroft overstated production RCA labels; Nostor generalized configuration-specific recovery results; Okapi conflated testbed, analytic-transition, and combined-design results
- Remaining: needs-review 57, complete-candidate 386; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 30

- Scope: `Miralis-SOSP25`, `MoE-nD-arXiv26`, `MorphServe-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 63 → 60; complete-candidate 380 → 383
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Miralis generalized offload microbenchmarks; MoE-nD treated no-detectable-loss as equality; MorphServe mixed mode-specific results, baseline scopes, and unsupported thresholds
- Remaining: needs-review 60, complete-candidate 383; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 29

- Scope: `MTraining-MLSys26`, `Mantle-SOSP25`, `MettEagle-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 66 → 63; complete-candidate 377 → 380
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: MTraining mixed distinct training/quality baselines and used nested bold; Mantle merged incompatible metadata workloads; MettEagle overstated an architectural CVE classification as security evidence
- Remaining: needs-review 63, complete-candidate 380; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 28

- Scope: `METIS-SOSP25`, `MLE-Bench-ICLR25`, `MPG-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: METIS and MLE-Bench pass complete-page checks; MPG is retained as `needs-review/full-text` because its figures lack independently auditable before/after numbers for the claimed fleet optimizations
- Manifest change: needs-review 68 → 66; complete-candidate 375 → 377
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: METIS generalized fixed operating-point comparisons; MLE-Bench used a placeholder author and unsupported step limit; MPG presented cited or trend-only fleet examples as independently quantified results
- Remaining: needs-review 66, complete-candidate 377; two source/evidence recovery items; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 27

- Scope: `LLaMEA-KernelTuner-MLSys26`, `LMCache-arXiv25`, `Loom-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 71 → 68; complete-candidate 372 → 375
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: LLaMEA linked the wrong raw paper and misdescribed P-score baselines; LMCache generalized component and centralized-storage results; Loom reversed/merged query baseline ranges and omitted case-study boundaries
- Remaining: needs-review 68, complete-candidate 375; one source-title-mismatch recovery item; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 26

- Scope: `KernelBypassTCP-ATC25`, `LEOCraft-ATC25`, `LLMStation-ATC25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 74 → 71; complete-candidate 369 → 372
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: KernelBypassTCP omitted core-budget boundaries; LEOCraft conflated interactive and week-scale simulations; LLMStation mixed SLO experiments, latency tradeoffs, and hardware scopes
- Remaining: needs-review 71, complete-candidate 372; one source-title-mismatch recovery item; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 25

- Scope: `KPerfIR-OSDI25`, `KTransformers-SOSP25`, `Kamino-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 77 → 74; complete-candidate 366 → 369
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: KPerfIR generalized a single-GEMM instrumentation result; KTransformers combined incomparable baselines and defer scenarios; Kamino treated representative-zone before/after measurements as randomized global production results
- Remaining: needs-review 74, complete-candidate 369; one source-title-mismatch recovery item; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 24

- Scope: `IntervalSkiplist-SOSP25`, `Jenga-SOSP25`, `KNighter-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 80 → 77; complete-candidate 363 → 366
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: IntervalSkiplist generalized high-contention throughput results; Jenga mixed incompatible context, utilization, and throughput scenarios and contained a self-link; KNighter mixed checker-success and triage FP denominators
- Remaining: needs-review 77, complete-candidate 366; one source-title-mismatch recovery item; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 23

- Scope: `HyperQ-OSDI25`, `IceCache-arXiv26`, `IntAttention-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 83 → 80; complete-candidate 360 → 363
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: HyperQ’s all-at-once and Poisson queue scenarios required separate boundaries; IceCache’s LongBench, synthetic passkey, and single-GPU RULER results needed distinct scopes; IntAttention needed explicit throughput/energy metrics and a non-nested observation heading
- Remaining: needs-review 80, complete-candidate 363; one source-title-mismatch recovery item; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 22

- Scope: `Greyhound-ATC25`, `HEC-ATC25`, `HexiScale-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 86 → 83; complete-candidate 357 → 360
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Greyhound mixed production trace and injected mitigation scales; HEC overstated benchmark soundness/completeness; HexiScale mixed measured heterogeneous results with cost-model/Metis simulations
- Remaining: needs-review 83, complete-candidate 360; one source-title-mismatch recovery item; FPRev remains isolated pending review

## [2026-07-16] Needs-review batch 21

- Scope: `G-HEMP-MLSys26`, `GoFS-SOSP25`, `GraphPy-ATC25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 89 → 86; complete-candidate 354 → 357
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: G-HEMP used unsupported rotation figures and inconsistent graph size; GoFS overstated inherited F2FS recovery as tested behavior; GraphPy generalized framework/version-specific GNN results
- Remaining: needs-review 86, complete-candidate 357; one source-title-mismatch recovery item

## [2026-07-16] Needs-review batch 20

- Scope: `Flashlight-MLSys26`, `FlexGuard-SOSP25`, `FunSearch-Nature24`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 91 → 89; complete-candidate 352 → 354
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Flashlight merged block-mask kernel speed with mask-construction cost; FlexGuard generalized selected workload wins despite counterexamples; FunSearch blurred best-of-run discovery and robustness
- Remaining: needs-review 89, complete-candidate 354; one source-title-mismatch recovery item

## [2026-07-16] Needs-review batch 19

- Scope: `FastACS-ATC25`, `Fawkes-SOSP25`, `FlashInfer-Bench-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 94 → 91; complete-candidate 349 → 352
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: FastACS mixed steady and abrupt scaling; Fawkes treated adapted-tool comparisons as stock baselines; FlashInfer-Bench generalized generated-kernel and one RMSNorm case into serving-wide evidence
- Remaining: needs-review 91, complete-candidate 352; one source-title-mismatch recovery item

## [2026-07-16] Needs-review batch 18

- Scope: `ExecuTorch-MLSys26`, `FCP-MLSys26`, `FLB-ATC25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 97 → 94; complete-candidate 346 → 349
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: ExecuTorch mixed backend and precision changes and generalized device results; FCP presented attention-module MFU as full-training evidence; FLB mixed testbed PFC outcomes with NS3 scaling results
- Remaining: needs-review 94, complete-candidate 349; one source-title-mismatch recovery item

## [2026-07-15] Needs-review batch 17

- Scope: `DecDEC-OSDI25`, `DreamDDP-MLSys26`, `EMT-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 100 → 97; complete-candidate 343 → 346
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: DecDEC generalized a client-kernel buffer metric and treated 3.5-bit OOM as a quality win; DreamDDP conflated iteration and target-performance timing; EMT mixed emulation/simulation evidence with hardware claims
- Remaining: needs-review 97, complete-candidate 346; one source-title-mismatch recovery item

## [2026-07-14] Needs-review batch 16

- Scope: `DEDE-OSDI25`, `DISAGG-MLSys26`, `DSA-2LM-ATC25`
- Method: three read-only source checks, followed by reviewer patches
- Sampling: 3/3 reviewed (100%)
- Result: DEDE and DSA-2LM pass page structure and paper quality checks; DISAGG is quarantined as `invalid/metadata-only`
- Manifest change: needs-review 102 → 100; complete-candidate 341 → 343
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Failure: DISAGG declares a raw source whose PDF/Markdown title is ProTrain. The page was reduced to a source-title-mismatch audit record; correct verified source is required before it can be rebuilt.
- Remaining: needs-review 100, complete-candidate 343; one source-title-mismatch recovery item

## [2026-07-14] Needs-review batch 15

- Scope: `CountingAtomicity-ATC25`, `Coyote-v2-SOSP25`, `DCP-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 105 → 102; complete-candidate 338 → 341
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: CountingAtomicity conflated static property inference with end-to-end crash testing; Coyote-v2 merged incompatible reconfiguration timing definitions; DCP conflated causal and sparse-mask baselines and hid planner CPU requirements
- Remaining: needs-review 102, complete-candidate 341

## [2026-07-14] Needs-review batch 14

- Scope: `ContextPilot-MLSys26`, `Converos-ATC25`, `CortenMM-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 108 → 105; complete-candidate 335 → 338
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: ContextPilot had nested bold and conflated benchmark-specific hit-ratio results; Converos blurred bounded model checking and endpoint workflow claims; CortenMM overstated proof scope and needed workload-specific performance boundaries
- Remaining: needs-review 105, complete-candidate 338

## [2026-07-14] Needs-review batch 13

- Scope: `Chitu-ATC25`, `Collective-NoC-MLSys26`, `ContextAwareMoE-CXLNDP-arXiv25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 111 → 108; complete-candidate 332 → 335
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Chitu required explicit WAN and injected-fault boundaries; Collective-NoC presented analytical large-mesh estimates as measured end-to-end results; ContextAwareMoE needed to distinguish routing-similarity evidence and simulated GPU–NDP results from production serving behavior
- Remaining: needs-review 108, complete-candidate 335

## [2026-07-14] Needs-review batch 12

- Scope: `COpter-SOSP25`, `CacheGen-SIGCOMM24`, `Cartridges-ICLR26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 114 → 111; complete-candidate 329 → 332
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: COpter misattributed aggregate solver speedups to CPLEX and hid trace/synthetic boundaries; CacheGen used abbreviated authors and treated task metrics as general generation fidelity; Cartridges used abbreviated authors and required explicit offline-training and peak-throughput boundaries
- Remaining: needs-review 111, complete-candidate 332

## [2026-07-14] Needs-review batch 11

- Scope: `CAGE-MLSys26`, `CATWILD-MLSys26`, `CHERIoT-RTOS-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 117 → 114; complete-candidate 326 → 329
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: CAGE conflated accuracy and validation-loss evidence and contained nested bold; CATWILD confused candidate chip-time coverage with adoption and used invalid approximation syntax; CHERIoT-RTOS made broad deployment and completed-verification claims beyond its FPGA measurements
- Remaining: needs-review 114, complete-candidate 329

## [2026-07-14] Needs-review batch 10

- Scope: `Basilisk-OSDI25`, `Belfast-OSDI25`, `Bin2Wrong-ATC25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 120 → 117; complete-candidate 323 → 326
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Basilisk generalized its 16-protocol corpus and omitted proof-artifact boundaries; Belfast turned a mechanism argument into a formal proof and generalized a 10-shard append result; Bin2Wrong simplified prior-work coverage, used invalid approximate notation, and lacked a structured oracle ceiling
- Remaining: needs-review 117, complete-candidate 326

## [2026-07-14] Needs-review batch 9

- Scope: `AutoScientists-arXiv26`, `BES-arXiv26`, `BLASST-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 123 → 120; complete-candidate 320 → 323
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: AutoScientists used an unresolved BioML internal numeric conflict and over-specified its optimistic-locking transport; BES presented three-run variance as statistically significant and blurred equal-budget comparisons; BLASST treated a calibrated threshold law as configuration-free and lacked attention-quality/kernel boundaries
- Remaining: needs-review 120, complete-candidate 323

## [2026-07-14] Needs-review batch 8

- Scope: `Atropos-SOSP25`, `AttributionSparseActivation-MLSys26`, `AutoMan-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 126 → 123; complete-candidate 317 → 320
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Atropos turned averages into per-scenario guarantees and misstated cancellation-hook coverage; AttributionSparseActivation mixed unrelated sparsity, quality, latency, and memory conditions and misstated the online predictor path; AutoMan generalized Multi-Paxos/KV results and included an unrelated KNighter claim
- Remaining: needs-review 123, complete-candidate 320

## [2026-07-14] Needs-review batch 7

- Scope: `ApproxMLIR-MLSys26`, `ArckFS-SOSP25`, `Atmosphere-SOSP25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 129 → 126; complete-candidate 314 → 317
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: ApproxMLIR attributed exact-baseline speedups to static approximation and claimed strict Pareto dominance despite ties; ArckFS+ overstated a targeted audit as proof of no architectural vulnerability and hid uneven regressions; Atmosphere omitted hardware boundaries, contradicted its I/O evaluation, and contained inaccurate TCB and invented scale-out statements
- Remaining: needs-review 126, complete-candidate 317

## [2026-07-14] Needs-review batch 6

- Scope: `Aegaeon-SOSP25`, `AlphaEvolve-arXiv25`, `AlphaProofNexus-arXiv26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 132 → 129; complete-candidate 311 → 314
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: Aegaeon applied 7 models/GPU to the whole system instead of the decoding pool and attributed 97% to swap alone; AlphaEvolve overstated a non-controlled thousands-vs-millions comparison as a precise sample-efficiency result; AlphaProof Nexus contained an inconsistent 6/9 cost comparison and omitted post-hoc/cost boundaries
- Remaining: needs-review 129, complete-candidate 314

## [2026-07-14] Needs-review batch 5

- Scope: `151-Trading-Strategies-SSRN18`, `ADR-MLSys26`, `AFaaS-OSDI25`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: needs-review 135 → 132; complete-candidate 308 → 311
- Validator change: added tested `empirical_evidence: none` exception for descriptive/reference works whose source explicitly contains no numeric experiment; locator and 2–5 Claim–Evidence rows remain mandatory
- Test result: lint 23/23, repair-manifest 6/6, linker 5/5; `git diff --check` passed
- Errors found during review: ADR benchmark 0-FP was incorrectly allowed to imply production precision despite a 49% FP analyst queue, and source-stem integrity was rechecked; AFaaS used Catalyzer instead of the stronger CataOnly baseline and blurred mocked comparison with online A/B; 151 Trading Strategies overstated code defaults and downstream influence despite containing no empirical results
- Remaining: needs-review 132, complete-candidate 311

## [2026-07-14] Invalid/abstract-only batch 4

- Scope: `TokenWeave-MLSys26`, `BOOST-MLSys26`, `DP-ZeRO-MLSys26`
- Method: three read-only full-text repair packets, followed by reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks; invalid and abstract-only queues are empty
- Manifest change: invalid 1 → 0; abstract-only 2 → 0; complete-candidate 305 → 308
- Test result: lint 22/22, repair-manifest 5/5, linker 5/5; `git diff --check` passed
- Errors found during review: TokenWeave treated a non-producing no-communication counterfactual as a theoretical lower bound; BOOST contained wrong topology, a reversed baseline order, self-link, and unresolved prose; DP-ZeRO overstated 100B utility and conflated system scale with private-training convergence
- Remaining: needs-review 135, complete-candidate 308

## [2026-07-14] Invalid batch 3

- Scope: `RaidServe-MLSys26`, `SpecDecodeBench-MLSys26`, `StreamDiffusionV2-MLSys26`
- Method: three read-only repair packets, followed by full-text reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: invalid 4 → 1; complete-candidate 302 → 305
- Test result: lint 22/22, repair-manifest 5/5, linker 5/5; `git diff --check` passed
- Errors found during review: RaidServe misattributed the 183× full recovery result to one component and invented an attention-quality trade-off; SpecDecodeBench presented a 4.9× perfect-oracle bound as an implemented adaptive system; StreamDiffusionV2 lacked evaluation boundaries and its source contains a 64.52/61.57 FPS prose-vs-figure conflict
- Remaining: invalid 1, abstract-only 2, needs-review 135, complete-candidate 305

## [2026-07-14] Invalid batch 2

- Scope: `Catur-MLSys26`, `Guard-MLSys26`, `PipelinedSharding-MLSys26`
- Method: three read-only repair packets, followed by full-text reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: invalid 7 → 4; complete-candidate 299 → 302
- Test result: lint 22/22, repair-manifest 5/5, linker 5/5; `git diff --check` passed
- Errors found during review: Catur and Guard contained placeholder authors and malformed nested bold; Guard conflated a 70% step-efficiency claim with MFU; PipelinedSharding converted the paper-defined 2G (2,000MB) into 2GB and treated reader-proposed future work as author claims
- Remaining: invalid 4, abstract-only 2, needs-review 135, complete-candidate 302

## [2026-07-14] Pilot batch 1

- Scope: `DAS-MLSys26`, `Matrix-MLSys26`, `FLoRIST-MLSys26`
- Method: three read-only repair packets, followed by full-text reviewer verification and local patches
- Sampling: 3/3 reviewed (100%)
- Result: 3/3 pass page structure and paper quality checks
- Manifest change: invalid 10 → 7; complete-candidate 296 → 299
- Test result: lint 22/22, repair-manifest 5/5, linker 5/5
- Errors found during review: FLoRIST mixed three incompatible communication/compute metrics; Matrix overstated unqualified quality preservation; DAS lacked all quantitative evaluation evidence
- Remaining: invalid 7, abstract-only 2, needs-review 135, complete-candidate 299
