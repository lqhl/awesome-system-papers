# OmniScientist: An Omni-Modal Omni-Discipline AI Scientist

Bobo Li<sup>1</sup>, Hao Fei<sup>2\*</sup>, Tianjie Ju<sup>1</sup>, Mong-Li Lee<sup>1</sup> and Wynne Hsu<sup>1</sup>

<sup>1</sup>National University of Singapore <sup>2</sup>University of Oxford

Project page: https://omni-scientist.github.io

Software & Skill: https://github.com/Omni-Scientist/OmniScientist

ABSTRACT Recent advances in foundation models have enabled AI scientists to automate increasingly complete research workflows, from hypothesis generation and code execution to manuscript preparation. Yet workflow coverage alone does not provide access to the full evidence on which scientific discovery depends. Existing systems typically reason over text, code, labels, or precomputed summaries, leaving scientifically decisive spatial, temporal, cross-channel, and procedural relations unavailable to the agent. We introduce OmniScientist, an end-to-end, omni-modal AI scientist that conducts multidisciplinary research directly from heterogeneous raw evidence. A perception layer and 3 autonomous agents for ideation, experiment, and writeup operate within a deterministic pipeline, allowing observations to shape research questions, experimental decisions, and final claims throughout the research lifecycle. By running idea, rigour, and claim checks in code, the system enforces novelty screening, statistical validity, execution provenance, and numerical traceability. We evaluate OmniScientist on 36 real-data cases spanning 5 discipline families, 4 families of scientific evidence, and modalities including images, signals, audio, video, 3-D structures, trajectories, tables, formulae, and graphs. The system completes the full path from raw data to a compiled manuscript in all 36 cases and achieves a mean overall paper score of 6 3 with the reference reasoning backbone. In paired comparisons against a blind variant that receives only precomputed scalar features, direct perception improves all 7 evaluation dimensions and wins 85% of head-to-head judgments. These results show that lifecycle-wide perception is essential to the evidence-grounded scientific discovery and provides a practical path toward broadly capable AI scientists.

KEYWORDS AI Scientist, Multimodal Agents, Autonomous Research, Scientific Discovery, LLM Agents, Tool Use

![](images/73aa8a6031615830843784bd1e8e58e6f0c0e904a3cfbb15e144bd1787f61afc.jpg)  
Figure 1. Overview of the OmniScientist framework. Raw multimodal observations spanning multiple disciplines (left) are fed into a unified engine that perceives evidence, executes falsifiable experiments, and grounds every claim (center). This continuous pipeline ultimately yields verifiable scientific discoveries across various fields (right).

## 1 Introduction

Recent advances in foundation models have expanded the scope of automated scientific discovery. Improvements in reasoning, code generation, and tool use (OpenAI, 2023; Anthropic, 2024; DeepSeek-AI, 2025) have moved scientific AI from task-specific systems, exemplified by protein structure prediction (Jumper et al., 2021), toward agents that coordinate hypothesis formulation, experiment execution, and scientific writing (Schmidgall et al., 2025; Yuan et al., 2025; Tang et al., 2025). At the current frontier, end-to-end systems can start from a research direction and autonomously produce candidate ideas, runnable code, experimental figures, complete manuscripts, and self-reviews (Lu et al., 2026; Yamada et al., 2025; InternAgent Team et al., 2025; Intology AI, 2025; Gottweis et al., 2026). These systems therefore cover almost the entire visible research workflow. A separate capability remains unresolved: an AI scientist must also derive defensible questions and claims from the heterogeneous observations on which science depends.

Scientific evidence reaches researchers in forms with markedly diferent internal structure. Text, formulae, sequences, and knowledge graphs encode symbolic relations, while microscopy, spectra, waveforms, audio, video, 3-D structures, distributions, and trajectories carry spatial, temporal, cross-channel, statistical, and procedural relations (Wang et al., 2023; Baltrušaitis et al., 2019; Yue et al., 2024; Li et al., 2024). All of these artifacts can be serialised into tokens or accessed through code. The decisive issue is which relations survive the interface. A caption can omit local morphology, an unordered feature vector can erase temporal order, and a small set of scalars can hide cross-channel inconsistency. Yet most current AI-scientist pipelines expose data through text, code, labels, or summaries prepared in advance (Lu et al., 2026; Yamada et al., 2025; Jiang et al., 2025; Schmidgall et al., 2025; Yuan et al., 2025; InternAgent Team et al., 2025). The agent therefore inherits a human-chosen representation before inquiry begins. This interface constrains the anomalies it can notice, the hypotheses it can formulate, and the claims it can support. Existing systems are increasingly workflow-complete, while remaining evidence-incomplete.

Strong multimodal models do not by themselves close this gap. Scientific multimodal benchmarks usually fix the observation and the question in advance (Wang et al., 2024; Roberts et al., 2024; Pramanick et al., 2024; Li et al., 2024), while scientific agents that use perception generally invoke it at a local stage, such as inspecting generated figures, scoring plots, reading an interface, or monitoring an apparatus (Yamada et al., 2025; Gandhi et al., 2025; Sun et al., 2026; Darvish et al., 2025; Mandal et al., 2025). Such uses can improve an isolated decision, yet they do not establish a research loop in which an observation can redirect the study. In a perception-driven AI scientist, raw evidence should influence which question is selected, how the experiment is designed, what is examined after execution, and which statements are admitted to the final manuscript. A broader observation and search space also enlarges the room for data leakage, repeated testing, hypothesising after results are known (HARKing), and unsupported reporting. Lifecycle-wide perception therefore needs a control structure that preserves provenance and enforces statistical and factual constraints.

To meet these requirements, we introduce OmniScientist (cf. Figure 1), an end-to-end, omni-modal AI scientist for multidisciplinary discovery. A task is specified by a dataset, a scientific subject, and a target property, together with the raw artifacts referenced by that specification. OmniScientist coordinates a perception layer with 3 autonomous agents for ideation, experiment, and writeup (Figure 3). Within each stage, a ReAct loop interleaves observation, reasoning, and action (Yao et al., 2023; Shinn et al., 2023; Schick et al., 2023), allowing evidence to shape question formation, experimental design, result inspection, and scientific argumentation. Around these open-ended agents, a thin deterministic pipeline controls stage transitions, returns to ideation when an experiment collapses or yields a null result, and admits each stage output only after a check enforced in code. The idea, rigour, and claim checks examine novelty evidence and falsifiability, leakage and efective sample size, execution provenance and multiple comparisons, anti-HARKing constraints, numerical traceability, and claim support. We further organise scientific evidence into 4 discipline-independent families, namely perceptual, symbolic, quantitative-statistical, and procedural evidence (cf. Table 2). The same engine can consequently operate on a seismogram, a CAD mesh, or a knowledge graph. Adding a discipline requires a new specification file, with no change to the core pipeline and no domain-specific research code.

We evaluate OmniScientist on a 36-case demonstration suite spanning 5 discipline families, all 4 evidence families, and modalities ranging from images and waveforms to audio, video, 3-D structures, trajectories, tables, formulae, and graphs (Table 1). The system completes the full path from raw data to a compiled paper in all 36 cases. With the reference reasoning backbone, the generated papers receive a mean overall score of 6 3 on a 7-dimensional rubric scored by 2 cross-family judges, and paper quality remains broadly consistent across evidence modalities (Tables 3 and 5). We then isolate the contribution of perception by comparing the full system with a blind variant that receives precomputed scalar features and never accesses the raw observation. Full perception improves every evaluated dimension, with the largest gains in multimodal grounding and scientific significance, and its papers win 85% of the head-to-head judgments (Figure 7). The gains appear in the scientific substance of the papers: the questions selected, the analyses executed, and the claims supported

by the resulting evidence.

In summary, our main contributions are as follows:

We present OmniScientist, an end-to-end, omni-modal, and discipline-agnostic AI scientist that works directly from heterogeneous scientific evidence. It extends automated discovery beyond workflow coverage by keeping spatial, temporal, statistical, and procedural relations available throughout the research process.

We propose a perception-first, multi-agent architecture where raw observations actively guide ideation, experimentation, and manuscript generation. Furthermore, we integrate code-enforced checks across the pipeline to screen for novelty, ensure statistical validity and execution provenance, prevent HARKing, and guarantee that all reported claims are traceable and supported by evidence.

We establish a 36-case demonstration suite across 5 discipline families and 4 families of scientific evidence. The 36 completed end-to-end runs, together with backbone comparisons and a paired blind ablation, demonstrate broad cross-disciplinary applicability and show that direct perception is essential to the evidence-grounded scientific discovery.

## 2 Related work

## 2.1 Autonomous agents for scientific discovery

Autonomous agents are increasingly participating in scientific discovery. Early frameworks targeted one domain and one instrument, executing laboratory procedures or choosing the next synthesis from difraction patterns (Boiko et al., 2023; Szymanski et al., 2023). Later systems widened to real scientific data across disciplines, proposing hypotheses that were subsequently validated at the bench (Mitchener et al., 2025; Villaescusa-Navarro et al., 2025; Swanson et al., 2025; Gottweis et al., 2026; Ghareeb et al., 2026). A parallel wave automated the entire research lifecycle on software repositories, from idea generation to a drafted and self-reviewed manuscript, with an improved numerical metric as the measure of success (Lu et al., 2026; Yamada et al., 2025; Jiang et al., 2025; Schmidgall et al., 2025; Yuan et al., 2025; InternAgent Team et al., 2025), most recently embedding that pipeline in a collaborative ecosystem (Shao et al., 2025). Despite these advances, current agents attend only to what a person has already turned into text, code, or a number, and overlook the raw evidence itself. As a result, almost every benchmark grades the artifacts a system produces and never what it can perceive (Chan et al., 2025; Starace et al., 2025; Chen et al., 2025; Wei et al., 2025). We therefore build an AI scientist that perceives the raw observation directly, across the 4 families of scientific evidence in Table 2.

## 2.2 Multimodal perception for science

General multimodal models already provide strong perceptual capability, through contrastive image-text pretraining (Radford et al., 2021) and instruction-following vision-language models (Alayrac et al., 2022; Liu et al., 2023). Scientific benchmarks have measured that capability on published charts and figures (Wang et al., 2024; Roberts et al., 2024; Pramanick et al., 2024; Li et al., 2024), on microscopy and materials observations (Lozano et al., 2024; Burgess et al., 2025; Alampara et al., 2025; Zhou et al., 2025), and on experiment video and bioacoustics (Xu et al., 2025; Robinson et al., 2025). Yet they treat perception as a standalone question-answering skill, with a human selecting the observation, posing the question, and judging the response. Even MicroVQA scores hypothesis generation and experiment proposal against fixed choices, and instrument-specific and pathology models remain predictors for tasks defined in advance (Chen et al., 2024). Scientific agents apply perception more directly, though only at isolated stages, inspecting their own figures (Yamada et al., 2025), scoring generated plots (Gandhi et al., 2025), reading a software interface (Sun et al., 2026), watching an apparatus mid-experiment (Darvish et al., 2025), or driving a microscope from fixed thresholds (Mandal et al., 2025). A few systems let observations inform claim formation (Yao et al., 2025; Zhao et al., 2026), though perception still plays a local and fragmented role in the research process. OmniScientist makes perception active at every stage, from forming the question to grounding the claims in the finished paper.

## 2.3 Agentic reasoning and orchestration

