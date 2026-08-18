# SOL-ExecBench: Speed-of-Light Benchmarking for Real-World GPU Kernels Against Hardware Limits

Edward Lin<sup>∗</sup>, Sahil Modi<sup>†</sup>, Siva Kumar Sastry Hari<sup>†</sup>, Qijing Huang<sup>†</sup>, Zhifan Ye<sup>†</sup>, Nestor Qin<sup>†</sup> Fengzhe Zhou<sup>†</sup>, Yuan Zhang<sup>†</sup>, Jingquan Wang<sup>†</sup>, Sana Damani<sup>†</sup>, Dheeraj Peri, Ouye Xie Aditya Kane, Moshe Maor, Michael Behar, Triston Cao, Rishabh Mehta, Vartika Singh Vikram Sharma Mailthody, Terry Chen, Zihao Ye, Hanfeng Chen, Tianqi Chen Vinod Grover, Wei Chen, Wei Liu, Eric Chung, Luis Ceze, Roger Bringmann Cyril Zeller, Michael Lightstone, Christos Kozyrakis, Humphrey Shi

NVIDIA

## Abstract

As agentic AI systems become increasingly capable of generating and optimizing GPU kernels, progress is constrained by benchmarks that reward speedup over software baselines rather than proximity to hardware-efficient execution. We present SOL-ExecBench, a benchmark of 235 CUDA kernel optimization problems extracted from 124 production and emerging AI models spanning language, diffusion, vision, audio, video, and hybrid architectures, targeting NVIDIA Blackwell GPUs. The benchmark covers forward and backward workloads across BF16, FP8, and NVFP4, including kernels whose best performance is expected to rely on Blackwell-specific capabilities. Unlike prior benchmarks that evaluate kernels primarily relative to software implementations, SOL-ExecBench measures performance against analytically derived Speed-of-Light (SOL) bounds computed by SOLAR, our pipeline for deriving hardware-grounded SOL bounds, yielding a fixed target for hardware-efficient optimization. We report a SOL Score that quantifies how much of the gap between a release-defined scoring baseline and the hardware SOL bound a candidate kernel closes. To support robust evaluation of agentic optimizers, we additionally provide a sandboxed harness with GPU clock locking, L2 cache clearing, isolated subprocess execution, and static analysis based checks against common reward-hacking strategies. SOL-ExecBench reframes GPU kernel benchmarking from beating a mutable software baseline to closing the remaining gap to hardware Speed-of-Light.

## 1 Introduction

As agentic AI systems become increasingly capable of generating and optimizing GPU kernels Chen et al. (2025); Xu et al. (2026), progress is constrained by how we evaluate them. Existing benchmarks often measure success by speedup over a software baseline, even though the real objective in kernel engineering is to approach hardware-efficient execution. This mismatch is becoming more consequential as each GPU generation introduces new performance-critical features at a rapid pace, while power efficiency becomes a primary constraint in data center deployments. In practice, manual optimization cannot keep up indefinitely with both the hardware feature cadence and the growth in model complexity, making AI-based kernel optimization increasingly necessary rather than optional.

The space of AI model architectures continues to grow. Beyond dense Transformers Vaswani et al. (2017), today’s frontier includes Mixture-of-Experts (MoE) models (DeepSeek-V3 DeepSeek-AI (2024), Qwen3-Coder-480B), state-space models or SSMs (Mamba-2 Dao and Gu (2024), Jamba AI21 Labs (2024)), linear attention variants (RWKV Peng et al. (2023), Gated Delta Rule Yang et al. (2024)), hybrid SSM-Transformer architectures (Nemotron-H NVIDIA (2025b)), and multi-modal systems combining vision, audio, and language (Qwen3-VL, Gemma-3n, Llama-3.2-Vision). Each architecture introduces novel computational primitives, e.g., Multi-head Latent Attention (MLA), SwiGLU MoE dispatch, 3D rotary embeddings for video, and chunk-based selective scan, that require specialized GPU kernels to fully leverage the hardware, as demonstrated by IO-aware attention kernels such as FlashAttention Dao et al. (2022). A single frontier model may contain dozens of such primitives, and developing speed-of-light (SOL) kernels for each is time-consuming. Moreover, kernel development and hardware design reinforce one another: understanding the kernels demanded by emerging workloads informs future hardware features, while new hardware capabilities in turn unlock further kernel optimizations. A benchmark for kernel optimization must therefore cover this architectural breadth, both to remain representative and to signal future workload trends to hardware designers.

This growing diversity of workloads, together with rapid progress in agentic AI systems that build on advances in LLM-based code generation and autonomously compile, profile, and iteratively refine GPU kernels Chen et al. (2021); Li et al. (2023); Lozhkov et al. (2024); Xu et al. (2026), makes benchmarking substantially more challenging. A benchmark must: (1) cover current frontier and emerging architectures, (2) include problems where achieving best performance requires exploiting new hardware features and precision formats, (3) include both post-training and inference workloads, (4) evaluate kernels against a hardware-grounded maximum achievable performance target rather than a mutable software baseline, and (5) provide evaluation infrastructure robust to adversarial optimization.

Recent benchmarks such as KernelBench Ouyang et al. (2025), FlashInfer-Bench Xing et al. (2026), BackendBench Saroufim et al. (2025), and TritonBench Li et al. (2025) have made important strides toward this goal (we discuss each in detail in Section 2). However, we find that no single existing benchmark addresses all of these criteria simultaneously. For example, KernelBench includes 250 PyTorch-to-CUDA problems but draws its model-level workloads from older architectures and measures speedup relative to PyTorch eager execution rather than hardware limits. FlashInfer-Bench captures real inference workloads on Blackwell, including FP8 MoE kernels, but does not cover post-training or lower-precision formats such as NVFP4.

We present SOL-ExecBench, a benchmark designed to meet these criteria. From 124 production and emerging AI models spanning LLMs, diffusion, vision, audio, video, and hybrid architectures, we use an LLM-aided pipeline to extract 7,400 computational subgraphs and curate 235 benchmark problems organized into four tiers by complexity and precision. Each problem is accompanied by a specification, PyTorch reference code, and up to ∼16 dynamically-shaped workloads, covering forward and backward passes across BF16, FP8, and NVFP4 on the NVIDIA B200 GPU.

The key departure from prior benchmarks is the evaluation target. Rather than rewarding speedup over a software reference alone, SOL-ExecBench evaluates kernels against Speed-of-Light (SOL) bounds, i.e., analytically derived lower bounds on execution time on the target hardware. We developed SOLAR, a pipeline that analytically derives these hardware-grounded SOL bounds from FLOP counts, byte counts, and peak GPU throughput and bandwidth. We combine these bounds with a predefined scoring baseline to derive the SOL Score, which measures how much of the baseline-to-SOL gap a candidate kernel closes. Under this metric, a score of 0.5 corresponds to matching the scoring baseline, while a score of 1.0 corresponds to reaching the hardware SOL bound. The score therefore reflects not only improvement over a baseline, but also the optimization headroom that remains relative to the maximum achievable hardware performance.

