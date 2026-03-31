# MLSys Paper Expert Memory

## Papers Analyzed

### SOSP 2025 - Session 7 (Storage and Databases)

- [cache_ext](3731569.3764820.md) — Customizing Linux page cache with eBPF (Columbia/IBM Research)
- [Aeolia](3731569.3764816.md) — Userspace interrupt-based storage stack (PKU/Microsoft Research/Igalia)
- [Sandman](3731569.3764804.md) — Fast sustainable storage with sleep-based scheduling (UCSD/SJTU/Samsung)
- [Loom](3731569.3764853.md) — High-frequency telemetry capture and querying (Brown/UW/Northwestern/Intel)
- [Pesto](3731569.3764799.md) — High performance BFT queries with SQL compatibility (Cornell/UC Berkeley)
- [Tiga](3731569.3764854.md) — Geo-distributed transactions with synchronized clocks (Stony Brook/NYU/Stanford)

### SOSP 2025 - Session 8 (ML and FPGA)

- [Tempo](3731569.3764840.md) — Compiled dynamic DL with symbolic dependence graphs (Imperial College London)
- [SAND](3731569.3764847.md) — Programming abstraction for video-based DL (KAIST/Chung-Ang)
- [METIS](3731569.3764855.md) — Fast quality-aware RAG with configuration adaptation (U Chicago/Princeton/Microsoft)
- [HedraRAG](3731569.3764806.md) — Co-optimizing generation and retrieval for heterogeneous RAG (UCSD/Rice)
- [Coyote v2](3731569.3764845.md) — Raised abstraction level for data center FPGAs (ETH Zurich/AMD Research)

### MLSys 2025 - Sessions 7 & 8 (Quantization/Sparsity & LLM Serving)

- [mlsys-2025-sessions-7-8-overview](mlsys-2025-sessions-7-8-overview.md) — Overview and index of all 10 papers analyzed

### Session 7: Quantization and Sparsity

- [LServe](mlsys-2025-lserve.md) — Long-sequence LLM serving with unified sparse attention (MIT Han Lab)
- [SampleAttention](mlsys-2025-sampleattention.md) — Adaptive structured sparse attention for long context LLM inference (Peking/CUHK/Zhipu.AI)
- [LightweightSparseMC](mlsys-2025-lightweight-sparse-mc.md) — N:M sparsity for microcontrollers with ISA extension (Politecnico di Torino/Bologna/ETH Zurich)
- [DynamicInputPruning](mlsys-2025-dip.md) — Predictor-free dynamic sparsity for SwiGLU LLMs with cache-aware masking (Qualcomm AI Research)
- [SparseTransX](mlsys-2025-sparsetransx.md) — SpMM-based KGE training framework (Texas A&M)

### Session 8: LLM and Diffusion Model Serving

- [Seesaw](mlsys-2025-seesaw.md) — Dynamic model re-sharding for high-throughput LLM inference (U Toronto/Vector Institute/CentML)
- [ScaleFusion](mlsys-2025-scalefusion.md) — Multi-GPU ST-DiT inference with communication-computation overlap (U Toronto/AWS)
- [TurboAttention](mlsys-2025-turboattention.md) — Quantized attention with FlashQ + SAS for LLMs (Microsoft/Georgia Tech)
- [FlexInfer](mlsys-2025-flexinfer.md) — CPU-GPU hybrid LLM inference with phase-aware scheduling (Georgia Tech/Meta/Intel)
- [SOLA](mlsys-2025-sola.md) — SLO-aware state-aware scheduling for LLM serving (Tsinghua/Infinigence AI)

## User Preferences

- [user-collaboration-style](user-collaboration-style.md) — Writing preferences and tone

## Methodology Notes

- Always use Chinese for report body text
- Technical terms in English
- Report structure: 9 sections per MLSys paper report
- File naming: match PDF basename (no .pdf suffix)
- Output path: reports/mlsys-2025/{basename_without_pdf}.md
- SOSP 2025 report structure: 10 sections (基础信息/研究背景/要解决问题/核心贡献/主要研究方法/设计与实现/主要实验结果/潜在问题-局限性/未来工作/个人评注)