Agentic reasoning provides the control foundation for autonomous scientific discovery. Early methods let a single agent interleave reasoning with tool use (Wei et al., 2022; Yao et al., 2023; Schick et al., 2023; Li and Zhao, 2026), revise its behaviour through verbal reflection (Li et al., 2026a; Shinn et al., 2023), and act on multimodal observations (Yang et al., 2023b). Scientific systems extend this paradigm through specialised roles. Agent laboratories divide the work among planning, coding, and reviewing agents (Schmidgall et al., 2025), virtual laboratories coordinate teams of domain experts (Swanson et al., 2025), and collaborative ecosystems connect agents through shared knowledge and review (Shao et al., 2025; Li et al., 2026b). Yet these systems orchestrate agents through prompts and generated messages, which leaves stage transitions and validation dependent on fallible model output. OmniScientist adopts a pipeline of agents, in which code controls the transitions, verifies that a stage’s output is grounded in real observations, and backtracks when it is not. Reasoning inside a stage stays open-ended, and the process around it stays predictable.

Table 1. The demonstration suite: 5 categories, 36 cases, one real downloadable dataset each, with the sample count per dataset. Ev-<sup>??</sup>idence – 4 perceptual, Ð symbolic, ¡ quantitative-statistical, = procedural. Modality – ë image, × signal,   spectrum, Ð audio, Å video, ò 3-D, È trajectory, O table, F formula, 	 sequence, a field, ¨ graph.  
![](images/703f4412e5a50a1c652354c6789e2c9ea3b7c02bf9c745bfe2710cf563566a88.jpg)

![](images/16a9dfd052d95f9cc0276a431518ebf130113f0068804a7cf17bb7c63442a2b5.jpg)  
Figure 2. Progression from raw evidence to verified findings across three demonstration cases. The top three rows track workflows in seismology, pathology, and 3-D CAD. From left to right, each row begins with raw evidence (a three-channel seismogram, a stained pathology tile, and a 3-D CAD model), identifies specific structural cues, and outlines the subsequent hypothesis and action sequence. The rightmost column displays the verified findings, such as the discovery that 21.7% of noise labels are real events. The bottom band depicts a precomputed interface where the artifact is reduced to a feature vector, resulting in lost structural relations and a narrower research question space.

## 3 Problem setting

## 3.1 Scientific evidence

Scientific discovery draws on research artifacts in several forms, including images, symbolic structures, numerical results, and records of experimental processes. Existing taxonomies typically organise scientific machine-learning data by representation, such as images, sequences, and graphs (Wang et al., 2023), while surveys of multimodal learning adopt similar schemes (Baltrušaitis et al., 2019). To distinguish artifacts by the primary reasoning required for their interpretation, we group scientific evidence into 4 discipline-independent families (Table 2): (1) the perceptual family, encompassing images, micrographs, spectra, waveforms, and 3-D structures; (2) the symbolic family, which covers evidence expressed in natural language or formal notation (e.g., documents, formulae, sequences, and knowledge graphs); (3) the quantitative-statistical family, comprising tables, measurements, and distributions; and (4) the procedural family, capturing trajectories, simulations, and agent traces. Here, symbolic covers evidence expressed in natural language or formal notation. Scientific multimodal benchmarks and domain foundation models already target many perceptual modalities (Yue et al., 2024; Li et al., 2024; Chen et al., 2024; Parker et al., 2024; Jakubik et al., 2023). The other 3 families account for the symbolic, statistical, and procedural artifacts that a research loop must also handle.

Current AI-scientist systems primarily process text and numerical data, which leaves perceptual and procedural evidence unexamined and narrows both the questions they can ask and the disciplines they can serve. Both families can be serialised into tokens. The relevant question is not what can be serialised, but which relations survive the interface. Captions used as textual summaries do not preserve the local spatial structure of pathology tiles, Sentinel-2 scenes, and three-component seismograms, and unordered scalar summaries discard the temporal ordering of migration tracks and simulations. Text-only interfaces built from these reductions therefore lose the structure on which the scientific conclusion depends. Figure 2 makes the contrast concrete on 3 cases of our suite, where the structural cues read of the raw record are what carry the finding, while the same artifact delivered as a precomputed vector arrives with those relations already removed.

Table 2. The 4 families of scientific evidence OmniScientist is designed to perceive.  
![](images/a46bbcda390640a2c17e2122b50e166a8211aee967dd34646951edc3cc82df31.jpg)

## 3.2 Task setting and demonstration suite

A task is presented to the system as a single specification file that details a dataset, a scientific subject, and a target property, alongside the corresponding raw data. Based on these inputs, the system is instructed to produce an evidence-grounded paper. Nothing else is supplied, and the specific methodology is left entirely to the agent. To evaluate this task formulation across disciplines, we assemble a demonstration suite comprising 5 top-level discipline categories and 36 second-level cases (Table 1). Each case utilizes one real, publicly downloadable dataset with a canonical citation. The suite ranges in scale from 12 symbolic-regression equations to a biomedical knowledge graph with 5 million edges, incorporating images, spectra, waveforms, audio, video, 3-D structures, tables, and symbolic graphs. All 4 aforementioned evidence families are represented. The perceptual family accounts for 28 of the 36 cases, reflecting the natural prevalence of image, signal, audio, video, and 3-D data in the selected disciplines. The remaining 8 cases from the symbolic, quantitative-statistical, and procedural families serve as breadth controls for settings where visual inspection contributes little and a text-only baseline is already expected to perform strongly.

This comprehensive suite enables rigorous testing of the engine’s domain agnosticism. Expanding to a new discipline requires merely writing an additional specification file. The underlying engine remains entirely unchanged; the identical perception, ideation, experimentation, and write-up loop operates seamlessly on a seismogram, a CAD mesh, or a knowledge graph without a single line of domain-specific code. Section E reproduces one such file in full. Finally, Table 4 reports the end-to-end runs enabled by this unified framework, quantitatively evaluating the true extent of the system’s cross-disciplinary capabilities.

## 4 The OmniScientist framework

In this section, we introduce the OmniScientist framework, an end-to-end AI scientist consisting of a perception layer and 3 autonomous agents for ideation, experiment, and writeup (Figure 3).

## 4.1 Perception layer

To function efectively, a multimodal AI scientist must perceive raw artifacts directly, upstream of any precomputed summaries. The perception layer supplies this grounding by organizing observations hierarchically. First, artifacts are categorized into an evidence family based on the reasoning paradigms they require. Within a given family, a specific modality defines the artifact’s exact representation (e.g., images, tables, or time-series signals), which the agent inspects using registered tools. Figure 4 illustrates the raw observations processed by the agent across 16 disciplines and 11 modalities, covering all 4 evidence families, along with the discoveries derived from this direct reading.

To balance thorough analysis with computational eficiency, the framework governs when and how the agent inspects raw data. Rather than immediately rendering visual plots, the agent prioritizes native numeric analysis by extracting key properties, such as FFT peaks or trend points, directly from the raw artifacts. Visual rendering is invoked only when spatial or structural patterns are essential. Furthermore, visual perception is budget-constrained to prevent unnecessary processing and enforce targeted inspection. Ultimately, the task context dynamically determines whether native numeric features, visual representations, or both are utilized, ensuring flexible perception without relying on hardcoded heuristics. Section D lists the tools this suite exposed, the modality that unlocks each one, and how heavily each was used across the suite.

![](images/3151602553462208412800f19d4ead786fb3da31cc264a434d005a2145938db9.jpg)  
Figure 3. Architecture of the OmniScientist framework. At the top, raw evidence from multiple disciplines enters the system, categorized into four evidence families (perceptual, symbolic, quantitative, and procedural) and 12 modalities. The core pipeline consists of three sequential stages. First, the Ideation stage (left) observes materials, searches literature, and formulates falsifiable hypotheses. Next, the Experiment stage (center) designs tests, executes code, and inspects results to generate an execution record containing standard output, figures, data, and configurations. Finally, the Writeup stage (right) selects, grounds, and reports claims supported exclusively by the execution record to compile the final paper. At the bottom, a lifecycle-wide perception layer provides spatial, temporal, cross-channel, statistical, and dynamic analysis capabilities. Dashed arrows indicate that these perception tools are available to all three stages of the pipeline.

## 4.2 Ideation

The ideation stage requires the agent to formulate a concrete, novel, and falsifiable question that can be answered computationally from the supplied data. Driven by a ReAct (Yao et al., 2023) loop, the agent autonomously sequences its discovery process. It begins by establishing grounding through an inventory of the materials and a decision on whether to inspect raw observations (Section 4.1). It then contextualizes these findings by searching the literature through OpenAlex (Priem et al., 2022) with Crossref (Hendricks et al., 2020) as a fallback. Building on this context, the agent develops at least 5 candidate ideas, assesses the novelty risk and feasibility for each, and selects the strongest candidate to finalize.

Because large language models are prone to hallucination and overconfidence, the stage output must pass a code-enforced check before it can be finalised. The check validates structural completeness by requiring a clear research question, hypothesis, experiment sketch, and falsification criterion. It verifies the thoroughness of the generation process by checking for the 5 self-filtered candidates and at least 3 focused literature searches. The proposed study must be executable in code and must not require a physical experiment. The system also requires leakage checks, efective-sample estimates, and visual audits to prevent methodological flaws. Furthermore, since a single bounded search cannot establish absolute priority, the system automatically tempers overconfident assertions by rewriting terms like first or never explored to appears under-explored based on this search. Section B states the loop this check terminates, lists every condition the 3 checks enforce, and reports which of them actually fired across the 36 runs.

## 4.3 Experiment

During experimentation, the agent autonomously translates the finalized idea into a methodological design and implements it through iterative code generation. It relies on a controlled run\_python environment that manages subprocess execution and figure capture. The agent operates in a continuous debugging loop, analyzing

## Perception is where discovery begins

16 cases, 11 modalities, all 4 evidence families. The red box marks what the agent read on the raw record;   
every result below it is the verified finding that observation led to.

![](images/67ff5c1b2a21edcaf6b3822d5e6c426efaa004dde4fe73749f1640ffb47bb90b.jpg)  
SAW dense patches sitting beside clear ones inside one lung field  
FOUND pneumonic fields are measurably patchier, d = 1.25 (AUC 0.85 vs 0.63 for raw pixels)

![](images/9bd471bd253eaf2c691318c48054a983c076ae2ac1fd54f75a7f53ef3a1ca63a.jpg)  
FOUND held-out complex tiles decompose into tumour, stroma and lympho mixtures (p = 0.34)

![](images/a4eabac6accc3ade02feb4ba2c157022e1f2adbf3eaa8c013e2af6bd3e8b65c0.jpg)  
SAW the same galaxies imaged at two survey depths  
FOUND the morphological reading holds: 83.8% vs 81.0%, McNemar p = 0.63, κ = 0.75

![](images/e30d6e336fbd423fc7b50675d684a6677674d2e833a146e00491e6209f9ad35d.jpg)  
FOUND rank order holds at 0.77 when the dominant band persists, 0.23 when it swaps (n = 218)

![](images/3e61f93fd4a8ff2ba8f7b5ee1635d8d2b03f9a3cd755b39ebdf3faf3a1f59e7d.jpg)  
FOUND 21.7% (163/750) of noise-labelled traces carry coherent transients, CI [18.8, 24.9]

![](images/b5eddb1b4d8a20a011de8929beeff375e8191c5ea27ed5106548dc5dc2cf1874.jpg)  
FOUND time-bandwidth product alone recovers the functional grouping of 32 species

![](images/ac5ad39beb341a4e17c23a923fd3b00511b538c594e93ea15c44a866cd743692.jpg)  
FOUND detector AUC falls 0.73 → 0.58 from the least to the most masked tertile

