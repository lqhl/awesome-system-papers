![](images/0c889d166afc25eadaf0cceec23c6870c0eb63b568518e9e203cee3295ba8ef5.jpg)

# ResearchClawBench: A Benchmark for End-to-End Autonomous Scientific Research

Shanghai Artificial Intelligence Laboratory

![](images/632fa885ed8049ec5596180df0ab075132597bdd71a8d91c62e502b32aaf2a50.jpg)  
(a)

![](images/1ba01c51a54aafed1bbc61265af718c5b62ddb473bbc8d8fa9d7d072e0e863bf.jpg)  
(b)  
Figure 1: Overview of ResearchClawBench. (a) ResearchClawBench spans 10 domains and 40 end-to-end tasks, covering diverse scientific questions and data modalities. (b) Overall scores of agents and LLMs; the 50-point line marks target-paper-level re-discovery, and scores above it indicate the discovery regime.

## Abstract:

AI coding agents are increasingly used for scientific work, but their end-to-end autonomous research capability remains dificult to verify. We present ResearchClawBench, a benchmark for evaluating autonomous scientific research across 40 tasks from 10 scientific domains. Each task is grounded in a real published paper, provides related literature and raw data, and hides the target paper during evaluation. Expert-curated multimodal rubrics decompose the target scientific artifacts into weighted criteria, enabling evaluation of target-paper-level re-discovery while leaving room for new discovery. We evaluate seven autonomous research (auto-research) agents under a unified protocol and seventeen native LLMs through the lightweight ResearchHarness. Current systems remain far from reliable re-discovery: the strongest autonomous agent, Claude Code, averages 21.5, and the strongest ResearchHarness LLM, Claude-Opus-4.7, averages 20.7, with an LLM frontier mean of only 26.5. Error analysis shows that failures concentrate in experimental protocol mismatch, evidence mismatch, and missing scientific core. ResearchClawBench provides a reproducible evaluation frontier for measuring progress toward autonomous scientific research.

Page https://internscience.github.io/ResearchClawBench-Home/

Code https://github.com/InternScience/ResearchClawBench

Data https://huggingface.co/datasets/InternScience/ResearchClawBench

## 1. Introduction

Automated scientific research [Douglas, 2025] is emerging as an important frontier in AI. Coding agents such as OpenClaw, Claude Code, and Codex CLI are increasingly marketed as tools that can “autonomously conduct research,” yet there is no principled way to assess whether such claims hold up under scrutiny. This calls for a benchmark that captures the full research process and can reliably evaluate open-ended scientific outputs.

Existing benchmarks cover adjacent but incomplete settings: scientific question answering and reasoning [Welbl et al., 2017, Rein et al., 2023], interactive scientific environments [Wang et al., 2022, Jansen et al., 2024], and automated research or paper reproduction [Lu et al., 2024, Starace et al., 2025]. However, none asks AI systems to start from raw experimental data, produce complete research outputs, and evaluate them with verifiable anchors. This gap makes it dificult to objectively measure AI autonomous research capability or compare progress across systems. Designing such a benchmark raises several non-trivial challenges. First, the task itself must be scientifically meaningful and aligned with real research scenarios. Second, scientific outputs are open-ended: a research report is dificult to assess by exact-match or simple unit tests, while LLM-as-judge evaluation can introduce bias [Li et al., 2025]. Third, scientific research is heterogeneous in data modalities, analytical methods, and evidence standards, so narrow coverage can overfit systems to limited skills.

We present ResearchClawBench (RCBench) to address these challenges. To ensure task significance, we start from real published papers: domain experts select target papers with clear scientific questions, accessible raw data, and practical research value, and convert them into executable task descriptions. To evaluate open-ended scientific outputs, we keep the target paper hidden on the evaluation side and construct expert-curated rubrics around it, decomposing expected outputs into verifiable and weighted sub-criteria. To support task diversity, RCBench spans 10 scientific domains, including Astronomy, Chemistry, Earth Science, Energy Science, Information Science, Life Science, Material Science, Mathematics, Neuroscience, and Physics, with tasks covering diagnostic analysis and metric optimization.

Building on this benchmark, we systematically evaluate 7 autonomous research agents on RCBench under a unified evaluation protocol. Our scoring is anchored at 50 points: a score at this level means the system’s output matches the target paper, while scores above it indicate discoveries. Results show that the strongest autonomous agent, Claude Code, averages 21.5; even when taking the best autonomous-agent result for each task, the frontier mean is only 24.6. These results indicate that current autonomous research agents remain far from reliable target-paper-level re-discovery.

To enable comparison with models that lack a full agent scafold [Liu et al., 2025b], we introduce ResearchHarness and use it to evaluate seventeen native LLM baselines. Claude-Opus-4.7 averages 20.7, and the LLM frontier mean is 26.5, showing that native LLMs also struggle to complete stable end-to-end re-discovery.

Through real scientific discovery tasks, end-to-end pipeline evaluation, and fine-grained rubrics, ResearchClawBench addresses a critical gap in the evaluation of autonomous scientific research.

We summarize our contributions as follows:

• ResearchClawBench: 40 real scientific discovery tasks with expert-annotated rubrics across 10 domains and diverse scenarios.

• ResearchHarness: a unified lightweight tool-use evaluation harness for LLM baselines.

• Unified evaluation: a systematic assessment of seven autonomous research agents and seventeen native LLM baselines, quantifying the gap between current AI research systems and target-paperlevel re-discovery.

## 2. Related Work

## 2.1. Scientific Capability and Scientific Task Benchmarks

Existing evaluations of AI scientific capability include scientific question answering, high-dificulty scientific reasoning, and domain-specific scientific benchmarks. SciQ [Welbl et al., 2017], GPQA [Rein et al., 2023], MMLU [Wang et al., 2024b], and Humanity’s Last Exam [Phan et al., 2025] mainly use question-answering, exam-style, or expert-level problems to measure scientific knowledge, factual understanding, and static reasoning. SciBench [Wang et al., 2023] further targets university-level mathematics, physics, and chemistry problems. ATLAS [Liu et al., 2025a] extends this line toward high-dificulty, multidisciplinary frontier scientific reasoning. Domain-specific benchmarks [Anjum et al., 2025] are also growing: PHYSICS evaluates open-ended university-level physics reasoning; ChemBench [Walker et al., 2010] and ChemLLMBench [Guo et al., 2023] focus on chemical knowledge, reaction understanding, molecular representation, and safety; EarthSE [Xu et al., 2025a] builds a multi-level evaluation for Earth science from foundational knowledge to open-ended exploration; and MSEarth [Zhao et al., 2025a] uses high-quality scientific publications for graduate-level Earth science assessment. These benchmarks are useful for scientific knowledge and domain reasoning, but they do not cover the full research loop required by autonomous scientific agents.

From the perspective of RCBench, these benchmarks remain centered on local scientific tasks, such as answering scientific questions, interpreting figures, retrieving database entries, or solving short domain-specific problems. Even when tasks are grounded in scientific contexts, they usually do not require a system to conduct literature review, process raw data, design and execute experiments, generate figures, and write a research report around the same open scientific question. They therefore evaluate scientific knowledge, domain reasoning, multimodal understanding, and other research subskills, but cannot determine whether AI systems can complete an independent scientific process that reaches discovery-level outcomes.

## 2.2. Research-Agent Benchmarks and Autonomous Research Systems

Compared with static scientific benchmarks, another line of work evaluates agents in dynamic researchlike settings, including scientific coding, paper reproduction, and autonomous scientific discovery. SciCode [Tian et al., 2024] evaluates code generation for realistic scientific problems, while Sci-DataCopilot [Rao et al., 2026] focuses on agentic preparation of raw scientific data for discovery workflows. MLAgentBench [Huang et al., 2023] places language agents in machine learning experimentation workflows and evaluates file operations, code execution, and feedback-driven iteration. MLE-bench [Chan et al., 2025] further uses Kaggle competitions to evaluate end-to-end machine learning engineering, and MLGym [Nathani et al., 2025] organizes machine learning research as a gym-style environment emphasizing experimental iteration, result analysis, and strategy adjustment. In paper reproduction, PaperBench [Starace et al., 2025] requires agents to implement methods and run experiments given a target paper, and evaluates whether reproduced experiments, results, and writing artifacts align with the original paper through hierarchical rubrics. CORE-Bench [Siegel et al., 2024] evaluates computational reproducibility from provided paper code and data, while ReproduceBench [Zhao et al., 2025b] studies automatic generation of executable experiment code from papers and their context. At the scientific-discovery level, ScienceWorld [Wang et al., 2022] and DiscoveryWorld [Jansen et al., 2024] place scientific tasks in interactive environments, requiring agents to act, observe, form hypotheses, design experiments, and analyze results in grounded text environments or virtual scientific worlds. ScienceAgentBench [Chen et al., 2025] extracts data-driven scientific discovery tasks from peer-reviewed papers, making evaluation closer to data-analysis workflows in real papers. SGI-Bench [Xu et al., 2025b] probes scientific general intelligence through scientist-aligned workflows spanning research, idea generation, experimentation, and analysis. AIRS-Bench [Lupidi et al., 2026] and MLR-Bench [Chen et al., 2026] target open-ended AI research or the full research lifecycle, further evaluating problem formulation, experimental progress, and result synthesis in open research settings. These works move scientific evaluation from static answers toward environment-based interaction. Beyond benchmarks, system-level eforts such as The AI Scientist [Lu et al., 2024], AI Co-Scientist [Gottweis et al., 2025], AI-Researcher [Tang et al., 2025], and InternAgent-1.5 [Feng et al., 2026] show the potential of LLM agents in automated paper generation, scientist-in-the-loop hypothesis evolution, long-horizon autonomous scientific discovery, and autonomous AI research.

Table 1: Comparison between ResearchClawBench and existing scientific or research-agent benchmarks. We compare grounding in real papers, raw data, executable interaction, end-to-end reports, broad domains, and open research scope; the Domains column reports the number of broad disciplinary fields rather than task themes or ML subareas. Green <sup>✓</sup>indicates yes, yellow △partial support, and red ×means no.  
![](images/ab8b572b2125b1e148d43a84d35c863fe992d24b7e6469f7b04ca9b4bf022e93.jpg)

These works share RCBench’s motivation of evaluating end-to-end scientific discovery in realistic research settings, but important gaps remain. ScienceWorld and DiscoveryWorld abstract real tasks into simulated worlds. SciCode, ScienceAgentBench, and SciDataCopilot focus more on local capabilities such as scientific coding, data analysis, or data preparation. MLE-bench, MLGym, and MLAgentBench are concentrated in machine learning settings, where scientific domains and evidence types remain limited. PaperBench, CORE-Bench, and AutoReproduce/ReproduceBench all focus on paper reproduction or computational reproducibility, but their central goal is reproduction around already given or exposed papers and code. SGI-Bench, AIRS-Bench, and MLR-Bench target scientistaligned workflows, open-ended AI research, or the full research lifecycle, but their main scenarios still emphasize workflow-capability measurement or AI/ML research, leaving a gap to broader naturalscience tasks, data modalities, and evidence standards. System-level agents such as The AI Scientist, AI Co-Scientist, AI-Researcher, and InternAgent-1.5 further motivate the need for a system-agnostic benchmark that can compare diferent autonomous research systems. In contrast, RCBench builds real research tasks from high-quality scientific papers, requires models to perform re-discovery under a hidden-target setting, and directly evaluates end-to-end autonomous scientific discovery while preserving room for future discovery-oriented studies across broader scientific domains and data types.

## 3. ResearchClawBench

We introduce ResearchClawBench. It has three core features. First, tasks are derived from scientific work and provide references and raw data. Second, tasks have research value: we prioritize work with well-defined questions, accessible data, and academic significance. Third, the benchmark builds rubrics around hidden target papers, converting open-ended outputs into verifiable signals.

![](images/d592cd230293827e5064e69486ff89c4184ebfc061f013dc5cd0e7323a08626a.jpg)  
Figure 2 | Overall framework of ResearchClawBench. Real papers, related literature, and raw data are converted into executable research task packages; agents and ResearchHarness LLMs interact with the same research gym, and their outputs are evaluated against rubric-critical scientific artifacts and supplemental quality dimensions.

## 3.1. Task Components

In ResearchClawBench, a task is denoted as

![](images/6293d149c181dc7655836552a3cd604d55529a67c4065db52ddbe90f485344e1.jpg)

where <sup>??</sup> is the task description, L is the related literature, D is the raw data, <sup>??</sup> is the hidden target paper, and A is the evaluation artifacts constructed around the target paper. Given task <sup>??</sup> and executable environment E, the system needs to generate

![](images/30cab8a8264b6e95c2061f93e001325d40b3ba9fce5dee2979e887d3cad25311.jpg)

where <sup>??</sup> denotes the experimental code and execution process, <sup>??</sup> denotes intermediate results, figures, and output files, and <sup>??</sup> denotes the final research report. The benchmark determines whether the system can generate high-quality research products based on (<sup>??,</sup> L<sup>,</sup> D), and whether those products reach or surpass the target paper <sup>??</sup> . A concrete task and its main components are shown in Table 2.

## 3.2. Data Construction

RCBench does not design merely “research-like” tasks. Instead, it preserves the structure of real scientific tasks [Zhou et al., 2023] as much as possible. It is built from high-quality published papers, but the target paper is not exposed to the evaluated system, and the system must independently conduct re-discovery from the task description, related literature, and raw data. RCBench currently contains 40 tasks across 10 scientific domains (Table 3).

Table 2 | A simplified task example from Astronomy\_000. Details are in Appx. B.  
![](images/f1516ef72dad095c954934f5b3d968f398dc4ebb2d3b2a9870ed3515f80150da.jpg)

Task construction is performed by domain experts as illustrated in Figure 3. Experts screen papers with clear questions, accessible data, and high research value. Here, research value includes scientific, economic, ecological, medical, and other dimensions, with the goal of ensuring that the benchmark evaluates problems that are themselves worth studying. Experts then extract the core question and rewrite it into an executable task description. They then organize related literature and raw data, construct rubrics from key target-paper artifacts, and package the materials into standardized tasks. Finally, experts cross-check tasks, fix issues, and filter unsuitable samples.

## 3.3. Evaluation Harness for LLM baselines: ResearchHarness

Table 3 | Task scenarios in RCBench.  
![](images/9ad27d8477bcd5f2329bf67214aca4908389d3fb690fbd50dfa6d3499a783901.jpg)

ResearchHarness is a lightweight tool-using harness that enables native LLMs to participate in

![](images/56798889ed3a62166fd9915d2107aecc64e74b4d1fa91973d1ca164cc9cb382e.jpg)  
Figure 3 | Data construction of RCBench. Experts select target papers, extract questions, collect literature and raw data, build rubrics and evaluation artifacts, package standardized tasks, and conduct cross-expert validation.

Table 4 | ResearchHarness tool surface. Tools are grouped into web and retrieval, files, and execution.  
![](images/812ea41e3b52fea62d2af15471c1011390b825fd325994c9bd6ebef555a84f36.jpg)

ResearchClawBench. By keeping the scafold small, ResearchHarness makes the evaluation closer to the model’s own capability and easier to extend. The harness follows a concise ReAct-style loop and obtains tool-use capability through OpenAI-compatible APIs and native tool calling.

As shown in Table 4, ResearchHarness provides three tool categories. Web tools support search and web access, with search via the Serper API and webpage fetching via Jina Reader. Local file tools support workspace operations, including discovering files, reading text, inspecting images, and extracting PDF through MinerU Wang et al. [2024a]. Local execution tools support computation and debugging through one-shot shell commands and persistent terminal workflows for longer local analyses during benchmark runs.

ResearchHarness also supports automatic context compaction for long multi-step tasks. When the message history approaches the input budget, ResearchHarness summarizes the accumulated interaction history into compact memory and continues the run with that memory; the default compaction trigger is 128k tokens.

## 3.4. Evaluation Metric: From Re-Discovery to Discovery

Scientific discovery is inherently open-ended and dificult to evaluate. Pure paper reproduction turns the problem into a closed-space optimization task, where the target paper is treated as a fixed answer key and scientifically meaningful deviations may be penalized. Fully open-ended evaluation has the opposite problem: without an anchor, the search space becomes too unconstrained to distinguish genuine scientific progress from plausible but unsupported claims. To balance openness and evaluability, ResearchClawBench introduces Reference-Anchored Discovery Score (RADS). RADS treats each target paper as a human reference study under the same scientific objective, rather than as a closed-form ground truth. The agent is evaluated by whether its evidence, quantitative results, mechanistic analysis, and experimental reasoning are weaker than, comparable to, or stronger than this reference study.

![](images/f9a4a80130a9614705ff1bafe240fb6ade214e9e9fd946047faeadf4e95ff611.jpg)  
Figure 4 | Schematic illustration of the metric design from re-discovery to discovery.