SOL-ExecBench also includes a sandboxed evaluation harness for reliable and reproducible scoring. To construct stronger scoring baselines, we build an agentic optimizer that improves the provided PyTorch reference implementations under the same evaluation protocol. Running this optimizer across the benchmark surfaced reward-hacking behaviors, i.e., attempts to game the evaluator rather than produce genuinely faster kernels, and these observations informed the mitigation techniques built into the harness.

Table 1: Comparison of GPU kernel generation benchmarks.  
![](images/9746f7a1c44bb09b62b7302180f9eb030594a0135cd2682dec503d4595bdbb3c.jpg)  
Target HW: Any = hardware-agnostic problems; BW+ = problems targeting Blackwell and newer architecture-specific features. Train: includes backward passes. Precision: dominant data types in problem set.

We validate SOL-ExecBench by running this agentic optimizer across all 235 problems. The resulting agent-generated baselines achieve a median SOL score of 0.732, placing them well above the S=0.5 midpoint while leaving clear headroom for further optimization. The SOL score correlates near-perfectly with the fraction of optimization headroom reclaimed, whereas speedup alone is a weaker predictor. During this process, 14.5% of agent submissions were flagged for reward hacking, underscoring the importance of robust evaluation infrastructure.

We publicly release the SOL-ExecBench dataset and evaluation harness at https://github.com/ NVIDIA/SOL-ExecBench. By anchoring evaluation to hardware SOL bounds rather than mutable software baselines, SOL-ExecBench reframes GPU kernel benchmarking around closing the remaining gap to hardware Speed-of-Light.

## 2 Related Work

Benchmarking GPU kernel generation for agents is a relatively new and rapidly evolving field with many existing benchmarks. We include some of the prominent ones here. Table 1 provides a structured comparison.

## 2.1 Related Benchmarks

KernelBench Ouyang et al. (2025) is a widely adopted benchmark for LLM-driven CUDA kernel generation. It contains 270 PyTorch problems across four levels: Level 1 (100 single operations such as matrix multiply and convolution), Level 2 (100 operator fusion patterns), Level 3 (50 complete model architectures), and Level 4 (20 aspirational tasks from HuggingFace models). KernelBench introduces the fast<sub>p</sub> metric, defined as the fraction of generated kernels that are both correct and achieve speedup > p× over the PyTorch eager baseline. Despite KernelBench’s popularity, its problems are sourced from models that are no longer state of the art (Level 3 includes ResNet, BERT, VGG), and solutions do not need to exercise the latest hardware features to beat the PyTorch baseline.

FlashInfer-Bench Xing et al. (2026) benchmarks inference primitives traced from production LLM serving systems (vLLM, SGLang). It uses the FlashInfer Trace schema to capture real operator shapes and data, yielding problems grounded in actual deployment. The MLSys 2026 competition tracks (fused MoE, sparse attention, gated delta net) target NVIDIA B200 GPUs and accept solutions in CUDA, Triton Tillet et al. (2019), CuTe DSL NVIDIA (2024a), and cuTile Bentz (2025). SOL-ExecBench incorporates FlashInfer-Bench’s 26 inference primitives and extends the approach to training workloads, quantized operations, and broader model coverage.

BackendBench Saroufim et al. (2025) benchmarks individual PyTorch backend operators (ATen ops), testing LLM-generated Triton kernels against PyTorch’s OpInfo test suites with tensor shapes traced from HuggingFace models. It covers 271 operators for correctness and 124 for performance, with the goal of upstreaming generated kernels directly into PyTorch. BackendBench operates at the library-operator level with relative performance metrics, whereas SOL-ExecBench targets application-level subgraphs extracted from full model architectures, includes backward passes and low-precision formats (FP8, NVFP4), and measures against hardware SOL bounds.

TritonBench Li et al. (2025) is the first benchmark specifically targeting Triton code generation. It contains 184 operators sourced from real GitHub repositories (TritonBench-G) with a complementary PyTorch-aligned set (TritonBench-T), and evaluates both correctness and hardware efficiency via DSL-specific metrics (memory tiling, work-group scheduling). TritonBench focuses on individual operator generation in Triton, whereas SOL-ExecBench targets multi-operator fused subgraphs from real model architectures and accepts solutions in many GPU language (CUDA, Triton, CUTLASS, etc.).

ComputeEval NVIDIA (2025a) provides 232 handcrafted CUDA programming tasks that test LLM competency across a broad range of GPU programming concepts, including Tensor Cores, CUDA Graphs, streams, warp primitives, and shared memory. It focuses on evaluating functional correctness (pass@k) and is well suited for assessing whether an LLM can write valid CUDA code. ComputeEval and SOL-ExecBench are complementary. ComputeEval primarily measures breadth of CUDA programming knowledge, while SOL-ExecBench focuses on the deeper challenge of optimizing deep learning workloads against hardware performance limits.

CUDABench Zhu et al. (2026) benchmarks text-to-CUDA generation with 500 tasks across six domains (AI, scientific computing, data analytics, signal processing, graphics, and scientific simulation/finance) at three difficulty levels. It introduces a roofline-based Performance-Score that, like our SOL metric, measures against hardware limits rather than software baselines. CUDABench targets general-purpose CUDA programming, whereas SOL-ExecBench focuses specifically on deep learning kernel optimization with problems extracted from production model architectures.

## 2.2 Speed-of-Light Metrics

Roofline analysis Williams et al. (2009) provides the theoretical framework underlying our SOL metric, bounding kernel performance by peak compute throughput and memory bandwidth. Orojenesis Huang et al. (2024) refines this by computing tighter, attainable data movement bounds for tensor algorithms as a function of on-chip buffer capacity, showing that na¨ıve roofline bounds can significantly overestimate achievable performance for operations with limited data reuse. Our use of SOL bounds aligns benchmark evaluation with the methodology used by NVIDIA’s internal kernel development teams, where performance is measured as a percentage of the hardware Speed-of-Light rather than relative to a software baseline. We build on Orojenesis to develop SOLAR (SOL Analysis for Runtime), our pipeline for automatically deriving tight, hardware-grounded SOL bounds from PyTorch reference implementations. SOLAR is described in detail in Section 4.2.

## 3 Benchmark Construction

We design SOL-ExecBench based on three principles drawn from the need for high-performance kernels in AI post-training applications, a domain seeing exponential growth:

• Application-grounded problems. Problems must be driven by state-of-the-art and emerging model architectures so that operator types, tensor shapes, and data types reflect what actually runs in production today and what will run in near future.

• Exercising latest hardware features. Problems and metric targets must encourage solutions that exercise the latest hardware features in newer GPU architectures (e.g., NVFP4 via 5thgeneration Tensor Cores on Blackwell GPUs).

• Post-training lifecycle. Problems must span the broader post-training lifecycle such as fine-tuning, RLHF, and inference serving, capturing forward and backward passes with reduced-precision data types (FP8, NVFP4) rather than inference-only forward kernels.