![](images/2a516c5ac65e5aa2bad7dc28630522acf832467f22535e0ceda0d50a2db95c0b.jpg)  
SAW two radar cells drifting together across the frame sequence  
FOUND mergers add +9.65 VIL-units/5-min over matched controls (p = 3.2 × 10<sup>−14</sup>)

![](images/fc8a420e3daad71d93aa97d5bfff1ffd9881c67b7693f5162c78e4476f2fa856.jpg)  
SAW targets moving through the sonar cone between frames

![](images/ec314c154e096f33f80cd27a4dba9ac3cdc24ace91b9c4c0ace6df56a65f31f5.jpg)  
FOUND site explains 81% of the rangedensity slope variance (H = 84.8, p < 0.0001)

![](images/98fd242956bbeac02fa857318b652bfeb527a5c71eb619282351d3c8b3ad30ef.jpg)

![](images/213f0e7174fee5209f0b9dd99581154d43a87eba5c1aa8b847a23a1cadbb229b.jpg)  
FOUND 1,500 clouds cluster into 11 morphotypes, AMI = 0.31 against a null at 0  
FOUND high-curvature periods precede slower intensification 24 h later (p = 2.4 × 10<sup>−4</sup>)

![](images/89d86f91b20e71c28bbbb2f0c5af334af23ce59e371a68b016b4ea2f31d5e460.jpg)  
FOUND random k-fold CV understates extrapolation error: leave-onefamily-out RMSE is 3.1–7.0× higher

![](images/f18388e1c3f384082fab2b02cff34be9accae2929f0ca6a71379f2d87cae6ab3.jpg)  
FOUND exponent variance follows the Cramér–Rao form: slope −1.002 vs −1 predicted, R<sup>2</sup> = 0.998

![](images/b56cace1f2e634d8ba74cb9b7e4112047485077b5adcef60da073f4e67bd179d.jpg)  
FOUND a composition-independent 9.5–11 bp periodicity: AUROC 0.55 vs 0.50 on composition-preserving shuffles

![](images/f72952ae4d6e24394c5fbe006f1b13d76fe29fa85c1ae2e19fa5c6a6085aea2c.jpg)  
SAW how many distinct functions a protein carries against its degree  
FOUND disease proteins carry more distinct functions than degree-matched controls, on held-out edges too

Figure 4. Raw observations and derived discoveries processed by the perception layer across 16 cases, 11 modalities, and all 4 evidence families. The figure presents a four-by-four grid of artifacts, each taken from that case’s own data exactly as the run received it, with the discipline named at the top left of every panel and the modality at the top right. Within each artifact, a red bounding box marks the specific feature flagged by the agent on the raw record. Below the artifact, the <sup>saw</sup> label reports the direct observation made by the agent, and the <sup>found</sup> label details the verified experimental result produced by that observation. The first three rows cover perceptual and procedural evidence, spanning images, spectra, signals, audio, video, three-dimensional structures, and trajectories. The bottom row presents quantitative and symbolic evidence, where the layer reads the native numeric structure of a table, a formula, a sequence, or a graph instead of rendering an image.

![](images/2a61e1b60368235c526762c0abef5404006c959d1d77ca7f3865fce780aa1264.jpg)  
Figure 5. Two-stage verification pipeline for experimental results and manuscript claims. In the top row from left to right, an unverified experimental result undergoes a rigour check that verifies real execution, accounts for all tests, tests for independence and leakage, and ensures the headline belongs to supported analyses. If a check fails, unsupported analyses are traced and null results trigger re-ideation. Successful validation yields a verified result with certified metrics and attached provenance. Further right, a claim check matches reported numbers ( ) to recorded outputs and reported <sup>?? .</sup> <sup>.</sup> <sup>.</sup> <sup>????</sup>claims ( ) to recorded analyses ( ), resulting in a manuscript with fully traced numbers and supported <sup>?? ??</sup>claims. The bottom band displays the execution record, which serves as the source of truth for both checks. This record captures data I/O, standard output, generated figures, and a complete list of all attempted tests including unsupported attempts ( ).

execution errors and regenerating scripts until successful. Throughout this process, it utilizes the perception layer to inspect raw input data or verify structural patterns in its own generated experimental plots. To ensure findings are robust and defensible, the agent incorporates a comprehensive suite of at least 4 analyses into the experimental design, combining a main hypothesis test with essential controls such as baselines, ablation studies, mechanism probes, or sensitivity sweeps.

Once the iterative execution concludes, a code-enforced exit check verifies result provenance and statistical validity (Algorithm 1). The check grounds the experiment in reality by confirming that the agent genuinely accessed the requested dataset and generated figures matching the raw execution trace. To prevent statistical manipulation, the system enforces a strict multiple-comparison correction that accounts for every test attempted during the debugging loop, which prevents artificial reductions in the correction denominator. It also applies a post-hoc rescue guard to ensure headline findings originate from primary tests, runs an independence check to eliminate circular predictions, and relegates any unsupported analyses to the execution trace. Figure 5 places this check and the later claim check in sequence, both auditing against the same execution record rather than against the text the agent wrote.

## 4.4 Writeup

The writeup stage is where breadth becomes visible in the artifact itself. A single template would make every case read like the same discipline, so the stage carries 5 structural specifications that fix the skeleton and the length of each venue style. Machine learning papers carry Related Work and Limitations, biomedical papers append Methods at the end, and chemistry papers merge Results and Discussion. The style is resolved from the case specification or inferred from the subject and stays decoupled from the research domain, so one engine writes a seismology study and a materials study in the idiom each field expects (Section F). Guided by this blueprint, drafting proceeds from a section-level outline into full paragraphs. Each section is expanded only from the slice of the structured experiment record it needs, so methodological detail reaches the method and data sections, the decisive numbers reach the results section, and a section cannot introduce detail it was never given. The abstract is written last from the same records, so its numbers agree with the main text. The remaining machinery is deterministic. A thesis planner selects the headline claim from the supported analyses and assigns the other results to supporting evidence, controls, or robustness checks, with the remainder kept in the run’s trace. References are retrieved through the OpenAlex API, an output pass filters the drafted sections and rolls back if it would prune too much, and a final meta-audit checks the generated claims against the experimental record (Figure 5) before the stage compiles the PDF. Section G gives the prompt that drives each stage verbatim, together with the rubric the judges receive.

![](images/811edba552941a2bf13c22e6e6984d5c3d1173cae14afaec9e22d3ff59efb096.jpg)

Table 3. Detailed review scores across reasoning backbones. Per-dimension means (0–10) are derived from a 2-judge cross-family panel (deepseek-v4-flash and gemini-2.5-flash-lite) over the entire case suite. For these evaluations, the framework and perception models are held fixed, with only the reasoning backbone swapped. Failed runs are excluded; thus, means are computed exclusively over successfully scored papers. The highest value in each column is highlighted, and coverage per backbone is detailed in Table 4. Notably, clarity exhibits the least degradation, whereas factual accuracy and soundness most closely track the underlying backbone strength.  
![](images/6f701eb37f662b670d19c1cd10ecb922c157973bcc83ef3219f8abeea80ab62b.jpg)

## 5 Evaluation

To comprehensively evaluate our proposed framework, we conduct extensive experiments across 36 datasets to verify its efectiveness. Furthermore, we present detailed ablation studies and in-depth analyses to elucidate the underlying mechanisms and demonstrate the overall superiority of the system. We also present 2 representative case studies to show that the system can conduct interesting and useful scientific discovery.

## 5.1 Experimental Setup

Models. Three roles run on separate models, and keeping them apart is what makes the comparison interpretable. The reasoning backbone drives all 3 stages and is the only component we swap. We use Claude Sonnet 5 (Anthropic, 2026) for the primary runs and compare against GPT-5.6 (OpenAI, 2026), GLM-5.2 (Zhipu, 2026), Kimi K2.7 (Kimi, 2025), and the open-weight Qwen3.5 (Qwen Team, 2026) (9B, 27B, 122B) and Gemma-4 (Google, 2026) (26B, 31B) families. The closed models are called through their oficial APIs, and the open-weight models are served locally. The perception model is pinned to Claude Sonnet 5 (Anthropic, 2026) in every run and never follows the backbone, so every look at a raw observation is served by the same model and a change in score is attributable to reasoning alone. Scoring is done by 2 judges from families outside the systems under test, deepseek-v4-flash and gemini-2.5-flash-lite. Table 4 records how much of the suite

Table 4. Backbone generality across the 36-case suite. The table reports the number of cases dispatched, the resulting completed papers, and the mean composite score for these successful runs.  
![](images/ab43017302c17444a7a8364d4e95fda3f0a13a0092a531d36090216264221678.jpg)

each backbone actually completed.

Parameters. Each stage operates under explicit computational limits to ensure bounded exploration and convergence. The ideation stage permits a maximum of 24 agent steps and 8 literature queries. Additionally, its visual perception is governed by an adaptive image budget of min<sup>(</sup>24 max<sup>(</sup>8 2 <sup>))</sup> inspections, where denotes the number of label groups in the data. The experimentation stage runs for at most 50 steps with 8 visual inspections, and each run\_python execution is strictly terminated after a 150-second timeout. To prevent infinite loops, the pipeline allows a maximum of 2 fallbacks to the ideation stage before halting the process. Finally, text generation is capped at 8,000 tokens per call. Under these configurations, a complete 3-stage execution costs between \$0.03 and \$4.34 depending on the backbone model, with the experimentation stage accounting for the majority of the expense. Each complete run outputs a structured JSON record, a Markdown summary, a replayable execution trace, and a compiled PDF report. Section C reports what a run consists of in practice, recovered from those traces.

Metrics. Each generated paper is evaluated across 7 dimensions on a scale from 0 to 10. These include 5 standard peer-review criteria (novelty, soundness, clarity, significance, and reproducibility), alongside 2 task-specific metrics: multimodal grounding and factual accuracy. We report a composite score, calculated as the mean of these 7 dimensions, as well as the judges’ independent overall scores. Notably, these scores exhibit minimal correlation with manuscript length (?? = 0 16), indicating that the evaluation is robust against verbosity bias. Finally, we report the system’s self-assessed verdict for each hypothesis. This verdict is extracted directly from the verified experiment record and categorized as supported, mixed, refuted, or null. Because Sonnet 5 demonstrates the highest stability across the complete evaluation suite, we designate it as the primary reasoning backbone for all subsequent analyses. Alternative models, such as GPT, GLM, and Kimi, were evaluated on specific subsets of the suite and are included for comparative reference.

## 5.2 Main Results

As shown in Table 3 and Figure 6, we highlight 3 key findings regarding the end-to-end quality of the generated manuscripts.

First, end-to-end generation achieves high quality and is consistent across top LLM backbones. OmniScientist automates the entire research pipeline and returns complete manuscripts across the suite. Powered by Claude, the framework achieves an overall score of 6 3 on the full suite. The strongest alternate backbones, such as <sup>.</sup>GLM and Kimi, fall within a remarkably similar performance range on their respective evaluated subsets.

Second, performance is highly robust across all disciplines and evidence modalities. Across the evaluated cases, generation quality remains remarkably stable regardless of the research domain or data type. Whether grouping the runs by discipline or by evidence modality, the median composite scores range tightly between 6 1 and 7 1 (Tables 5 and 6). Furthermore, the highest-scoring manuscripts broadly span all domain categories, demonstrating strong generalization.