A score of 50 denotes reference-level scientific evidence. Scores below 50 indicate insuficient discovery potential, typically due to incorrect analysis, shallow experiments, missing key evidence, incomplete reporting, or failure to identify the core scientific object. Scores above 50 indicate reference-surpassing evidence and therefore suggest new-discovery potential: the agent demonstrates capabilities that may support scientific findings beyond routine reproduction. Across the two main task types in ResearchClawBench, target optimization and diagnostic analysis, scores above 50 may correspond respectively to stronger quantitative results, or to more complete explanations, clearer mechanisms, and new insights. RADS does not claim that every score above 50 is a validated new discovery. Scientific discovery is intrinsically low-probability and requires further verification. Instead, RADS measures an auto-research agent’s professional capacity to generate credible scientific evidence and to increase the probability of real discovery. In this sense, RADS evaluates agents toward end-to-end scientific discovery, while avoiding over-claiming on any single benchmark case.

Operationally, RADS is implemented through expert-constructed rubrics that evaluate whether the final report and generated artifacts recover or advance the key scientific content of the target paper. Each rubric item is built around a concrete scientific artifact in the hidden target paper and is assigned one of two types, text or image, corresponding to textual scientific content and multimodal figure evidence. Each item specifies concrete criteria extracted from the paper’s key contributions, technical keywords that the judge should verify, and a weight reflecting the item’s importance. During evaluation, the judge selects the appropriate evaluation mode according to the item’s content and

Table 5 | Main results on ResearchClawBench. The full score is 100; 50 indicates target-paper-level re-discovery, while scores above 50 go beyond the target paper.  
![](images/465ee93b75b26a8678b9216d67162473ee3237e4fb965dca19152b17702983c8.jpg)  
type, and scores the model output using these rubric signals.

## 4. Experiments

## 4.1. Experimental Setup

We evaluate seven agents: Claude Code [Anthropic, 2026a], Codex CLI [OpenAI, 2026a], ARIS Codex [Yang et al., 2026, OpenAI, 2026a], OpenClaw [OpenClaw contributors, 2026], Nanobot [HKUDS, 2026], EvoScientist [Lyu et al., 2026], and ResearchClaw [Yang, 2026]. We also evaluate seventeen native LLM baselines through ResearchHarness: Claude-Opus-4.6 [Anthropic, 2026b], Claude-Opus-4.7, DeepSeek-V4-Pro [DeepSeek-AI, 2026], GLM-5.1 [Z.AI, 2026], GPT-5.4 [OpenAI, 2026b], GPT-5.5, Gemini-3.1-Pro [Google, 2026a], Gemini-3.5-Flash [Google, 2026b], Grok-4.1 [xAI, 2025], Grok-4.3 [xAI, 2026], Kimi-K2.5 [Team et al., 2026], Kimi-K2.6 [Moonshot AI, 2026], MiMo-V2- Pro [Xiaomi, 2026], MiMo-V2.5 [XiaomiMiMo, 2026], Qwen3.5-397B-A17B [Qwen Team, 2026a], Qwen3.6-Plus [Qwen Team, 2026b], and Qwen3.7-Max [Qwen Team, 2026c]. All systems are evaluated on the 40 tasks in ResearchClawBench. After each run, GPT-5.1 [OpenAI, 2025] scores the final report against the rubrics.

Cost vs. score

![](images/e08730d19b3c3ac1edeaeee2632d65913f30bc7264d976919d1cc25c71578cef.jpg)

![](images/c1d30f0e099c5016bdd65cb22576ee595ce78acea43e9583fce9b892c57aad68.jpg)

Figure 5 | Resource-score relationships for mean task cost and runtime versus mean rubric score.  
![](images/a9fc22963420234b34abe58bf2ca1bb2e474c3b2a6408234a6a5f439f180913d.jpg)  
Figure 6 | Error type distribution. Experiment Design Mismatch means the protocol, processing, baseline, or validation difers from the target paper; Evidence Mismatch means figures, numbers, or conclusions mismatch critical evidence; Scientific Core Missing means the core mechanism or finding is missing; Goal Misalignment means the system solves a related but non-equivalent problem; Reliability / Reporting Failure means unsupported claims, invalid evidence, or reporting failures; Execution Failure means no usable artifacts are generated.

## 4.2. Main Results

Table 5 reports scores for autonomous agents and ResearchHarness LLMs across the ten scientific domains. Current systems remain far from reliable end-to-end re-discovery: the best autonomous agent, Claude Code, reaches only 21.5 on average, and the autonomous-agent frontier mean is only 25.8. The best LLM, Claude-Opus-4.7, reaches 20.7, with an LLM frontier mean of 26.5.

Claude Code is the strongest overall agent, but it is not dominant. It wins only 12 out of 40 tasks at the task level and diferent agents show highly consistent task dificulty; among the 28 pairwise task-level correlations induced by the autonomous-agent configurations, the median is 0.77 and the range is 0.64–0.86. ResearchHarness LLMs show a similar pattern. Claude-Opus-4.7 has the highest overall mean, while diferent models lead in diferent domains: Claude-Opus-4.6 remains strongest in Astronomy, Earth, Energy, and Math; GLM-5.1 leads Chemistry; Gemini-3.5- Flash leads Information; GPT-5.4 leads Life; DeepSeek-V4-Pro leads Material; Claude-Opus-4.7 leads Neuroscience; and Qwen3.7-Max leads Physics.

## 4.3. Four Supplemental Dimensions

![](images/7f2aa73ce8cb2e8d8cd28e185b161c55c10424475d77c2a2cbb50dcbd238b26d.jpg)

![](images/a97d8a598b3a4a31f09947b99bfc4d9b2a02a4d7e20b4b3113403e78fc34ee7d.jpg)

![](images/afd8dbb6112b115f23402bd33ff80a96f833f95fa208429a4567578f1cd74506.jpg)

![](images/7eae0bbd6e8e00ebe37c9dd3fb7a99be3077d063adf83a0e252316544aa3a8e3.jpg)

![](images/12d6becf61f76af107f04135807a78594997247030f9352d9c88d5428fb16c68.jpg)  
Figure 7 | Case study for Physics 002. OpenClaw recovers the most direct XEB trend but misses several rubric-critical components of the target fidelity-estimation evidence chain.

Table 6: Supplemental quality dimensions. Comp., Instr., and Prof. abbreviate Comprehensiveness, Instruction Following, and Professionalism. Purple shading is normalized across all scores in this table.  
![](images/12aba4d0d0f665ee0b48e2f07837451d74da8887a18c6768796142d95b75392f.jpg)

Beyond rubrics, RCBench evaluates reports along four additional dimensions: Comprehensiveness, Depth, Instruction Following, and Professionalism.

Table 6 reports the seven agents’ scores on these four supplemental dimensions. Systems often exceed 70 on Professionalism, while the other dimensions are lower; diferent systems lead in Professionalism, Depth, and Instruction Following.

This result shows that models re-

main weaker on the substantive quality of research content than on presentation quality. The four dimensions also have weak correlations with rubric score. Thus, the central challenge is not producing a polished report, but recovering rubric-critical scientific evidence.

## 4.4. Runtime and Cost Analysis

We further analyze the relationship between mean cost, mean runtime, and rubric score. In Figure 5, systems closer to the upper-left region obtain higher scores with lower resource use. We use Pareto frontiers to mark the efective resource-score boundary among current systems. The eficient knee in the cost dimension is Qwen3.7-Max, while the eficient knee in the runtime dimension is OpenClaw.

Overall, score appears to have only a weak positive relationship with resource investment, and this relationship is largely elevated by Claude Code, which combines a high score with high cost and long runtime. This suggests that the current tasks may not yet lie within the stable capability boundary of existing models: even when a model spends more time, the additional computation does not necessarily produce a stable improvement in the final result. As the following error analysis shows, system failures more often reflect scientific goal misalignment and experimental-protocol deviation than insuficient iterative trial-and-error.

## 4.5. Error Analysis

We analyze all 280 runs from the seven autonomous agents over 40 tasks and group fine-grained labels into six error types. Figure 6 shows that failures concentrate on Experiment Design Mismatch, Evidence Mismatch, and Scientific Core Missing, rather than Goal Misalignment, Reliability / Reporting Failure, or Execution Failure.

This distribution shows that the main problem is not that agents cannot generate reports or that execution simply fails. Instead, agents gradually depart from the target paper in protocol, key evidence, or mechanistic interpretation, such as by selecting the wrong data-processing method, baseline, validation setting, or experimental protocol.

## 4.6. Case Study

Figure 7 shows OpenClaw’s result on Physics 002. OpenClaw obtains the highest score among all autonomous agents on this task, but the score is only 27.45. The task centers on random quantum circuit sampling and asks the system to estimate fidelity from measured counts and ideal reference probabilities. The corresponding rubrics require more than a single fidelity curve: they also require multiple scaling analyses, validation, mirror-circuit inference, the gate-counting error model, and multi-estimator consistency.

OpenClaw recovers the most direct part of the task: it computes counts-weighted linear XEB and recovers the trend that fidelity decreases with depth on the <sup>??</sup> = 40 verification subset. As a result, it receives 47/50 on the fifth rubric item and 40/50 on <sup>??</sup> = 40 depth scaling. However, it does not recover the full evidence chain: fixed-<sup>??</sup> = 12 qubit scaling lacks log-XEB and multi-metric consistency, <sup>??</sup> = 56 validation lacks MB regression or depth-24 mirror-circuit inference, and the gate-counting fidelity model is completely absent. This case shows that agent analysis often stops at the most direct observable trend while missing the finer verification steps and physical modeling required for target-paper-level re-discovery.

## 5. Conclusion

We presented ResearchClawBench, a benchmark for evaluating end-to-end autonomous research across 10 scientific domains and 40 real-paper-derived tasks. Given only a task description, related literature, raw data, and an executable environment, systems must design experiments, execute analyses, and produce research reports that are judged by expert-built rubrics. Results show that current agents and harnessed LLMs remain far from reliable scientific re-discovery: many produce complete reports but deviate from the target paper in experimental protocols, mechanism explanations, or evidence chains. Future work will expand task coverage and study longer-horizon research processes

under real evidence constraints.

## 6. Limitations

ResearchClawBench has several important limitations.First, the current tasks primarily evaluate dry-lab research based on existing data, code, and literature, and cannot assess wet-lab research that requires real experimental platforms, sample preparation, or instrument operation. Second, current scoring mainly targets the final report rather than fine-grained research steps. Thrid, Evaluating truly new scientific conclusions requires more reliable evaluation methods than rubrics constructed around existing target papers.

## References

Khizar Anjum, Muhammad Arbab Arshad, Kadhim Hayawi, Efstathios Polyzos, Asadullah Tariq, Mohamed Adel Serhani, Laiba Batool, Brady Lund, Nishith Reddy Mannuru, Ravi Varma Kumar Bevara, et al. Domain specific benchmarks for evaluating multimodal large language models. arXiv preprint arXiv:2506.12958, 2025.

Anthropic. Claude Code. https://docs.claude.com/en/docs/claude-code/overview, May 2026a.

Anthropic. Claude Opus 4.6. https://www.anthropic.com/news/claude-opus-4-6, February 2026b.

Jun Shern Chan, Neil Chowdhury, Oliver Jafe, James Aung, Dane Sherburn, Evan Mays, Giulio Starace, Kevin Liu, Leon Maksin, Tejal Patwardhan, et al. Mle-bench: Evaluating machine learning agents on machine learning engineering. In International Conference on Learning Representations, volume 2025, pages 50466–50494, 2025.

Hui Chen, Miao Xiong, Yujie Lu, Wei Han, Ailin Deng, Yufei He, Jiaying Wu, Yibo Li, Yue Liu, and Bryan Hooi. Mlr-bench: Evaluating ai agents on open-ended machine learning research. Advances in Neural Information Processing Systems, 38, 2026.

Ziru Chen, Shijie Chen, Yuting Ning, Qianheng Zhang, Boshi Wang, Botao Yu, Yifei Li, Zeyi Liao, Chen Wei, Zitong Lu, et al. Scienceagentbench: Toward rigorous assessment of language agents for data-driven scientific discovery. In International Conference on Learning Representations, volume 2025, pages 96934–96990, 2025.

DeepSeek-AI. DeepSeek-V4-Pro. https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro, April 2026.

David M Douglas. Researchers’ perceptions of automating scientific research. AI & SOCIETY, 40(5): 4131–4144, 2025.

Shiyang Feng, Runmin Ma, Xiangchao Yan, Yue Fan, Yusong Hu, Songtao Huang, Shuaiyu Zhang, Zongsheng Cao, et al. Internagent-1.5: A unified agentic framework for long-horizon autonomous scientific discovery, 2026. URL https://arxiv.org/abs/2602.08990.

Google. Gemini 3.1 Pro. https://blog.google/innovation-and-ai/ models-and-research/gemini-models/gemini-3-1-pro/, February 2026a.

Google. Gemini 3.5 Flash. https://blog.google/innovation-and-ai/ models-and-research/gemini-models/gemini-3-5/, May 2026b.

Juraj Gottweis, Wei-Hung Weng, Alexander Daryin, Tao Tu, Anil Palepu, Petar Sirkovic, Artiom Myaskovsky, Felix Weissenberger, Keran Rong, Ryutaro Tanno, et al. Towards an ai co-scientist. arXiv preprint arXiv:2502.18864, 2025.

Taicheng Guo, Bozhao Nan, Zhenwen Liang, Zhichun Guo, Nitesh Chawla, Olaf Wiest, Xiangliang Zhang, et al. What can large language models do in chemistry? a comprehensive benchmark on eight tasks. Advances in neural information processing systems, 36:59662–59688, 2023.

HKUDS. nanobot. https://github.com/HKUDS/nanobot, May 2026.

Qian Huang, Jian Vora, Percy Liang, and Jure Leskovec. Mlagentbench: Evaluating language agents on machine learning experimentation. arXiv preprint arXiv:2310.03302, 2023.

Peter Jansen, Marc-Alexandre Côté, Tushar Khot, Erin Bransom, Bhavana Dalvi Mishra, Bodhisattwa Prasad Majumder, Oyvind Tafjord, and Peter Clark. Discoveryworld: A virtual environment for developing and evaluating automated scientific discovery agents. Advances in Neural Information Processing Systems, 37:10088–10116, 2024.

Dawei Li, Bohan Jiang, Liangjie Huang, Alimohammad Beigi, Chengshuai Zhao, Zhen Tan, Amrita Bhattacharjee, Yuxuan Jiang, Canyu Chen, Tianhao Wu, et al. From generation to judgment: Opportunities and challenges of llm-as-a-judge. In Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing, pages 2757–2791, 2025.

Hongwei Liu, Junnan Liu, Shudong Liu, Haodong Duan, Yuqiang Li, Mao Su, Xiaohong Liu, Guangtao Zhai, Xinyu Fang, Qianhong Ma, et al. Atlas: A high-dificulty, multidisciplinary benchmark for frontier scientific reasoning. arXiv preprint arXiv:2511.14366, 2025a.

Yue Liu, Sin Kit Lo, Qinghua Lu, Liming Zhu, Dehai Zhao, Xiwei Xu, Stefan Harrer, and Jon Whittle. Agent design pattern catalogue: A collection of architectural patterns for foundation model based agents. Journal of Systems and Software, 220:112278, 2025b.

Chris Lu, Cong Lu, Robert Tjarko Lange, Jakob Foerster, Jef Clune, and David Ha. The ai scientist: Towards fully automated open-ended scientific discovery. arXiv preprint arXiv:2408.06292, 2024.

Alisia Lupidi, Bhavul Gauri, Thomas Simon Foster, Bassel Al Omari, Despoina Magka, Alberto Pepe, Alexis Audran-Reiss, Muna Aghamelu, Nicolas Baldwin, Lucia Cipolina-Kun, et al. Airs-bench: a suite of tasks for frontier ai research science agents. arXiv preprint arXiv:2602.06855, 2026.

Yougang Lyu, Xi Zhang, Xinhao Yi, Yuyue Zhao, Shuyu Guo, Wenxiang Hu, Jan Piotrowski, Jakub Kaliski, Jacopo Urbani, Zaiqiao Meng, et al. Evoscientist: Towards multi-agent evolving ai scientists for end-to-end scientific discovery. arXiv preprint arXiv:2603.08127, 2026.

Moonshot AI. Kimi K2.6. https://www.kimi.com/blog/kimi-k2-6, April 2026.

Deepak Nathani, Lovish Madaan, Nicholas Roberts, Nikolay Bashlykov, Ajay Menon, Vincent Moens, Amar Budhiraja, Despoina Magka, Vladislav Vorotilov, Gaurav Chaurasia, et al. Mlgym: A new framework and benchmark for advancing ai research agents. arXiv preprint arXiv:2502.14499, 2025.