Following these principles, we extract problems from 124 production AI models spanning six domains, target the NVIDIA B200 GPU, and include forward and backward passes across BF16, FP8, and NVFP4 precisions, producing 235 benchmark problems organized into four categories.

![](images/ea0e70b7c6035f495fba7ccf9c57548d935ecb5a8191b5a96d239318d82f898e.jpg)  
Figure 1: Overview of the SOL-ExecBench construction pipeline. Input is 124 source models spanning six domains; output is 235 validated benchmark problems in four categories.

## 3.1 Source Model Coverage

We source models from HuggingFace, Artificial Analysis, and arXiv, prioritizing both established and emerging architectures that represent the current and possibly future frontier of AI workloads. In total, we process 124 models spanning six domains.

Large language models (61 models). This group includes dense Transformers such as Llama-3.x, Gemma-3, and Phi-4; Mixture-of-Experts models such as DeepSeek-V3/R1, Qwen3-Coder-480B, and GLM-4.7, and newer attention variants such as Kimi-K2. Together, they introduce operations such as grouped-query attention, SwiGLU MoE dispatch, and multi-token prediction.

Diffusion models—text and image (24 models). Image generation models include Stable Diffusion variants, FLUX.1/2, HunyuanImage, Qwen-Image-Edit, Step1X-Edit, Bria-3.2, FIBO, Sana, and HiDream, contributing adaptive layer normalization, dual-stream joint attention, and VAE encoder/decoder blocks. Text diffusion models (e.g., LLaDA-8B) introduce parallel denoising over token sequences, a distinct computational pattern from autoregressive generation.

Vision (6), Audio/Speech (9), and Video (2 models). The vision set includes models such as SAM-HQ, ConvNextV2, VMamba, NAFNet, Swin2SR, and MaskGIT, the audio set includes both ASR models (Whisper, Parakeet-TDT, Canary) and TTS/voice models (Voxtral, OpenVoice, Kokoro, XTTS-v2, Granite-Speech-3.3-8B), and the video set includes Wan2.2-T2V. These domains contribute windowed attention, conformer encoders, and 3D RoPE-based spatial attention.

Multimodal and hybrid architectures (22 models). This category includes vision-language models such as Qwen3-VL, Qwen3-Omni, Llama-3.2-Vision, Gemma-3n, Molmo-7B-D, and MiMo-V2- Flash; OCR and document-understanding models such as DeepSeek-OCR; and SSM and hybrid architectures such as Jamba, Nemotron-H, and RWKV-v7 that combine attention, state-space, and MoE primitives.

## 3.2 Extraction Pipeline

The extraction pipeline proceeds in four stages as shown in Figure 1.

Model preparation. For each model, we load the architecture definition and extract the full model source code together with configuration constants such as hidden size, number of attention heads, and data types.

Subgraph extraction. A frontier LLM analyzes each prepared model to identify important computational subgraphs, producing standalone PyTorch implementations with all constants inlined. Forward passes are generated sequentially to enable deduplication. Backward passes are generated in parallel. For quantized models, specialized prompts guide the LLM to use the appropriate low-precision primitives. From 124 models, we extract 7,400 subgraphs spanning forward and backward passes.

Curation and sampling. Each subgraph is characterized across 11 dimensions, including operation type, model domain, precision, compute intensity, and forward/backward split, and stratified sampling selects a diverse subset with balanced coverage. The sampling maintains a target ratio of single-kernel to multi-kernel fused problems and reserves dedicated slots for quantized operations. Each selected subgraph is converted into a benchmark problem by an LLM-based driver generator. Because curation is decoupled from extraction, the subgraph pool can be resampled to target different benchmark goals without re-running extraction.

Validation. Validation has three components. First, multiple rounds of human expert review together with LLM-based review check that each problem is well-formed, captures the intended subgraph, and has a correct reference implementation. Second, execution-based checking verifies numerical correctness across all workloads, with tolerances calibrated from repeated reference runs.

Third, we run an agentic kernel optimizer against every candidate problem. This pass exposed specification loopholes in some problems. These are cases where the agent could achieve high speedups by exploiting ambiguities in the problem definition rather than writing a genuinely faster kernel. Problems that failed any of these checks, or that were susceptible to such specification gaming, are pruned, yielding a final set of 245 validated problems. Of these, we release 235 as the public benchmark and reserve 10 for a forthcoming competition. Game and cheat detection in the evaluation harness is described further in Section 4.4.

## 3.3 Problem Specification Format

Each problem is defined by three components following an extended FlashInfer Trace schema.

Definition. The definition specifies the problem name, operation type, typed symbolic axes (const, var, or expr), input/output tensor shapes and dtypes, and a reference implementation.

Reference. The reference is a self-contained PyTorch implementation with a top-level run() function. Problems requiring structured inputs (e.g., sparse indices, paged KV caches) additionally define a get inputs() function.

Workloads. The workloads provide concrete axis values across multiple (often around 16) dynamically shaped instances per problem, with typical dynamic axes including batch size ∈ {1, . . . , 64} and sequence length ∈ {128, . . . , 8192}.

## 4 Dataset and Evaluation

The composition of the problems in the benchmark are subject to change over time. At the time of this publication, SOL-ExecBench contains 235 problems organized into four categories by complexity and precision as described in Table 2. Each problem is released with a full specification, PyTorch reference implementation, and an optimized baseline.

Table 2: Benchmark category summary.  
![](images/e813dfa2842ef40a626aac2a180da7a377b11dbf50c36a6d21f14a65406c9347.jpg)

## 4.1 Problem Characterization

Figure 2 provides four characterization views of the 235 problems in SOL-ExecBench. As shown in Figure 2(a), L1 and L2 together account for 176 problems (75%). Of the full set, 189 problems (80%) are forward passes and 46 (20%) are backward passes. Problems in Quant and FlashInfer-Bench sections are entirely forward. The backward problems cover patterns such as gradient scatter through MoE routing, backward softmax with softcapping, and backpropagation through fused norm-residual chains.

Figure 2(b) shows the operation-type distribution. Attention dominates with 81 problems (35%), consistent with attention remaining a primary optimization target across LLM, vision, and multimodal architectures. MoE follows with 36 (15%), then normalization 27 (12%), embedding/positional encoding 20 (9%), linear/projection 16 (7%), other operations 13 (6%), fused blocks 11 (5%), GEMM and MLP/activation 10 each (4%), convolution 6 (3%), and SSM/Mamba 5 (2%).

![](images/20f6a37ccfa86f5992e395ad85cdb801de9d4e4432f481952031e3f436d168fd.jpg)  
(a) Benchmark Categories

![](images/418db52cce6c42a6820a52624a565e4e718e67c0239188ab7ae0068c31794e96.jpg)  
(b) Operation Types

![](images/a58fc3f41d3b511225bd87ecc14a642248d986505364caab4922c889178f5355.jpg)  
(c) Model Domains