Third, factual accuracy consistently leads the evaluation metrics across all reasoning engines. The relative ordering of the qualitative evaluation dimensions is highly concordant across the various backbones, achieving a median pairwise Spearman correlation of 0 82. Across these models, factual accuracy consistently ranks at <sup>.</sup>the top. This uniformity aligns directly with the shared provenance requirement, which holds each reasoning engine to the same rigorous evidence standards, while exit checks anchor every reported outcome to real program output regardless of model fluency.

Table 5. Backbone quality aggregated by evidence modality and discipline family. Results are grouped by modality on the left and by discipline family on the right. The reported metric is the mean composite score evaluated by the 2-judge cross-family panel on a scale of 0 to 10. A dash indicates that a backbone produced no scored papers for that specific category.  
![](images/985414138ce8266decb6bdc4b3d7414692901e732c93444cf786f26b6da2802e.jpg)

## 5.3 The Perception and Component Ablation

To evaluate the contribution of direct observation to the research process, we compare our framework against a blind baseline. This baseline receives only precomputed scalar features, simulating the interface of a conventional text-only system. A cross-family panel of judges evaluates the two manuscripts head-to-head. To ensure a more sensitive assessment than isolated scoring, we randomise the presentation order to eliminate positional bias. Across the 5 cases featuring a scalar-blind counterpart, the perception-enabled framework consistently outperforms, winning 85% of the comparisons averaged over cases.

A dimensional analysis reveals how multimodal perception elevates manuscript quality. When scored by the judge common to both conditions, the perception module yields the most substantial gains in multimodal grounding (<sup>+</sup>2 8) and significance (<sup>+</sup>1 8), while factual accuracy is equally high in both conditions (Figure 7). The improvement in grounding stems from the framework’s ability to process raw observations directly, a capability absent from text-only baselines. More importantly, the gains in significance show that multimodal perception broadens the scope of the claims a study can support. Crucially, these perceptual enhancements do not compromise empirical rigor. Because both conditions are subject to the same strict provenance verification, every reported metric must be directly traceable to actual program outputs, regardless of the input modality.

We conduct a leave-one-out ablation study to isolate the contributions of individual framework components (Figure 9). The prior-art search and the iterative agentic loop emerge as the most critical drivers of overall quality. Omitting the prior-art search results in the steepest performance decline (from 6 9 to 5 7), because the <sup>. .</sup>system becomes prone to proposing redundant or previously published ideas. Similarly, reducing the iterative agentic loop to a single pass significantly degrades manuscript quality. The novelty check successfully fulfills its targeted role; its removal results in a full-point decrease in the evaluated novelty score. Finally, provenance enforcement operates at a fundamentally diferent level. Because it is a deterministic constraint enforced at the code level, it does not directly alter the narrative text evaluated by the scoring rubric. Instead, its critical function is to mathematically guarantee the strict traceability of every reported empirical claim.

## 5.4 Mechanism Analysis

Direct observation fundamentally alters the research trajectory. An in-depth qualitative analysis of the 5 paired runs reveals how the performance gains discussed in Section 5.3 manifest within the practical workflow. In every instance, the perception-driven system anchors its research questions on attributes exclusive to the raw multimodal records. Specific examples include the morphology extracted by a vision model from a galaxy image, the polarization of a three-component waveform, the texture of a pathology tile, the geometry of a CAD point cloud, and the per-point organ labels of a repeated plant scan. Conversely, the blind baseline invariably restricts its hypothesis formulation to precomputed scalar features. Consequently, the two systems formulate and execute entirely distinct research trajectories, demonstrating that the advantage of multimodal perception extends far beyond mere stylistic diferences in manuscript composition. Table 7 details these operational divergences. The seismology case starkly illustrates the operational deficit of the blind baseline. Relying solely on textual feature names, the blind system designed a study that required data fields absent from the actual recording, necessitating extensive and reactive re-planning. In contrast, the perception-driven framework leveraged direct observation to formulate a viable, immediately executable hypothesis from the outset.

Perception dominates across all dimensions, with tie distributions highlighting its specific contributions. The head-to-head comparison also records tied outcomes, revealing a clear separation among the evaluation dimensions. Excluding ties, the perception-driven system secures 70% to 87% of the winning preferences across all 7 metrics. The primary divergence between dimensions lies in the frequency of these tied judgments. For multimodal grounding, significance, and novelty, the tie rate approaches zero, indicating that the two manuscripts remain consistently distinguishable in these areas. Conversely, roughly a quarter of the comparisons result in ties for factual accuracy and reproducibility. This consistent baseline aligns seamlessly with our design expectations, because both conditions are subject to the same strict provenance verification and only report metrics directly traceable to actual program executions. This distinct distribution of ties is fully illustrated in Figure 8.

Table 6. Review rubric performance across the complete evaluation suite using the Sonnet 5 backbone. The 2-judge cross-family panel evaluated all cases on a scale of 0 to 10. Using a single backbone ensures direct comparability across all columns. Factual accuracy reaches 7 0 or higher in 30 of the 36 completed cases.  
![](images/74e6f5991ed96ca9f4ce089a4613a39d1be38663d271ddb25c8f7313226b1338.jpg)

Robustness across disciplines and modalities. An examination of the aggregate results in Table 5 reveals that performance diferences across diverse discipline families and evidence modalities become negligible once the backbone model is held constant. Statistically, none of these cross-domain variations reach significance under a case-level permutation test, demonstrating the broad applicability of the perception-driven framework. Table 8 lists 13 of these end-to-end runs with the system’s own evaluation metric and headline finding, taken verbatim from the verified experiment record.

Per-case review profiles across the seven review dimensions (two-judge panel, 0–10)  
![](images/47e5ffc5ba75367aa0bd68f979e9c558da30a0458604b016300c2a1586c62d0f.jpg)  
Figure 6. Per-case review profiles across the 7 dimensions. Radar plots are shown for 9 high-coverage cases spanning 4 evidence modalities; each line represents one backbone, scored by a 2-judge panel (on a 0–10 scale). The strong backbones (Sonnet 5, GLM, Kimi) exhibit the largest, most balanced profiles, while the weak open models (Qwen3.5-9B, Gemma-4-26B) collapse inward, particularly in novelty and significance, although clarity varies the least across all models.

Varying sensitivity to backbone scaling. Crucially, the evaluation dimensions exhibit varied sensitivities to backbone model capabilities. Factual accuracy and soundness most sharply diferentiate the strong foundational models from the smaller open-weight alternatives, each demonstrating a 2 9-point performance gap between the largest and smallest models (Figure 10). In contrast, multimodal grounding is the least sensitive metric, shifting by only 1 2 points across the identical model range. Consequently, a stronger reasoning backbone does not inherently provide the perceptual competence that these multimodal tasks demand.

![](images/9f47bab9c02de041c39728495169d803b8e421d06818e85e8acb6a784ae9831e.jpg)

![](images/3650833d3e2b03d4430249d336c4c587c52218cb3a4f977f3725a0b10cba992c.jpg)  
Figure 8. Breakdown of head-to-head judgments. For each dimension, the 3 bars show the share of all judgments won by OmniScientist, won by the same system with perception removed, and declared a tie. Judges never tie on novelty or significance, the dimensions enhanced by perception, and tie most often on factual accuracy and reproducibility, which both conditions share through the provenance check.

Figure 7. Dimension-wise perception gain. For the 5 cases evaluated under both conditions, the chart shows the mean scores with perception removed (pink) and for the full OmniScientist (teal), scored by the same judge across both settings. The 2 panels of this row share one colour key. The largest gain is observed in multimodal grounding, while factual accuracy remains identical since both conditions undergo the same provenance check.  
![](images/27da7d1284394e3386ead1ca1099259f85aadc3fbbb58d4a26594baa557986ad.jpg)  
Figure 9. Component ablation on the seismology case, where each configuration removes a single component with the backbone fixed. Novelty is the judged novelty score and Composite the 7-dimension mean, both evaluated by the DS-V4-Flash judge (0–10). The dashed line marks the composite score of the full system.

![](images/d3f6787727fc6d82f84fcbbb894edb6cce6c170eb64a6e8e954d3895ea1d07dd.jpg)  
Figure 10. Review dimension scores across diferent backbone strengths. Data reflects the 6 backbones with the broadest case coverage, ordered by overall score. The score gap between the strongest and weakest backbones is largest for factual accuracy and smallest for multimodal grounding.

## 5.5 Case Study 1: Auditing a Seismic Benchmark

To investigate how direct multimodal observation drives autonomous hypothesis generation, we trace the framework’s execution on auditing roughly 1,500 three-component broadband seismograms from the STEAD catalogue. The input data is evenly split between earthquake and noise labels. Upon visually processing the raw waveforms, the agent identified a clear onset-and-decay envelope within a trace explicitly labelled as noise, where only a stationary background was expected (Figure 11). The system did not override the dataset label, and instead used this conflict to formulate a targeted research question: what exact fraction of the noise-labelled traces carries coherent transient energy. This hypothesis stems entirely from processing the raw visual morphology of the waveform, making it completely imperceptible to a baseline system that relies solely on predefined scalar features.

To resolve this formulated question, the agent autonomously engineered a composite detector integrating an

Table 7. Comparison of feature utilization between the two systems. In all paired cases, the perceiving system focuses on information inherent in the raw records, whereas the blind system relies solely on the provided scalar features despite sharing the same task and backbone.  
![](images/d6631bef2538d15a36e8b16eab7e95f52989a1a1ceee2d84277d838f36584fd0.jpg)

STA/LTA characteristic function with amplitude, rectilinearity, planarity, and a cross-channel coincidence term. By setting thresholds at the 99th percentile of 3 label-agnostic surrogate nulls, the system established that 21 7% (163 of 750) of the noise-labelled traces carry coherent, polarised, cross-component transient bursts, bounded by a 95% confidence interval of <sup>[</sup>18 8 24 9<sup>]</sup> (Table 9 and Figure 11). Through an autonomous ablation study, the agent demonstrated that removing the coincidence term collapses the detection rate to a 2 0% amplitude-only <sup>.</sup>baseline, efectively isolating timing coincidence as the primary mechanistic driver (Figure 11). The framework verified the robustness of the 19% to 25% estimate across a 50-fold range of false-alarm rates, 3 distinct null models, 4 windowing choices, and a station-cluster bootstrap over 417 distinct stations. Furthermore, when the empirical data refuted a pre-registered hypothesis concerning instrument types, the system objectively headlined the prevalence finding and relegated the instrument question to a boundary result. Throughout this derivation, the provenance check ensured that every reported threshold and statistical claim originated directly from executable code output. This estimate remained stable across alternative false-alarm rates, null models, windowing choices, and a station-cluster bootstrap over 417 distinct stations.

## 5.6 Case Study 2: A Texture Signature in Paediatric Chest Radiographs

While the previous case study demonstrated the system’s ability to correct dataset labels, this second evaluation illustrates its capacity to establish a novel positive finding directly from raw visual data. The agent received paediatric frontal chest radiographs carrying only a normal or pneumonia label, with no precomputed features. Reading the radiographs directly, it observed that pneumonic lung fields were not uniformly brighter but unevenly mottled, with dense patches sitting beside clear ones (Figure 12). It converted that observation into a measurable quantity, the spatial dispersion of a sliding-window local Shannon-entropy map, and pre-specified the hypothesis that this patchiness separates the two labels independently of the overall entropy level.