OpenAI. GPT-5.1 for developers. https://openai.com/index/gpt-5-1-for-developers/, November 2025.

OpenAI. OpenAI Codex CLI. https://github.com/openai/codex, May 2026a.

OpenAI. Introducing GPT-5.4. https://openai.com/index/introducing-gpt-5-4/, March 2026b.

OpenClaw contributors. OpenClaw. https://github.com/openclaw/openclaw, May 2026.

Long Phan, Alice Gatti, Ziwen Han, Nathaniel Li, Josephina Hu, Hugh Zhang, Chen Bo Calvin Zhang, Mohamed Shaaban, John Ling, Sean Shi, et al. Humanity’s last exam. arXiv preprint arXiv:2501.14249, 2025.

Qwen Team. Qwen3.5-397B-A17B. https://qwen.ai/blog?id=qwen3.5, February 2026a.

Qwen Team. Qwen3.6-Plus. https://qwen.ai/blog?id=qwen3.6, April 2026b.

Qwen Team. Qwen3.7: The agent frontier. https://qwen.ai/blog?id=qwen3.7, May 2026c.

Jiyong Rao, Yicheng Qiu, Jiahui Zhang, Juntao Deng, Shangquan Sun, Fenghua Ling, Hao Chen, Nanqing Dong, Zhangyang Gao, Siqi Sun, et al. Scidatacopilot: An agentic data preparation framework for agi-driven scientific discovery. arXiv preprint arXiv:2602.09132, 2026.

David Rein, Betty Li Hou, Asa Cooper Stickland, Jackson Petty, Richard Yuanzhe Pang, Julien Dirani, Julian Michael, and Samuel R Bowman. Gpqa: A graduate-level google-proof q&a benchmark. arXiv preprint arXiv:2311.12022, 2023.

Zachary S Siegel, Sayash Kapoor, Nitya Nagdir, Benedikt Stroebl, and Arvind Narayanan. Core-bench: Fostering the credibility of published research through a computational reproducibility agent benchmark. arXiv preprint arXiv:2409.11363, 2024.

Giulio Starace, Oliver Jafe, Dane Sherburn, James Aung, Jun Shern Chan, Leon Maksin, Rachel Dias, Evan Mays, Benjamin Kinsella, Wyatt Thompson, et al. Paperbench: Evaluating ai’s ability to replicate ai research. arXiv preprint arXiv:2504.01848, 2025.

Jiabin Tang, Lianghao Xia, Zhonghang Li, and Chao Huang. Ai-researcher: Autonomous scientific innovation. arXiv preprint arXiv:2505.18705, 2025.

Kimi Team, Tongtong Bai, Yifan Bai, Yiping Bao, SH Cai, Yuan Cao, Y Charles, HS Che, Cheng Chen, Guanduo Chen, et al. Kimi k2. 5: Visual agentic intelligence. arXiv preprint arXiv:2602.02276, 2026.

Minyang Tian, Luyu Gao, Shizhuo D Zhang, Xinan Chen, Cunwei Fan, Xuefei Guo, Roland Haas, Pan Ji, Kittithat Krongchon, Yao Li, et al. Scicode: A research coding benchmark curated by scientists. Advances in Neural Information Processing Systems, 37:30624–30650, 2024.

Theo Walker, Christopher M Grulke, Diane Pozefsky, and Alexander Tropsha. Chembench: a cheminformatics workbench. Bioinformatics, 26(23):3000–3001, 2010.

Bin Wang, Chao Xu, Xiaomeng Zhao, Linke Ouyang, Fan Wu, Zhiyuan Zhao, Rui Xu, Kaiwen Liu, Yuan Qu, Fukai Shang, et al. Mineru: An open-source solution for precise document content extraction. arXiv preprint arXiv:2409.18839, 2024a.

Ruoyao Wang, Peter Jansen, Marc-Alexandre Côté, and Prithviraj Ammanabrolu. Scienceworld: Is your agent smarter than a 5th grader? In Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing, pages 11279–11298, 2022.

Xiaoxuan Wang, Ziniu Hu, Pan Lu, Yanqiao Zhu, Jieyu Zhang, Satyen Subramaniam, Arjun R Loomba, Shichang Zhang, Yizhou Sun, and Wei Wang. Scibench: Evaluating college-level scientific problemsolving abilities of large language models. arXiv preprint arXiv:2307.10635, 2023.

Yubo Wang, Xueguang Ma, Ge Zhang, Yuansheng Ni, Abhranil Chandra, Shiguang Guo, Weiming Ren, Aaran Arulraj, Xuan He, Ziyan Jiang, et al. Mmlu-pro: A more robust and challenging multitask language understanding benchmark. Advances in Neural Information Processing Systems, 37: 95266–95290, 2024b.

Johannes Welbl, Nelson F Liu, and Matt Gardner. Crowdsourcing multiple choice science questions. In Proceedings of the 3rd Workshop on Noisy User-generated Text, pages 94–106, 2017.

xAI. Grok 4.1 Model Card. https://data.x.ai/2025-11-17-grok-4-1-model-card.pdf, November 2025.

xAI. Grok 4.3. https://docs.x.ai/developers/models/grok-4, May 2026.

Xiaomi. MiMo-V2-Pro. https://mimo.xiaomi.com/, March 2026.

XiaomiMiMo. MiMo-V2.5. https://huggingface.co/XiaomiMiMo/MiMo-V2.5, April 2026.

Wanghan Xu, Xiangyu Zhao, Yuhao Zhou, Xiaoyu Yue, Ben Fei, Fenghua Ling, Wenlong Zhang, and Lei Bai. Earthse: A benchmark evaluating earth scientific exploration capability for large language models. In The Fourteenth International Conference on Learning Representations, 2025a.

Wanghan Xu, Yuhao Zhou, Yifan Zhou, Qinglong Cao, Shuo Li, Jia Bu, Bo Liu, Yixin Chen, Xuming He, Xiangyu Zhao, et al. Probing scientific general intelligence of llms with scientist-aligned workflows. arXiv preprint arXiv:2512.16969, 2025b.

Mingxin Yang. Researchclaw. https://github.com/ymx10086/ResearchClaw, 2026. GitHub repository.

Ruofeng Yang, Yongcan Li, and Shuai Li. Aris: Autonomous research via adversarial multi-agent collaboration. arXiv preprint arXiv:2605.03042, 2026.

Z.AI. GLM-5.1. https://docs.z.ai/guides/llm/glm-5.1, April 2026.

Xiangyu Zhao, Wanghan Xu, Bo Liu, Yuhao Zhou, Fenghua Ling, Ben Fei, Xiaoyu Yue, Lei Bai, Wenlong Zhang, and Xiao-Ming Wu. Msearth: A multimodal scientific dataset and benchmark for phenomena uncovering in earth science. arXiv preprint arXiv:2505.20740, 2025a.

Xuanle Zhao, Zilin Sang, Yuxuan Li, Qi Shi, Weilun Zhao, Shuo Wang, Duzhen Zhang, Xu Han, Zhiyuan Liu, and Maosong Sun. Autoreproduce: Automatic ai experiment reproduction with paper lineage. arXiv preprint arXiv:2505.20662, 2025b.

Shuyan Zhou, Frank F Xu, Hao Zhu, Xuhui Zhou, Robert Lo, Abishek Sridhar, Xianyi Cheng, Tianyue Ou, Yonatan Bisk, Daniel Fried, et al. Webarena: A realistic web environment for building autonomous agents. arXiv preprint arXiv:2307.13854, 2023.

## A. Authors

## Core Authors

Wanghan Xu<sup>1,2,∗</sup>, Shuo Li<sup>1,3,∗</sup>, Tianlin Ye<sup>1,3</sup>, Qinglong Cao<sup>1</sup>, Yixin Chen<sup>1</sup>, Hengjian Gao<sup>1,2</sup>, Yiheng Wang<sup>1</sup>, Qi Li<sup>1</sup>, Kun Li<sup>1</sup>

## Contributors

Sheng Xu<sup>1,3</sup>, Shengdu Chai<sup>1,3</sup>, Fangchen Yu<sup>1,4</sup>, Xiangyu Zhao<sup>6</sup>, Zhangrui Zhao<sup>1</sup>, Weijie Ma<sup>3</sup>, Zijie Guo<sup>1,3</sup>, Koutian Wu, Haoyu Zhou<sup>7</sup>, Haoxiang Yin<sup>8</sup>, Lixue Cheng<sup>9</sup>, Chaofan Hu<sup>1,10</sup>, Haoxuan Li<sup>11</sup>, Lu Mi<sup>11</sup>, Xuxuan Xie<sup>12</sup>, Yifan Zhou<sup>2</sup>, Ruizhe Chen<sup>1</sup>, Zhiwang Zhou<sup>1,5</sup>, Xingjian Guo<sup>1,3</sup>, Yuhao Zhou<sup>1,8</sup>, Xuming He<sup>1,13</sup>, Shengyuan Xu<sup>1,2</sup>

## Scientific Directors

Xinyu Gu<sup>1</sup>, Jiamin Wu<sup>1,4</sup>, Mianxin Liu<sup>1</sup>, Chunfeng Song<sup>1</sup>, Fenghua Ling<sup>1</sup>, Dongzhan Zhou<sup>1</sup>, Shixiang Tang<sup>1</sup>, Yuqiang Li<sup>1</sup>, Mao Su<sup>1</sup>, Peng Ye<sup>1,4</sup>, Siqi Sun<sup>1,3</sup>, Bin Wang<sup>3</sup>, Xue Yang<sup>2</sup>, Zhenfei Yin<sup>14</sup>, Tianfan Fu<sup>1,15</sup>, Guangtao Zhai<sup>1,2</sup>, Wanli Ouyang<sup>1</sup>, Bo Zhang<sup>1</sup>

## Corresponding Authors

Lei Bai<sup>1</sup>, Wenlong Zhang<sup>1</sup>

## Main Afiliations

<sup>1</sup>Shanghai Artificial Intelligence Laboratory

<sup>2</sup>Shanghai Jiao Tong University

<sup>3</sup>Fudan University

<sup>4</sup>The Chinese University of Hong Kong

<sup>5</sup>Tongji University

<sup>6</sup>Hong Kong Polytechnic University

<sup>7</sup>Xi’an Jiaotong-Liverpool University

<sup>8</sup>Sichuan University

<sup>9</sup>Hong Kong University of Science and Technology

<sup>10</sup>Beijing Normal University

<sup>11</sup>Tsinghua University

<sup>12</sup>Southeast University

<sup>13</sup>Zhejiang University

<sup>14</sup>University of Oxford

<sup>15</sup>Nanjing University

## B. Task Information

Table 7 | Task information for the 40 ResearchClawBench tasks. Each row corresponds to one task. The Data column lists the name, modality, and description fields from each task’s task\_info.json.  
![](images/2c4c5d1b009045a10eb90c4ab79fc42f414687dadb6b6f77be7f6c0af3ca8cac.jpg)

![](images/45d121fad8271f8d4526e96d3269533cf2362d548f728e2d2e4da5b3c5bda910.jpg)

![](images/039a524dd98f01f3be46864640009a18bbe073a11cc883f992bb8e79767b8b68.jpg)

![](images/fd614ba21de028e0cc3a5a58ba9701970a3ed97997bc3e47743b5b33d4396c68.jpg)

![](images/282befa0be769980f4772c4529bc82b152801fb860dc062b3cdcb505bf1c8d33.jpg)

![](images/26076ff3bc4cf05c5b6bf9fa63f7407f0fe7a8691270d82c0d7405fdf3910e98.jpg)

![](images/c7c0a1c5cd2731b83c9ab8993e80e9086c04ccd8ff05b168f9f31c719ad01377.jpg)

![](images/112e041c83ceb5d276daa24882b91ec509e30135203c1599fcd14cd6530553c0.jpg)

![](images/4a89708397cf4495d3dc8ea53c73bc1f6b3fce28c3bb8db115f70df7ffc3d5eb.jpg)

![](images/d848283acf020433aa6258e8d64279c3996e9bf45ca4397ef40eb7dc219b6227.jpg)

![](images/c82fca4bd707ffa10d1f72d4341f07351f951eaa7fe1dc29cabc876557ae386d.jpg)

![](images/f244d36cc9687d167d1384b63b97e063356840fc894dc9e3227822db2964bef6.jpg)

![](images/724eb8a831f47e4e839a4003af3aaf0dd57cd5b083463daaae39df3b2d9b280e.jpg)

![](images/403598039feb6756380f6e19c45a7627f3eb0ead3f786ddead2734357d6bc331.jpg)

![](images/8cb52e537e1f45ea60fb3aea19476b32b86fa284c684625a84e67c33dacaf14a.jpg)

![](images/1ec007fe20fb263a0a515e98198fb4ce4969b661eccb14e1a00a7ab5e323d9f9.jpg)

![](images/7a42d9236c93554e4340ab311a721db38fbc50811c21bb0df148e985c366d5a7.jpg)

![](images/9cc9b70899783df6c7ade4c2178fadb0c44e899ea078d0edae8616f6cea3ae11.jpg)

![](images/844f97b3f4d837923b698e3a499af5bb0670fcf7faf6e4168abfae85e042539c.jpg)

## C. Per-Task Results

Table 8 | Per-task total rubric scores for each task and system. Panel (a) reports autonomous-agent scores: C.Code: Claude Code; Codex: Codex CLI; ARIS: ARIS Codex; Open: OpenClaw; Nano: Nanobot; Evo0: EvoScientist v0.0.4; Evo1: EvoScientist v0.1.1; RClaw: ResearchClaw. Panel (b) reports ResearchHarness LLM scores: C4.6/C4.7: Claude-Opus-4.6/4.7; DS: DeepSeek-V4-Pro; GLM: GLM-5.1; G5.4/G5.5: GPT-5.4/5.5; Gem/GemF: Gemini-3.1-Pro/Gemini-3.5-Flash; G4.1/G4.3: Grok-4.1/4.3; K2.5/K2.6: Kimi-K2.5/2.6; M2P/M2.5: MiMo-V2-Pro/V2.5; Q3.5/Q3.6/Q3.7: Qwen3.5-397B-A17B/Qwen3.6-Plus/Qwen3.7-Max. A dash indicates that the model directly crashed or failed during execution.

![](images/ab9a4c76e94f2544787566eb4109cf9626ce7866fe2a39e36e361345778225ef.jpg)

Table 8 continued. Panel (a) Autonomous agents.  
![](images/290f07662007730ead3ed2b58e2abce897b6e8c8918b50b3414b0140a813bce8.jpg)

![](images/37e8774339d3d15e322533f20f4f1cfa17ab9634850edacca7d9dce464e4d26b.jpg)

![](images/a39aa87c80ad58fae1e59d7ff2c9254931d2060a8377499a2608bd38acba8108.jpg)

## D. Detailed Demonstrations

Figure 8 | Detailed demonstrations of representative system behaviors. We select four detailed demonstrations to illustrate representative system behaviors. The first two panels are high-scoring runs, whereas the latter two are task-winning runs on lower-scoring tasks; although those latter runs obtain the highest scores within their respective tasks, their absolute scores remain low.

## (a) Physics\_003

## Meta Info

• System / Model: ResearchHarness / GPT-5.5

• Total Score: 49

• Duration: 264 seconds

• Cost: \$0.99

## Task

Input: Monolayer epitaxial graphene samples and mid-infrared pump excitation parameters (wavelength: 5 microm, intensity, polarization angle). Output: Direct, energy- and momentum-resolved observation of Floquet-Bloch states (replica bands of the Dirac cone) via time-resolved and angle-resolved photoemission spectroscopy (tr-ARPES). Scientific Goal: To experimentally confirm the existence of Floquet-Bloch states in a paradigmatic 2D material and elucidate the underlying scattering mechanism involving photon-dressed Volkov final states.

## Data

• raw\_trARPES\_data.h5 (structure data). Raw, unprocessed 4D data arrays (energy, momentum kx/ky, time delay) from the tr-ARPES experiment. Path: ./data/raw\_trARPES\_data.h5.

• processed\_band\_data.json (feature data). Processed data containing the extracted positions and intensities of the main Dirac cone and replica bands. Path: ./data/processed\_band\_ data.json.

• polarization\_dependence\_data.csv (sequence data). Tabular data containing the measured intensity of the replica band for each pump polarization angle (thetap). Path: ./data/ polarization\_dependence\_data.csv.

## Rubrics

1. Image | Weight(0.5): Energy-momentum map from tr-ARPES showing the main Dirac cone and a clear replica band induced by the 5 microm pump excitation. Path: images/comprehensive\_ results\_summary.png. Expected evidence: Clear visualization of the main Dirac cone.; Clear visualization of a replica band shifted from the main cone.; Axes labeled with energy (eV) and momentum (Angstrom-1).; Data acquired at a time delay of \~1 ps after pump excitation..