![](images/f80582abcfba265d9ad0baba545b0f24915a98dd66898f6aeb5f129785cdc15d.jpg)  
(d) Precision  
Figure 2: Problem characterization of the 235 SOL-ExecBench problems across four dimensions. (a) Benchmark category breakdown (forward/backward split shown with hatching). (b) Distribution by primary operation type. (c) Problems by model domain, stacked by benchmark category. (d) Distribution by primary compute precision.

Figure 2(c) breaks down problems by model domain, stacked by benchmark category. LLMs contribute the largest share (153 problems, 65%), followed by Multimodal (27), Diffusion (25), Vision (13), Audio/Speech (11), and Video (6). LLM problems span all four categories; Diffusion and Vision problems are concentrated in L1 and L2.

Figure 2(d) shows the distribution by primary compute precision, defined as the dtype of the primary data tensors (not accumulation buffers). BF16 is the most common format (107 problems, 46%), reflecting the dominance of modern LLM and diffusion workloads. FP32 accounts for 79 problems (34%), concentrated in audio, vision, and diffusion models. FP8 (19, 8%) and NVFP4 (15, 6%) are exclusively in the Quant category, while FP16 (12, 5%) appears mostly in audio and GEMM workloads. A small set of 3 problems (1%) are labeled Mixed. These are integer- and booleandominated kernels, attention mask construction, MoE token routing sort, and multimodal position index computation, where no single floating-point format applies.

Lastly, each problem has 16 workloads (FlashInfer-Bench: 7–48) covering dynamic axes such as batch size ∈ {1, . . . , 64} and sequence length ∈ {128, . . . , 8,192} (not plotted in the figure). Seventy-eight problems (33%) use custom input generation for structured inputs such as paged KV caches, MoE routing tensors, and sparse attention masks.

![](images/86d8029748da5ac1390652e62d9c196962d4b31033af88e859cc3f15a9c1c911.jpg)  
Figure 3: SOLAR pipeline for deriving the Speed-of-Light bound T<sub>SOL</sub> from a PyTorch model and input shape.

![](images/0159a695e50d2df530984a0b64ca1ad3a0790cf53a6ce10e95edd808283ebb52.jpg)  
(d) SOL bound (B200@1.5GHz)  
Figure 4: SOLAR pipeline on a concrete SOL-ExecBench L1 problem.

## 4.2 SOL Bound Derivation

To quantify the remaining headroom for improvement and validate the claimed speedups of generated kernels, we include the Speed-of-Light (SOL) runtime for each problem in the benchmark. These bounds are derived using SOLAR<sup>2</sup>, a tool developed to estimate the minimum theoretical runtime achievable for PyTorch programs on target hardware. As illustrated in Figure 3, SOLAR consists of three analysis stages:

1. Graph Extractor: The extractor traces the PyTorch model to produce an operator graph capturing dataflow, operator types, and intermediate tensor shapes. It is built upon the torchview library Kurttutan (2022), which leverages forward hooks to collect tensor metadata during a live forward pass. By leveraging this mechanism, SOLAR respects PyTorch’s eager execution and dynamic control flow, enabling it to capture the exact execution path without requiring a static model graph.

2. Agentic Einsum Converter: This stage translates PyTorch operators into an extended einsum expression Kjolstad et al. (2017); Odemuyiwa et al. (2024)—a generalization of Einstein summation Einstein (1922) that represents tensor computations using index-based notation.

• Representation: This canonical form unifies tensor algebra operations and explicitly exposes tensor iteration spaces and compute patterns, from which SOLAR performs operator analysis and derives FLOP counts and memory traffic.

• Lookup Mechanism: SOLAR maintains a persistent lookup table mapping PyTorch operators to validated einsum conversion functions. For operators already present in the table, the conversion is applied directly.

• Automation: For previously unseen operators, an LLM agent generates a candidate conversion function and validates it by emulating the einsum expression and comparing results with the original PyTorch operator. This enables automated self-correction before the new entry is added to the lookup table.

3. SOL Analyzer: The resulting einsum graph and target hardware specifications are passed to the SOL Analyzer. It computes performance using a roofline model Williams et al. (2009) based on peak compute throughput and memory bandwidth at the target frequency:

![](images/19882366bff03be4e51b1180c127cb53ac5e29a8cb2e6baccebeb8ad3e2a54f1.jpg)

(1)

The analyzer accounts for graph-level fusion and prefetch optimizations. It also supports Orojenesis Huang et al. (2024) to derive tighter bounds by modeling off-chip data movement as a function of on-chip buffer capacity, accounting for the reality that not all tensor data can be staged on-chip for full reuse.

Figure 4 illustrates the SOLAR pipeline on a concrete SOL-ExecBench L1 problem from Jamba-Reasoning-3B which performs fused attention output projection with residual addition. Figure 4(a) depicts the PyTorch code that performs a matmul followed by an elementwise add. The Graph Extractor takes the PyTorch program as input and produces an operator graph with explicit nodes (matmul, add, transpose) and tensor shapes (Figure 4(b)). Next, the LLM-based Einsum Converter maps the operator graph to an extended einsum graph: the matmul maps to a single contraction node ACB,BH→ACH and the projection to an elementwise add ACH,ACH→ACH node (Figure 4(c)). Finally, the SOL Analyzer derives FLOPs and memory traffic from the Einsum graph and generates a roofline bound on a B200 GPU. For this workload, the kernel is compute-bound with a fused memory footprint of about 126 MB and an arithmetic intensity of 427, yielding an SOL runtime of 0.06 ms (Figure 4(d)).

A current limitation of SOLAR is that its analysis is based solely on tensor shapes rather than values. Consequently, it cannot capture value-dependent optimizations such as compression or constant propagation, and may overlook performance gains from structured or repeated data that enable more efficient memory access or algebraic simplifications. Additionally, the SOL bound may not be tight in practice due to hardware variability, such as power capping or thermal throttling.

## 4.3 Metric: SOL Score

We define a new performance metric, the SOL score, denoted by S ∈ [0, 1]. It measures how close a kernel is to the hardware SOL relative to a fixed baseline runtime. Let T denote the runtime of the baseline implementation, T<sub>SOL</sub> the runtime estimated by SOLAR, and T<sub>k</sub> the measured runtime of the candidate kernel. We assume T<sub>b</sub> > T<sub>SOL</sub> and T<sub>k</sub> ≥ T<sub>SOL</sub>, so that the baseline-to-SOL gap is positive. If either assumption is violated in practice, we treat the case as an audit signal and report it for SOLAR bound review and reward-hacking inspection (Section 4.4.1).

The SOL score is defined as

![](images/fc218952dd62e0a6a01428a70a7728de0545aa1dc3156581f80fccce2eac9d8b.jpg)

(2)

which can be written equivalently as

![](images/62b91ad947753dbcb468372d96f6523b552d6a010eed21d1e01c2f612c121abc.jpg)

(3)

The SOL score lies in [0, 1] and has these three anchor properties (also illustrated in Figure 5):

![](images/955a79fca6e3e4f138918d5fab1962e544e9c52d167a43acc18f65f71967b466.jpg)