The observed separation is substantial and generalises robustly to out-of-sample data. Spatial heterogeneity separates normal from pneumonic lung fields with a large efect size (Cohen’s > 1 2) that remains remarkably stable across both development and held-out splits (Table 10). The agent subsequently verified that this finding constitutes an independent diagnostic signal, completely distinct from broadly brighter or generally textured lungs. When evaluated in a multivariable model, the spatial metric provides significant synergistic gains over mean entropy alone, yielding a peak area under the curve (AUC) of 0 851 on the held-out set. Furthermore, <sup>.</sup>this structured interpretation decisively outperforms naive raw-pixel baselines, confirming that the predictive power stems directly from the system’s high-level spatial abstraction. The finding also proves highly resilient to hyperparameter variations, maintaining strong statistical significance across ablations of the sliding-window scale and bounding-box dimensions, successfully satisfying rigorous Bonferroni correction throughout all multiple-hypothesis testing.

Table 8. Overview of 13 end-to-end runs, grouped by evidence modality and spanning all 4 families. Evaluation metrics are systemspecific, extracted verbatim from verified experiment records.  
![](images/756bb1a59b00e4265392a63c67c32205f845854838b6852b0369555c7f489fdb.jpg)

Table 9. Numbers the system produced for the STEAD noise audit.  
![](images/55d972604a7448d7b7e608cdf4642fa264e9fbcf69196c121aaf326f8eebc10e.jpg)

The formulation of this hypothesis provides compelling evidence of genuine perceptual capability. Identifying spatial heterogeneity demands direct visual engagement with the radiograph’s intrinsic properties. The system must actively observe these spatial patterns to conceptualize the metric prior to any mathematical quantification, a critical inductive step entirely inaccessible to text-bound statistical data mining.

![](images/0c447ce5b1c8e568e1b00c7161e3ab197e287010f8372e526452f98b500175f6.jpg)

![](images/81865dd33dc1e4f5afcfd0fefeb61bae89ce9da8281a51f54c98db1d0924fffc.jpg)  
Figure 11. The seismic audit at a glance. Left: 4 of the three-component traces the agent read, amplitude normalised. The first is a labelled earthquake, shown for reference, and the second a labelled noise trace that really is stationary background. The last two are also labelled noise, yet each carries a coherent onset at the dashed line, with an STA/LTA peak above the upper quartile of the labelled earthquakes and an onset rectilinearity near 1. All 4 were selected by the run’s own stored onset statistics rather than by eye. Right: the share of noise-labelled traces the full detector flags, with its 95% confidence interval, against 3 label-agnostic controls. Removing the cross-channel coincidence term collapses the detector to the amplitude-only rate, which is what identifies timing coincidence across components as the mechanism it is using.

![](images/3964aad40fab581d80249b69c0b317f93e5f68db9653f764bef3eb5aa3a1ae67.jpg)

![](images/538abdcf532853ea629cf0cb5614004f146e137d449cf4a14dc91ab6c8d68419.jpg)  
Figure 12. Visualization and evaluation of sliding-window local-entropy features. Left: Normal and pneumonic radiographs paired with their local-entropy maps. The displayed samples correspond to the median patchiness of each class. Notably, the pneumonic entropy map exhibits higher variance (i.e., a mottled appearance) compared to the relatively smooth normal map. Right: Classification performance on the held-out test set. Entropy-derived features achieve score of 0 840–0 851, <sup>. .</sup>significantly outperforming the raw-pixel baseline (0 634). This indicates that the discriminative signal relies on local structural patterns rather than raw pixel intensities.

Table 10. Numbers the system produced for the paediatric chest radiograph study. As in Table 9, every value is traceable to a real run\_python standard output.  
![](images/c89343975ffbebbc9e196f1887bdda7ffb7705065836896249c54b0c4bd576cc.jpg)

## 6 Conclusion

In this paper, we present OmniScientist, an end-to-end, omni-modal, and discipline-agnostic AI scientist. By integrating multimodal perception directly into the research lifecycle, the system enables raw observations to drive ideation, steer experimental execution, and substantiate the claims of the resulting manuscript. The framework demonstrates extensive cross-disciplinary applicability by successfully completing a 36-case demonstration suite spanning 5 discipline families. Comprehensive evaluations across 9 model backbones validate its capabilities, and paired ablations establish that direct multimodal perception is inherently decisive for scientific discovery. Ultimately, OmniScientist establishes a foundational blueprint for future AI scientists and the broader development of automated empirical research.

## References

Nawaf Alampara, Mara Schilling-Wilhelmi, Martiño Ríos-García, Indrajeet Mandal, Pranav Khetarpal, Hargun Singh Grover, et al. Probing the limitations of multimodal language models for chemistry and materials research. Nature Computational Science, 5:952–961, 2025. doi: 10.1038/s43588-025-00836-3.

Jean-Baptiste Alayrac, Jef Donahue, Pauline Luc, Antoine Miech, Iain Barr, Yana Hasson, Karel Lenc, Arthur Mensch, Katherine Millican, Malcolm Reynolds, et al. Flamingo: A visual language model for few-shot learning. In Advances in Neural Information Processing Systems (NeurIPS), 2022.

Anthropic. The Claude 3 model family: Opus, sonnet, haiku. Anthropic, 2024. Model card.

Anthropic. Claude. Anthropic, 2026. https://www.anthropic.com/claude.

Rossella Aversa, Mohammad Hadi Modarres, Stefano Cozzini, Regina Ciancio, and Alberto Chiusole. The first annotated set of scanning electron microscopy images for nanoscience. Scientific Data, 5:180172, 2018. doi: 10.1038/sdata.2018.172.

Tadas Baltrušaitis, Chaitanya Ahuja, and Louis-Philippe Morency. Multimodal machine learning: A survey and taxonomy. IEEE Transactions on Pattern Analysis and Machine Intelligence, 41(2):423–443, 2019. doi: 10.1109/TPAMI.2018.2798607.

Marion F. Baumgardner, Larry L. Biehl, and David A. Landgrebe. 220 band AVIRIS hyperspectral image data set: June 12, 1992 indian pine test site 3, 2015.

Jens Behley, Martin Garbade, Andres Milioto, Jan Quenzel, Sven Behnke, Cyrill Stachniss, and Jürgen Gall. SemanticKITTI: A dataset for semantic scene understanding of LiDAR sequences. In IEEE/CVF International Conference on Computer Vision (ICCV), 2019.

Daniil A. Boiko, Robert MacKnight, Ben Kline, and Gabe Gomes. Autonomous chemical research with large language models. Nature, 624(7992):570–578, 2023.

James Burgess, Jefrey J. Nirschl, Laura Bravo-Sánchez, Alejandro Lozano, Sanket Rajan Gupte, Jesus G. Galaz-Montoya, et al. MicroVQA: A multimodal reasoning benchmark for microscopy-based scientific research. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 2025.

Jun Shern Chan, Neil Chowdhury, Oliver Jafe, James Aung, Dane Sherburn, Evan Mays, et al. MLE-bench: Evaluating machine learning agents on machine learning engineering. In International Conference on Learning Representations (ICLR), 2025.

Richard J. Chen, Tong Ding, Ming Y. Lu, Drew F. K. Williamson, Guillaume Jaume, Andrew H. Song, et al. Towards a general-purpose foundation model for computational pathology. Nature Medicine, 30:850–862, 2024. doi: 10.1038/ s41591-024-02857-3.

Ziru Chen, Shĳie Chen, Yuting Ning, Qianheng Zhang, Boshi Wang, Botao Yu, et al. ScienceAgentBench: Toward rigorous assessment of language agents for data-driven scientific discovery. In International Conference on Learning Representations (ICLR), 2025

Kourosh Darvish, Marta Skreta, Yuchi Zhao, Naruki Yoshikawa, Sagnik Som, Miroslav Bogdanović, et al. ORGANA: A robotic assistant for automated chemistry experimentation and characterization. Matter, 8:101897, 2025. doi: 10.1016/j.matt.2024.10.015.

DeepSeek-AI. DeepSeek-R1 incentivizes reasoning in LLMs through reinforcement learning. Nature, 645:633–638, 2025. doi: 10.1038/s41586-025-09422-z.

Andrea Flack, Wolfgang Fiedler, Julio Blas, et al. Costs of migratory decisions: A comparison across eight white stork populations. Science Advances, 2(1):e1500931, 2016. doi: 10.1126/sciadv.1500931.

Kahaan Gandhi, Boris Bolliet, and Inigo Zubeldia. Enhancing agentic autonomous scientific discovery with vision-language model capabilities. arXiv preprint arXiv:2511.14631, 2025.

Ali E. Ghareeb, Benjamin Chang, Ludovico Mitchener, Angela Yiu, Caralyn J. Szostkiewicz, Dmytro Shved, Gavin J. Gyimesi, Jon M. Laurent, et al. A multi-agent system for automating scientific discovery. Nature, 655:497–505, 2026. doi: 10.1038/s41586-026-10652-y.

Google. Gemma 4 technical report, 2026.

Juraj Gottweis, Wei-Hung Weng, Alexander Daryin, Tao Tu, Petar Sirkovic, Artiom Myaskovsky, et al. Accelerating scientific discovery with Co-Scientist. Nature, 655:487–496, 2026. doi: 10.1038/s41586-026-10644-y.

Kam Hamidieh. A data-driven statistical model for predicting the critical temperature of a superconductor. Computational Materials Science, 154:346–354, 2018. doi: 10.1016/j.commatsci.2018.07.052.

Patrick Helber, Benjamin Bischke, Andreas Dengel, and Damian Borth. EuroSAT: A novel dataset and deep learning benchmark for land use and land cover classification. IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing, 12(7):2217–2226, 2019. doi: 10.1109/JSTARS.2019.2918242.

Ginny Hendricks, Dominika Tkaczyk, Jennifer Lin, and Patricia Feeney. Crossref: The sustainable source of communityowned scholarly metadata. Quantitative Science Studies, 1(1):414–427, 2020.

Weihua Hu, Matthias Fey, Marinka Zitnik, Yuxiao Dong, Hongyu Ren, Bowen Liu, Michele Catasta, and Jure Leskovec. Open graph benchmark: Datasets for machine learning on graphs. In Advances in Neural Information Processing Systems (NeurIPS), volume 33, 2020.

David P. Hughes and Marcel Salathé. An open access repository of images on plant health to enable the development of mobile disease diagnostics through machine learning and crowdsourcing. arXiv preprint arXiv:1511.08060, 2015.

InternAgent Team, Bo Zhang, Shiyang Feng, Xiangchao Yan, Jiakang Yuan, Runmin Ma, et al. InternAgent: When agent becomes the scientist. building closed-loop system from hypothesis to verification. arXiv preprint arXiv:2505.16938, 2025.

Intology AI. Zochi technical report, 2025. Technical report, Intology AI.

Johannes Jakubik et al. Foundation models for generalist geospatial artificial intelligence. arXiv:2310.18660, 2023.

Zhengyao Jiang, Dominik Schmidt, Dhruv Srikanth, Dixing Xu, Ian Kaplan, Deniss Jacenko, et al. AIDE: AI-driven exploration in the space of code. arXiv preprint arXiv:2502.13138, 2025.

John Jumper, Richard Evans, Alexander Pritzel, Tim Green, Michael Figurnov, Olaf Ronneberger, Kathryn Tunyasuvunakool, Russ Bates, et al. Highly accurate protein structure prediction with AlphaFold. Nature, 596(7873):583–589, 2021.

Jakob Nikolas Kather, Cleo-Aron Weis, Francesco Bianconi, et al. Multi-class texture analysis in colorectal cancer histology. Scientific Reports, 6:27988, 2016. doi: 10.1038/srep27988.