2. Image | Weight(0.3): Plot showing the intensity of the replica band as a function of pump polarization angle (thetap), demonstrating a characteristic anisotropy. Path: images/floquet\_ volkov\_simulation.png. Expected evidence: Intensity plotted against polarization angle (thetap).; Shows a clear periodic variation (e.g., sinusoidal) in intensity.; Matches the trend predicted by the Volkov state scattering model.; Experimental data points overlaid with theoretical fit curve..

3. Text | Weight(0.2): The anisotropy in the replica band intensity confirms that the replication mechanism involves scattering with photon-dressed Volkov final states, not just the initial Floquet-Bloch state. Path: N/A. Expected evidence: Explicitly states the involvement of Volkov final states.;

Links the polarization dependence to the scattering mechanism.; Distinguishes this mechanism from simpler band replication..

## Generated Report

## Energy- and Momentum-Resolved Floquet-Bloch Signatures in Pumped Monolayer Graphene

## Abstract

I analyzed the provided monolayer epitaxial graphene tr-ARPES datasets to test whether a 5 microm mid-infrared pump produces photon-spaced replica bands of the Dirac cone and whether the replica intensity carries a polarization dependence consistent with photon-dressed photoemission final states. The processed feature table contains two symmetry-related entries for each first-order replica. When each replica is mapped back to its inferred parent dispersion by subtracting order x pump\_energy, both the order = -1 and order = +1 features are separated from the parent by 0.248 eV, equal to the pump photon energy stored in the processed data. Raw pump-on minus pump-of maps also show localized intensity enhancement around the processed replica target region. The polarization series has maxima near 0 deg, 90 deg, and 180 deg and lower intensity at intermediate angles; a pi-periodic cos(2thetap) model gives a small fitted modulation contrast of 0.00261. Thus the workspace data support photon-spaced Floquet-Bloch replica features in graphene and show a weak polarization-angle dependence compatible with matrix-element/final-state dressing, while the limited seven-angle series and lack of a delay-indexed 4D raw cube prevent a stronger mechanistic separation of initial-state Floquet dressing from Volkov final-state efects.

## 1. Scientific objective and context

The task is to identify direct, energy- and momentum-resolved Floquet-Bloch states in monolayer epitaxial graphene under a 5 microm mid-infrared pump. In tr-ARPES, the relevant experimental signature is pump-induced spectral weight that appears as sidebands or replica bands displaced by integer multiples of the pump photon energy from a parent Bloch dispersion. The related-work corpus emphasizes this observable: Floquet-Bloch states are detected through pump-induced replica/sideband spectral weight in energy-momentum photoemission maps, while photon-dressed Volkov final states and photoemission matrix elements can shape the observed replica intensity and its polarization dependence. Extracted related-work notes are saved in outputs/related\_work\_contract.json.

The analysis therefore focused on four traceable questions:

1. Do the processed band features contain replica bands displaced by one pump photon from a parent Dirac-cone feature?

2. Are these features visible in energy-momentum raw pump-on/pump-of spectra?

3. Does the replica intensity vary with pump polarization angle in a pi-periodic way expected for a polarization-sensitive photoemission pathway?

4. What limitations remain for time-domain and Volkov-mechanism inference?

## 2. Data and reproducible workflow

## 2.1 Input files

The analysis used the three provided data files without modifying data/:

• data/raw\_trARPES\_data.h5: HDF5 spectra containing energy and momentum axes, a pumpof spectrum, and pump-on spectra for seven pump polarization angles.

• data/processed\_band\_data.json: extracted Dirac-cone dispersion and first-order replica features.

• data/polarization\_dependence\_data.csv: replica intensity versus pump polarization angle.

A reproducible script is saved as code/analyze\_floquet\_trarpes.py. It regenerates the numeric outputs in outputs/ and PNG figures in report/images/.

## 2.2 Data overview

The raw HDF5 file contains a 200-point energy axis from -0.5 to 0.5 eV with a median spacing of 0.005025 eV, and a 150-point kx axis from -0.3 to 0.3 Angstrom-1 with a median spacing of 0.004027 Angstrom-1. Seven polarization angles are present: 0 deg, 30 deg, 60 deg, 90 deg, 120 deg, 150 deg, and 180 deg. The raw spectra are 2D energy-kx arrays for pump of and for each polarization angle. The HDF5 file also includes a time\_delays axis, but no delay-indexed 4D intensity dataset was present, so the raw time-delay dynamics could not be reconstructed. This is recorded in outputs/ data\_overview.json.

![](images/6f0ed9faa10c7c760969fd0ea6e8a6dc8e4e86a50aba7f9704f7749842728d40.jpg)

![](images/441a79a8c4eec73c1947d1d5b36e1a17679491a54326fe124f7da498308da12c.jpg)

![](images/42cade72e5587995af562e82f58dc193eeac4d07827bb8be9a48eefc9bb28d4c.jpg)  
Data overview: pump-of, pump-on, and pump-induced diference map

Figure 1. Pump-of, pump-on at thetap = 0 deg, and pump-induced diference maps. The cyan marker denotes the processed replica target region used for raw-window validation.

## 3. Methods

## 3.1 Replica-band energy test

For each processed replica entry with order n = +-1, I computed an inferred parent energy

![](images/84d484be3da3018949569e0130aa87012348fa13edfeec7e6a02a723f4004889.jpg)

using the pump energy stored in the processed feature file, pump\_energy = 0.248 eV. A Floquet-Bloch replica passes this basic energy-consistency test when

![](images/c46723c8673fc3c8814958463321d6f963bc3b2151ba518f7d0cceca540b5d5f.jpg)

The resulting per-feature table is saved as outputs/band\_summary.csv, and the order-averaged table is saved as outputs/band\_order\_summary.csv.

## 3.2 Raw-map validation

To verify that the processed target corresponds to a pump-induced signal in raw spectra, I subtracted the pump-of map from each pump-on map and averaged the diference over a window centered on the CSV target point: target\_energy = 0.248744 eV, target\_kx = 0.042282 Angstrom-1, with half-widths 0.03 eV and 0.02 Angstrom-1. The angle-resolved raw-window values are saved in outputs/raw\_replica\_window\_signal\_by\_angle.csv. I also exported an energy distribution curve through the target momentum to outputs/energy\_distribution\_curves\_target\_k.csv.

## 3.3 Polarization-dependence model

The measured replica intensity was fit with the minimal pi-periodic model

![](images/98682d3c788b67acc273f73e7fec94fb78b9ac2f2a36d0d2742528532751c978.jpg)

This model captures the leading anisotropic dependence expected for a polarization-sensitive transition matrix element or Volkov-like final-state dressing. The fitted amplitude, phase, contrast, and bootstrap intervals are saved in outputs/polarization\_fit.json, with the fitted curve in outputs/ polarization\_fit\_curve.csv.

## 4. Results

![](images/f6442f5c9effe0ff7a1bfa46ce098b5adf6366797c4461b23d5a3130789f9dd9.jpg)

## 4.1 Photon-spaced replica features

The processed feature table contains four replica-band entries: two for order = -1 and two for order = +1. Their order-averaged separations from the inferred parent feature are:

![](images/f3ef8a5350ff7caa81eb5c0a0692c5136743e715cc7c3bdde801bd5b04a6b4c5.jpg)

Both first-order sidebands are exactly one processed pump photon energy from the inferred parent energy in the extracted dataset. The two orders therefore satisfy the defining photon-spacing criterion for Floquet-Bloch replicas. The two orders have comparable intensities, with the positive-order mean intensity slightly larger than the negative-order mean intensity in this feature table.

![](images/4cb669bdf67ec9c22fae2a6738c86966435d45a5744f5a9d9ef7df28ac5a02ff.jpg)

![](images/1a96fcc8a34e738df22e5bc4b6afb370e3ec920ece64ab910a61b13fb3d5f8be.jpg)  
Processed Dirac dispersion and photon-spaced replica bands

Figure 2. Left: extracted Dirac-cone dispersion and identified replica features. Right: order-averaged replica-parent separations compared with the 0.248 eV pump photon energy.

## 4.2 Raw pump-induced signal near the replica region

The raw HDF5 maps support the presence of a pump-induced feature near the processed target region. Averaging pump-on minus pump-of intensity in the target window gives positive values for all polarization angles:

![](images/c58499c1290ff92ca42827aeed9f44dfaf547c16e875b31f8c8e496e760dfcc5.jpg)

The target-window pump-induced enhancement is strongest at 0 deg, 90 deg, and 180 deg, matching the angle groups where the processed intensity is also high. This provides an independent check that the processed polarization dependence is reflected in the raw maps.

![](images/e4d78cdfabf0321b4662b70ad66ff85ae504b22759b82a77d03d4c980508f050.jpg)

![](images/512b41d521eedbd4e1f03aca0ed936cdfc960d917bf6e587fb5b162881563e53.jpg)

![](images/def50a88972047f78e371ca2a524b98885faf80223cf9c14846846bf396517e7.jpg)

![](images/ebf0cb1518dedaa81cec6e557bf8d077a7c14b12c2fadb20180fa7c2cb97c306.jpg)  
Raw-map and energy-distribution validation

Figure 3. Pump-induced diference maps for thetap = 0 deg and 90 deg, an energy distribution curve through the target momentum, and comparison of raw-window signal with mean-subtracted processed polarization intensity.

## 4.3 Polarization dependence and Volkov final-state interpretation

The polarization CSV shows a weak but structured intensity variation. The fitted pi-periodic model gives:

• model: I(theta)=c+a cos(2theta)+b sin(2theta);

• mean component c = 0.500477;

• anisotropic amplitude 0.001305;

• fitted phase 0.206 deg modulo 180 deg;

• modulation contrast 0.00261;

• bootstrap 95% interval for contrast: [0.000682, 0.036761];

• coeficient of determination R2 = 0.047 for seven angle points.

The small R2 reflects that the absolute modulation is weak relative to the point-to-point scatter and the dataset contains only seven polarization angles. Nevertheless, the raw and processed data both show the same high-low grouping: stronger replica signal near 0 deg, 90 deg, and 180 deg and weaker signal at 30 deg, 60 deg, 120 deg, and 150 deg. This behavior is consistent with polarization-sensitive photoemission matrix elements, including photon-dressed Volkov final-state scattering, but it is not by itself a unique proof of the Volkov mechanism.

![](images/37b814e8642307405d9d3c88e25f04f326236fe758c5dff194bea059b79397bc.jpg)

![](images/fc3cb28059e490406f8c6c8ac85010012116aadb923b8381a8bd002962408605.jpg)  
Polarization-dependent replica intensity  
Figure 4. Replica intensity versus pump polarization angle with a pi-periodic fit, shown both on linear and polar axes.

## 5. Validation and traceability

## 5.1 Directly verified from workspace data

• The raw HDF5 axes, spectra shapes, and intensity ranges are summarized in outputs/data\_ overview.json.

• The processed replicas are photon-spaced from their inferred parent energy by 0.248 eV for both first-order sidebands; see outputs/band\_summary.csv and outputs/band\_order\_ summary.csv.

• Raw pump-on minus pump-of maps have positive target-window enhancement at all measured polarization angles; see outputs/raw\_replica\_window\_signal\_by\_angle.csv.

• The polarization fit parameters and bootstrap intervals are saved in outputs/polarization\_ fit.json.

• Claim-level support is tabulated in outputs/claim\_recovery\_table.csv.

## 5.2 Related-work context

The related-work extraction in outputs/related\_work\_contract.json supports using pumpinduced, photon-spaced ARPES sidebands as the central Floquet-Bloch observable and motivates treating polarization-angle dependence as evidence for photoemission matrix-element or Volkov final-state contributions.

## 5.3 Limitations and assumptions

• The task description mentions raw 4D arrays over energy, momentum, and time delay. The available HDF5 file contains an energy axis, a kx axis, a time\_delays axis, and 2D pump-on/of spectra by polarization angle, but no delay-indexed 4D intensity dataset. I therefore could not extract rise/decay constants or time-delay-dependent Floquet formation dynamics.

• The analysis is efectively one-dimensional in momentum (kx) because no ky axis or ky-resolved dataset was present in the inspected HDF5 file.

• The Volkov final-state interpretation is supported indirectly through polarization-dependent intensity and related-work context. A decisive separation of initial-state Floquet replicas from finalstate Volkov sidebands would require additional observables such as probe-energy dependence, full vector-potential calibration, or a detailed photoemission matrix-element simulation.

• The polarization fit has low R2 because the modulation is very small and only seven angles are available. The qualitative high-low angle grouping is robust in both processed and raw-window signals, but the fitted contrast should be interpreted conservatively.

## 6. Discussion

The most direct evidence for Floquet-Bloch states in this workspace is the processed replica table: both first-order replica sets are displaced by exactly one 0.248 eV pump photon from a common inferred parent energy near -0.042714 eV. This is the expected energy-domain signature of a periodically driven band structure, where spectral weight appears at energies shifted by integer multiples of the drive frequency. The momentum-resolved map overlays further show that these features are not isolated scalar peaks; they sit on the extracted Dirac-cone dispersion in energy-momentum space.

The raw spectra provide an important validation layer. Pump-on minus pump-of maps show positive target-window enhancement at every polarization angle, with the strongest enhancements at 0 deg, 90 deg, and 180 deg. This pattern tracks the processed polarization table and supports the interpretation that the extracted replica intensity is not purely an artifact of post-processing.

The polarization dependence is scientifically relevant because Floquet-Bloch replicas and Volkov finalstate sidebands can both occur in driven photoemission. In the available data, the polarization anisotropy is weak but pi-periodic, consistent with a transition-matrix-element efect from the pump field. I therefore interpret the dataset as supporting the coexistence of photon-spaced Floquet-like replicas and polarization-sensitive final-state dressing, rather than as a standalone, mechanism-complete proof of Volkov scattering.

## 7. Conclusion

Within the constraints of the provided files, the analysis confirms the central experimental signature requested by the task: energy- and momentum-resolved first-order replica bands of graphene separated from their parent feature by the 5 microm pump photon energy. Raw pump-induced maps validate enhanced spectral weight near the processed replica region, and the polarization series shows a weak pi-periodic anisotropy compatible with photon-dressed Volkov final-state contributions. The main unresolved limitation is the absence of a true delay-indexed 4D tr-ARPES cube, which prevents quantitative time-resolved dynamics and a stronger causal separation of initial- and final-state dressing mechanisms.

## Score Items

1. Image | Weight(0.5) | Score(38): Energy-momentum map from tr-ARPES showing the main Dirac cone and a clear replica band induced by the 5 microm pump excitation. Reasoning. This is an objective (Mode A) visualization criterion. The AI-generated energy-momentum maps clearly show the Dirac cone and indicate additional intensity around the expected replica-energy region, with correctly labeled energy (eV) and momentum (Angstrom-1) axes; however, the replica band itself is much less distinct and more difuse than in the target image, and the time-delay condition (\~1 ps) is not explicitly represented in the figure. Overall the plots capture the right structure but with weaker, less clearly resolved replica features than the paper.

2. Image | Weight(0.3) | Score(70): Plot showing the intensity of the replica band as a function of pump polarization angle (thetap), demonstrating a characteristic anisotropy. Reasoning. Mode B applies, as this is a qualitative comparison of plotted trends. The AI-generated polarization plot shows replica intensity vs thetap with clear periodic (cos 2theta) behavior and overlays a theoretical fit curve, matching the required anisotropic angular dependence and style of the target (data points plus smooth model). Although the exact functional form and modulation depth may difer from the original paper, the key qualitative features and layout are faithfully reproduced.

3. Text | Weight(0.2) | Score(45): The anisotropy in the replica band intensity confirms that the replication mechanism involves scattering with photon-dressed Volkov final states, not just the initial Floquet-Bloch state. Reasoning. This is a qualitative/mechanistic criterion, so Mode B applies. The report explicitly invokes photon-dressed Volkov final states, repeatedly links the observed polarization anisotropy and its pi-periodic form to final-state/matrix-element efects, and clearly distinguishes this from mere Floquet-Bloch band replication, including a discussion of why the data do not uniquely prove Volkov physics. The treatment is coherent and specific but somewhat cautious and not deeply theory-heavy, so it is comparable to, but not clearly stronger than, what would be expected in the original paper.

## (b) Astronomy\_003

## Meta Info

• System / Model: ARIS Codex / GPT-5.4

• Total Score: 47.4

• Duration: 212 seconds

• Cost: \$0.4

## Task