![](images/702d615b6515a35a6aae7342974c617ce35ee476a7c1bc8217e8d119abe542e2.jpg)  
Figure 5: SOL score as a function of kernel runtime T<sub>k</sub>, shown for T<sub>SOL</sub> = 50 and T<sub>b</sub> = 100. The metric is anchored at S = 1 when T<sub>k</sub> = T<sub>SOL</sub> and at S = 0.5 when T<sub>k</sub> = T<sub>b</sub>, and decays smoothly toward 0 as runtime increases. The curve also highlights the metric’s nonlinearity: the same runtime improvement yields a larger score gain when it occurs closer to the SOL regime.

We design the score to assign the baseline a midpoint score rather than zero so that the metric separates three regimes on a common bounded scale: below-baseline performance (S < 0.5), abovebaseline but sub-SOL performance (0.5 < S < 1), and SOL-level performance (S = 1). In the below-baseline performance region the metric decays smoothly towards zero as runtime increases. The term T<sub>b</sub> − T<sub>SOL</sub> represents the performance headroom between the baseline and the hardware SOL. Accordingly, the SOL score measures how effectively a candidate kernel closes this gap. A score greater than 0.5 indicates that the kernel outperforms the baseline, while a score close to 1 indicates that it approaches hardware-efficient execution. Earlier we assumed T<sub>b</sub> > T<sub>SOL</sub>, but as T<sub>b</sub> → T<sub>SOL</sub>, we consider the problem is solved and do not evaluate new submissions for that problem. We experimented with variations of this formulation that use clip and/or sigmoid to achieve the same objective, but chose this formulation for its simplicity.

To ensure that performance credit is awarded only to functionally correct kernels, we introduce a correctness indicator C ∈ {0, 1} for each problem. A kernel that fails validation is assigned C = 0 and therefore receives zero performance credit, regardless of runtime.

For a benchmark suite with N problems, the overall SOL score is defined as the arithmetic mean of the per-problem scores:

![](images/0b4c223c3195e050001c6e0b805f5866949c24534f9109e49cf6f9aecc323265.jpg)

(4)

We use the arithmetic mean because each per-problem SOL score is already bond to [0, 1] and carries the same interpretation across problems, so averaging preserves that interpretation at the suite level. This formulation extends naturally to a best-of-k setting for agentic systems that generate multiple candidate solutions per problem, although we omit that extension here for brevity.

## 4.4 Evaluation Framework

Solutions are accepted as a JSON specification containing source files, the implementation language, build configuration, target hardware, and an entry-point function. The current evaluator supports Python, Triton, and CUDA/C++ through torch.utils.cpp extension, including implementations built on PTX, CUTLASS, CuTE DSL, cuBLAS, cuDNN, and cuTile.

Each benchmark problem ships with a PyTorch reference implementation that defines the intended semantics and enables correctness checking. This reference is written primarily for portability, readability, and functional coverage and may not offer high performance, so it should be interpreted as a functional specification rather than as a strong software performance baseline. We therefore separate the notions of reference implementation and runtime baseline. To compute the SOL score, we define a scoring baseline T<sub>b</sub> for each problem, which anchors the midpoint of the metric (Section 4.3). The scoring baseline is currently held internal to the benchmark and may be released in a future version. Because the scoring baseline is not fixed to a specific implementation, it may be updated over time as stronger baselines become available, allowing the benchmark to remain a challenging performance target as the state of the art advances. We describe how the current scoring baselines are obtained below in Section 4.5.

For correctness checking, the evaluator first executes the pinned reference to materialize reference outputs, then compares candidate outputs against those references across multiple seeded trials. Validation checks output shape, data type, and basic tensor sanity, rejecting spurious inf/NaN values and degenerate all-zero outputs when the reference is nontrivial. For dense tensor outputs, correctness is defined by a workload-specific tolerance tuple (atol, rtol, matched ratio) stored in workload.jsonl. For BF16/FP32 problems, these thresholds are calibrated offline by repeatedly probing the reference on randomized inputs and applying a 1.25× safety margin to the required absolute tolerance. Specialized evaluators are used for quantized and sampling problems. For quantized kernels, correctness is compared against cuBLAS reference implementations via PyTorch or against an FP32 reference when the former is unavailable.

To measure runtime, we use CUDA events with 10 warmup iterations and 50 timed iterations per trial over 3 trials, with the reported runtime taken as the mean across trials. Before every timed iteration, the harness clears the L2 cache by zeroing a 256 MB device buffer, and it clones tensor arguments so each run starts from fresh inputs with new addresses rather than reusing state from previous iterations. Benchmarking on a given GPU is serialized, and clocks are locked through nvidia-smi at hardware-specific frequencies (1,500 MHz for B200) to improve reproducibility. The harness reports absolute runtime in milliseconds, and relative metrics such as speedup and SOL score are computed later against the scoring baseline defined for a given benchmark release.

Each submitted solution is compiled and executed in a dedicated subprocess, isolating evaluator state so one solution cannot affect later ones. This design also supports round-robin scheduling across multiple GPUs and allows failed workers to be discarded and relaunched without interrupting the rest of the benchmark. A 300-second timeout guards against hangs and infinite loops, and reference outputs together with reference timing data are prepared separately and transferred to solution workers through IPC.

## 4.4.1 Reward Hacking and Mitigation

Prior work observed that agentic optimization systems are susceptible to reward hacking, where the optimizer exploits loopholes in the evaluation environment to maximize its score without actually solving the underlying task correctly Lange et al. (2025). In the context of GPU kernel optimization, we also observed agents generating code that bypassed timing mechanisms, violated benchmark constraints, or exploited the repetitive nature of the timing loop to achieve artificially low runtimes. We categorize these exploits into three main families: concurrency exploit, state caching, and environment manipulation, as summarized in Table 3.

Concurrency exploit involves hiding execution time from the benchmark’s torch.cuda.Event timers. Agents achieved this by dispatching work to background Python threads, launching kernels on unrecorded non-default CUDA streams, or exploiting torch.jit.fork for unintended parallel execution. A particularly sophisticated variant exploited the capturing mechanics of torch.cuda.CUDAGraph and streams where torch.cuda.CUDAGraph creates its own implicit, non-default stream for the capture region, which non-PyTorch libraries are not explicitly aware of. In one CuTe DSL instance, the implicit stream was not forwarded to the CuTe kernel, so the initial capture pass executed the math and populated the output buffer with correct results to pass the correctness check, but subsequent graph replays during the timing loop were devoid of work and executed in negligible time.

State caching exploits take advantage of the benchmark’s repetitive timing loop. Agents would compute the result once during the initial correctness check, cache the output (or intermediate variables)

Table 3: Observed reward hacking strategies by agentic kernel optimizers and corresponding mitigations.  
![](images/977f7d6d3fcba7d1eb804fffb1ea46a7cc80b2abd54cb3bfe1f7973669d70ab5.jpg)