Justin Kay, Peter Kulits, Suzanne Stathatos, et al. The Caltech Fish Counting dataset: A benchmark for multiple-object tracking and counting. In European Conference on Computer Vision (ECCV), 2022.

Bob Kemp, Aeilko H. Zwinderman, Bert Tuk, Hilbert A. C. Kamphuisen, and Josefien J. L. Oberéyé. Analysis of a sleep-dependent neuronal feedback loop: the slow-wave microcontinuity of the EEG. IEEE Transactions on Biomedical Engineering, 47(9):1185–1194, 2000. doi: 10.1109/10.867928.

Daniel S. Kermany, Michael Goldbaum, Wenjia Cai, et al. Identifying medical diagnoses and treatable diseases by image-based deep learning. Cell, 172(5):1122–1131.e9, 2018. doi: 10.1016/j.cell.2018.02.010.

Sangpil Kim, Hyung-gun Chi, Xiao Hu, Qixing Huang, and Karthik Ramani. A large-scale annotated mechanical components benchmark for classification and retrieval tasks with deep neural networks. In European Conference on Computer Vision (ECCV), pages 175–191, 2020. doi: 10.1007/978-3-030-58523-5\_11.

Sunghwan Kim, Jie Chen, Tiejun Cheng, Asta Gindulyte, Jia He, Siqian He, Qingliang Li, Benjamin A. Shoemaker, Paul A. Thiessen, Bo Yu, et al. PubChem 2025 update. Nucleic Acids Research, 53(D1):D1516–D1525, 2025. doi: 10.1093/nar/gkae1059.

Kimi. Kimi K2: Open agentic intelligence, 2025.

Kenneth R. Knapp, Michael C. Kruk, David H. Levinson, Howard J. Diamond, and Charles J. Neumann. The international best track archive for climate stewardship (IBTrACS): Unifying tropical cyclone data. Bulletin of the American Meteorological Society, 91(3):363–376, 2010. doi: 10.1175/2009BAMS2755.1.

Barbara Lafuente, Robert T. Downs, Hexiong Yang, and Nathan Stone. The power of databases: the RRUFF project. In Thomas Armbruster and Rosa Micaela Danisi, editors, Highlights in Mineralogical Crystallography, pages 1–30. W. De Gruyter, Berlin, Germany, 2015. doi: 10.1515/9783110417104-003.

Bobo Li, Rui Wu, Zibo Ji, Meishan Zhang, Hao Fei, Min Zhang, Mong-Li Lee, and Wynne Hsu. Taming actor-observer asymmetry in agents via dialectical alignment. In Proceedings of ACL, pages 24068–24084, 2026a.

Shawn Li and Yue Zhao. The autonomy tax: Defense training breaks llm agents, 2026. URL https://arxiv.org/abs/2603. 19423.

Shawn Li, Chenxiao Yu, Han Wang, Wei Yang, Ryan Rossi, Franck Dernoncourt, Xiyang Hu, Philip Yu, Chaowei Xiao, Huan Zhang, and Yue Zhao. Fortis: Benchmarking over-privilege in agent skills, 2026b. URL https://arxiv.org/abs/ 2605.09163.

Zekun Li, Xianjun Yang, Kyuri Choi, Wanrong Zhu, Ryan Hsieh, HyeonJung Kim, et al. MMSci: A dataset for graduate-level multi-discipline multimodal scientific understanding. arXiv preprint arXiv:2407.04903, 2024.

LIGO-Virgo Collaboration. Open data from the first and second observing runs of Advanced LIGO and Advanced Virgo. SoftwareX, 13:100658, 2021. doi: 10.1016/j.softx.2021.100658.

Chris J. Lintott et al. Galaxy zoo: morphologies derived from visual inspection of galaxies from the Sloan Digital Sky Survey. Monthly Notices of the Royal Astronomical Society, 389(3):1179–1189, 2008. doi: 10.1111/j.1365-2966.2008.13689.x.

Chengyu Liu, David Springer, Qiao Li, Benjamin Moody, et al. An open access database for the evaluation of heart sound algorithms. Physiological Measurement, 37(12):2181–2213, 2016. doi: 10.1088/0967-3334/37/12/2181.

Haotian Liu, Chunyuan Li, Qingyang Wu, and Yong Jae Lee. Visual instruction tuning. In Advances in Neural Information Processing Systems (NeurIPS), 2023.

Alejandro Lozano, Jefrey Nirschl, James Burgess, Sanket Rajan Gupte, Yuhui Zhang, Alyssa Unell, et al. ??-bench: A vision-language benchmark for microscopy understanding. In Proceedings of NeurIPS (Datasets and Benchmarks Track), 2024.

Chris Lu, Cong Lu, Robert Tjarko Lange, Yutaro Yamada, Shengran Hu, Jakob Foerster, David Ha, and Jef Clune. Towards end-to-end automation of AI research. Nature, 651:914–919, 2026. doi: 10.1038/s41586-026-10265-5.

Indrajeet Mandal, Jitendra Soni, Mohd Zaki, Morten M. Smedskjaer, Katrin Wondraczek, et al. Evaluating large language model agents for automation of atomic force microscopy. Nature Communications, 16:9104, 2025. doi: 10.1038/s41467-025-64105-7.

Ludovico Mitchener, Angela Yiu, Benjamin Chang, Mathieu Bourdenx, Tyler Nadolski, Arvis Sulovari, et al. Kosmos: An AI scientist for autonomous discovery. arXiv preprint arXiv:2511.02824, 2025.

S. Mostafa Mousavi, Yixiao Sheng, Weiqiang Zhu, and Gregory C. Beroza. STanford EArthquake Dataset (STEAD): A global data set of seismic signals for AI. IEEE Access, 7:179464–179476, 2019. doi: 10.1109/ACCESS.2019.2947848.

Ngoc Giang Nguyen, Vu Anh Tran, Duc Luu Ngo, Dau Phan, Favorisen Rosyking Lumbanraja, Mohammad Reza Faisal, Bahriddin Abapihi, Mamoru Kubo, and Kenji Satou. DNA sequence classification by convolutional neural network. Journal of Biomedical Science and Engineering, 9(5):280–286, 2016. doi: 10.4236/jbise.2016.95021.

OpenAI. GPT-4 technical report. arXiv preprint arXiv:2303.08774, 2023.

OpenAI. GPT-5.6. OpenAI, 2026.

Eric C. Orenstein, Oscar Beĳbom, Emily E. Peacock, and Heidi M. Sosik. WHOI-Plankton: A large scale fine grained visual recognition benchmark dataset for plankton classification. arXiv preprint arXiv:1510.00745, 2015.

Liam Parker et al. AstroCLIP: A cross-modal foundation model for galaxies. Monthly Notices of the Royal Astronomical Society, 531:4990–5011, 2024. doi: 10.1093/mnras/stae1450.

Shraman Pramanick, Rama Chellappa, and Subhashini Venugopalan. SPIQA: A dataset for multimodal question answering on scientific papers. In Advances in Neural Information Processing Systems (NeurIPS) Datasets and Benchmarks Track, 2024.

Jason Priem, Heather Piwowar, and Richard Orr. OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts. arXiv preprint arXiv:2205.01833, 2022.

Maša Prodanović, Maria Esteva, Matthew Hanlon, Ganesh Nanda, and Prateek Agarwal. Digital rocks portal: a repository for porous media images. Digital Rocks Portal, University of Texas at Austin, 2015.

Harsh Purohit, Ryo Tanabe, Kenji Ichige, Takashi Endo, Yuki Nikaido, Kaori Suefusa, and Yohei Kawaguchi. MIMII dataset: Sound dataset for malfunctioning industrial machine investigation and inspection. In Workshop on Detection and Classification of Acoustic Scenes and Events (DCASE), 2019.

Qwen Team. Qwen3.5. Alibaba Qwen, 2026. https://huggingface.co/Qwen.

Alec Radford, Jong Wook Kim, Chris Hallacy, Aditya Ramesh, Gabriel Goh, Sandhini Agarwal, Girish Sastry, Amanda Askell, Pamela Mishkin, Jack Clark, Gretchen Krueger, and Ilya Sutskever. Learning transferable visual models from natural language supervision. In International Conference on Machine Learning (ICML), 2021.

Jonathan Roberts, Kai Han, Neil Houlsby, and Samuel Albanie. SciFIBench: Benchmarking large multimodal models for scientific figure interpretation. In Proceedings of NeurIPS (Datasets and Benchmarks Track), 2024.

David Robinson, Marius Miron, Masato Hagiwara, Benno Weck, Sara Keen, Milad Alizadeh, et al. NatureLM-audio: An audio-language foundation model for bioacoustics. In International Conference on Learning Representations (ICLR), 2025.

Laela Sayigh, Mary Ann Daher, Julie Allen, Helen Gordon, Katherine Joyce, Claire Stuhlmann, and Peter Tyack. The Watkins Marine Mammal Sound Database: An online, freely accessible resource. Proceedings of Meetings on Acoustics, 27 (1):040013, 2016. doi: 10.1121/2.0000358.

Harald Schäfer, Eder Santana, Andrew Haden, and Riccardo Biasini. A commute in data: The comma2k19 dataset. arXiv preprint arXiv:1812.05752, 2018.

Timo Schick, Jane Dwivedi-Yu, Roberto Dessì, Roberta Raileanu, Maria Lomeli, Eric Hambro, Luke Zettlemoyer, Nicola Cancedda, and Thomas Scialom. Toolformer: Language models can teach themselves to use tools. In Advances in Neural Information Processing Systems (NeurIPS), 2023.

Samuel Schmidgall et al. Agent laboratory: Using LLM agents as research assistants. arXiv preprint arXiv:2501.04227, 2025.

David Schunck, Federico Magistri, et al. Pheno4D: A spatio-temporal dataset of maize and tomato plant point clouds for phenotyping and advanced plant analysis. PLOS ONE, 16(8):e0256340, 2021. doi: 10.1371/journal.pone.0256340.

Chenyang Shao, Dehao Huang, Yu Li, Keyu Zhao, Fengli Xu, Yong Li, Tie-Yan Liu, et al. OmniScientist: Toward a co-evolving ecosystem of human and AI scientists. arXiv preprint arXiv:2511.16931, 2025.

Noah Shinn, Federico Cassano, Edward Berman, Ashwin Gopinath, Karthik Narasimhan, and Shunyu Yao. Reflexion: Language agents with verbal reinforcement learning. In Advances in Neural Information Processing Systems (NeurIPS), 2023.

Giulio Starace, Oliver Jafe, Dane Sherburn, James Aung, Jun Shern Chan, Leon Maksin, et al. PaperBench: Evaluating AI’s ability to replicate AI research. arXiv preprint arXiv:2504.01848, 2025.

Dan Stowell, Michael D. Wood, Hanna Pamuła, Yannis Stylianou, and Hervé Glotin. Automatic acoustic detection of birds through deep learning: the first Bird Audio Detection challenge. Methods in Ecology and Evolution, 10(3):368–380, 2019. doi: 10.1111/2041-210X.13103.

Jennifer J. Sun, Tomomi Karigo, Dipam Chakraborty, et al. The multi-agent behavior dataset: Mouse dyadic social interactions. In Advances in Neural Information Processing Systems (NeurIPS) Datasets and Benchmarks Track, 2021.

Qiushi Sun, Zhoumianze Liu, Chang Ma, et al. ScienceBoard: Evaluating multimodal autonomous agents in realistic scientific workflows. In International Conference on Learning Representations (ICLR), 2026.