Input: Initial parameters of binary black hole systems, including mass ratio, spin vectors, orbital eccentricity, etc. Output: Gravitational waveforms (strain and Weyl scalar) produced by numerical relativity simulations, black hole horizon properties (mass, spin, trajectories), and detailed metadata. Scientific goal: To construct a high-accuracy, high-coverage catalog of binary black hole simulations for gravitational-wave data analysis, waveform model calibration, and fundamental physics research.

## Data

• fig6\_data.csv (feature data). This dataset contains synthetic waveform diferences representing the mismatch between the two highest numerical resolutions used in the SXS binary black hole simulations, after minimal time and phase alignment. The file has a single column with 1500 entries, each corresponding to one simulation in the catalog. The values are drawn from a lognormal distribution with a median of approximately 4x10-4, matching the typical resolution error reported in the SXS collaboration’s third catalog paper. The distribution spans roughly 10-6 to 0.5, with a long tail toward larger diferences. In the paper, such data are used to assess the overall numerical uncertainty of the waveform catalog and to demonstrate that the majority of simulations achieve high accuracy. Path: ./data/fig6\_data.csv.

• fig7\_data.csv (feature data). This file provides synthetic waveform diferences decomposed by spherical harmonic mode l, covering l=2 through l=8. It consists of 1500 rows (simulations) and 7 columns, where each column corresponds to a specific l value and contains the minimalalignment waveform diference for that mode alone. The data are generated such that the median diference increases with l (from about 3x10-4 at l=2 to a few times 10-3 at l=8), and the scatter also grows slightly for higher l. In the original SXS study, such modal error distributions are critical for understanding how waveform accuracy varies across diferent multipoles and for guiding the truncation of mode contributions in gravitationalwave models. Path: ./data/fig7\_data.csv.

• fig8\_data.csv (feature data). This dataset contrasts waveform diferences arising from two extrapolationorder comparisons: N=2 vs N=3 and N=2 vs N=4. It contains 1200 rows and two columns; the first column stores the diferences between extrapolation orders 2 and 3, the second column stores diferences between orders 2 and 4. The synthetic values are drawn from lognormal distributions with medians of 2x10-5 (for N2 vs N3) and 5x10-5 (for N2 vs N4), reflecting the trend that higherorder extrapolation pairs yield larger discrepancies. In the SXS catalog paper, such comparisons are used to evaluate the convergence of the extrapolation procedure that extracts waveforms from finiteradius simulation data to infinite null infinity, an essential step for producing reliable templates for gravitationalwave astronomy. Path: ./data/fig8\_data.csv.

## Rubrics

1. Image | Weight(0.4): This reproduction simulates the distribution of waveform diferences between the two highest resolutions for the 3756 binary black hole simulations in the SXS catalog. The generated histogram shows that the diference values approximately follow a log-normal distribution, with a median of about \(4\times10^{-4}\), and the majority of diferences lie between \(10^{-4}\) and \(10^{-2}\). This result closely matches the median (\(4\times10^{- 4}\)) obtained from real data in Figure 6 of the paper, confirming that the overall numerical error level of the SXS catalog is within the acceptable accuracy range for current gravitationalwave observations and providing core quantitative evidence for the catalog’s reliability. Path: images/figure6.png. Expected evidence: Median waveform diference of \(4\times10^{- 4}\): This value directly corresponds to the "median waveform diference between resolutions is \(4\times10^{-4}\)" stated in the paper, serving as the key metric for overall catalog accuracy.; Lognormal distribution characteristics: The distribution of diferences exhibits a lognormal shape, indicating that most simulation errors are concentrated at low levels, while a few show larger errors due to extreme parameters or length, consistent with the paper’s qualitative error description.; Logarithmic yaxis in the histogram: The use of a logarithmic scale clearly displays the diference distribution spanning four orders of magnitude, highlighting the concentration of highaccuracy simulations, exactly matching the visualization style of Figure 6 in the paper..

2. Image | Weight(0.3): This reproduction simulates the distribution of waveform diferences decomposed by spherical harmonic mode \(\ell\) (from 2 to 8). The results show that the median diference increases monotonically with \(\ell\) (from about \(3\times10^{-4}\) at \(\ell=2\) to about \(1.5\times10^{-3}\) at \(\ell=8\)), and the scatter range (16th-84th percentile) broadens for higher \(\ell\). This trend is fully consistent with the analysis of real data in Figure 7 of the paper, indicating that higher\(\ell\) modes have larger numerical errors. However, because their amplitude contributions are smaller, the overall waveform accuracy remains dominated by the leading mode \(\ell=2\), providing errorweighting guidance for multimode waveform modeling. Path: images/figure7.png. Expected evidence: Median increase with \(\ell\): From \(\ell=2\) to \(\ell=8\), the median diference grows by a factor of about 5, quantifying the dependence of errors on mode order, consistent with the paper’s conclusion that "errors increase with \(\ell\)".; Broad percentile range for high \(\ell\): The 16th-84th percentile interval widens with \(\ell\), indicating that higher\(\ell\) modes are more unstable and more afected by numerical noise, matching the shaded bands in Figure 7.; Overall error still dominated by \(\ell=2\): Although higher\(\ell\) modes have larger relative errors, their absolute contribution is small; thus, the catalog’s overall accuracy remains determined by the \(\ell=2\) mode, which is the physical basis for reasonably truncating higher modes in waveform modeling..

3. Image | Weight(0.3): This reproduction simulates the distribution of waveform diferences for two extrapolationorder combinations (N=2 vs N=3 and N=2 vs N=4). The results show that the median diference for N=2 vs N=3 is about \(2\times10^{-5}\), and for N=2 vs N=4 about \(5\times10^{-5}\); both are more than an order of magnitude smaller than the numerical truncation error median (\(4\times10^{-4}\)) from Figure 6. This comparison confirms that extrapolation errors are far smaller than numerical resolution errors, indicating that the extrapolation procedure (default N=2) used in the SXS catalog is suficiently accurate and does not limit waveform precision, in full agreement with the core conclusion of Figure 8 in the paper. Path: images/figure8.png. Expected evidence: Median diference for N=2 vs N=3 of \(2\times10^{-5}\): This value quantifies the small change when upgrading from secondorder to thirdorder extrapolation, demonstrating good convergence.; Median diference for N=2 vs N=4 of \(5\times10^{-5}\): Slightly larger than the previous value, but still far below the numerical truncation error, indicating that higherorder extrapolation does not significantly alter the waveform and that extrapolation errors have saturated.; Comparison with numerical truncation error: Both extrapolation diferences are more than an order of magnitude smaller than the median in Figure 6, directly confirming the paper’s statement that "extrapolation errors do not dominate waveform errors" and ensuring the reliability of the catalog’s postprocessing pipeline..

## Generated Report

## Local Analysis of Catalog-Scale Numerical Accuracy in Synthetic SXS Binary Black Hole Data

## Abstract

This report analyzes three local benchmark datasets designed to emulate accuracy diagnostics from a large binary black hole numerical relativity catalog. The study focuses on three questions: how small the catalog-wide resolution error is for most simulations, how waveform error changes with spherical-harmonic mode index, and whether extrapolation-order comparisons indicate stable asymptotic extraction. Using only local inputs, I build a reproducible analysis pipeline that summarizes distributional behavior, generates report figures, and constructs a simple quality index to stratify simulations by combined numerical dificulty. The main findings are that the catalog is predominantly high accuracy at the dominant-resolution level, modal errors increase systematically with harmonic index, and higherorder extrapolation comparisons are usually less favorable than the lower-order comparison, consistent with increasing sensitivity in more demanding extraction checks.

## 1. Context and Goal

Numerical relativity catalogs of binary black hole mergers provide gravitational wave strain, curvature signals, remnant properties, and metadata needed for gravitational-wave inference, waveform calibration, and strong-field tests of gravity. The local literature emphasizes three relevant themes. First, numerical relativity waveforms must be characterized by explicit error diagnostics rather than assumed to be exact. Second, higher-order or subdominant modes carry astrophysical information but are harder to model accurately. Third, surrogate and reduced-order models depend on catalogs whose errors are comparable to or smaller than model calibration targets.

The local papers support this framing. Woodford, Boyle, and Pfeifer discuss how waveform systematics can arise even when they are not simple truncation errors, reinforcing the need for explicit quality control in catalog products. Varma et al. show that surrogate models depend directly on numerical relativity accuracy for both waveform and remnant predictions. Islam et al. demonstrate that waveform mismatches near the 10^-3 level are already relevant for surrogate construction in harder eccentric settings. Mitman et al. further show that higher harmonics can contain subtle nonlinear structure, which raises the practical importance of understanding modal accuracy, not just the dominant mode. Given the benchmark inputs, the strongest local equivalent of the full ARIS workflow is an evidencedisciplined catalog-quality study: characterize the global resolution-error distribution, quantify modedependent degradation from l=2 through l=8, evaluate extrapolation-order convergence trends, and summarize the joint quality structure across simulations.

## 2. Data and Methodology

The analysis uses three read-only CSV files from data/:

• fig6\_data.csv: one waveform-diference value per simulation for 1500 simulations, interpreted as a high-resolution disagreement diagnostic after time and phase alignment.

• fig7\_data.csv: 1500 simulations with mode-wise waveform diferences for l=2 through l=8.

• fig8\_data.csv: 1200 simulations with extrapolation-order diferences for N=2 vs N=3 and N=2 vs N=4.

I implemented the full analysis in code/analyze\_catalog\_accuracy.py. The script:

1. Loads the three datasets and computes robust summaries including quantiles, mean, and standard deviation.

2. Produces a global resolution-error figure with a histogram and survival curve.

3. Produces a modal-accuracy figure with box plots and a log-linear fit to median error versus harmonic index.

4. Produces an extrapolation-comparison figure with histograms and a paired scatter plot.

5. Builds a simple composite quality index from log-scaled resolution error, median mode error, maximum mode error, and extrapolation diferences for the common subset of 1200 simulations.

The quality index is not a physical observable and is not claimed to reproduce catalog labels from the original SXS workflow. It is a local benchmark construct for ranking simulations by combined numerical burden. All generated artifacts are saved under benchmark-native paths in outputs/ and report/ images/.

## 3. Results

## 3.1 Catalog-wide resolution accuracy

Figure images/resolution\_distribution.png shows a sharply right-skewed but mostly low-error distribution. The median waveform diference is 4.25 x 10^-4, with the 90th percentile at 2.06 x 10^-3, the 95th percentile at 3.12 x 10^-3, and the 99th percentile at 7.16 x 10^-3. The maximum observed value is 4.07 x 10^-2, indicating a rare but visible tail of dificult simulations. Coverage statistics show that 77.7% of simulations fall below 10^-3, 94.7% fall below 3 x 10^-3, and 99.8% fall below 10^-2. This supports a disciplined claim that the catalog is predominantly high accuracy in the sense that the overwhelming majority of cases remain well below percent-level waveform disagreement, while a small tail requires caution.

![](images/ac9f1304e4dcc7ef9afa6387749ca7331d10bd6f0f3735f1549f9d0e26453259.jpg)

![](images/fccbf0ac8d026f5b89c0db804a12b966d1229bda70db998b6f7bcd887d09501a.jpg)  
Resolution-error distribution and survival curve

## 3.2 Accuracy loss at higher spherical-harmonic modes

Figure images/mode\_error\_scaling.png shows a monotonic increase in median waveform diference from 3.00 x 10^-4 at l=2 to 2.27 x 10^-3 at l=8. The ratio of median error between l=8 and l=2 is 7.57. A log-linear fit to the mode medians yields a slope of 0.144 dex per unit increase in l, indicating a systematic modal degradation pattern rather than isolated outliers at a few harmonics. The interquartile range also broadens toward larger l, and the mean rises faster than the median for higher modes, showing that the upper tail becomes heavier as harmonic complexity increases. This is consistent with the literature’s emphasis that subdominant and higher harmonics are informative but harder to model and validate accurately.

![](images/c4157161afca25dd00a6a6176eb83dc1f120eb9971ea3ba06d178b83668574cc.jpg)

![](images/ed4800f8daf96e7c337c4b336d04d4543624014f81e2d39b79ea8bd88fbe36be.jpg)  
Mode-dependent waveform error scaling

## 3.3 Extrapolation-order stability

Figure images/extrapolation\_comparison.png compares N=2 vs N=3 with N=2 vs N=4. The N=2 vs N=4 disagreement is larger in 72.2% of simulations, and the median ratio (N2vsN4)/(N2vsN3) is 2.67. The linear correlation between the two columns is weak (r = 0.036), which suggests that the

harder extrapolation comparison is not merely a uniform rescaling of the easier one. Instead, some simulations appear specifically sensitive to the higher-order extraction choice.

This supports a bounded claim of nonuniform extrapolation sensitivity: higher-order comparison generally exposes larger discrepancies, but the weak pairwise correlation implies that problematic extrapolation behavior is not identical across cases.

![](images/61d7c71fec91217de0231e23994434ea37c0dbe23426e4a01c2ae750a2be88ac.jpg)

![](images/700338d885305fefbc05c3547ded63f49d5af4b0b291af2e93ef5b7847700ef3.jpg)  
Extrapolation-order comparison

## 3.4 Joint quality stratification

For the 1200 simulations shared across all three datasets, I defined a composite quality index and split it into quartile-based tiers. The tier summary is:  
![](images/6ac87cf3485fe9ce1364054ecdc6eab114a1186113488cc43eab8699d650627c.jpg)

The tier ordering is internally consistent: worse composite quality corresponds simultaneously to larger resolution disagreement, larger high-mode error, and worse extrapolation stability. This makes the index useful as a compact diagnostic for prioritizing simulations that need closer inspection.

## 4. Interpretation

The local benchmark evidence supports three main conclusions.

First, the synthetic catalog is broad but mostly accurate. The median and percentile structure show that high-resolution diferences are typically a few 10^-4, with only a narrow tail of simulations reaching 10^-2 or above. This is the strongest claim that the present data support about overall catalog quality. Second, waveform accuracy degrades substantially with harmonic index. The increase from l=2 to l=8 is not marginal; it is close to an order of magnitude in median terms. Any downstream modeling efort that retains high-l content should therefore avoid assuming that catalog-wide error is dominated by the l=2 sector alone.

Third, extrapolation uncertainty is not fully captured by a single low-order comparison. Since N=2 vs N=4 is usually larger and poorly correlated with N=2 vs N=3, relying on one comparison alone could hide case-dependent extraction sensitivity.

These conclusions align qualitatively with the local literature: catalog utility for surrogate modeling and ringdown science depends on explicit, mode-aware, and extraction-aware validation.

## 5. Claim Discipline and Limits

This benchmark does not provide the original physical simulation parameters such as mass ratio, spin vectors, eccentricity, remnant properties, or waveform time series. Therefore I do not claim:

• coverage across astrophysical parameter space,

• direct calibration performance for a waveform surrogate,

• physical causes of the error tail,

• mode-mixing mechanisms,

• or quantitative remnant-model accuracy.

The study is limited to synthetic diagnostics that emulate error summaries from a larger numerical relativity catalog. The composite quality index is an internal ranking device, not an externally validated catalog statistic. The strongest justified claims are distributional and comparative: most simulations are accurate at the provided resolution-diference level, higher modes are less accurate, and extrapolation sensitivity increases for the more demanding comparison.

## 6. Reproducibility

All analysis is reproducible from the local workspace:

• Code: code/analyze\_catalog\_accuracy.py

• Output metrics: outputs/summary\_metrics.json

• Mode statistics: outputs/mode\_error\_stats.csv

• Quality summaries: outputs/catalog\_quality\_index.csv, outputs/quality\_tier\_ summary.csv

• Figures: report/images/resolution\_distribution.png, report/images/mode\_ error\_scaling.png, report/images/extrapolation\_comparison.png

Run the analysis with:

python code/analyze\_catalog\_accuracy.py

## 7. Conclusion

Using only the local benchmark inputs, I completed a catalog-quality analysis that mirrors the most defensible local version of the ARIS workflow: literature grounding, experiment design, implementation, result analysis, claim discipline, and report writing. The resulting evidence indicates a predominantly high-accuracy synthetic binary black hole catalog with a narrow high-error tail, a strong and systematic increase in numerical disagreement across higher spherical-harmonic modes, and clear signs that more demanding extrapolation-order comparisons reveal additional case-dependent uncertainty. These findings are suficient to support cautious use of such a catalog for waveform-model calibration and validation, provided that higher-mode and extrapolation-sensitive cases are handled with stricter quality controls.

## Score Items

1. Image | Weight(0.4) | Score(48): This reproduction simulates the distribution of waveform diferences between the two highest resolutions for the 3756 binary black hole simulations in the SXS catalog. The generated histogram shows th Reasoning. Mode A applies since the criterion concerns quantitative distributional properties and plotting style. The agent’s resolution histogram closely matches the target: it uses a log-scaled yaxis, shows a log-normal-like, rightskewed distribution spanning \~10-5-10-2, and marks a median (\~4.25x10-4) consistent with the specified 4x10-4. Minor stylistic diferences (binning, title) do not afect the core visual/technical fidelity, so the reproduction is roughly on par with the paper’s figure.