in global dictionaries, and simply copy the cached tensor during timed iterations. Similarly, agents employed lazy evaluation by returning FakeTensor objects that only executed computation during the eq correctness check, effectively skipping all math during the timing phase. Finally, environment manipulation included monkey-patching critical timing functions (e.g., Event.elapsed time) and downgrading compute precision (e.g., executing an FP32 problem in FP16 and upcasting the result). For the latter, we recognize that some problems don’t require the full 32-bits of precision, so downcasting is permitted when input and output data types match and tight tolerances are met. We have also observed some non-PyTorch submissions that embedded pre-compiled machine code (ELF binaries or cubin blobs) as base64-encoded strings and loaded them at runtime via ctypes or cuModuleLoadData to bypass source-level review entirely.

To ensure the integrity of the SOL score, we implement an evaluation sandbox to resist accepting common reward-hacking strategies used by agentic optimizers. It checks for tampering with the timing path, detects work hidden on side CUDA streams, clones inputs between runs to reduce state leakage, and combines strict output validation with subprocess isolation so invalid or adversarial solutions do not receive performance credit. The evaluation framework enforces strict dynamic checks: it monitors active thread counts, asserts that outputs are fully materialized torch.Tensor objects (rejecting subclasses), injects torch.cuda.synchronize() passes to catch hidden asynchronous work, and verifies the memory addresses of critical timing functions to prevent monkey-patching. To mitigate state caching, we run multiple correctness trials with randomized inputs and explicitly clear a 256 MB GPU L2 cache buffer before every timed iteration. To prevent agents from using memory addresses (data ptr) as cache keys during the timing loop, the harness implements a fresh memory allocator that shifts memory pointers by 256 B every iteration in a pre-allocated buffer. For more complex or obfuscated patterns such as dynamic stream creation, semantic caching, or unauthorized file I/O, we employ an LLM-as-a-judge to perform static code analysis on all submissions prior to execution. Finally, because novel exploits occasionally emerge, all candidate solutions proposed for adoption as a new scoring baseline undergo manual human review before acceptance into the dataset.

To reduce reward hacking, the current evaluator makes two conservative design choices: it disallows CUDA streams and relies on PyTorch’s default memory allocator. Disallowing CUDA streams helps prevent hidden-work exploits, but it also means user kernels may not fully reproduce the torch.compile-based scoring baseline. We view this as an acceptable restriction for high-compute LLM kernels that typically benefit little from multi-stream execution. Relying on PyTorch’s eager allocator likewise improves practicality and readability, but it can disadvantage non-PyTorch kernels on subgraphs with a >50% VRAM watermark because PyTorch may reserve and retain freed memory for reuse. Future versions could improve these safeguards through better stream-checking methods, allocator controls such as PYTORCH NO CUDA MEMORY CACHING, custom PyTorch builds, or a non-

PyTorch reference implementation with a static allocator, though each option introduces its own compatibility, readability, or maintenance tradeoffs.

## 4.5 Scoring Baselines

Each problem in SOL-ExecBench has a scoring baseline (not released) that is different from the reference program and is a higher-performance implementation that serves as the runtime anchor T<sub>b</sub> in the SOL score (Equation 2). Any solution faster than T<sub>b</sub> will receive a score above 0.5, reflecting an improvement over an already-optimized kernel.

These baseline implementations were generated using an agentic kernel optimization system. The optimizer operates in a turn-based, multi-agent manner. For each problem, we launch multiple agents independently to optimize the runtime of the provided PyTorch reference implementation under a fixed time and cost budget. After each round, we collect all valid submitted solutions and expose them to the next cohort of agents, which may use any of these correct candidates as a starting point or reference for further optimization in the next round.

Each agent is restricted to producing solutions using only PyTorch and standard Python packages. Agents are equipped with tools and skills to submit their implementations to the remote evaluation sandbox described in Section 4.4 for correctness checking and benchmarking. In addition, every submitted solution is inspected by an LLM-based judge to detect requirement violations and common cheating patterns.

Only solutions that compile successfully, pass correctness verification, and satisfy the our reward hacking mitigation mechanism are retained as the baseline candidates. After the prescribed number of rounds, we aggregate all valid candidates produced by all agents across all turns and select the fastest kernel for each problem as the final optimized baseline.

## 5 Experiments

## 5.1 Experimental Setup

All experiments are conducted on NVIDIA DGX B200 nodes equipped with 8× NVIDIA Blackwell B200 GPUs, each providing 192 GB of HBM3e memory and 8 TB/s of memory bandwidth NVIDIA (2024b,c). The software stack is built on an NVIDIA-provided Docker image with CUDA 13.1.1, cuDNN 9.17.1, PyTorch 2.9.0, and NVIDIA driver 580.95. Each benchmark run uses a single GPU with SM clocks locked at 1,500 MHz via nvidia-smi to reduce frequency-scaling noise, matching the evaluation harness described in Section 4.4.

## 5.2 SOL Score versus Speedup

A natural way to evaluate a kernel optimization so far has been to measure its speedup over a PyTorch reference. We begin by evaluating an agent-generated solutions using this metric. Figure 6 plots this speedup (T<sub>ref</sub> /T<sub>k</sub>, x-axis) against how far the solution still remains from the SOL bound (T<sub>k</sub>/T<sub>SOL</sub>, yaxis) for every workload (k) in SOL-ExecBench. Results show that the two quantities are uncorrelated (r=0.10 on a log–log scale), i.e., a solution can be 10× faster than PyTorch yet remain > 10× away from the hardware SOL. A speedup-only metric will rank such a kernel favorably, obscuring the substantial optimization headroom that still remains before reaching the SOL bound. We also note that some workloads also fall below the x=1.0 line, indicating slowdowns relative to the reference implementation.

Figure 7 plots the same axes but colors each workload by its SOL score S (calculated according to Equation 2) and overlays iso-score contour lines. High-S points (blue, S ≥ 0.9) cluster toward the lower-right corner, with high speedup and small SOL distance, while low-S points (red, S < 0.4) sit in the upper-left. Solutions in the upper-right quadrant, which are fast relative to PyTorch but still far from SOL, receive only intermediate scores (S ≈ 0.5–0.7). The iso-score lines further show that S is not simply a relabeling of speedup. The same speedup maps to very different SOL scores depending on SOL distance. This confirms that S integrates both axes of optimization into a single bounded value that neither speedup nor SOL proximity can capture alone.

![](images/0b38c340507b7c5194144925ac7754a5d3bf1e3e3c68e81523120ab19f9d20b0.jpg)  
Figure 6: Speedup over the PyTorch reference (x-axis) versus distance from the hardware SOL (y-axis) for every problem and workload is shown here.

![](images/dbd20f61e5d0b1a550d203bf41f92e3f2884c58c9c2fe058043d9b5a9e073132.jpg)  
Figure 7: SOL score landscape is shown here. Each point is colored by its SOL-score band and iso-score contour lines (S=0.5, 0.7, 0.9) are overlaid. The axes are the same as Figure 6.

![](images/62b9dfa95d081762a801761c1d643791ef8afa659267404948c4da6f48563a22.jpg)  
(a) SOL score vs. fraction of headroom reclaimed, colored by category is shown here.