Kyle Swanson, Wesley Wu, Nash L. Bulaong, John E. Pak, and James Zou. The virtual lab of AI agents designs new SARS-CoV-2 nanobodies. Nature, 646:716–723, 2025. doi: 10.1038/s41586-025-09442-9.

Nathan J. Szymanski, Bernardus Rendy, Yuxing Fei, Rishi E. Kumar, Tanjin He, David Milsted, et al. An autonomous laboratory for the accelerated synthesis of inorganic materials. Nature, 624:86–91, 2023. doi: 10.1038/s41586-023-06734-w.

Makoto Takamoto, Timothy Praditia, Raphael Leiteritz, Dan MacKinlay, Francesco Alesiani, Dirk Pflüger, and Mathias Niepert. PDEBench: An extensive benchmark for scientific machine learning. In Advances in Neural Information Processing Systems (NeurIPS) Datasets and Benchmarks Track, 2022.

Jiabin Tang, Lianghao Xia, Zhonghang Li, and Chao Huang. AI-Researcher: Autonomous scientific innovation. arXiv preprint arXiv:2505.18705, 2025.

Silviu-Marian Udrescu and Max Tegmark. AI Feynman: A physics-inspired method for symbolic regression. Science Advances, 6(16):eaay2631, 2020. doi: 10.1126/sciadv.aay2631.

Vladimír Ulman, Martin Maška, Klas E. G. Magnusson, et al. An objective comparison of cell-tracking algorithms. Nature Methods, 14:1141–1152, 2017. doi: 10.1038/nmeth.4473.

U.S. DOT FHWA. Next generation simulation (NGSIM) vehicle trajectories and supporting data. ITS DataHub (data.transportation.gov), 2016.

Mark S. Veillette, Siddharth Samsi, and Christopher J. Mattioli. SEVIR: A storm event imagery dataset for deep learning applications in radar and satellite meteorology. In Proceedings of NeurIPS, volume 33, 2020.

Francisco Villaescusa-Navarro, Boris Bolliet, Pablo Villanueva-Domingo, Adrian E. Bayer, Aidan Acquah, Chetana Amancharla, et al. The Denario project: Deep knowledge AI agents for scientific discovery. arXiv:2510.26887, 2025.

Mike Walmsley et al. Galaxy zoo DECaLS: Detailed visual morphology measurements from volunteers and deep learning for 314,000 galaxies. Monthly Notices of the Royal Astronomical Society, 509(3):3966–3988, 2022. doi: 10.1093/mnras/stab2093.

Hanchen Wang, Tianfan Fu, Yuanqi Du, Wenhao Gao, Kexin Huang, Ziming Liu, Payal Chandak, Shengchao Liu, Peter Van Katwyk, Andreea Deac, et al. Scientific discovery in the age of artificial intelligence. Nature, 620:47–60, 2023. doi: 10.1038/s41586-023-06221-2.

Zirui Wang, Mengzhou Xia, Luxi He, Howard Chen, Yitao Liu, Richard Zhu, et al. CharXiv: Charting gaps in realistic chart understanding in multimodal LLMs. In Proceedings of NeurIPS (Datasets and Benchmarks Track), 2024.

Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed H. Chi, Quoc V. Le, and Denny Zhou. Chain-of-thought prompting elicits reasoning in large language models. In Proceedings of NeurIPS, 2022.

Jiaqi Wei, Yue-Jin Yang, Xiang Zhang, Yuhan Chen, Xiang Zhuang, Zhangyang Gao, et al. From AI for science to agentic science: A survey on autonomous scientific discovery. arXiv preprint arXiv:2508.14111, 2025.

Yicheng Xu, Yue Wu, Jiashuo Yu, Ziang Yan, Tianxiang Jiang, Yinan He, et al. ExpVid: A benchmark for experiment video understanding and reasoning. arXiv preprint arXiv:2510.11606, 2025.

Yutaro Yamada, Robert Tjarko Lange, Cong Lu, Shengran Hu, Chris Lu, Jakob Foerster, Jef Clune, and David Ha. The A Scientist-v2: Workshop-level automated scientific discovery via agentic tree search. arXiv preprint arXiv:2504.08066, 2025.

Jiancheng Yang, Rui Shi, Donglai Wei, Zequan Liu, Lin Zhao, Bilian Ke, Hanspeter Pfister, and Bingbing Ni. MedMNIST v2: A large-scale lightweight benchmark for 2d and 3d biomedical image classification. Scientific Data, 10:41, 2023a. doi: 10.1038/s41597-022-01721-8.

Zhengyuan Yang et al. MM-ReAct: Prompting ChatGPT for multimodal reasoning and action. arXiv:2303.11381, 2023b.

Lance Yao, Suman Samantray, Ayana Ghosh, Kevin M. Roccapriore, Libor Kovarik, Sarah I. Allec, and Maxim Ziatdinov. Operationalizing serendipity: Multi-agent AI workflows for enhanced materials characterization with theory-in-the-loop. arXiv preprint arXiv:2508.06569, 2025.

Shunyu Yao, Jefrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, and Yuan Cao. ReAct: Synergizing reasoning and acting in language models. In International Conference on Learning Representations (ICLR), 2023.

Jiakang Yuan, Xiangchao Yan, Botian Shi, et al. Dolphin: Moving towards closed-loop auto-research through thinking, practice, and feedback. arXiv preprint arXiv:2501.03916, 2025.

Xiang Yue et al. MMMU: A massive multi-discipline multimodal understanding and reasoning benchmark for expert AGI. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 2024.

Bingchen Zhao, Sara Beery, and Oisin Mac Aodha. Autonomous scientific discovery via iterative meta-reflection. arXiv preprint arXiv:2607.01131, 2026.

Zhipu. GLM-5: From vibe coding to agentic engineering, 2026.

Yuhao Zhou, Yiheng Wang, Xuming He, Ao Shen, Ruoyao Xiao, Zhiwei Li, et al. Scientists’ first exam: Probing cognitive abilities of MLLM via perception, understanding, and reasoning. arXiv preprint arXiv:2506.10521, 2025.

## A Additional evaluation detail

This section provides the supporting analyses for the primary evaluation presented in Section 5.2. These supplementary results include the per-paper computational cost across diferent backbones (Table 11), a heatmap visualization of the backbone performance rubric (Figure 13), a dimension-by-dimension breakdown of the perception gain (Table 12), and the validation metrics for the judge panel (Table 13).

Table 11. Cost per paper by backbone model. The experiment stage dominates the overall cost across all evaluated systems. <sup>†</sup>Openweight backbones were run locally.  
![](images/2675505ed54589964cf0c3654524ef724e12007b58f9da37c219fa2f64ee6b46.jpg)

Table 12. Perception gain per evaluation dimension. Across 5 blind pairs and 1 vision-off pair, each cell represents the difference in panel scores (original scale: 0–10) between the perception-enabled system and the blind baseline. Positive values indicate that visua perception improves performance. <sup>†</sup> Cardiology uses the weaker vision-off run.  
![](images/282b5fcc8c2ba8456aa7f1c0e310f0aa99d6be719ecdc063ef469cd57f0f4027.jpg)

Table 13. Validating the judge before it is trusted; the target column lists the pre-set acceptance thresholds.  
![](images/b77ebaecfb5df62b72cb1c8d00821f176837044810a9d8f3a5b59150cfe0abb1.jpg)

Listing 1 reproduces the rubric both judges receive. It is the whole of what they are told, besides the manuscript source, its figure captions, and the authors’ result ledger, and the same text is used for every case and every backbone.

Review rubric: the whole of what each judge is told You are an expert, critical peer reviewer for a top venue, reviewing ONE paper produced by an automated multimodal research system. Judge ONLY what is written in the paper and shown in its figures. Do NOT inflate scores.

Score these SEVEN dimensions, each an INTEGER 1-10 (1=very poor, 10=excellent), and be strict -- an incremental or workshop-level paper must be scored as such, never rubber-stamped: 1. novelty -- originality against real prior art.

2. soundness -- method and statistics correct (controls, multiple-comparison correction, no leakage).

3. clarity -- presentation and structure.

![](images/e149bcacb687bb7d7910f920b795cebc1453a57e5fab9a1478803ef59cb2a357.jpg)  
Figure 13. Heatmap visualization of the evaluation scores from Table 3. Darker cells indicate higher panel scores. Model reasoning strength corresponds to row darkness, with the strongest backbones positioned at the top and smaller open-weight models at the bottom. Notably, factual accuracy consistently achieves the highest scores (the darkest column) across all evaluated models

4. significance -- importance of the finding.

5. reproducibility -- enough detail to re-run.

6. mm\_grounding -- does the paper GENUINELY use the visual / observational evidence (the attached figures of raw observations), or is it just statistics on scalar features? Reward papers that SHOW and INTERPRET raw observations; penalize ones whose figures are absent, unreadable, or decorative.

7. factual\_accuracy -- does EVERY headline number in the paper trace to the AUTHORS' RESULT

LEDGER below? Penalize any statistic or claim not supported by the ledger.

Listing 1. The review rubric, verbatim. Each judge receives this, the manuscript source, the figure captions, and the authors result ledger, and nothing else.

## B The checks enforced in code

The idea, rigour, and claim checks of Section 4 are not model self-assessment. Each is a Python predicate that receives the stage’s finalize payload and the accumulated loop state, returning either acceptance or a reason string. A rejection is appended to the conversation as a new observation and the agent continues; the stage cannot end until the predicate accepts or the step budget runs out. Algorithm 2 details the loop, Table 14 lists every condition, and Table 15 reports what those conditions rejected over the 36 primary runs.

The distribution in Table 15 indicates where an autonomous researcher most often goes wrong. Two thirds of all rejections concern result selection rather than arithmetic: the agent had run a broad battery, one analysis came out non-significant, and the draft still treated it as a finding. Outright fabrication is rare, with a single provenance rejection across 36 runs; this is expected if reported numbers are normally copied from real standard output. Most of the remainder involves schema discipline, where a field the manuscript later depends on was simply left blank.

Table 14. Every condition enforced by the 3 checks. Each row is a separate predicate in the stage’s exit function; failing any predicate returns the agent to the loop with the corresponding demand as the reason. The claim check runs on the drafted manuscript rather than a finalize payload, so it acts on the text itself.  
![](images/145bd1f562055e065cab97545bee83f80ab2c7a56d0a3b8ed2663d9d232cbc3c.jpg)

Algorithm 2 One gated stage. The agent reasons freely inside the loop, while the stage boundary is a deterministic predicate over the run’s own record. Algorithm 1 expands the predicate  for the experiment stage.

Require: system prompt , task message , tools , exit predicate , step budget , perception budget   
<sup>?? ?? ?? ??</sup><sub>1:</sub> ← [ ]<sub>; ??</sub> ← {good\_runs<sub>=0</sub> searched<sub>=0</sub> img\_used<sub>=0</sub> stdout<sub>=</sub>∅}   
<sup>ℎ ??,</sup> <sup>??</sup>2: for = 1 to do   
3: ← Model( ) ⊲ reasoning plus zero or more tool calls   
4: <sup>?? ℎ,</sup> <sup>??</sup>for all tool calls <sup>∈</sup> do   
5: <sup>?? ??</sup>if is a perception call and ?? <sup>img\_used ≥</sup> then   
6: <sup>?? ←</sup> “budget exhausted”   
7: <sup>??</sup>else   
8: ← Execute( )<sub>;</sub> <sub>update ??</sub> ⊲ stdout, data reads, searches, looks   
9: <sup>??</sup>end if   
10: append  to   
11: end for   
12: if called finalize then   
13: <sup>(</sup>ok why<sup>)</sup> <sup>←</sup> <sup>(</sup> payload ??<sup>)</sup> ⊲ the check, in code, over what really happened   
14: <sup>,</sup>if ok then   
15: return payload ⊲ stage output admitted   
16: else   
17: append why to ⊲ the agent is told what failed and continues   
18: end if   
19: end if   
20: end for   
<sub>21:</sub> return Failed ⊲ the outer pipeline backtracks to ideation