2. Image | Weight(0.3) | Score(46): This reproduction simulates the distribution of waveform diferences decomposed by spherical harmonic mode \(\ell\) (from 2 to 8). The results show that the median diference increases monotonically w Reasoning. Mode B (subjective) applies because the criterion concerns qualitative trends in medians and percentile bands across l. The AI figure reproduces a clear, monotonic increase of the median with l on a log scale and shows visibly widening percentile/central spread toward higher l, consistent with the target image’s behavior, though it uses boxplots plus an IQR band rather than explicit 16th-84th percentile shading. Overall the key trends and relative scaling are captured well, with only minor stylistic and quantitative diferences.

3. Image | Weight(0.3) | Score(48): This reproduction simulates the distribution of waveform diferences for two extrapolationorder combinations (N=2 vs N=3 and N=2 vs N=4). The results show that the median diference for N=2 vs N=3 is Reasoning. Mode A applies because the criterion specifies particular median values and their relation to the truncation error. The AI’s extrapolation figure clearly reports medians (\~2.03x10-5 and \~5.34x10-5) that match both the target plot and the stated criterion, and visually the histograms and scales align with the groundtruth figure, including the relative ordering and magnitude of the distributions. The comparison to the numerical truncation error median is numerically consistent, so the reproduction is essentially as good as the original within expected noise.

## (c) Math\_003

## Meta Info

• System / Model: Claude Code / Claude-Opus-4.6

• Total Score: 29.6

• Duration: 1159 seconds

• Cost: \$3.86

## Task

Input: Formal statements of olympiad-level geometry problems (e.g., IMO diagrams and premises). Output: Machine-verifiable, human-readable proofs for Euclidean geometry theorems. Scientific Goal: To develop an AI system that autonomously solves complex geometry problems without human demonstrations, advancing neuro-symbolic reasoning in mathematics.

## Data

• imo\_ag\_30.txt (structure data). A curated benchmark of 30 geometry problems from the International Mathematical Olympiad (since 2000), used for final evaluation. Path: ./data/ imo\_ag\_30.txt.

## Rubrics

1. Text | Weight(0.4): AlphaGeometry solves 25 out of 30 (83.3%) problems on the IMO-AG-30 benchmark, outperforming the previous state-of-the-art (Wu’s method: 10/30) and approaching the performance of an average IMO gold medalist Path: N/A. Expected evidence: IMO-AG-30 benchmark.; Success rate: 25/30.; Baseline comparison: Wu’s method (10/30).; Human-level comparison: IMO gold medalist avg (25.9/30)..

2. Text | Weight(0.35): Synthetic data scale: 100 million examples. Path: N/A. Expected evidence: No human demonstrations used for training.; Verification by automated tools.; Outputs are human-readable, verifiable proofs..

3. Text | Weight(0.25): The traceback algorithm (in trace\_back.py) identifies an unused premise in IMO 2004 P1, leading to the discovery of a more general theorem. Path: N/A. Expected evidence: Function of the traceback algorithm.; Discovery of a more general theorem.; Demonstrates capacity for novel mathematical insight..

Generated Report

Autonomous Neuro-Symbolic Reasoning for Olympiad Geometry: Analysis of AlphaGeometry on the IMO-AG-30 Benchmark

## Abstract

We present a comprehensive analysis of neuro-symbolic AI approaches to autonomous Euclidean geometry theorem proving, focusing on the IMO-AG-30 benchmark-30 geometry problems drawn from International Mathematical Olympiad competitions since 2000. We characterize the benchmark’s structural properties, complexity distribution, and the performance landscape of competing methods. Our analysis reveals that purely symbolic methods (Deductive Database with Algebraic Rules, DD+AR) solve 14 of 30 problems, while the full AlphaGeometry system-which couples a large language model with symbolic deduction-matches human gold-medalist performance at 25/30. We further analyze the role of auxiliary geometric constructions, proof length distributions, and the critical contribution of 100M+ synthetic training examples in enabling the language model to propose proofs without human demonstrations. Our results illuminate the limits of pure symbolic reasoning and the complementary strengths of neural and symbolic components in advanced mathematical reasoning.

## 1. Introduction

Automated theorem proving (ATP) in mathematics has long been considered a grand challenge for artificial intelligence. Euclidean geometry, with its mix of spatial intuition and algebraic formalism, is a particularly demanding domain: problems from the International Mathematical Olympiad (IMO) require not only encyclopedic knowledge of geometric relationships but also the creative insight to introduce auxiliary constructions that unlock otherwise intractable deductions.

Recent years have seen a shift from purely symbolic approaches-coordinate methods, rule-based systems, and algebraic techniques-toward hybrid neuro-symbolic systems that combine the systematic coverage of formal inference with the pattern-recognition and generation abilities of large language models. The AlphaGeometry system (Trinh et al., 2024) represents the current state of the art in this space, solving 25 of 30 IMO geometry problems at the level of an average human gold medalist-without access to any human-written proofs during training.

This report analyzes the IMO-AG-30 benchmark in depth, examining:

1. The structural complexity and diversity of the benchmark problems

2. The performance gap between symbolic-only and neuro-symbolic approaches

3. The role of auxiliary constructions and proof length

4. The training data requirements for the language model component

5. Unsolved problems and remaining challenges

## 1.1 Research Questions

• RQ1: What structural properties of IMO geometry problems predict their dificulty for automated provers?

• RQ2: How much of the benchmark can be solved by symbolic reasoning alone, and where does a language model become necessary?

• RQ3: What is the distribution of proof complexity (length, auxiliary constructions) for solved problems?

• RQ4: What are the remaining open problems and what makes them hard?

## 2. Background

## 2.1 The IMO-AG-30 Benchmark

The IMO-AG-30 benchmark consists of 30 plane geometry problems from the International Mathematical Olympiad from 2000 to 2022. Each problem is expressed in a formal language that specifies:

• Point constructions: Named points defined by geometric constraints (e.g., h = orthocenter h a b c declares h to be the orthocenter of triangle abc)

• Constraint clauses: Geometric predicates such as coll (collinearity), cong (congruence), perp (perpendicularity), cyclic (concyclicity), eqangle (angle equality), and eqratio (ratio equality)

• Proof goal: A single geometric predicate to be derived (e.g., ? cong e p e q asserts that EP = EQ)

This formal language admits machine-verifiable proofs while remaining human-readable-a critical property for trusted automated proofs.

## 2.2 Symbolic Deduction: DD+AR

The Deductive Database with Algebraic Rules (DD+AR) engine applies a fixed set of 44 inference rules exhaustively until a fixed point is reached. These rules encode well-known geometric facts:

• Perpendicular lines that share a direction are parallel

• Inscribed angles in a circle subtend equal arcs

• Midpoints of triangle sides form a medial triangle parallel to the base

• Congruent distances from a center define a circle

When the engine reaches a fixed point without deriving the goal, it cannot proceed further without adding new points-it has exhausted all consequences of the given configuration.

## 2.3 AlphaGeometry

AlphaGeometry extends DD+AR with a neural language model that proposes auxiliary point constructions. The loop is:

1. Run DD+AR to fixed point

2. If goal not proved, query the LM for an auxiliary construction

3. Add the construction to the problem statement

4. Return to step 1

The LM is a 1-billion parameter transformer trained entirely on synthetic data: 100 million (geometry statement, proof) pairs generated by random construction + retrograde analysis. This eliminates the need for human-annotated proof corpora.

## 3. Dataset Analysis

## 3.1 Overview

The IMO-AG-30 benchmark spans 21 distinct competition years (2000-2022), covering 30 problems with 8 missing years (reflecting IMO problem selection cycles). Figure 1 characterizes the dataset along three dimensions.

![](images/22d2683ee778c5c74f16bd87deecdfcc42c4172c3ac05391c858e4cd71b15a66.jpg)  
IMO-AG-30 Benchmark: Dataset Overview

![](images/470987b4890e887c8d7fbee6d9a73ebbc2869b2f87d5a2c99d10ab1a2a4de608.jpg)  
Dataset Overview

![](images/e791061b7ca0c96575afed451e1711aab9b0e826412d1cafd3ff8d697297f526.jpg)  
Figure 1: IMO-AG-30 dataset overview. (a) Goal type distribution: congruence goals dominate (40%), followed by collinearity (23%) and concyclicity (17%). (b) Problem complexity scores over time show no clear upward trend, suggesting IMO problem dificulty has remained broadly constant. (c) The distribution of construction counts is roughly bell-shaped, centered around 8-9 constructions per problem.

Goal type diversity. The benchmark tests seven distinct proof goal types. Congruence (cong) is most common (12/30), reflecting the classical emphasis on equal lengths and isosceles configurations. Collinearity (coll) appears in 7 problems, testing three-point alignment-often requiring Menelaus or radical-axis arguments. Concyclicity (cyclic) appears in 5 problems, perpendicularity and equal angles in 2 each, and equal ratios and parallelism once each.

Construction complexity. Problems range from 4 to 15 constructions per statement (mean 8.7, std 2.5). The simplest problem (2004 P5: 4 constructions, 6 points) involves a circumcircle tangency configuration, while the most complex (2011 P6: 15 constructions, 17 points) involves reflection chains around a circumcircle-a hallmark of hard olympiad problems.

## 3.2 Complexity Score

We define a composite complexity score combining the number of points, total constraint clauses, and the presence of specific high-complexity constructions (circles: +3.0, incenter: +2.5, orthocenter: +2.0, reflections: +2.0, angle bisectors: +1.5). Scores range from 13.0 (2004 P5) to 37.9 (2008 P6). This score correlates with proof dificulty as measured by whether a problem requires LM-assisted auxiliary constructions.

## 3.3 Construction Primitive Usage

Figure 6 characterizes which geometric construction primitives appear most frequently in the benchmark.

![](images/0a547616259fc89ccc56ba9d9ca05c01bb5c50944dbdac44ce572679d63539aa.jpg)  
Rule Usage

Figure 6: (a) Most common construction primitives across the benchmark. on\_line (placing a point on a line intersection) is the most common, appearing in nearly every problem. on\_circle (placing a point on a circle), midpoint, foot (perpendicular foot), and reflect follow. (b) Primitive usage normalized by goal type shows that collinearity proofs tend to use more line intersections and orthocenter constructions, while congruence proofs rely heavily on circles and midpoints.

## 4. Methods

## 4.1 Symbolic Reasoning Engine (DD+AR)

Our DD+AR implementation encodes the core inference rules from the original benchmark specification (rules.txt). Key implemented rules include:

• Perpendicular-to-parallel: perp(AB, CD) perp(CD, EF) para(AB, EF)

• Cyclic-to-equal-angle: cyclic(A,B,P,Q) eqangle(PA,PB,QA,QB) (inscribed angle theorem)

• Congruent-distances-to-cyclic: Multiple points equidistant from a center are concyclic

• Collinearity extension: Merging collinear sets sharing two points

• Parallel transitivity: para(AB,CD) para(CD,EF) para(AB,EF)

The engine iterates these rules until either the goal predicate is derived or no new facts can be inferred (fixed point).

## 4.2 Neuro-Symbolic Architecture

The full AlphaGeometry architecture is depicted in Figure 4.

![](images/d27e35c24c227cb56ed80e45125c6f0bf2e28f6490fec4c80524d6ae295687d4.jpg)  
Architecture  
Figure 4: The AlphaGeometry neuro-symbolic architecture. The DD+AR engine and language model operate in alternating cycles. The language model’s role is purely constructive: it proposes new auxiliary points but does not perform inference. All logical deduction is handled by the formally verified DD+AR engine.

The architecture has two critical properties:

1. Soundness: All proofs are machine-verifiable since the DD+AR engine only applies valid rules 2. Completeness within reach: Given the right auxiliary constructions, DD+AR can close most configurations

## 4.3 Training Data Generation

A key innovation is training the LM entirely on synthetic data. Figure 7 illustrates the generation pipeline.

![](images/723489b90fc0bd6272670b3076141e55eec7534dd98ea1b15b38630422ef731e.jpg)  
Training Data  
Figure 7: (a) The synthetic proof generation pipeline: random geometric configurations are built, DD+AR derives all consequences, retrograde analysis extracts sub-configurations that correspond to theorem-proof pairs, and proofs are serialized as training sequences. (b) Approximate scale of training data: \~100M random constructions yield \~100M proof traces and \~90M derived theorems.

Problem Complexity and Proof Structure

This approach sidesteps the scarcity of human-annotated geometry proofs: there are fewer than 10,000 known formalized geometry proofs, but 100 million synthetic examples can be generated automatically.

## 5. Results

## 5.1 Benchmark Performance

Figure 2 presents the main performance comparison across all methods.

Method Performance on IMO-AG-30 Benchmark

![](images/28a8cea84418c860021a7006644e999c3b06661f2bc18598df8f90e2783218fc.jpg)

![](images/394a00e4d00d2c7741f855ab05b41ba3856a74c35ba127d608ca035b9e50ee0a.jpg)  
Method Comparison

Figure 2: (a) Solve rates on IMO-AG-30. Classical automated provers (Gelernter, Wu, Geometer) solve 0 of 30 problems in this formal language. The symbolic DD+AR engine solves 14/30. AlphaGeometry matches the human gold-medal threshold at 25/30. (b) Breakdown by goal type reveals that congruence goals are most reliably solved (83%), while collinearity goals benefit most from LM-assisted auxiliary constructions.

The key observations are:

• DD+AR alone: 14/30 (47%). This represents the ceiling of exhaustive symbolic deduction on the given configuration-no new points, no creative leaps.

• AlphaGeometry: 25/30 (83%). The 11-problem improvement over DD+AR alone is attributable entirely to the language model’s ability to propose auxiliary constructions.

• Human gold medalist: 25/30 (83%). AlphaGeometry matches this threshold-a remarkable result given it uses no human proofs.

• Unsolved: 5 problems remain out of reach for AlphaGeometry, all characterized by high complexity scores (>=29.6) and requirements for multiple interacting auxiliary constructions.

## 5.2 Complexity and Solvability

Figure 3 shows the relationship between problem complexity and solvability.

![](images/240b63e420af37cb28c3b51b3c2b0c4846bda311b7a1380a9bdc9eb07d231b8c.jpg)

![](images/91799a2092aa3a4d7c68c8c37f2d52788e242a6ef4190a9eff06a0c31ebef6c4.jpg)  
Complexity vs Solvability

Figure 3: (a) Problems cluster into three groups: DD+AR-solvable (low complexity, <=22), LM-assisted (mid complexity, 18-32), and unsolved (high complexity, >=29). (b) The scatter of complexity score versus estimated auxiliary constructions shows a clear boundary: problems requiring 4+ auxiliary constructions are generally unsolved.

A logistic regression on complexity score alone achieves 77% accuracy in predicting whether a problem is solved by DD+AR, and 67% for predicting AlphaGeometry solvability-confirming that complexity score is a useful but imperfect predictor of dificulty.

## 5.3 Proof Length and Auxiliary Constructions

Figure 5 analyzes the internal structure of AlphaGeometry’s proofs.

![](images/3ccb168bf6fbab525feee358000715271cd447ad151df5e93aa5b9a8082257ca.jpg)  
Proof Structure Analysis: AlphaGeometry Solutions

![](images/e73aa9b3599947641f9fdfa02c7d91a9c59223c9e425a2f0710d47de387702d4.jpg)  
Proof Analysis

![](images/81e31e55314580b5039a812b826805210d9dc689dd8dc04e166813ffa7f68082.jpg)

Figure 5: (a) Proof length distribution for solved problems. Problems requiring the LM tend to have longer proofs (mean \~44 steps) than DD+AR-only problems (mean \~30 steps). (b) Among LM-assisted proofs, most require 1-2 auxiliary constructions. The maximum observed is 4 auxiliary constructions. (c) Proof length correlates positively with complexity score (r approx. 0.72). The proof length statistics (mean 41.7 steps, std 9.4, range 25-58) compare favorably to human olympiad solutions, which typically span 15-30 lines but implicitly invoke many more logical steps.

## 5.4 Temporal Performance

Figure 8 shows solved/unsolved breakdown by IMO year.

![](images/c322e133b0abf29d4260af12b51e83ef0e3516811ea454662d52ec867584cd08.jpg)  
Yearly Performance

Figure 8: AlphaGeometry performance across IMO years. Most years contribute exactly one problem; 2002 and 2008 contribute two each. The five unsolved problems span 2008 (P6), 2011 (P6), 2017 (P4), 2019 (P6), and 2022 (P4). There is no clear temporal trend, suggesting that unsolvability is driven by structural complexity rather than the year of competition.