![](images/963be6c70ae66a72dc546d8052ee8449cafe28bec290b64ebab14a02046338bc.jpg)  
(b) Speedup vs. fraction of headroom reclaimed, colored by SOL score is shown here.  
Figure 8: Validating the SOL score against fraction of headroom reclaimed. Both panels share the same x-axis.

To validate that the SOL score faithfully reflects optimization quality, we compare it against fraction of headroom reclaimed, calculated as (T<sub>ref</sub> − T<sub>k</sub>)/(T<sub>ref</sub> − T<sub>SOL</sub>), which measures how much of the total optimization gap the solution closed. Figure 8(a) plots the SOL score against this fraction directly. The two are nearly perfectly correlated (Pearson r=0.981), confirming that S faithfully tracks it. The curve lies above the y=x diagonal because the score formulation guarantees S ≥ 0.5 whenever the solution matches or beats the reference.

Figure 8(b) plots speedup (y-axis) against the same x-axis (fraction of headroom reclaimed). Here each point is colored by its SOL score from red (S≈0) through yellow to dark green (S≈1). The key observation is the horizontal spread: at a fixed speedup of 3×, headroom reclaimed ranges from below 0.2 to above 0.8, depending on how far the reference was from the SOL bound to begin with. This reinforces why speedup alone is insufficient as a predictor of optimization quality. The color gradient shows that the SOL score tracks the reclaimed headroom well, i.e., darker green (higher S) consistently aligns with higher headroom reclaimed, regardless of the speedup value. Quantitatively, speedup correlates with headroom reclaimed at r=0.81, whereas the SOL score achieves r=0.98. The stronger correlation of the SOL score confirms the value of incorporating the hardware SOL bound into the evaluation metric, as S uncovers the blind spot that speedup alone leaves.

![](images/fa648e02ecb64f98085c16d12839e11e69249a41d172153066fceda39bc572ca.jpg)  
Figure 9: Distribution of reward hacking exploits detected across agent submissions by exploit type and problem category is shown here.

## 5.3 Mitigating Reward Hacking

As mentioned earlier we observed reward hacking as the agent solved the problems. Figure 9 shows the distribution of the exploits detected across all agent submissions, broken down by exploit types, as defined in Table 3. Precision downgrade is the most common exploit (259 kernels, 6.4% of all submissions), where agents compute in a lower precision (e.g., FP16 instead of FP32) and upcast the result to pass validation. Monkey patching (134, 3.3%) overrides critical timing functions such as Event.elapsed time to report artificially low runtimes. Stream injection (100, 2.5%) hides work on unsynchronized CUDA streams that the timing harness does not record. Reuse of cached output (67, 1.6%) caches correct results during the correctness check and replays them during the timing loop. Less frequent but still present are JIT forking, one-time correctness, and thread injection. In total, 589 submissions (14.5%) were flagged and rejected by the combination of dynamic runtime checks and LLM-based static analysis described in Section 4.4.1. These results underscore the importance of robust evaluation infrastructure when using agentic systems for kernel optimization.

## 5.4 Scoring Baseline

Figure 10 characterizes the agent-generated solutions across all four benchmark categories. The score distributions (Figure 10(a)) show median SOL scores of 0.688 for L1, 0.761 for L2, 0.757 for Quant, and 0.789 for FlashInfer-Bench, with an overall median of 0.732. These median score lies comfortably above the S=0.5 midpoint for each category, confirming that our agent solutions consistently outperform the PyTorch reference. At the same time, scores seldom reach S=1, i.e., optimization headroom remains in every category. L1 shows the broadest spread, reflecting the diversity of single-operation kernel types, while FlashInfer-Bench clusters highest, reflecting the focused optimization effort in the FlashInfer production suite.

Figure 10(b) directly compares the distance of the PyTorch reference and the agent solution from the SOL bound. Nearly all workloads fall below the diagonal, confirming that the solutions are closer to the SOL bound. The median reduction in SOL distance is 2.0× for L1, 2.7× for L2, 2.9× for Quant, and 3.4× for Fl-Bench. Because the agent solution represents the current optimization frontier, solutions that outperform the reference implementation will serve as the scoring baseline T in the SOL score formula (Equation 2) for future evaluations. This scoring baseline can be updated over time as stronger solutions emerge.

## 6 Conclusion

We presented SOL-ExecBench, a benchmark for GPU kernel optimization built around hardware Speed-of-Light (SOL) targets. SOL-ExecBench includes 235 problems assembled from 124 frontier and emerging AI models, covering post-training and inference workloads, modern precision formats, and kernels that benefit from new hardware features. We also introduce SOLAR, a pipeline that analytically derives hardware-grounded SOL bounds from PyTorch programs, giving each problem a stable target beyond a software baseline. We introduce the SOL score, a new metric for generated kernels. Unlike speedup alone, it reveals the remaining headroom by measuring how much of the gap between a scoring baseline and the SOL bound a candidate kernel closes. We also provide a robust evaluation harness with defenses against reward hacking, informed by the failure modes we observed from agent-generated solutions. Our agentic optimizer produces strong baseline solutions, with the overall median SOL score of 0.732, which shows that substantial optimization headroom still remains. Looking ahead, we expect SOL-ExecBench to evolve with new workloads, stronger baselines, and community submissions so that it remains aligned with the frontier of models, kernels, and hardware.

![](images/f3dd25a23c9f5e203ea92debdab6090a0f602afb1f1bf9c02325faf753343a56.jpg)

(a) SOL score distribution per category is shown here. Histograms (top) with median (solid) and mean (dashed) lines; box plots (bottom). The S=0.5 line marks parity with the PyTorch reference.  
![](images/3170a0af5fabb3ec3c51fa86f61736f2be11d18512d174bdbbc3e7ca33ee4cbe.jpg)  
(b) Distance from the hardware SOL for the PyTorch reference versus the agent solution is shown here.  
Figure 10: Agent solution (new scoring baseline) results are analyzed here.

## Acknowledgments and Disclosure of Funding

We thank Aditya Alturi, Ali Hassani, Avery Huang, Po-Han Huang, Lucas Liebenwein, Alessandro Morari, Przemek Tredak, and Scott Yokim, Subhash Ranjan, Michael Fu, Matt Frazier for their contributions to this work. GenAI tools were used to create content in this paper.

## References

AI21 Labs. 2024. Jamba: A Hybrid Transformer-Mamba Language Model. arXiv:2403.19887

Jonathan Bentz. 2025. Simplify GPU Programming with NVIDIA CUDA Tile in Python. NVIDIA Technical Blog. https://developer.nvidia.com/blog/ simplify-gpu-programming-with-nvidia-cuda-tile-in-python/

Mark Chen, Jerry Tworek, Heewoo Jun, Qiming Yuan, Henrique Ponde de Oliveira Pinto, Jared Kaplan, Harri Edwards, Yuri Burda, Nicholas Joseph, Greg Brockman, et al. 2021. Evaluating Large Language Models Trained on Code. arXiv:2107.03374