Table 15. Check rejections across the 36 primary runs. The two count columns differ because a single run can be rejected multiple times by the same condition. The checks refused 115 finalize attempts in total, and only 4 of the 36 runs reached both stage exits without ever being sent back. The dominant single cause is result selection: in 26 runs, the agent tried to present a non-significant analysis as a finding and was made to demote it.

![](images/5777700636cb8ebc595885a0825983e3aff2924cf0a58d9fc65bd5a850eac821.jpg)

## C Run-level execution statistics

Table 16 reports the composition of a single system run, measured over the 36 primary runs by replaying their stored traces. Ideation and experiment difer sharply in character. Ideation is search-heavy and perceptionheavy, spending most of its calls on literature searches and raw item inspection, and it never runs code. Experiment is execution-heavy, averaging 31 8 run\_python calls per run, and it returns to the raw evidence only occasionally because the observation that shaped the question has already been made. Table 17 reports what those runs concluded.

Table 16. Run composition across the 36 primary runs. Counts represent issued tool calls recovered from each run’s stored trace. The step budget is 24 for ideation and 50 for experiment, and no run exhausted either.  
![](images/4c9ba899b8abde74d6ed71e3ba9230e8d7f105aa7454585eaff5ce980210b392.jpg)

Table 17. Outcomes of the 36 primary runs. The verdicts are the system’s own, taken from the verified experiment record. Demoted analyses were executed and remain in the trace, but the claim check excludes them from the manuscript.  
![](images/1019c2ce1bd10e1c776fc1388f76e6dd4db716349f43f2320e28342480529b0a.jpg)

Two of these numbers deserve comment. The 2 refuted and 17 mixed verdicts are not system failures but the intended behaviour of the rigour check, which admits an honest negative as a valid exit and forbids promoting a weak result to the headline. The 67 demoted analyses reflect this same mechanism, since roughly a fifth of everything the system computed was run, found wanting, and deliberately kept out of the paper.

## D The perception layer

Table 18 lists the perception tools this suite exposed and how heavily each was used across the 36 primary runs. The table reveals two properties of the design. First, a modality is never forced into an image. Signals, audio, video, 3-D structures, and trajectories each expose a native reader that returns numbers in the modality’s own terms alongside a visual reader that renders the artifact for inspection, allowing the agent to choose between them. Second, the visual channel is used substantively rather than incidentally, since 173 of the 337 perception calls went to a look\_at\_\* tool and every tool listed was invoked at least once.

Table 18. The perception layer. A modality automatically unlocks its tools from the specification file, requiring no per-discipline registration. Cases indicates how many of the 36 primary runs had the tool available, and Calls indicates how many times it was invoked.  
![](images/3b2e65a40d20e42e95e39a0f371fbd5c95fd679376eddf9651dcef4e4d64a59a.jpg)

## E Task specification for a new discipline

Adding a discipline requires one specification file and no change to the engine. Listing 2 shows the file for the seismology case of Section 5.5, abridged to 2 of its roughly 1,500 members. Four fields carry the science: the role the agent assumes, the subject the data describes, the property each record measures, and the open request. The member list contains only the file paths and any metadata the dataset ships with. The file names no method, hypothesis, or analysis, and the engine reads no part of it as a special case. The modality field, or the file extension when it is absent, unlocks the perception tools of Table 18.

```jsonl
Task specification: the seismology case
"role": "a seismologist analyzing three-component broadband seismic waveforms",
"subject": "a 60-second three-component (E, N, Z) seismogram sampled at 100 Hz (a 3 x 6000
array) recorded at a broadband seismic station (the STEAD catalogue)",
"property": "ground-motion amplitude over time on three orthogonal components; each trace is
catalogued as either a local earthquake or ambient noise; earthquake traces
additionally carry source magnitude, epicentral distance (km) and depth (km), and
every trace carries station network, station code and instrument channel metadata",
"request": "Find a concrete, novel, testable question this data can answer, decide your own
method, run real code on the waveforms, and produce a short publishable paper.",
"members": [
{"idx": 0, "file": "data/seis_0000.npy", "label": "earthquake", "modality": "signal",
"network": "NN", "station": "COLR", "channel": "HH",
"magnitude": 1.2, "distance_km": 17.2, "depth_km": 8.6},
{"idx": 1, "file": "data/seis_0001.npy", "label": "noise", "modality": "signal",
"network": "AG", "station": "LCAR", "channel": "HH",
"magnitude": null, "distance_km": null, "depth_km": null}
]
}
```  
Listing 2. The complete task specification for the seismology case, abridged to 2 of its roughly 1,500 members. The engine reads nothing else about the discipline.

## F Field-specific writeup specifications

Table 19. The 5 structural specifications that the writeup stage can resolve to. The abstract column shows the word range for a single-paragraph abstract.  
![](images/9a68e337e411a95c6353f62da2950ffd05a898683038eb6696784521fe28a491.jpg)

The writeup stage supports 5 structural specifications, resolved from the case specification or inferred from the subject. Table 19 shows their skeletons. Each section additionally receives a word budget, a paragraph count, and a paragraph-level outline. The drafting pass expands this outline one section at a time, using only the slice of the experiment record allocated to that section. The structural diferences between these skeletons reflect actual field conventions: a machine-learning paper includes Related Work and Limitations, a biomedical paper puts Methods last, and a chemistry paper merges Results with Discussion.

## G Stage prompts

Ideation and experiment are each driven by a single system prompt assembled at run time from the case specification, allowing one template to serve every discipline. The role and request come from Listing 2, and the list of available perception tools comes from the detected modalities. Listings 3 and 4 reproduce the process and grounding sections of these two prompts verbatim, omitting the tool inventory and role interpolation. The writeup stage has no comparable single text because it is prompted one section at a time using the structural specification in Section F and the slice of the experiment record available to that section.

Two properties of these prompts are worth noting alongside the checks of Section B. First, every demand the prompt makes is also a predicate. Because the prompt states what is wanted and the exit check refuses the stage when it is missing, the instruction does not depend on the model choosing to comply. Second, the prompts never name a discipline, a modality, or a method. They describe how to conduct research, and the specification file supplies what the research is about.

Ideation stage: system prompt

PROCESS (keeps the idea non-trivial, novel, AND actually runnable -- do not skip it):

1. INSPECT THE MATERIALS: list\_materials (and use the perception tools on a few representative items) to identify WHAT KIND of data this is and what is actually in it.

2. KNOWN LANDSCAPE: a SMALL number of FOCUSED literature searches (about 3-6) to establish what is already well-established, so you deliberately AVOID it.

3. FIND THE QUESTION: from what the materials actually contain, decide the most concrete, novel, testable question this data can genuinely support. Do NOT force a question the data cannot sustain.

4. BRAINSTORM >=5 candidate research projects. Use what you OBSERVED in the materials to GENERATE candidates from concrete patterns, not literature alone. Self-screen EACH on novelty\_risk (already published / obvious? low / med / high).

5. FEASIBILITY (be brutally honest -- this is a HARD GATE): rate each candidate fully\_computational -- can it be carried out END-TO-END on a computer with NO wet-lab experiment? Also note falsifiable and statistical\_power at this sample size.

6. SELECT the ONE candidate that is GENUINELY NOVEL and fully\_computational=YES -- the goal is NOVEL AND feasible, NOT the safest option; also falsifiable, and 'valuable even if it fails', preferring one whose core hypothesis was inspired by inspecting the materials rather than literature alone.

7. Develop the selected candidate into a full, falsifiable proposal and call finalize\_idea.

GROUNDING RULES (a proposal that violates these is NOT ready -- the exit gate enforces them): - VISION: when you look at an item you are ALSO shown its GIVEN label; RECONCILE your read with it. If they disagree, do NOT proceed on your read -- flag it, re-check the id / label, lower confidence. Never name a class outside the given label space, and never characterize a group

you did not view.

\- NOVELTY: run >=3 focused searches incl. one aimed at your SELECTED idea specifically; phrase novelty as 'based on this search, appears under-explored' -- NEVER 'unstudied / first / no prior work'.

\- CLAIM SCOPE: separate what the data DIRECTLY shows from a broader mechanism or causal claim it cannot prove; keep the research\_question and the minimal\_publishable\_claim on the supported side.

\- STAT POWER: estimate from the REAL data counts how many DECISIVE events your key test needs; if they will be rare, use CONTINUOUS signals or the full dataset -- do not rely on a handful of hard events.

\- NO LEAKAGE: no step may use ground-truth labels at inference / decision time; any label-conditioned selection is oracle / upper-bound only and needs a label-agnostic counterpart plus its false-positive rate.

Listing 3. Ideation system prompt, process and grounding sections, verbatim. The tool list and the role string are interpolated from the case specification.

Experiment stage: system prompt

A FULL STUDY = this battery (do every one the data can support; aim for >=5 analyses and \~8 figures / tables):

(1) PRIMARY: the pre-specified test of your hypothesis. It MAY come out weak or fail -- that is fine and normal; do NOT force it to look like a win.

(2) BASELINE: contrast vs a simpler / alternative method or a trivial baseline.

(3) ABLATION: remove or vary a component to show which part drives the result.

(4) MECHANISM: dig into WHY the efect arises, not just that it does.

(5) BREAKDOWN: split by group / class / condition / time -- where it holds and where not.

(6) SENSITIVITY: vary the key thresholds / hyperparameters / subsample and show the finding is stable.

(7) LEAKAGE / GROUPING: if the data carries ANY grouping id (source / event / subject / patient / site / recording / network), you MUST evaluate under a group-disjoint or leave-one-group-out split, and report the group-out metric next to the random-split one.

IRON RULE -- NO FABRICATION: every number you report MUST come from real run\_python output. NEVER hard-code, invent, or 'expand' data rows -- LOAD the real data. If the data genuinely cannot support the test, run what you can and report verdict='infeasible' with what you found.

RIGOR (the exit gate enforces these):

\- MULTIPLE COMPARISONS: if you run several statistical tests, COUNT every test you actually ran and correct for THAT count (Bonferroni / FDR); report which results survive. Do not under-count the tests.

\- INDEPENDENCE: if your predictor and your outcome come from the SAME model or representation, the correlation may be circular -- use an INDEPENDENT predictor or explicitly scope the claim to 'within this representation'.

\- HONEST POWER: a sub-result resting on very few events is 'suggestive', NOT a confirmed finding -- say so.

REFRAME (do this at the END, before you finalize): pick the LEAD = the single STRONGEST SUPPORTED analysis in your battery. HARKing guard: a LEAD is only allowed if it (a) survives your multiple-comparison correction, (b) has a clear efect size, and (c) is not just the best of many noisy tries; if nothing clears this bar, report verdict='mixed' or 'null' honestly -- do NOT promote a weak result. Put any failed or weak analysis (including a failed PRIMARY) in 'demoted'; the paper does not mention it, it only lives in the trace.

Listing 4. Experiment system prompt: the battery, the anti-fabrication rule and the anti-HARKing rule, verbatim.