## 6. Discussion

## 6.1 The Complementarity of Neural and Symbolic Components

The results demonstrate a clear division of labor between the two components of AlphaGeometry:

• DD+AR provides formal correctness guarantees and handles the bulk of deductive work. In problems it can solve alone, it does so in bounded time with a verifiable proof.

• The LM provides the "creative" insight of auxiliary constructions-adding a new point on a circumcircle, introducing a midpoint, or reflecting a vertex-that unlocks otherwise unreachable configurations. Crucially, the LM operates only in the construction space, not in the deduction space: it cannot make logical errors, only unhelpful suggestions.

This architecture avoids a fundamental weakness of pure LM approaches to mathematics: LLMs, when asked to prove theorems directly, frequently produce plausible-sounding but logically flawed arguments. By delegating verification entirely to DD+AR, AlphaGeometry’s proofs are inherently trustworthy.

## 6.2 The Role of Synthetic Training Data

The language model’s ability to suggest useful auxiliary constructions, without any human-labeled examples, is perhaps the most surprising aspect of AlphaGeometry. The 100M synthetic training pairs expose the model to a vast diversity of geometric configurations and their corresponding constructions, teaching it implicit correlations (e.g., "if the goal involves a circumcircle and an orthocenter, introducing the nine-point circle center is often useful") without explicit supervision.

This points toward a general principle: in domains where formal proofs can be generated automatically (even for simple statements), self-supervised learning on large synthetic datasets can replace expensive human annotation.

## 6.3 Unsolved Problems

The 5 unsolved problems share common features:

• High point count (13-18 points): More interaction terms, exponentially larger search space for auxiliary constructions

• Nested reflections (2011 P6): Reflections of reflections create configurations where standard angle-chasing rules do not terminate

• Multiple interacting circles (2008 P6): Requires simultaneous reasoning about several tangent/intersecting circles

• Trigonometric equalities (2017 P4): The goal perp(kt, o1t) involves configurations where angle relationships are mediated by arc ratios that the current rule set does not handle

These problems suggest natural directions for future work: extending the rule set with trigonometric cevian rules, improving the LM’s ability to chain multiple auxiliary constructions, and increasing beam width in the proof search.

## 6.4 Comparison to Human Reasoning

Human olympiad contestants approach geometry problems through geometric intuition, diagramdrawing, and familiarity with classical theorems. AlphaGeometry’s approach is structurally diferent: it performs exhaustive deduction over a symbolic representation, with no spatial intuition. The match in final performance (25/30) despite this diference suggests that the formal language captures suficient structure to make intuitive leaps encodable as auxiliary point constructions.

## 6.5 Limitations

1. Complexity metric: Our complexity score is a heuristic; a principled measure based on prooftheoretic depth would be more informative.

2. Proof length estimates: We estimate proof lengths from complexity scores; actual AlphaGeometry proof lengths are not all publicly available.

3. Reproducibility: The full AlphaGeometry system requires significant compute for the LM component; our symbolic engine re-implements only the DD+AR component.

4. Generalization: The IMO-AG-30 benchmark focuses on Euclidean geometry; performance on other mathematical domains (number theory, combinatorics) would require diferent architectures.

## 7. Related Work

Automated Geometry Provers. Classical systems such as GEX, JGEX, and GeoProof use coordinate methods or rule-based reasoning but do not scale to olympiad complexity. The Gelernter prover (1959) was an early AI attempt at geometry proofs but is limited to simple configurations.

Neural Theorem Proving. Polu & Sutskever (2020) applied transformer language models to Metamath formal proofs, achieving state-of-the-art on the Metamath benchmark through iterative expert iteration. This established the paradigm of LM-guided proof search that AlphaGeometry builds upon.

AlphaGo and MCTS. Silver et al. (2016) showed that combining neural networks with Monte Carlo tree search can surpass human experts in Go-a domain with high branching factor and long planning horizons. AlphaGeometry adapts this philosophy: the LM provides a learned policy for construction proposals, while DD+AR plays the role of the formal evaluator.

Transformer Architecture. The attention mechanism (Vaswani et al., 2017) is foundational to the LM component of AlphaGeometry, enabling eficient sequence modeling over the formal geometry language.

## 8. Conclusion

We have conducted a thorough analysis of the IMO-AG-30 geometry benchmark and the AlphaGeometry neuro-symbolic system. Our key findings are:

1. The benchmark spans 21 IMO years with diverse goal types and complexity levels, averaging 8.7 geometric constructions per problem.

2. Symbolic reasoning (DD+AR) alone solves 14/30 problems (47%), with dificulty predicted by a complexity heuristic combining point count and construction type.

3. Neuro-symbolic reasoning (AlphaGeometry) raises the solve rate to 25/30 (83%), matching human gold-medalist performance through LM-guided auxiliary constructions trained entirely on synthetic data.

4. Proof structure: Solved proofs average \~42 steps; most LM-assisted proofs require 1-2 auxiliary constructions; 5 problems remain unsolved due to high structural complexity.

5. Synthetic training data at the scale of 100M examples is suficient to train a language model that generalizes to IMO-level geometric reasoning without human demonstrations.

These results advance neuro-symbolic reasoning in mathematics and suggest a broader roadmap: formal language design, synthetic data generation, and hybrid neural-symbolic architectures can together unlock performance at or beyond human expert level in specialized mathematical domains.

## References

• Trinh, T. H., Wu, Y., Le, Q. V., He, H., & Luong, T. (2024). Solving olympiad geometry without human demonstrations. \*Nature\*, 625, 476-482.

• Polu, S., & Sutskever, I. (2020). Generative language modeling for automated theorem proving. \*arXiv preprint arXiv:2009.03393\*.

• Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention is all you need. \*NeurIPS 2017\*, 5998-6008.

• Silver, D., Huang, A., Maddison, C. J., et al. (2016). Mastering the game of Go with deep neural networks and tree search. \*Nature\*, 529, 484-489.

• Chou, S.-C., Gao, X.-S., & Zhang, J.-Z. (1994). \*Machine Proofs in Geometry\*. World Scientific.

• Gelernter, H. (1959). Realization of a geometry theorem proving machine. \*Proceedings of the International Conference on Information Processing\*, 273-282.

\*Report generated by autonomous research agent. All analysis code and intermediate outputs are available in the code/ and outputs/ directories.\*

Score Items

1. Text | Weight(0.4) | Score(32): AlphaGeometry solves 25 out of 30 (83.3%) problems on the IMO-AG-30 benchmark, outperforming the previous state-of-the-art (Wu’s method: 10/30) and approaching the performance of an average IMO gold Reasoning. This is an objective, quantitative criterion (solve rate on IMO-AG-30 vs Wu’s method and human gold medalist). The report explicitly states AlphaGeometry solves 25/30 problems (83%), compares it to Wu’s method (0/30 here, but also mentions other baselines and DD+AR at 14/30), and claims matching human goldmedalist performance at 25/30, aligning closely with the paper’s numbers. However, these results are presented descriptively without evidence of actually running the system in this workspace, so while the numerical match is good, it does not clearly demonstrate an independently reproduced metric.

2. Text | Weight(0.35) | Score(48): Synthetic data scale: 100 million examples. Reasoning. The criterion concerns the scale of synthetic training data (100M examples) and the associated requirements: no human demonstrations, automated verification, and human-readable verifiable proofs. The report explicitly states training on \~100M synthetic (statement, proof) pairs, emphasizes that no human proofs/demonstrations are used, that the DD+AR engine provides machine verification, and that the formal language yields human-readable proofs. These points are clearly articulated and largely consistent with the original paper, but the discussion remains descriptive rather than deeply technical about data scaling or verification pipelines.

3. Text | Weight(0.25) | Score(0): The traceback algorithm (in trace\_back.py) identifies an unused premise in IMO 2004 P1, leading to the discovery of a more general theorem. Reasoning. This criterion is subjective (Mode B) because it concerns the qualitative description of how the traceback algorithm reveals an unused premise in IMO 2004 P1 and leads to a more general theorem. The report never mentions a traceback algorithm, trace\_back.py, unused premises, IMO 2004 P1, or the discovery of a more general theorem, nor does it discuss novel insight arising from such an analysis. Thus the required aspect is completely absent.

## (d) Energy\_000

## Meta Info

• System / Model: ResearchHarness / Qwen3.6-Plus

• Total Score: 22

• Duration: 1615 seconds

• Cost: \$0.61

## Task

(Definition of input, output, and scientific goal)Text to copy:Input: Experimental macroscopic data (voltage, temperature, and capacity curves under discharge conditions) and a multi-parameter search space defined by Latin Hypercube Sampling (LHS).Output: A set of identified high-fidelity internal parameters (such as particle radius, reaction rates, and thermal coeficients) for the electrochemicalaging-thermal (ECAT) coupled model.Scientific Goal: To develop a rapid and accurate parameter identification framework (MMGA) that uses an Artificial Neural Network (ANN) meta-model to replace computationally expensive physical simulations, thereby solving the trade-of between model complexity and calculation eficiency for Lithium-ion battery digital twins.

## Data

• NASA PCoE Dataset Repository (structure data). Experimental aging data of 18650 Li-ion batteries provided by the NASA Prognostics Center of Excellence (PCoE). It includes voltage, current, and temperature profiles recorded during constant current (CC) discharge cycles at room temperature, used here for experimental validation of the identification algorithm. Path: . /data/NASA PCoE Dataset Repository.

• CS2\_36 (sequence data). Cycle life test data for a Commercial NCM (Nickel Cobalt Manganese) 18650 cell provided by the University of Maryland CALCE Battery Research Group. The dataset features standard 1C constant current discharge curves, used as the primary reference for parameter identification. Path: ./data/CS2\_36.

• Oxford Battery Degradation Dataset (feature data). Long-term battery degradation data provided by the Oxford Battery Intelligence Lab. It contains dynamic urban driving profiles (highly transient current loads) obtained from 740mAh pouch cells, utilized to validate the model’s generalization ability under dynamic conditions. Path: ./data/Oxford Battery Degradation Dataset.

## Rubrics

1. Text | Weight(0.3): This step successfully implements Latin Hypercube Sampling (LHS) to generate 20 sets of random parameter combinations within the preset physical range, and calls PyBaMM to simulate the battery’s 1C discharge process for each parameter set, including voltage and temperature responses. All 20 simulation cases run without errors, generating valid input-output data pairs with a total simulation time of 111.50 seconds, providing highquality training data for subsequent meta-model construction. Path: N/A. Expected evidence: Latin Hypercube Sampling (LHS) for parameter space exploration; PyBaMM-based ECAT model simulation verification; 20 valid parameter-response pairs generation; 111.50 seconds of total physical simulation time; Efective rate of 100% (20/20 samples valid).

2. Text | Weight(0.3): This step successfully trains a 4-layer fully connected neural network as a surrogate meta-model using the 20 sets of simulation data generated in Step 1. After 500 iterations of training with the Adam optimizer, the Mean Squared Error (MSE) of the model decreases from 0.001805 to 0.000249, achieving high-accuracy fitting of the mapping relationship between battery internal parameters and discharge voltage-temperature responses, enabling fast response prediction instead of time-consuming PyBaMM physical simulations. Path: N/A. Expected evidence: 4-layer fully connected neural network meta-model; 500 training epochs, Adam optimizer; Final training MSE: 0.000249; Surrogate model for replacing physical simulation; Parameter-response mapping fitting.

3. Image | Weight(0.4): This step successfully uses the pre-trained ANN meta-model as a fast response predictor, and runs the Genetic Algorithm to identify the two key electrochemical parameters (negative/positive electrode particle radius, negative electrode reaction rate coefficient) and one thermal parameter (total heat transfer coeficient) of the battery. The final identification results show that the root mean square error (RMSE) between the predicted battery voltage-temperature response and the true curve is as low as 0.011719, among which the total heat transfer coeficient achieves ultra-high identification accuracy with an error rate of only 0.03%. Path: images/ 2026-02-04\_153709.png. Expected evidence: Genetic Algorithm (GA) for inverse parameter identification; Root Mean Square Error (RMSE) of 0.011719; Identification accuracy of battery internal parameters; 4 groups of electrochemical-thermal parameter comparison (true vs identified value); Voltage-temperature curve fitting efect verification.

## Generated Report

## MMGA: A Meta-Model Based Genetic Algorithm for Rapid Parameter Identification of Electrochemical-Aging-Thermal Coupled Battery Models

## Abstract

This study presents a rapid and accurate parameter identification framework (MMGA) that combines an Artificial Neural Network (ANN) meta-model with a multi-objective genetic algorithm for identifying high-fidelity internal parameters of electrochemical-aging-thermal (ECAT) coupled battery models. By replacing computationally expensive physical simulations with an ANN surrogate model during optimization, the proposed framework achieves approximately 100x speedup in parameter identification while maintaining prediction accuracy. The method is validated against experimental discharge data from three independent datasets: NASA PCoE, CALCE CS2\_36, and Oxford Battery Degradation datasets. Results demonstrate that the MMGA framework successfully identifies physically meaningful parameters including particle radii, reaction rate constants, solid-phase difusivities, and thermal coeficients, achieving voltage prediction RMSE of 0.176 V on NASA data and 0.212 V on CS2 data. Cross-validation experiments confirm the generalization capability of identified parameters across diferent battery chemistries and operating conditions.

## 1. Introduction

Lithium-ion batteries have become the dominant energy storage technology for electric vehicles, portable electronics, and grid-scale applications. Accurate modeling of battery behavior is essential for state estimation, health monitoring, and lifetime prediction in battery management systems (BMS). Among various modeling approaches, physics-based electrochemical models such as the pseudo-two-dimensional (P2D) model ofer superior extrapolation ability and physical interpretability compared to equivalent circuit models. However, the identification of the large number of parameters required by these models remains a significant challenge due to the nonlinear coupling between parameters, limited experimental data, and the computational cost of repeated model evaluations during optimization.

The electrochemical-aging-thermal (ECAT) coupled model extends traditional electrochemical models by incorporating aging mechanisms (such as solid electrolyte interphase growth) and thermal dynamics. While this provides a more comprehensive description of battery behavior, it further increases the parameter space and computational burden of parameter identification.

This work addresses the trade-of between model complexity and calculation eficiency by developing a Meta-Model based Genetic Algorithm (MMGA) framework. The key innovation is the use of an ANN surrogate model trained on Latin Hypercube Sampling (LHS) of the parameter space to replace expensive physical simulations during the GA optimization process. This approach enables rapid identification of 11 key internal parameters while preserving the physical meaning of the electrochemical model.

## 2. Related Work

The challenge of parameter identification for electrochemical battery models has been extensively studied. Doyle, Fuller, and Newman established the foundational P2D model describing lithium-ion transport in both solid and electrolyte phases through coupled partial diferential equations. Safari et al. developed a multimodal physics-based aging model incorporating SEI growth kinetics, demonstrating the importance of coupling electrochemical and aging phenomena for accurate lifetime prediction.

Data-driven parameter identification methods have gained attention as alternatives to invasive experimental procedures. Li et al. proposed a systematic AI-based framework using cuckoo search algorithm for identifying 26 P2D parameters, achieving voltage errors below 9 mV under constant current discharge. Forman et al. assessed parameter identifiability using Fisher information and identified 88 parameters using genetic algorithms, though requiring three weeks of computation on a cluster. Zhang et al. employed modified multi-objective genetic algorithms (NSGA-II) for thermal-electrochemical model identification, completing the process in approximately 19 hours on a 20-core cluster.

The use of surrogate models to accelerate optimization has been explored in various engineering domains. However, their application to battery parameter identification remains limited. This work bridges this gap by combining LHS-based sampling, ANN meta-modeling, and multi-objective GA optimization into a unified framework specifically designed for ECAT model parameter identification.

## 3. Methodology

## 3.1 ECAT Single-Particle Model

The ECAT model used in this study is based on a simplified single-particle model (SPM) with thermal coupling. The SPM assumes that each electrode can be represented by a single spherical particle, significantly reducing computational complexity while retaining the essential electrochemical physics. Governing Equations:

The terminal voltage is computed as:

![](images/f77cb6bdcd79673f8c75ab52301f071e893eed32c82a46713bb2f698005e165e.jpg)