Terry Chen, Bing Xu, and Kirthi Devleker. 2025. Automating GPU Kernel Generation with DeepSeek-R1 and Inference-Time Scaling. NVIDIA Technical Blog. https://developer.nvidia.com/blog/ automating-gpu-kernel-generation-with-deepseek-r1-and-inference-time-scaling/

Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, and Christopher Re. 2022. FlashAttention: Fast ´ and Memory-Efficient Exact Attention with IO-Awareness. In Advances in Neural Information Processing Systems (NeurIPS).

Tri Dao and Albert Gu. 2024. Transformers are SSMs: Generalized Models and Efficient Algorithms Through Structured State Space Duality. arXiv:2405.21060

DeepSeek-AI. 2024. DeepSeek-V3 Technical Report. arXiv:2412.19437

Albert Einstein. 1922. The general theory of relativity. In The meaning of relativity. Springer, 54–75.

Qijing Huang, Po-An Tsai, Joel S. Emer, and Angshuman Parashar. 2024. Mind the Gap: Attainable Data Movement and Operational Intensity Bounds for Tensor Algorithms. In Proceedings of the 51st Annual International Symposium on Computer Architecture (ISCA). Best Paper Nominee.

Fredrik Kjolstad, Shoaib Kamil, Stephen Chou, David Lugato, and Saman Amarasinghe. 2017. The tensor algebra compiler. Proceedings of the ACM on Programming Languages 1, OOPSLA (2017), 1–29.

Mert Kurttutan. 2022. torchview: Visualize PyTorch Models. https://github.com/ mert-kurttutan/torchview

Robert Tjarko Lange, Qi Sun, Aaditya Prasad, Maxence Faldor, Yujin Tang, and David Ha. 2025. Towards Robust Agentic CUDA Kernel Benchmarking, Verification, and Optimization. arXiv:2509.14279 [cs.SE] https://arxiv.org/abs/2509.14279

Jianling Li, Shangzhan Li, Zhenye Gao, Qi Shi, Yuxuan Li, Zefan Wang, Jiacheng Huang, Haojie Wang, Jianrong Wang, Xu Han, Zhiyuan Liu, and Maosong Sun. 2025. TritonBench: Benchmarking Large Language Model Capabilities for Generating Triton Operators. In Findings of the Association for Computational Linguistics (ACL).

Raymond Li, Loubna Ben Allal, Yangtian Zi, Niklas Muennighoff, Denis Kocetkov, Chenghao Mou, Marc Marone, Christopher Akiki, Jia Li, Jenny Chim, et al. 2023. StarCoder: May the Source Be with You!. In Transactions on Machine Learning Research.

Anton Lozhkov, Raymond Li, Loubna Ben Allal, Federico Cassano, Joel Lamy-Poirier, Nouamane Tazi, Ao Tang, Dmytro Pykhtar, Jiawei Liu, Yuxiang Wei, et al. 2024. StarCoder 2 and The Stack v2: The Next Generation. arXiv:2402.19173

NVIDIA. 2024a. CUTLASS: CUDA Templates for Linear Algebra Subroutines. https://github. com/NVIDIA/cutlass

NVIDIA. 2024b. NVIDIA B200 GPU Data Sheet. https://www.nvidia.com/en-us/ data-center/b200/

NVIDIA. 2024c. NVIDIA Blackwell Architecture Technical Brief. https://www.nvidia.com/ en-us/data-center/technologies/blackwell-architecture/

NVIDIA. 2025a. ComputeEval: Evaluating LLM Capabilities for CUDA Programming. https: //github.com/NVIDIA/ComputeEval

NVIDIA. 2025b. Nemotron-H: A Family of Hybrid Transformer-SSM Models. https:// huggingface.co/nvidia/Nemotron-H-47B-Base-8K

Toluwanimi O. Odemuyiwa, Joel S. Emer, and John D. Owens. 2024. The EDGE Language: Extended General Einsums for Graph Algorithms. arXiv:2404.11591 [cs.DS] https://arxiv.org/abs/ 2404.11591

Anne Ouyang, Simon Guo, Simran Arora, Alex L. Zhang, William Hu, Christopher Re, and Azalia´ Mirhoseini. 2025. KernelBench: Can LLMs Write Efficient GPU Kernels?. In Proceedings of the 42nd International Conference on Machine Learning (ICML). https://github.com/ ScalingIntelligence/KernelBench Also Best Paper at DL4C and SSI-FM workshops at ICLR 2025.

Bo Peng, Eric Alcaide, Quentin Anthony, Alon Albalak, Samuel Arcadinho, Stella Biderman, Huanqi Cao, Xin Cheng, Michael Chung, Matteo Grella, et al. 2023. RWKV: Reinventing RNNs for the Transformer Era. arXiv:2305.13048

Mark Saroufim, Sahan Paliskara, Jiannan Wang, Bert Maher, Manuel Candales, Shahin Sefati, and Laura Wang. 2025. BackendBench: Benchmarking LLM-Generated Triton Kernels for PyTorch Backend Operators. https://github.com/pytorch/BackendBench

Philippe Tillet, Hsiang-Tsung Kung, and David D. Cox. 2019. Triton: An Intermediate Language and Compiler for Tiled Neural Network Computations. In Proceedings of the 3rd ACM SIGPLAN International Workshop on Machine Learning and Programming Languages. 10–19.

Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, and Illia Polosukhin. 2017. Attention Is All You Need. In Advances in Neural Information Processing Systems (NeurIPS). 5998–6008.

Samuel Williams, Andrew Waterman, and David Patterson. 2009. Roofline: An Insightful Visual Performance Model for Multicore Architectures. Commun. ACM 52, 4 (2009), 65–76.

Shanli Xing, Yiyan Zhai, Alexander Jiang, Yixin Dong, Yong Wu, Zihao Ye, Charlie Ruan, Yingyi Huang, Yineng Zhang, Liangsheng Yin, Aksara Bayyapu, Luis Ceze, and Tianqi Chen. 2026. FlashInfer-Bench: Building the Virtuous Cycle for AI-driven LLM Systems. arXiv:2601.00227 https://github.com/flashinfer-ai/flashinfer-bench MLSys 2026 competition.

Bing Xu, Terry Chen, Fengzhe Zhou, Tianqi Chen, Yangqing Jia, Vinod Grover, Haicheng Wu, Wei Liu, Craig Wittenbrink, Wen-mei Hwu, et al. 2026. VibeTensor: System Software for Deep Learning, Fully Generated by AI Agents. arXiv preprint arXiv:2601.16238 (2026).

Songlin Yang, Jan Kautz, and Ali Hatamizadeh. 2024. Gated Delta Networks: Improving Mamba2 with Delta Rule. arXiv:2412.06464

Jiace Zhu, Wentao Chen, Qi Fan, Zhixing Ren, Junying Wu, Xing Zhe Chai, Chotiwit Rungrueangwutthinon, Yehan Ma, and An Zou. 2026. CUDABench: Benchmarking LLMs for Text-to-CUDA Generation. arXiv:2603.02236