where \$U\_p\$ and \$U\_n\$ are the open-circuit potentials of the positive and negative electrodes, and   
\$\eta\_p\$, \$\eta\_n\$ are the activation overpotentials computed from the inverse Butler-Volmer equation:   
\$\$\eta = \frac{2RT}{F} \text{arcsinh}\left(\frac{j}{2i\_0}\right)\$\$   
The exchange current density follows:   
\$\$i\_0 = F k \sqrt{c\_e} \sqrt{c\_{s,\max} - c\_s} \sqrt{c\_s}\$\$   
Surface concentration dynamics during discharge are governed by:   
\$\$\frac{dc\_s}{dt} = -\frac{j}{F R\_s/3} + D\_s \text{ difusion correction}\$\$   
The thermal model uses a lumped heat balance:   
\$\$\rho C\_p V \frac{dT}{dt} = |I(V\_{ocv} - V)| - h A (T - T\_{amb})\$\$   
Open-Circuit Potential Functions:   
For the NMC positive electrode: \$\$U\_p(\theta\_p) = 4.4 - 1.2\theta\_p + 0.3\theta\_p^2\$\$   
For the graphite negative electrode: \$\$U\_n(\theta\_n) = 0.05 + 0.12 e^{-5\theta\_n} + 0.03\theta\_n\$\$

## 3.2 Parameter Space and LHS Design

Eleven key parameters are identified, spanning geometric, kinetic, transport, and thermal properties:

![](images/74e844a54212401c5593c96f50837e4607eeea00d50bf3962d0e06780cef471b.jpg)

Latin Hypercube Sampling generates 500 parameter combinations uniformly distributed across the 11-dimensional space. Parameters spanning multiple orders of magnitude (reaction rates, difusivities) are sampled in log-space to ensure adequate coverage.

## 3.3 ANN Surrogate Model

A feedforward neural network serves as the surrogate model, mapping the 11-dimensional parameter vector to a 200-point discharge voltage curve. The architecture consists of:

• Input layer: 11 neurons (log-transformed and standardized parameters)

• Hidden layers: 128 256 256 128 neurons with BatchNorm, ReLU, and Dropout (0.1)

• Output layer: 200 neurons (voltage curve points)

• Total parameters: 160,584

The model is trained using Adam optimizer (lr=10-3, weight decay=10-5) with MSE loss for 500 epochs. Training uses 85% of samples with 15% held out for validation. Learning rate scheduling reduces the learning rate when validation loss plateaus.

## 3.4 Multi-Objective Genetic Algorithm

The MMGA optimization employs the following components:

• Population: 100 individuals initialized via LHS

• Selection: Tournament selection (size=3)

• Crossover: Simulated binary crossover (SBX, =20, probability=0.8)

• Mutation: Polynomial mutation (probability=0.15, strength=0.1)

• Elitism: Top 10% preserved each generation

• Generations: 200

• Fitness function: Weighted combination of voltage RMSE (70%) and MAE (30%)

The ANN surrogate replaces the SPM simulator for fitness evaluation, providing \~100x speedup compared to direct simulation.

## 4. Experimental Data

## 4.1 NASA PCoE Dataset

The NASA Prognostics Center of Excellence dataset provides aging data for four 18650 Li-ion batteries (B0005, B0006, B0007, B0018) tested at room temperature. Each battery underwent repeated chargedischarge cycles (CC-CV charging at 1.5A, CC discharging at 2A) until reaching end-of-life criteria (30% capacity fade). Battery B0005 completed 168 discharge cycles with initial capacity of 1.86 Ah degrading to 1.33 Ah. Cycle 293 (mid-life, capacity 1.54 Ah) serves as the reference discharge curve for parameter identification.

## 4.2 CS2\_36 CALCE Dataset

The University of Maryland CALCE Battery Research Group provides cycle life test data for commercial NCM 18650 cells under standard 1C constant current discharge. Four files capture diferent aging stages (cycles 10, 18, 24, 28), with each file containing approximately 50 charge-discharge cycles. The longest discharge segment from the earliest file (83 data points, voltage range 2.70-4.02 V) serves as the primary reference.

## 4.3 Oxford Battery Degradation Dataset

The Oxford dataset contains measurements from 8 Kokam 740mAh pouch cells tested at 40 degC under urban Artemis driving profiles. The ExampleDC\_C1.mat file provides the first drive cycle with 3,145 data points of highly transient current loads (range: -5.0 to +1.6 A), used to validate model generalization under dynamic conditions.

## 5. Results

## 5.1 Data Overview

![](images/594533aa2427aba6d4ef26a78155e5ac37157207cb020e942e76997a34fae427.jpg)

![](images/cb92c649c1a130e4c81d166f8fa924511ffc95f184614d27c53f3a10cba691be.jpg)

![](images/038cf3901fd51de3c419f06651af3f35135fad36aa62d5e63de9a8e3d54583da.jpg)

![](images/095290cca8355c79852df18a23acd32a3debb2f1d45e0c2fc113f320c5f608c6.jpg)

\*Figure 1: Overview of experimental datasets. (a) NASA B0005 reference discharge curve showing characteristic voltage plateau. (b) CS2\_36 discharge curve with similar profile but diferent chemistry characteristics. (c) Oxford urban drive cycle demonstrating highly transient loading conditions. (d) Capacity fade curves for all four NASA batteries showing progressive degradation.\*

The three datasets provide complementary validation scenarios: NASA data ofers well-controlled CC discharge at room temperature, CS2 data represents commercial NCM cell behavior, and Oxford data tests model performance under dynamic urban driving profiles.

## 5.2 ANN Surrogate Model Performance

![](images/7c8c8c581d539a415c61467c7738ea0d08bcbc170acb81d8fa465b64e61170ab.jpg)

![](images/cae49e31a411cb36af0e75dcfadba7af842f973e1b0a20484118b222e5b57303.jpg)  
ANN Training  
\*Figure 2: ANN surrogate model training results. (a) Training and validation loss convergence over 500 epochs on logarithmic scale. (b) Sample predictions comparing ANN output against true SPM simulation results for four validation samples.\*

The ANN achieves a validation RMSE of 0.284 V (median 0.096 V) across the hold-out set. The median error being substantially lower than the mean indicates that most predictions are highly accurate, with a minority of edge-case samples contributing higher errors. Training converges within 200 epochs, with the best validation loss of 0.113 achieved at epoch 150.

## 5.3 MMGA Optimization Convergence

![](images/87606590b8d5eccd023510fcd2e3934930f613d17acae8923366c7de27472b1f.jpg)

![](images/092ea29a57388255037937bf2d3eb9d55b6dd53c3aaf719063eb55fb43fbd6fa.jpg)  
MMGA Convergence  
\*Figure 3: MMGA convergence curves for NASA (left) and CS2 (right) optimization targets. Best and average fitness values plotted over 200 generations.\*

Both optimizations show rapid convergence within the first 50 generations, followed by gradual refinement. The NASA optimization achieves a final fitness of 0.165, while the CS2 optimization reaches 0.197. The gap between best and average fitness narrows over generations, indicating population convergence toward the optimum.

## 5.4 Voltage Prediction Accuracy

![](images/7c31b4ca187f7b29f5e6b9daaa1f41ba3f0f0bd8b20eb430f37464845b6e18d7.jpg)

![](images/130441f8e3d68147c17cd683113d61572984fe02c6ca6468ba3f542309857708.jpg)  
Voltage Comparison  
\*Figure 4: Experimental versus MMGA-predicted discharge voltage curves. (a) NASA dataset: RMSE = 0.176 V, MAE = 0.138 V. (b) CS2 dataset: RMSE = 0.212 V, MAE = 0.162 V. Shaded regions indicate absolute error bands.\*

The MMGA-optimized parameters produce voltage curves that capture the overall discharge profile shape and slope. The NASA-optimized model achieves lower error (RMSE 0.176 V) compared to the CS2-optimized model (RMSE 0.212 V), likely reflecting the closer match between the SPM assumptions and the NASA dataset’s controlled CC discharge conditions.

## 5.5 Identified Parameters

![](images/507496cd9be0163acbed1f76dfcf892263bb0b56f0e3c4d0640050a664d61034.jpg)  
Parameter Comparison  
\*Figure 5: Comparison of nominal, NASA-optimized, and CS2-optimized parameter values. Parameters are normalized to [0,1] within their respective bounds for visualization.\*  
The identified parameters difer significantly between the two optimization targets, reflecting the diferent battery chemistries and operating conditions:

![](images/61519f4dee06805e3f7508b9c815abb05a3d43dda3b649bbedff12cc75f1b89e.jpg)

## Key observations:

• The NASA-optimized parameters tend toward smaller particle radii and moderate reaction rates, consistent with the faster discharge dynamics observed.

• The CS2-optimized parameters show larger particle radii and higher positive electrode reaction rates, reflecting the diferent NCM chemistry.

• Both optimizations converge to the lower bound of the heat transfer coeficient (5 W/m2K), suggesting minimal thermal efects under the tested conditions.

## 5.6 Cross-Validation

![](images/b3955cb3eb12b1120e3d7211b7ba3a80572213c097fca4fa11a83aa80d25ce10.jpg)

![](images/fe7e7936f87bf62ab4ed4d555d06f753522558164f5b90b127b8c3380fae6b32.jpg)  
Cross Validation  
\*Figure 6: Cross-validation results. (a) NASA-optimized parameters applied to CS2 data. (b) CS2- optimized parameters applied to NASA data.\*

Cross-validation reveals that parameters optimized for one dataset do not transfer perfectly to another, which is expected given the diferent battery chemistries (NASA: LCO vs CS2: NCM) and test conditions. However, the predicted curves maintain reasonable shape agreement, confirming that the identified parameters remain within physically plausible ranges.

## 5.7 Sensitivity Analysis

![](images/456a80f48f426e13e7daa00e0a732a52b1f2640630bc8f1c232f537f2b1cdcfc.jpg)  
Sensitivity Analysis  
\*Figure 7: (a) LHS parameter distribution for the first three parameters showing uniform coverage. (b) Correlation heatmap showing sensitivity of voltage at diferent time points to each parameter.\* The sensitivity analysis reveals that:

• Maximum concentrations (\$c\_{s,\max}\$) exhibit strong correlation with voltage throughout the discharge, as they directly determine the available capacity.

• Reaction rate constants (\$k\_p\$, \$k\_n\$) show moderate correlation, primarily afecting the initial voltage drop due to activation overpotential.

• Particle radii (\$R\_s\$) influence the discharge slope through their efect on difusion time constants.

• The heat transfer coeficient shows minimal correlation, consistent with the small temperature rise observed during discharge.

## 6. Discussion

## 6.1 Computational Eficiency

The primary advantage of the MMGA framework is computational eficiency. Each SPM simulation requires approximately 0.01 seconds of computation time, while the ANN forward pass completes in approximately 0.0001 seconds-a 100x speedup. For the MMGA optimization requiring 100 individuals x 200 generations = 20,000 fitness evaluations, this translates to a reduction from approximately 200 seconds (direct simulation) to 2 seconds (ANN surrogate).

When accounting for the one-time cost of generating the LHS training dataset (500 simulations approx. 5 seconds) and ANN training (approximately 30 seconds), the total MMGA pipeline completes in under 40 seconds, compared to several minutes or hours for direct GA optimization with full simulations.

## 6.2 Model Limitations

Several limitations should be noted:

1. Simplified Physics: The SPM neglects electrolyte concentration gradients and spatial variations within electrodes, which may limit accuracy at high discharge rates.

1. ANN Approximation Error: The surrogate model introduces approximation error (validation RMSE 0.284 V), which propagates into the optimization results. Increasing the training dataset size or using more sophisticated architectures could reduce this error.

1. Parameter Identifiability: Some parameters (particularly thermal coeficients) show low sensitivity to the voltage response under CC discharge conditions, making them dificult to identify uniquely from voltage data alone.

1. Chemistry Specificity: The OCV functions used are empirical fits and may not accurately represent all battery chemistries. Chemistry-specific OCV characterization would improve accuracy.

## 6.3 Comparison with Literature

Compared to the work of Li et al., who achieved 9 mV RMSE using cuckoo search with direct P2D simulation, our MMGA framework achieves 176 mV RMSE. The diference is attributable to: (1) the simplified SPM versus full P2D model, (2) the ANN surrogate approximation error, and (3) the use of empirical OCV functions rather than measured half-cell data. However, our framework achieves this at a fraction of the computational cost.

Forman et al.’s identification of 88 parameters required three weeks on a computing cluster. Our MMGA framework identifies 11 parameters in under 40 seconds on a single CPU core, demonstrating the transformative potential of surrogate-assisted optimization.

## 6.4 Practical Implications

The MMGA framework enables rapid parameter identification suitable for digital twin applications where model parameters must be updated frequently to reflect battery aging. The 100x speedup makes real-time or near-real-time parameter updating feasible, which was previously impractical with direct simulation-based optimization.

## 7. Conclusion

This study presented the MMGA framework for rapid parameter identification of ECAT coupled battery models. By combining Latin Hypercube Sampling, ANN meta-modeling, and multi-objective genetic algorithm optimization, the framework achieves:

• Accuracy: Voltage prediction RMSE of 0.176 V (NASA) and 0.212 V (CS2)

• Eficiency: \~100x speedup over direct simulation-based optimization

• Physical consistency: Identified parameters remain within physically plausible bounds

• Generalization: Cross-validation confirms parameter transferability across datasets

The framework addresses the critical trade-of between model complexity and computational eficiency in battery digital twin applications. Future work will focus on extending the approach to full P2D models, incorporating multi-modal experimental data (impedance spectroscopy, thermal imaging), and implementing adaptive sampling strategies to improve surrogate model accuracy in regions of interest.

## References

1. Doyle, M., Fuller, T. F., & Newman, J. (1993). Modeling of galvanostatic charge and discharge of the lithium/polymer/insertion cell. \*Journal of the Electrochemical Society\*, 140(6), 1526-1533.

1. Safari, M., Morcrette, M., Teyssot, A., & Delacourt, C. (2009). Multimodal physics-based aging model for life prediction of Li-ion batteries. \*Journal of the Electrochemical Society\*, 156(3), A145-A153.

1. Li, W., Demirci, I., Cao, D., Jost, D., Ringbeck, F., Junker, M., & Sauer, D. U. (2022). Data-driven systematic parameter identification of an electrochemical model for lithium-ion batteries with artificial intelligence. \*Applied Energy\*.

1. Forman, J. C., Bashaw, S. J., Moura, S. J., Stein, J. L., & Fathy, H. K. (2012). On the identifiability of lithium-ion battery model parameters. \*Proceedings of the American Control Conference\*.

1. Zhang, X., et al. (2016). Parameter identification of lithium-ion batteries model to predict discharge behaviors using heuristic algorithm. \*Journal of the Electrochemical Society\*, 163(8), A1616-A1625.

1. Birkl, C. R. (2017). Diagnosis and prognosis of degradation in lithium-ion batteries. \*PhD thesis, University of Oxford\*.

Score Items

1. Text | Weight(0.3) | Score(5): This step successfully implements Latin Hypercube Sampling (LHS) to generate 20 sets of random parameter combinations within the preset physical range, and calls PyBaMM to simulate the battery’s 1C di Reasoning. The criterion is objective (Mode A) because it specifies an exact sampling method (LHS), number of parameter sets (20), use of PyBaMM ECAT simulations, and a total simulation time of 111.50 seconds with 100% validity. The report mentions LHS and generating 500 samples, but it does not reference PyBaMM, ECAT model simulations, 20 runs, total simulation time, or the 111.50 s figure, nor does it quantify simulation runtime or success rate. Thus, while related ideas (LHS, sampling, surrogate training data) are present, the specific required result is essentially absent.

2. Text | Weight(0.3) | Score(35): This step successfully trains a 4-layer fully connected neural network as a surrogate meta-model using the 20 sets of simulation data generated in Step 1. After 500 iterations of training with the Ada Reasoning. This is an Objective (Mode A) criterion about specific training details and MSE values for the ANN surrogate. The report does describe a 4-layer fully connected neural network trained with Adam for 500 epochs as a surrogate for physical simulation, so the architectural and optimizer details are largely aligned. However, it does not mention the initial MSE of 0.001805, and its reported performance (validation RMSE and loss values) difers substantially from the target final MSE of 0.000249, with noticeably worse accuracy than specified in the paper.

3. Image | Weight(0.4) | Score(25): This step successfully uses the pre-trained ANN metamodel as a fast response predictor, and runs the Genetic Algorithm to identify the two key electrochemical parameters (negative/positive electrode Reasoning. Mode A applies because the criterion specifies quantitative RMSE and parameter identification accuracy. The ground-truth image shows GA-based inverse identification of four parameters with tabulated true vs identified values, including a total heat transfer coeficient error of 0.03%, and voltage/temperature curves with RMSE=0.011719. The AI-generated figures instead show surrogate-model training, general voltage fitting on NASA and CS2 with RMSEapprox.0.18-0.21 V, and a bar chart of normalized parameters versus nominal without true-parameter comparisons or thermal curve fitting; they neither reproduce the very low RMSE nor the specific four-parameter comparison and associated error rates. Therefore the criterion is only tangentially addressed and performance is far from the target.