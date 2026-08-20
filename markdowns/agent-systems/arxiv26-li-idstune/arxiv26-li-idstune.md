# IDSTune: A Multi-Agent Collaborative Framework for Integrated Database System Tuning

Yiyan Li<sup>\*</sup>, Guanli Liu<sup>†</sup>, Renata Borovica-Gajic<sup>†</sup>, Haoyang Li<sup>\*</sup>, Zihang Qiu<sup>\*</sup>, Xinmei Huang<sup>\*</sup>, Andreas Kipf<sup>‡</sup>, Cuiping Li<sup>\*</sup>, Hong Chen

<sup>\*</sup> Renmin University of China, <sup>†</sup> The University of Melbourne, <sup>‡</sup> University of Technology Nuremberg {liyiyan,lihaoyang.cs,qiuzihang2024,huangxinmei,licuiping,chong}@ruc.edu.cn {guanli.liu1,renata.borovica}@unimelb.edu.au andreas.kipf@utn.de

## Abstract

Database tuning is critical for achieving high performance in modern database management systems (DBMSs). Existing methods typically optimize a single component—knobs, indexes, or mate rialized views—without accounting for their interdependencies. This limitation arises because these components require diferent tuning strategies and are dificult to integrate within a unified framework. As a result, directly extending a method to multiple components or simply combining separate methods often fails to capture cross-component collaboration and shared tuning signals. Moreover, existing methods are insuficient for handling diverse workloads, evolving data, and dynamic query patterns.

To address these limitations, we propose IDSTune, an integrated tuning framework that jointly optimizes multiple configuration components through LLM-driven multi-agent collaboration. ID-STune operates in two phases: (i) workload compression, which extracts and selects task-relevant features, and (ii) configuration recommendation, where specialized agents collaboratively generate and refine configurations for knobs, indexes, and materialized views under the supervision of a centralized coordinator. By incorporating feedback and external knowledge retrieval, IDSTune achieves efi cient and globally consistent tuning. Extensive experiments show that IDSTune achieves up to 38% performance improvement and 57% faster tuning, with strong adaptability across diverse scenarios.

## Keywords

Database Tuning, Large Language Models, Physical Design, Knobs

## 1 Introduction

Modern database management systems (DBMSs) expose numerous tunable components, typically categorized into three types: knobs, indexes, and materialized views (MVs) [10]. Knobs typically correspond to system-level parameters that influence database behavior, whereas indexes and MVs represent discrete physical design decisions that directly modify the database structure and expand the query plan search space, often incurring non-trivial creation and maintenance costs. Together, these components define the DBMS configuration, which determines how queries are executed and how eficiently the system performs. Finding the optimal configuration for a given workload is challenging due to the high-dimensional na ture of these components and their complex interdependencies [46].

Over the past decade, extensive studies have explored single component tuning [9, 19, 22, 27, 37, 43], including knobs [22, 27], indexes [19, 37], and MVs [9, 43]. While these approaches efectively

![](images/dfc80289870a06c61bb45afba5b90dc52f41e3a758d2b83ffb4254d975274e38.jpg)

![](images/6ab155d3113d0a700f62cea286f85f3b143a2224e1db6f26484ade9a1ea567d9.jpg)  
Figure 1: Combining UniView (materialized views recommendation) and <sup>??</sup>Tune (knob and index recommendation) results in a slowdown, while IDSTune improves performance on the JOB benchmark: (a) overall performance, and (b) Query 33b. optimize individual components, they remain limited in scope and fail to capture dependencies across diferent DBMS subsystems.

To address this, recent research has extended beyond singlecomponent tuning to jointly optimize multiple configurations [14, 36, 46]. Existing studies can be broadly categorized into two directions: (1) Knob+Index tuning, which investigates the interaction between system parameters and indexes [14, 46]; and (2) MV+Index tuning (often referred to as physical design tuning), which explores the joint efects of indexes and materialized views [36].

Although these methods achieve promising results within their respective configuration spaces, they essentially target only a subset of the database configuration spectrum. As a result, they struggle to generalize to real-world scenarios involving multiple configuration types. Moreover, they lack coordination mechanisms to reconcile conflicting recommendations across components, often leading to inconsistent or suboptimal configurations. For example, in the JOB benchmark [23], combining <sup>??</sup>-Tune [14] (a leading knob and index tuning algorithm) with UniView [43] (a state-of-the-art MV recommendation method) leads to degraded performance, as shown in Fig. 1(a). This efect is particularly evident in query 33b (Fig. 1(b)), where conflicting optimizations—UniView materializing an intermediate result and <sup>??</sup>-Tune increasing work\_mem—cause a plan change and substantial unnecessary computation. This highlights the need for an integrated framework that jointly optimizes multiple components and resolves cross-component conflicts.

Extending existing tuning methods to additional components reveals three fundamental limitations:

(L1) Limited optimization efectiveness. Diferent configuration components are highly interdependent, and optimizing them in isolation often produces conflicting adjustments. As a result, combining locally optimal solutions may fail to achieve global optimality or even degrade performance.

(L2) Ineficient tuning process. Even single-component ML-based methods [24, 45] often require hundreds of iterations to converge. Each iteration involves executing the workload (i.e., workload replay), leading to tuning processes lasting for hours. When multiple tuning algorithms are combined, cumulative training and evaluation costs become prohibitively high.

(L3) Limited scenarios. Existing approaches are usually designed for fixed configuration spaces, specific database engines, and static workloads, making them dificult to apply to complex, diverse, and dynamic real-world production scenarios.

To address these challenges, we propose IDSTune (Integrated Database System Tuning), a framework driven by large language model (LLM)-based multi-agent collaboration. At its core, a centralized supervisor coordinates multiple specialized agents, detects conflicts, and enforces globally consistent configuration decisions.

IDSTune decomposes the tuning process into two main phases: (i) workload compression, which extracts and filters task-relevant workload features; and (ii) configuration recommendation, where specialized agents collaboratively optimize knobs, indexes, and MVs under centralized supervision. This coordinated multi-agent design enables holistic optimization across interdependent configuration components (addressing L1), while its iterative feedback mechanism accelerates convergence and improves tuning eficiency (addressing L2). Additionally, rich features, training-free design, and search capability enable our method to be rapidly deployed and adapt to diverse application scenarios (addressing L3).

Our work makes the following contributions:

• We propose IDSTune, the first LLM-driven multi-agent frame work for integrated database tuning, jointly optimizing knobs, indexes, and MVs within a unified process.

• We design a centralized multi-agent architecture with built-in search, where heterogeneous agents collaboratively refine tuning decisions through coordinated interaction and feedback, handling cross-component complexity.

• We introduce a feature-based workload compression paradigm that adaptively selects workload- and task-relevant features, providing compact, informative tuning contexts.

• We conduct extensive experiments on seven workloads spanning OLTP, OLAP, and real-world scenarios, demonstrating that IDSTune consistently outperforms state-of-the-art baselines in efectiveness, eficiency, and robustness, with detailed ablations and analysis of LLM-related overhead.

The remainder of this paper is organized as follows. Section 2 reviews related work on database system tuning, including MLand LLM-based approaches. Section 3 provides an overview of the IDSTune framework. Section 4 details the workload compression phase, while Section 5 presents the multi-agent tuning architecture. Section 6 reports experimental results and ablation studies, and Section 7 concludes the paper.

## 2 Background and Related Work

Database system tuning has long been recognized as a key factor in achieving high query performance. A wide range of configurable components, including knobs, indexes, and MVs, collectively determine query eficiency and resource utilization. Early approaches relied on heuristic rules and cost models embedded in the DBMS optimizer [41, 52], but they often failed to adapt to complex workloads and evolving environments. Over time, research has evolved from rule-based heuristics [16] to learning-based [20] and, more recently, LLM-enhanced tuning methods [22]. We here review representative ML- and LLM-based approaches for database tuning.

## 2.1 ML-Based Approaches

In recent years, a large body of research has applied machine learning techniques to database system tuning [7, 19, 24, 36, 47]. These methods learn the relationship between workloads and DBMS performance metrics and iteratively refine tuning decisions through feedback. Representative systems such as OtterTune [7], CDB-Tune [45], and QTune [24] apply ML and reinforcement learning (RL) to recommend knob settings. Other studies target physical design tasks such as index recommendation [19] and MV selection [43], demonstrating the efectiveness of learning-based tuning.

More recent work explores the joint optimization of multiple configuration types to capture cross-component dependencies. For example, several studies investigate knob+index co-tuning [14, 46] or MV+index co-tuning [36], modeling interactions between configuration elements. While these approaches represent an important step toward holistic tuning, they are limited to pairwise combinations and specific workloads. This motivates the need for an integrated tuning framework that can jointly consider multiple configuration spaces in a coordinated and adaptive manner.

## 2.2 LLM-Based Approaches

Large language models have demonstrated strong generalization and reasoning capabilities across a wide range of complex optimization tasks [11, 17, 22, 51]. Unlike traditional ML models that require extensive domain-specific training, LLMs can integrate contextual knowledge and infer relationships among interdependent factors [25]. These capabilities make LLMs particularly suitable for database system tuning [28], which demands understanding workload semantics, navigating large configuration spaces [49], and balancing trade-ofs among multiple objectives [13].

Motivated by these strengths, recent studies have begun applying LLMs to data management tasks. Early eforts focus on natural language interfaces, such as text-to-SQL translation [12, 26] and query rewriting [30, 31], where LLMs demonstrate strong reasoning and contextual understanding of SQL queries. Beyond query-level understanding, LLMs have also been explored for system-level tasks such as performance diagnosis [51] and index recommendation [29].

More recently, researchers have started integrating LLMs into database tuning [28]. For instance, AgentTune [27] and LLMIdx-Advis [48] leverage LLMs for knob tuning and index recommendation, respectively, while <sup>??</sup>-Tune employs an LLM to jointly recommend knobs and indexes. However, these systems rely on the most straightforward form of LLM invocation, treating the LLM as a single-call decision maker for one or two configuration types, without coordination among multiple agents. As a result, they fail to exploit the potential of LLMs for multi-component database optimization. Moreover, their inputs are static and predefined, lacking the ability to retrieve external domain knowledge from the web, which further limits adaptability and performance [27].

![](images/87d36512725c9d54d2750eaa5435691cb065249596732529034d383c9ea2f41a.jpg)  
Figure 2: Overview of the two phases of IDSTune. In Phase I (Workload Compression), the input workload is first transformed into structured features and then filtered by a Selection Agent for downstream tuning. In Phase II (Configuration Recommendation), multiple Specialist Agents (e.g., knob, index, and view specialists) independently generate candidate configurations based on the compressed workload. Their outputs are iteratively consolidated and refined by a Supervisor Agent to resolve conflicts and ensure completeness. A hybrid Safety Guardrails module further validates the final configuration before deployment.

## 3 Overview

IDSTune is an LLM-driven multi-agent collaborative framework for database configuration recommendation. As shown in Fig. 2, the framework operates in two phases: Phase I (Workload Compression) and Phase II (Configuration Recommendation). The following paragraphs summarize the key ideas of each phase, while the detailed mechanisms are described in Sections 4 and 5.

Phase I: Workload Compression. IDSTune first <sup>➊</sup> represents the input workload as a set of descriptive features capturing SQL query patterns, data distribution, and runtime statistics (Section 4.1). Since diferent agents emphasize diferent workload characteristics, IDSTune adapts feature selection accordingly. For instance, OLAP workloads prioritize features such as join complexity and aggregation depth, whereas OLTP workloads rely more on transaction throughput and contention. To prevent irrelevant information from diluting the LLM’s attention, IDSTune <sup>➋</sup> employs a Selection Agent to filter relevant features for each tuning task (Section 4.2).

Phase II: Configuration Recommendation. After workload compression, IDSTune performs integrated configuration optimization through a centralized multi-agent framework composed of Specialist Agents and a Supervisor Agent (Section 5). <sup>➌</sup> Each specialist agent focuses on a specific configuration component (e.g., knobs, indexes, or materialized views) and independently proposes candidate settings. <sup>➍</sup> Their outputs are merged into a unified tun ing report, which is then reviewed by the supervisor agent. <sup>➎</sup> The supervisor checks for potential conflicts, redundancies, and missing configurations, and requests revisions when necessary. This iterative feedback process continues until a coherent and optimized configuration report is produced. <sup>➏</sup> Before deployment, the tuning report is rigorously validated by our hybrid Safety Guardrails component. The combination of white-box rule-based constraints and black-box LLM-based verification serves as a final safeguard to filter out invalid or risky parameters. Any detected violation is immediately fed back to the agents for correction (Section 5.3). <sup>➐</sup> The final configuration is subsequently applied to the DBMS for evaluation, and the resulting performance feedback is incorporated into future iterations. Inspired by REACT [44], all agents in ID-STune are also equipped with web-search capabilities to retrieve external domain knowledge before taking actions (Section 5.4).

## 4 Workload Compression

LLM-based tuning requires a task-aware workload representation to serve as part of the input for perceiving the current tuning task [14]. Directly feeding raw SQL statements and execution traces results in long prompts that exceed token budgets and obscure critical signals. Prior tuning methods rely on workload representations to guide configuration optimization [20, 50], which can be classified into two categories: (1) encoding-based methods [50], which map workloads to high-dimensional vectors (generalizable but often training-heavy and less interpretable), and (2) informationextraction methods [14], which extract lightweight attributes such as workload type and query templates. Both approaches have limitations. Encoding-based methods may over-abstract the workload, losing essential semantic details and requiring additional model training. Information-extraction methods are overly coarse, capturing only high-level characteristics, thereby constraining the LLM’s ability to reason comprehensively about the workload.

To balance expressiveness and interpretability, IDSTune employs a feature-based workload compression scheme consisting of two stages: feature representation, which encodes workloads into structured query, data, and system features (Section 4.1); and feature selection, which filters relevant features for each agent (Section 4.2).

## 4.1 Workload Representation

Motivated by how experienced DBAs carefully analyze workloads through inspecting query patterns, examining data distributions

Conference’17, July 2017, Washington, DC, USA

![](images/b35389ee6a2d9c3768c1435677a55f53ccaa2c2a87c04719d57631f19faa0941.jpg)  
Figure 3: Three categories of features in IDSTune.

and statistics, and monitoring system status [49], IDSTune captures three complementary categories of features, as illustrated in Fig. 3:

(1) Query Features describe the characteristics of SQL statements, including statistical properties (query count, read/write ratio, average number of tables accessed) and per-query details (text, execution cost).

(2) Data Features capture schema and structural information, such as tables, columns, indexes, data volume, and other properties that influence access patterns.

(3) System Features reflect the DBMS and runtime environment, including static configurations (engine type, CPU, RAM) and dynamic metrics (CPU utilization, cache hit ratio, concurrency level) that indicate operational state.

This design combines static signals (e.g., schema and statistics) with dynamic runtime feedback (e.g., operator costs, resource utilization), providing a comprehensive, interpretable, and contextaware workload description. Unlike prior methods [14] that extract features once and rely on cost-model estimates, IDSTune maintains an evolving representation updated with real execution feedback, enabling more accurate and adaptive tuning.

As illustrated by the motivating example in Fig. 1, when tuning PostgreSQL 15 for JOB benchmark Query 33b, increasing work\_mem while a related materialized view produces no rows can degrade performance due to cardinality misestimation, which leads the optimizer to switch from index-based plans to hash joins. This exam ple highlights the importance of observing dynamic metrics, which enable IDSTune to detect such anomalies beyond static estimates.

## 4.2 Feature Selection

After representing the workload, the next step is to identify which features are most relevant for tuning. Feeding all features into the LLM is ineficient, as it produces redundant prompts, increases token usage, and raises latency. Moreover, diferent specialist agents (knob, index, view) require distinct feature subsets, making heuristic selection insuficient for generalizing across workloads and tasks.

To address this, IDSTune employs an LLM-based Selection Agent that frames feature selection as a reasoning problem. The prompt<sup>1</sup> is primarily composed of the following three components: (1) a Task Description that specifies the agent’s objective for the current tuning task, (2) Candidate Features are listed by name and semantics (rather than raw values) to control token cost, and (3) an Output Format that requests a compact JSON list of the selected features. Given this prompt, the LLM returns a minimal yet suficient subset for the downstream specialist. This design simulates the reasoning process of a DBA: before starting the tuning process, the DBA observes the current workload and database environment (the candidate features), identifies the most relevant metrics for the task (the task description), and summarizes them into a concise checklist (the output format).

## 5 Configuration Recommendation

While workload compression provides concise and task-relevant context, the next challenge lies in translating it into efective configuration decisions across multiple interdependent components. Traditional tuning methods typically rely on a single model to optimize one configuration type in isolation. However, database components such as knobs, indexes, and materialized views interact in complex and often nonlinear ways, making independent optimization insuficient. To address this challenge, IDSTune introduces a multi-agent collaborative framework that coordinates specialized agents responsible for diferent configuration dimensions under the supervision of a central controller. IDSTune further integrates real-time DBMS feedback and external knowledge retrieval to enable adaptive and eficient tuning across all components.

## 5.1 Multi-Agent Collaborative Tuning

IDSTune employs a centralized multi-agent framework composed of two types of agents: (1) Specialist Agents, each responsible for optimizing a specific configuration component (knobs, indexes, or materialized views); and (2) a Supervisor Agent, which coordinates collaboration among specialists and manages interactions with the DBMS. The overall workflow is illustrated in Fig. 4.

At the beginning of each optimization round, every specialist agent independently proposes its recommendations. For example, the View Specialist suggests candidate materialized views, the Index Specialist recommends appropriate index designs, while the Knob Specialist recommends parameter settings. These outputs are consolidated into a unified optimization report covering all configuration components. Since specialists focus only on their respective subtasks, their recommendations may overlap or conflict (e.g., creating both an index and a materialized view on the same table). The Supervisor Agent inspects the report to identify potential conflicts, redundancies, or inconsistencies and instructs the corresponding specialists to refine their proposals. This iterative coordination continues until the supervisor deems the configuration satisfactory or the revision count is exhausted<sup>2</sup>. Prior to execution, the final configuration is further validated by our hybrid safety guardrails module. The final configuration is then applied to the DBMS, feedback is collected, and the contextual information in the prompt is updated to guide the next optimization round.

In addition, all agents in IDSTune are equipped with web-search capabilities. Before generating their actions, agents can query external sources to retrieve relevant domain knowledge or implementation details, as described in Section 5.4.

This collaborative tuning framework ofers several key advan tages: (1) Improved performance. By decomposing the complex multi-component tuning task into specialized subtasks, each agent can focus on its area of expertise, leading to more efective optimiza tion; (2) Reduced cost. The modular design reduces redundant computation and promotes eficient reuse of prior knowledge; and (3) Transparency and interpretability. Users are able to transparently observe how tuning recommendations are derived, along with the underlying considerations.

![](images/a8347979fd81907f23f86e7f3be900c4be025349d1e844352428221f42f55615.jpg)  
Figure 4: IDSTune’s multi-agent collaborative tuning workflow.

## 5.2 Agent Designs

We now detail the design of the two key types of agents in IDSTune: the Specialist Agent and the Supervisor Agent, which together enable collaborative, eficient, and conflict-free database tuning.

Specialist Agents. Each specialist agent is responsible for optimizing a specific configuration component, such as knobs, indexes, or materialized views. All specialist agents share a unified prompt structure designed to ensure consistent reasoning and outputs across diferent tuning subtasks:

• Role Definition defines the agent’s identity as an experienced DBA specializing in a particular configuration domain.

• Task Description outlines the tuning objective, i.e., to recommend database configurations that improve a specific performance metric (e.g., throughput or latency). When invoked by the supervisor agent, this section may also integrate additional constraints or revision requirements provided by the supervisor.

• Workload Features provide the subset of workload and system features selected for this agent during the Workload Compression phase. The dynamic features are continuously updated through out the iterative tuning process to reflect the latest DBMS state.

• Current Configuration displays the current values of the con figuration parameters relevant to this agent’s domain.

• External Information represents auxiliary knowledge that assists the agent in making more informed tuning decisions. This information originates from two sources: (1) Web Retrieval: When the agent determines that the current context is insufi cient for accurate tuning, it queries the web to obtain additional domain knowledge. (2) Supervisor Instructions: Guidance or revision commands issued by the Supervisor Agent, which can include specific constraints or contextual hints for refinement.

• Output Format defines the structure of the LLM’s response, ensuring consistent and parsable outputs for aggregation.

Supervisor Agent. The Supervisor Agent serves as the central coordinator and quality controller of the framework. It reviews consolidated tuning reports from all specialist agents to identify conflicts or redundancies. When issues arise, it provides feedback and instructs the relevant specialists to refine recommendations. This process iterates until the configuration is deemed satisfactory.

The prompt structure of the Supervisor Agent largely mirrors that of the specialists, with two key diferences:

(1) Additional Inputs: The Supervisor Agent receives two extra components, the tuning report and the memory window. The tuning report aggregates optimization suggestions from all specialists and serves as the primary material for review, while the memory window contains historical refinement examples used as few-shot prompts to guide the supervisor’s reasoning.

(2) Output Structure: The Supervisor Agent outputs (a) an overall decision on the current tuning report (e.g., “Accept” or “Reject”), and (b) a set of revision instructions specifying which configurations require modification and how they should be refined. If the decision is Accept, the configuration is applied to the DBMS; otherwise, revision commands are issued and the corresponding specialists perform targeted adjustments.

## 5.3 Safety Guardrails

While LLMs are powerful, they are prone to hallucinations. To ensure the safety and reliability of the tuning process, IDSTune incorporates hybrid safety guardrails that combine rule-based whitebox constraints with LLM-based semantic verification.

First, the rule-based constraints layer filters out hallucinated configuration names and invalid values using constraints derived from DBMS documentation and hardware specifications. These rules are configured once per machine or DBMS with minimal manual efort. Subsequently, the LLM-based verification layer reviews the proposed configuration for logical consistency and interparameter dependencies, identifying subtle risks that pass static checks. For example, setting wal\_level to minimal while keeping max\_wal\_senders <sup>></sup> 0 may pass individual range checks but would cause a database startup failure. The LLM module detects this semantic inconsistency, whereby replication requires a higher WAL level, and rejects the configuration.

These checks are performed strictly before the configuration is applied to the database. Upon detection of an error by either layer, the specific feedback is returned to the supervisor agent to rectify the configuration. This hybrid approach ensures that only configurations that are both physically safe and semantically sound are deployed, significantly enhancing robustness.

## 5.4 Search Capability

Another key advantage of IDSTune over existing tuning frameworks lies in its integration of external knowledge retrieval. All agents can access web resources in real time to augment their reasoning with up-to-date, domain-specific information. This design follows the principles of the ReAct framework, a widely adopted retrieval-augmented reasoning paradigm in NLP [44]. Before executing an action, each agent first evaluates whether the available context is suficient for decision-making. If so, the agent proceeds normally; otherwise, it proactively performs a web query (via Google’s programmable search engine API [15]) to gather and sum marize relevant external information. The retrieved content is then incorporated into the prompt as supplementary context, enabling the LLM to generate more accurate and informed recommendations.

To provide flexibility and user control, this web-search functionality can be configured in three operational modes: Forced-On Mode: All agents must perform a web search before every execution. Forced-Of Mode: The web search function remains disabled throughout the tuning process. Auto Mode: Each agent autonomously decides whether a web search is necessary based on its contextual confidence. As demonstrated in Section 6.5.6, these modes exhibit diferent trade-ofs, with Auto Mode achieving the best overall balance between tuning quality and computational eficiency. To mitigate the additional token overhead from searchaugmented prompts, we omit numeric values from the Workload Features section and retain only concise descriptions of feature names and functionalities. Preliminary experiments show that this strategy efectively reduces token usage and inference latency without compromising tuning performance. In addition, we cache and reuse retrieved results across executions for eficiency and stability.

This search-enhanced design ofers several notable benefits: (1) Eficiency: Unlike traditional methods that pre-embed extensive auxiliary information into prompts, our agents retrieve only task relevant knowledge on demand, reducing computational and token costs. (2) Adaptability: By removing the need for manual auxiliary data management and enabling multiple operational modes, the framework adapts to diverse scenarios with minimal efort.

## 6 Experimental Evaluation

This section describes the experimental setup, evaluation methodology, and results. We compare IDSTune against state-of-the-art database tuning approaches across diverse workloads and settings. All implementations, datasets, and evaluation scripts are publicly available at: https://github.com/intlyy/IDSTune/tree/main.

## 6.1 Experimental Setup

Workloads. To evaluate the performance of IDSTune, we utilize four widely adopted public benchmarks: two OLAP benchmarks (TPC-H [39] and JOB [23]) and two OLTP benchmarks (TPC-C [38] and SYSBENCH [21]). Specifically, for OLAP, we use the TPC-H benchmark with a scale factor of 10, resulting in 14 GB of data and 22 complex queries. The JOB benchmark includes 113 complex queries on 9 GB of data. For OLTP, we utilize the TPC-C benchmark with 10 warehouses and 32 connections. Additionally, we employ the SYSBENCH benchmark with the OLTP-Read-Write workload, loading 50 tables with 1,000,000 rows each, resulting in a total dataset size of approximately 10 GB.

To assess the practical applicability of IDSTune, we include three real-world benchmarks: SDSS (16 GB), Birds (8 GB) and Redbench. SDSS (seventh Data Release of Sloan Digital Sky Survey) [6] is an OLAP dataset containing digital astronomy data, accessible via various tools including navigation and SQL search tools. Birds, on the other hand, is an OLTP benchmark gathered by the SQLShare [18] project. It contains 17 tables that primarily record physiological and ecological characteristics of various bird species. Redbench [42] is a recently proposed benchmark that generates trace-driven workloads derived from Amazon Redshift, enabling the evaluation under dynamic workload scenarios.

Hardware and Software. Unless otherwise specified, all experiments are conducted on a machine equipped with an Intel i7-7700 processor (8 cores, 3.60 GHz) and 16 GB RAM, running PostgreSQL v15.1. To support tuning indexes and query options in PostgreSQL, we install the HypoPG [2] v1.4 and a patched version of pg\_hint\_plan [3] v1.6 extensions.

Baselines. Considering that our method supports multi- configuration optimization, we design baselines that cover single-, dual-, and triple-configuration tuning methods. To the best of our knowledge, IDSTune is the first approach capable of jointly tuning views, indexes, and knobs. Therefore, the triple-configuration baseline is constructed by combining existing methods.

• AgentTune [27] (Knob Only): AgentTune is a state-of-theart knob tuning framework that achieves strong optimization performance and fast convergence across diverse scenarios. It leverages LLMs to emulate a DBA’s tuning process and uses a tree-based search strategy to eficiently explore the configuration space and identify suitable knob values.

• Dexter [1] (Index Only): Dexter is a widely used automatic indexer for Postgres, based on HypoPG [4] and PostgreSQL optimizer’s workload costs. It works by generating hypothetical indexes and leveraging the optimizer’s cost estimates to select the index set that ofers the best performance gain.

• Uniview [43] (View Only): Uniview is a unified autonomous materialized view management system that supports various popular databases and achieves superior performance in practical industry scenarios, leveraging greedy strategies or reinforcement learning (RL) for view selection and maintenance.

• <sup>??</sup>-Tune [14] (Knob and Index): <sup>??</sup>-Tune is a framework that leverages large language models for automated database knob and index tuning. It generates multiple candidate knob and index configurations through iterative prompting and selects the best-performing one after evaluation.

• Proto-X [46] (Knob and Index): Proto-X holistically tunes knob and index configuration spaces. The key idea is to capture similarities across multiple configuration spaces, encode them into a high-dimensional representation, and synthesize “protoactions” to navigate toward promising configurations.

• HMAB [36] (Index and View): HMAB jointly tunes indexes and MVs, using a hierarchical multi-armed bandit framework.

• Uniview + <sup>??</sup>-Tune (Knob, Index and View): This baseline first runs Uniview to optimize MVs, followed by <sup>??</sup>-Tune to tune knobs and indexes. This order yields better results than the reverse, as <sup>??</sup>-Tune requires multiple workload executions, and Uniview optimization improves the overall runtime eficiency.

• Proto-X + Uniview (Knob, Index and View): In this baseline, we replace <sup>??</sup>-Tune in the previous setting with Proto-X and adjust the optimization order. Due to Proto-X’s candidate mechanism, the process involves frequent EXPLAIN and HypoPG operations, and introducing materialized views can amplify latency during online tuning. This highlights that not only the optimization methods but also their order can significantly affect both tuning efectiveness and training eficiency.

• AgentTune + HMAB (Knob, Index and View): This baseline first employs AgentTune to determine the knob configuration, followed by HMAB to optimize the index and view. The rationale behind this order is that AgentTune converges quickly and provides high-quality configurations, which accelerate HMAB’s training and improve its overall efectiveness.

Tuning Settings. We allocate the same tuning time for all methods. In our approach, the LLM is configured with a temperature of 0 to eliminate the influence of randomness on the results. For <sup>??</sup>-Tune and AgentTune, the temperatures are set to 0.35 and 1, respectively, consistent with their oficial implementations, as both methods leverage stochasticity to generate multiple candidate configurations in a single round. We employ GPT-4.1 (this choice is justified in Section 6.6.3) as the underlying large language model for all LLMbased methods. For UniView, which provides both Greedy-based and RL-based implementations, we adopt the Greedy-based version because our preliminary experiments show that it achieves comparable optimization performance to the RL-based version while requiring significantly less training time. For Proto-X and HMAB, we strictly follow the configurations described in their original papers. HMAB was originally implemented on Microsoft SQL Server; in our experiments, we use its PostgreSQL-compatible version.

## 6.2 Main Results

The experimental results prove that our method outperforms existing state-of-the-art in both Performance, Eficiency and Stability. IDSTune discovers superior knob configurations. As shown in Fig. 5, IDSTune consistently finds the best configurations across all evaluated benchmarks. In the OLAP benchmark, IDSTune consistently outperforms all baseline methods. On JOB, it achieves at least a 38.3% and 34.7% reduction in latency compared to nonhybrid and hybrid baseline methods, respectively, while maintaining a clear advantage in other workloads like TPC-H and SDSS ( <sup>614.87−379.25</sup><sub>.</sub> = 38<sup>.</sup>3%, <sup>580.66−379.25</sup><sub>.</sub> = 34<sup>.</sup>7%). These gains are attributed to IDSTune’s integrated optimization strategy, which considers all configuration components jointly and thereby avoids the mutual interference that often arises when tuning them independently.

In the OLTP benchmark, this trend persists. In terms of throughput, IDSTune outperforms baselines by at least 18.8% on Birds, respectively ( <sup>34.53−29.07</sup><sub>.</sub> 29 07 = 18<sup>.</sup>8%). Similar superiority is consistently observed across TPC-C and SYSBENCH. By contrast, several triple-configuration baselines (e.g., Uniview + <sup>??</sup>-Tune and Proto-X + Uniview) fail on OLTP workloads. The primary reason lies in the inherent limitations of many existing tuning approaches, which are primarily designed and optimized for OLAP workloads. When applied to transactional scenarios, especially those involving materialized views, these methods may even degrade performance. The frequent data updates in OLTP environments can make materialized views extremely expensive to maintain, which can undermine their potential benefits. In comparison, our framework can efectively recognize the workload type through the workload representation and accordingly generate appropriate configuration recommendations. This adaptive capability enables IDSTune to maintain robust performance across diverse workload patterns.

IDSTune ofers the highest tuning eficiency. It can be observed from Fig. 5 that IDSTune converges rapidly, achieving the optimal configuration fastest across nearly all OLAP benchmarks. For instance, on the JOB benchmark, IDSTune achieves the best-found configuration within only two optimization rounds, whereas the most competitive baseline, AgentTune+HMAB, requires significantly more efort. Compared to this leading baseline, IDSTune achieves a 56.9% reduction in tuning time ( <sup>2803.31−1208.43</sup><sub>.</sub> = 56<sup>.</sup>9%). 2803 31 For transactional workloads, although the absolute tuning time of IDSTune is not particularly outstanding, its optimization eficiency, defined as the performance improvement ratio per unit time, remains superior to nearly all existing approaches.

This significant eficiency advantage can be attributed to two main factors: (1) In-framework iterative refinement. The multiagent architecture of IDSTune enables partial “in-context iteration” during the recommendation stage. Through communication among agents, candidate configurations are self-assessed and refined before execution, resulting in higher-quality recommendations. In comparison, existing approaches, whether ML-based or LLM-based, almost entirely rely on actual database executions to evaluate configuration quality, a process that is both time-consuming and costly. For OLAP workloads, the workload execution time substantially exceeds the algorithmic recommendation time. Hence, allocating a longer and more deliberate recommendation phase to achieve higher-quality configurations is justified. Further analysis is provided in Section 6.7. (2) Parallel optimization of multiple configuration components. IDSTune jointly optimizes all configuration types (knobs, indexes, and views) in parallel, whereas existing multicomponent baselines such as UniView + <sup>??</sup>-Tune, Proto-X + UniView, and AgentTune + HMAB adopt sequential optimization strategies, leading to significantly higher latency.

IDSTune generalizes well to real-world workloads. When deployed in a production environment, our method consistently delivered strong performance. Under the OLAP workload (SDSS), IDSTune successfully reduces the latency from 965.48 s (default configuration) to 465.43 s, outperforming all baselines by an average of 32.7% ( <sup>783.56−527.39</sup><sub>783.56</sub> = 32<sup>.</sup>7%). For OLTP workload (Birds), IDSTune also achieves the highest throughput, exceeding the average performance of other baselines by 1<sup>.</sup>6× times ( <sup>34.53</sup><sub>.</sub> = 1<sup>.</sup>6). These results demonstrate that IDSTune can efectively generalize to real-world tuning tasks, even in real-world production environments that LLMs have never encountered before, highlighting its strong transferability and practical utility.

IDSTune demonstrates optimal stability across multiple repeated runs. To rigorously evaluate the robustness and reproducibility of all tuning algorithms, we conduct five independent tuning sessions per method and report the median along with the interquartile range (Q1–Q3) of the best observed performances. The shaded regions in Figure 5 illustrate the performance variability of each method over the tuning process.

Across all benchmarks, IDSTune exhibits the narrowest interquar tile ranges, indicating minimal performance fluctuation and strong robustness compared to baselines. This stability can be attributed to two key design choices. <sup>➊</sup> The integrated LLM is configured with a temperature of 0, efectively eliminating stochasticity during the configuration generation process. <sup>➋</sup> Our search framework employs a history-aware caching mechanism that records previously evaluated configurations and trajectories, thereby avoiding redundant exploration and ensuring deterministic behavior.

![](images/daebe45d9227db02e6f51ec62147e29179884e7f174c52a311498328964120bf.jpg)

Figure 5: Performance comparison of best-found configurations throughout the tuning process across six diferent benchmarks. Note that at the beginning of each curve, all methods exhibit the same performance as the default configuration, since the system needs to complete one full benchmark run to obtain valid performance feedback. The duration before the first performance point thus corresponds to the time of configuration recommendation, application, and workload execution.  
![](images/936ff5a90cf7bf79a0758c7eb2c919cff7abe5800c91789736282507c45c2539.jpg)  
(a) PostgreSQL + enhanced machine (b) Microsoft SQL Server  
Figure 6: Experiments on diferent: (a) hardware, and (b) database engine.

## 6.3 Scalability Study

6.3.1 Database Scaling. We now evaluate the scalability of ID-STune by examining its performance across diferent database scales. Specifically, we conduct experiments on the TPC-H benchmark with four data sizes: 1 GB, 5 GB, 10 GB, and 20 GB. The results are summarized in Table 1.

As database scale increases, absolute performance degrades for both default and optimized configurations, as expected due to higher data volume and execution complexity. Yet, IDSTune consistently delivers substantial improvements of 7 − 9× over the default config uration across all scales, demonstrating robust performance under scaling (( <sup>78.19</sup><sub>.</sub> = 7<sup>, 6013.04</sup><sub>.</sub> = 9)).

Importantly, the overhead of IDSTune, in terms of both token consumption and runtime, remains largely constant and does not grow with the database size. This is because our workload compression mechanism is based on feature extraction rather than directly encoding raw workloads. Consequently, for larger and more complex workloads with long execution times (e.g., hours per run), the additional tuning overhead introduced by IDSTune becomes negligible and is well justified by the resulting performance gains.

6.3.2 Hardware Scaling. As detailed in Section 6.1, our primary evaluations are conducted on a server with an 8-core CPU and 16 GB of RAM. To investigate the impact of hardware on tuning performance, we deploy the database on a machine equipped with 40 cores (Intel Xeon Gold 5118 @ 2.30GHz) and 256 GB of RAM. The experimental outcomes are presented in Figure 6 (a).

We observe that the relative efectiveness of diferent methods becomes less pronounced at larger scales. Approaches that optimize knobs achieve significant performance gains, primarily because, under abundant resources such as memory, suboptimal configurations become the performance bottleneck compared to physical structures like indexes. Meanwhile, IDSTune consistently outperforms all baselines and achieves the lowest final latency, demonstrating its superior ability to adapt to diverse hardware environments.

6.3.3 Database Engine Generalization. To evaluate cross-engine generalization, we replace PostgreSQL with Microsoft SQL Server [32] while keeping all other experimental settings unchanged. Due to limited support of some baselines on SQL Server, we additionally include Database Tuning Advisor (DTA) [33], a competitive physical design tuning approach specifically designed for this database engine, as a strong baseline.

As shown in Figure 6 (b), IDSTune consistently maintains superior performance on SQL Server, outperforming all applicable baselines. While some methods sufer from degraded efectiveness due to their reliance on database-specific features, IDSTune remains robust by leveraging its search capability to retrieve relevant knowledge and its LLM-driven coordination across tuning actions. Compared to DTA, which focuses solely on physical design optimization, IDSTune delivers better overall performance by jointly optimizing multiple configuration dimensions. Furthermore, IDSTune is easy to deploy in practice, as it adopts a training-free design that avoids additional preparation overhead. These results highlight the strong cross-engine generalization ability of IDSTune.

![](images/59b167871036b595cbdf7dd5798261830b0682daeb0ee714b1b49763a6d7784f.jpg)

Table 1: Scalability experiment.  
![](images/a8c53bdec07fef5f15bb68531f1cb07d823ceef9bd197700593f28ca3c2e9e31.jpg)

Table 2: Ablation study on the workload compression.  
![](images/42f951b5703bbf3205d42943ffbd46770e48680ed17f80b8b7a17b0c33f8b61f.jpg)  
Figure 7: Robustness analysis under progressive data drift.

## 6.4 Robustness Against Drift

In real-world deployments, the DBMS environment under tuning may vary due to data drift, query drift, or workload changes. Given this, we now analyze whether IDSTune can still efectively guide the database toward promising configurations when its memory becomes outdated. We first examine data and query drift, followed by a real-world evolving workload trace.

For combined baselines, components are executed sequentially under static workloads. However, handling drift requires re-activating previously completed processes, which most methods do not support. Therefore, they are not considered in this section.

6.4.1 Data Drift. We construct a progressive data drift scenario based on the JOB benchmark. Specifically, we partition the dataset using the production\_year attribute. The initial state contains only historical data (years < 2005). We then introduced new data in 20% increments (Stages 20% to 100%), creating five distinct drift events. Each stage was allocated the same tuning budget of time. We utilized the original queries from the JOB benchmark.

Figure 7 reports the performance trajectory across the six stages. We observe that IDSTune outperforms baselines in two key aspects. First, it exhibits minimal performance degradation at the onset of data drift. Unlike methods that rely solely on fragile physical design structures (indexes and materialized views) which are prone to invalidation during distribution shifts, IDSTune incorporates knob tuning as a stabilizing factor. Knobs generally retain their eficacy even when data distribution changes, providing a performance bufer. Second, IDSTune demonstrates rapid recovery following drift events. This is attributed to our adaptive feature extraction mechanism. By refreshing the features prior to each optimization round, IDSTune timely detects the underlying distribution shifts, enabling the agent to adjust its search strategy immediately.

![](images/c2b20bfd12f06c5cf65e5675cb657fb944a624fb0f19c50f7baa0035eb73e9f1.jpg)

![](images/4b821f198e6cb7f0795071231f516a1f3da76fd6b39167641c7c7aacbf540060.jpg)  
(a) Query drift  
(b) Real-world trace  
Figure 8: Experiments on: (a) query drift, and (b) real-world trace.

6.4.2 Query Drift. To evaluate IDSTune’s resilience to schemalevel query drift, we divide the JOB workload into two disjoint sets. Specifically, based on the 33 query templates in JOB, we randomly split the templates and their derived queries into two subsets, resulting in JOB\_A (16 templates, 48 queries) and JOB\_B (15 templates, 65 queries). This partition ensures minimal overlap between the two subsets, thereby reducing the extent to which methods can benefit from previously observed query patterns.

Figure 8 (a) presents the results. We observe that methods incorporating knob tuning are generally less afected by query drift and recover faster than those focusing solely on physical design optimization. This is mainly because knob configurations capture system-level performance characteristics that are less tightly coupled with specific query patterns. On top of this, IDSTune further outperforms all baselines. Its stronger resilience to drift comes from its richer feature representation, which incorporates not only query features but also data features that remain stable under query drift. Moreover, IDSTune adapts more quickly because its features are dynamically updated after each execution, allowing it to respond promptly to newly arrived queries.

6.4.3 Real Workload Trace. Compared with classical benchmarks such as TPC-H and JOB, real-world production workloads are typically more write-intensive and evolve over time, exhibiting both data and query drift [40]. To evaluate the efectiveness of tuning methods under such realistic conditions, we use Redbench [42] to emulate real-world workload trace. Specifically, we construct a oneweek workload trace based on JOB templates, consisting of SELECT and diverse DML operations. The tuning methods are required to optimize the database at the end of each day. This setup implies that the workload of the next day is never observed during tuning, posing a continuous adaptation challenge.

The results are shown in Figure 8 (b), where the black curve represents the performance under the default configuration. IDSTune achieves an average improvement of approximately 29.9% over the default configuration ( <sup>144.93−101.54</sup><sub>.</sub> = 29<sup>.</sup>9). Importantly, in more complex real-world scenarios, the performance gains become more pronounced, while the associated optimization cost remains nearly unchanged. We also observe that, under such continuously evolving workloads, existing methods are prone to negative optimization, especially those relying heavily on historical data. In contrast, LLMbased methods, such as LambdaTune and AgentTune, exhibit more stable performance. IDSTune further distinguishes itself as the only method that consistently achieves positive improvements through out the entire trace, which is particularly critical for real-world scenarios where performance regressions are unacceptable. This advantage stems from its rich feature representation and multiagent coordination mechanism, which enable robust adaptation under dynamic workload conditions.

## 6.5 Ablation Studies

To further evaluate the efectiveness of each component in our framework, we conduct comprehensive ablation studies throughout the entire tuning process. In addition, we examine the impact of diferent LLMs on tuning performance. Unless otherwise specified, all ablation experiments are conducted on JOB benchmark.

6.5.1 Ablation Study on the Workload Compression. First, we conduct ablation studies to evaluate the efectiveness of our workload compression module. Specifically, we compare three diferent work load representation strategies: (1) Workload representation + selection, i.e., the method used in IDSTune; (2) Workload representation only, where the workload is embedded without feature selection; (3) No workload, where the workload compression module is removed, and only the most basic hardware and database information can be accessed.

The results are shown in Table 2. Our workload compression approach achieves the best overall performance, as IDSTune provides a comprehensive and fine-grained workload representation that allows the LLM to more efectively perceive and reason about query patterns. However, this does not imply that simply increasing the amount of information always improves results. As demonstrated by the "Representation Only" variant, providing the full unfiltered feature set can actually degrade performance, since not all information is useful. Even when the workload compression module is completely removed, our method still achieves a noticeable performance improvement over the default configuration, demonstrating that IDSTune remains efective even under extreme conditions.

6.5.2 Efectiveness of Multi-Agent Collaborative Tuning Framework. To validate the efectiveness of our collaborative multi-agent architecture, we compare IDSTune with two simplified designs: (1) Multi-agent non-collaborative, where the supervisor is removed and each specialist agent (knob, index, view) operates independently without inter-agent communication; and (2) Single-Agent, which merges all agents into a single LLM call that recommends all configuration types at once.

Table 3: Efectiveness of Multi-Agent Collaborative Tuning.  
![](images/94eb5ebc6684c1a0a3977ec2eb5d721beb8e484d0ce42f1e55b8a39d8dacc80c.jpg)

![](images/d703f58b9deb39889b9beeb6dca511c7c24e6d2f894c06fde406c2f9431c38c0.jpg)

![](images/8ca0dc42ab1f5b6f5063928067cd0dcef176184e0119db5de674a3143df684e2.jpg)  
(a) Agent Composition  
(b) Revision Count  
Figure 9: Ablation studies on: (a) agent composition, and (b) revision count.

The results are reported in Table 3. We make three key observations. (1) Both the multi-agent non-collaborative variant and the single-agent baseline consistently underperform IDSTune across all workloads. This performance gap highlights the importance of explicit collaboration among specialized agents, especially in complex tuning scenarios where diferent configuration types interact and jointly afect system performance. By enabling structured communication and iterative coordination, IDSTune avoids suboptimal decisions that arise when configuration dimensions are optimized in isolation or entangled within a single monolithic reasoning process. (2) IDSTune incurs higher token consumption and tuning runtime than the simplified baselines. This overhead mainly stems from maintaining multiple specialized agents and enabling inter-agent communication and iterative coordination. Importantly, such overhead is largely fixed and does not scale with workload size or execution complexity, as discussed in Section 6.3. This ensures that, for complex workloads with long execution times (e.g., hours per run), the additional tuning cost remains negligible relative to the performance gains.

6.5.3 Ablation study on Agent Composition. To understand how diferent types of tuning agents complement each other and contribute to overall tuning efectiveness, we compare the following variants: (1) IDSTune-Index/View/Knob Only, where only one type of agent is retained; (2) IDSTune-Knob & Index, keeping only knob and index agents; (3) IDSTune-Knob & View, keeping knob and materialized view agents; (4) IDSTune-View & Index, keeping materialized view and index agents.

Fig. 9(a) presents the results of the ablation study. We observe that applying individual components in isolation or combining them in pairs can still lead to noticeable performance improvements over the default configuration, indicating that each specialized agent contributes meaningful optimization capability. This also demon strates the flexibility of IDSTune, as the framework can be adapted to diferent practical requirements by selectively enabling specific agents. However, no single agent or agent pair can consistently match the performance of the full collaborative framework, high lighting the complementary nature of diferent tuning dimensions and the importance of holistic coordination among agents.

Table 4: Ablation study on safety guardrails.  
![](images/fce1d31f7cf0c8ef3c1fd8cc2dda2231547fe64048f352fa5bdfc9a1bbbd1aab.jpg)

6.5.4 Ablation Study on Revision Count. We now study the impact of the revision count, which controls the maximum number of iterative refinements allowed when agents fail to reach consensus during collaborative tuning. Intuitively, a larger revision count enables more thorough coordination among agents, but also incurs higher LLM inference costs. This experiment aims to quantify this trade-of and identify a practical setting.

We vary the revision count from 0 to 6, keeping all other configurations unchanged. Fig. 9(b) reports tuning latency and token consumption under diferent revision counts. Increasing the revision count initially improves latency, as additional iterations allow agents to refine decisions and resolve inconsistencies. However, gains diminish after five revisions, indicating convergence. In contrast, token consumption grows steadily with the revision count due to extra LLM calls. Consequently, increasing revisions beyond five yields marginal performance improvements at a higher cost. Based on this, we set the revision count to five, achieving a balance between tuning efectiveness and LLM overhead.

6.5.5 Ablation study on safety guardrails. Our safety guardrails integrate rule-based constraints and LLM-based verification to synergistically guarantee tuning reliability and prevent invalid configu rations. To evaluate the specific contribution of each component, we conducted an ablation study comparing the following four variants: (1) IDSTune: The complete framework with full safety mechanisms; (2) w/o rule-based constraints: The variant with the static constraints removed; (3) w/o LLM-based verification: The variant with the semantic verification disabled; (4) w/o safety guardrails: The variant where the entire safety mechanism is excluded.

The results are summarized in Table 4. False Negative indicates a failure to intercept, resulting in unsafe configurations being applied, whereas False Positive refers to incorrectly flagging a valid configuration as unsafe. As observed, the complete IDSTune system maintained a zero invalid configuration rate throughout the process, demonstrating the robustness and reliability of our approach. In contrast, all variants lacking specific safety components generated unsafe configurations. Consequently, without guardrails to intercept these unreasonable configurations, the optimization process is disrupted, negatively impacting the final performance. Another noteworthy observation is regarding token consumption. Although the LLM-based verification module introduces additional

Table 5: Ablation study on the search mechanism.  
![](images/2eed34ed3f8977329391893b7c11eb3b9b400cd200ebebf9d3645166f9567c31.jpg)

![](images/89f62afc12a99a276ca8b5090c2f14b4506aebb50510fbcda9ad1cf9ae4c88a6.jpg)

![](images/eadd3825dcbe1bde09cd9b0b9045bd844227154e59efe8c9851f29ef5ecabda0.jpg)  
(a) Best Found Performance  
(b) Creation Time  
Figure 10: Impact of memory budget on: a) performance and b) creation time.

LLM calls and the risk of false positives, removing it surprisingly resulted in increased total token usage. This is primarily because the prompts used for verification are concise and executed only prior to deployment, incurring minimal overhead. Conversely, the absence of verification leads to wasted iterations on invalid configurations. The cost of these failed trials—which require re-generating contexts and restarting the dialogue—significantly outweighs the marginal token cost of the verification prompts.

6.5.6 Ablation Study on the Search Mechanism. Our framework allows agents to retrieve external knowledge from the Web and provides three operational modes: (1) Forced-On, where all agents perform a web search before every execution; (2) Auto, where each agent decides autonomously whether a web search is needed based on contextual confidence; and (3) Forced-Of, where web search is disabled throughout the tuning process.

Table 5 presents the performance, time cost, and token consumption under diferent modes. We can observe that agents generally benefit from search, as it allows them to acquire up-to-date or domain-specific knowledge during tuning. However, this improvement comes at a cost, i.e., longer execution time or higher token usage. Therefore, for users who prioritize optimization performance, the Forced-On mode is preferable, whereas the Forced-Of mode is more suitable for time- or token-sensitive scenarios. Overall, the Auto Mode achieves the best trade-of between performance and eficiency, and thus serves as the default setting in IDSTune.

## 6.6 Sensitivity Experiments

To better understand the sensitivity of IDSTune to key factors, We next analyze its behavior under diferent settings. We begin with an ablation study on memory budget in Section 6.6.1, followed by analyses of the efects of tuning time and LLMs in Section 6.6.2 and Section 6.6.3, respectively.

6.6.1 IDSTune’s Performance under Diferent Memory Budgets. This section presents experiments across four diferent memory budgets, 0.1X, 0.5X, 1X (approximately equal to the data size), and 2X, under TPC-H benchmark, to understand the memory budget’s impact on solution fitness. Among all baselines, only our method and HMAB can actively control the memory budget. As shown in Figure 11(a), both IDSTune and HMAB perform poorly under low memory budgets. As the allocated memory increases, IDSTune steadily improves and eventually converges, whereas HMAB exhibits slight performance degradation after convergence. This behavior is mainly attributed to HMAB’s search mechanism, which tends to aggressively explore a large number of physical design candidates. When the search space becomes excessively large, such exploration incurs substantial overhead and can even hinder performance. In con trast, IDSTune’s LLM-based multi-agent framework enables more disciplined utilization of the allocated memory, leading to more stable performance. This is further validated in Figure 11(b), where IDSTune’s physical design creation time does not continuously increase with the memory budget.

![](images/75a61bcfda5c9b03c0bb2b7abda36e1342af14e9d2761dfbea9b61188d0acd35.jpg)

![](images/50850c1c5608ca3e56f6f00b454ae2b98e5bb7b152ea91a263cf7017c02eb3c5.jpg)  
Figure 11: Impact of time budget on performance.

6.6.2 Efect of Tuning Time. As discussed in Section 6.1, we allocate the same tuning time for all methods (3600s for OLAP workloads and 1200s for OLTP workloads). To examine the impact of the time budget, we evaluate each method under 0.5× and 10× the original setting on TPC-H (OLAP) and TPC-C (OLTP). As shown in Figure 11, the bar chart reports the time required for each method to reach its best-found configuration under the extended budget, while the markers illustrate the best performance achieved under diferent time budgets. To account for inherent performance variability in database systems, we adopt a 5% improvement threshold when determining whether a new configuration is better. We observe that our method consistently achieves the best performance across all time budgets. Moreover, for most methods, the original time budget is suficient to reach near-optimal performance. The only exception is ProtoX, which appears to benefit from longer tuning time, likely due to its reinforcement learning nature requiring more training iterations. In contrast, for LLM-based methods such as LambdaTune, excessively long tuning durations may incur additional computational cost without proportional performance gains. Thus, from a holistic perspective that considers both efectiveness and eficiency, the current time settings strike a reasonable balance.

6.6.3 Efect of Diferent LLMs. We analyze the efect of LLMs on tuning performance. Specifically, IDSTune is tested with GPT-5 [4], GPT-4.1 [35], GPT-4o [34], Claude-3 [8] and Claude-4.7 [5] on JOB benchmark. As shown in Fig. 12, all variants achieve consistent and strong performance, indicating that the efectiveness does not rely on any specific LLM. We observe that more powerful models, such as the recently released Claude-4.7, can further improve performance. While it achieves a 19.2% improvement over our primary model, it is around 4× more expensive and has a longer runtime. Nevertheless, we expect that such models will become more costeficient and faster over time. This trend suggests that our approach can naturally benefit from future advances in LLMs.

![](images/96bbfbb6929161405db6bc5de2ea47058f8876b3cc6fc813dc174090703acb6b.jpg)  
Figure 12: Diferent LLMs.

![](images/23bf30476332598201c85adf5ab016eb0599229d700514510d5b4eb8dc981f50.jpg)  
Figure 13: Time breakdown.

## 6.7 Cost Analysis

There are two main types of overhead in DBMS knob tuning: (1) initial profiling overhead and (2) runtime overhead. Initial profiling overhead refers to the time required to collect training data or pre-train models before tuning begins (e.g., RL model in Uniview requires tens of hours of training for cold start; AgentTune needs to prepare and process relevant information in advance before tuning [26]). Runtime overhead is the time the tuner takes to recommend a new configuration for evaluation.

IDSTune ofers out-of-the-box flexibility with minimal initial profiling overhead compared to previous methods. We evaluate the runtime overhead by presenting the number of tokens consumed, monetary costs, and time required using GPT-4.1. In the main experiments (Section 6.2), IDSTune incurs 2977.46 K tokens, with a total cost of 13.82 USD. Furthermore, we compare the time consumption of diferent methods in a single tuning process, which can be divided into three stages: algorithm recommendation time, index/view creation time, and workload execution time, as shown in Fig. 13. We observe that the configuration recommendation time is generally negligible compared with the workload replay time and the physical design creation time. Compared with other methods, IDSTune incurs a relatively longer algorithm recommendation time, mainly due to the iterative communication among multiple agents and the refinement of the tuning report. However, this additional cost leads to the shortest workload execution time (i.e., the best achieved database performance) and thus the shortest overall tuning time. In summary, IDSTune’s LLM-related costs are feasible and practical, making it suitable for real-world large-scale deployment.

## 7 Conclusion

This paper presents IDSTune, an LLM-driven multi-agent collaborative framework for integrated database system tuning, representing the first solution to jointly optimize knobs, indexes, and MVs in a unified framework. In contrast to traditional methods that tune these components in isolation, IDSTune provides a more adaptable solution for heterogeneous database systems, exhibits stronger tolerance to data and workload drift, and better supports both OLAP and OLTP settings. Evaluated against other state-of-the-art baselines under diverse scenarios, IDSTune discovers configurations that improve performance by up to 38% over the next best approach.

## Acknowledgments

The authors used ChatGPT to assist with English editing and code development. No experimental results or original contributions were generated solely by AI tools.

## References

[1] 2017. Introducing Dexter, the Automatic Indexer for Postgres — ankane. https://medium.com/@ankane/introducing-dexter-the-automatic-indexer-forpostgres-5f8fa8b28f27. Accessed: 2025-10-27.

[2] 2023. HypoPG. https://hypopg.readthedocs.io/. Accessed: 2025-10-27.

[3] 2023. pg\_hint\_plan. https://github.com/17zhangw/pg\_hint\_plan/tree/parallel\_ patch. Accessed: 2025-10-27.

[4] 2025. Introducing GPT-5. https://openai.com/index/introducing-gpt-5/. Accessed: 2025-10-27.

[5] 2026. Introducing Claude Opus 4.7. https://www.anthropic.com/news/claude opus-4-7. Accessed: 2026-4-18.

[6] Kevork Abazajian, Jennifer Adelman-McCarthy, Marcel Agüeros, Sahar Allam, Carlos Prieto, Deokkeun An, Kurt Anderson, Scott Anderson, James Annis, N. Bahcall, C. Bailer-Jones, John Barentine, Bruce Bassett, Andrew Becker, Timothy Beers, Eric Bell, Vasily Belokurov, Andreas Berlind, Eileen Berman, and Daniel Zucker. 2009. The Seventh Data Release of the Sloan Digital Sky Survey. The Astrophysical Journal Supplement Series 182 (05 2009), 543. doi:10.1088/0067- 0049/182/2/543

[7] Dana Van Aken, Andrew Pavlo, Geofrey J. Gordon, and Bohan Zhang. 2017. Auto matic Database Management System Tuning Through Large-scale Machine Learn ing. In Proceedings of the 2017 ACM International Conference on Management of Data, SIGMOD Conference 2017, Chicago, IL, USA, May 14-19, 2017, Semih Salihoglu, Wenchao Zhou, Rada Chirkova, Jun Yang, and Dan Suciu (Eds.). ACM, 1009–1024. doi:10.1145/3035918.306402

[8] Anthropic. 2024. Introducing the next generation of Claude. (2024). Available at: https://www.anthropic.com/news/claude-3-family.

[9] Elena Baralis, Stefano Paraboschi, and Ernest Teniente. 1997. Materialized Views Selection in a Multidimensional Database. In VLDB’97, Proceedings of 23rd International Conference on Very Large Data Bases, August 25-29, 1997, Athens, Greece, Matthias Jarke, Michael J. Carey, Klaus R. Dittrich, Frederick H. Lochovsky, Pericles Loucopoulos, and Manfred A. Jeusfeld (Eds.). Morgan Kauf mann, 156–165. http://www.vldb.org/conf/1997/P156.PDF

[10] Surajit Chaudhuri and Vivek R. Narasayya. 2007. Self-Tuning Database Systems: A Decade of Progress. In Proceedings of the 33rd International Conference on Very Large Data Bases, University of Vienna, Austria, September 23-27, 2007, Christoph Koch, Johannes Gehrke, Minos N. Garofalakis, Divesh Srivastava, Karl Aberer, Anand Deshpande, Daniela Florescu, Chee Yong Chan, Venkatesh Ganti, Carl-Christian Kanne, Wolfgang Klas, and Erich J. Neuhold (Eds.). ACM, 3–14. http://www.vldb.org/conf/2007/papers/special/p3-chaudhuri.pdf

[11] Jacob Devlin, Ming-Wei Chang, Kenton Lee, and Kristina Toutanova. 2019. BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. arXiv:1810.04805 [cs.CL] https://arxiv.org/abs/1810.04805

[12] Ju Fan, Zihui Gu, Songyue Zhang, Yuxin Zhang, Zui Chen, Lei Cao, Guoliang Li, Samuel Madden, Xiaoyong Du, and Nan Tang. 2024. Combining Small Language Models and Large Language Models for Zero-Shot NL2SQL. Proc. VLDB Endow. 17, 11 (2024), 2750–2763. https://www.vldb.org/pvldb/vol17/p2750-fan.pdf

[13] Michail Georgoulakis Misegiannis, Vasiliki (Verena) Kantere, and Laurent d’Orazio. 2022. Multi-objective query optimization in Spark SQL. In Proceedings of the 26th International Database Engineered Applications Symposium (Budapest, Hungary) (IDEAS ’22). Association for Computing Machinery, New York, NY, USA, 70–74. doi:10.1145/3548785.3548800

[14] Victor Giannakouris and Immanuel Trummer. 2025. <sup>??</sup>-Tune: Harnessing Large Language Models for Automated Database System Tuning. Proc. ACM Manag. Data 3, 1, Article 2 (Feb. 2025), 26 pages. doi:10.1145/3709652

[15] Google. 2025. Programmable Search Engine: Build and manage a search engine for your site. https://developers.google.com/custom-search. Accessed: 2025-10-27.

[16] Major Hayden. 2024. MySQLTuner — A script to review and tune your MySQL installation. https://github.com/major/MySQLTuner-perl. Accessed: 2025-07-22.

[17] Xinmei Huang, Haoyang Li, Jing Zhang, Xinxin Zhao, Zhiming Yao, Yiyan Li, Tieying Zhang, Jianjun Chen, Hong Chen, and Cuiping Li. 2025. E2ETune: End-to-End Knob Tuning via Fine-tuned Generative Language Model. arXiv:2404.11581 [cs.AI] https://arxiv.org/abs/2404.11581

[18] Shrainik Jain, Dominik Moritz, Daniel Halperin, Bill Howe, and Ed Lazowska. 2016. SQLShare: Results from a Multi-Year SQL-as-a-Service Experiment. In Proceedings of the 2016 International Conference on Management of Data (San Francisco, California, USA) (SIGMOD ’16). Association for Computing Machinery, New York, NY, USA, 281–293. doi:10.1145/2882903.2882957

[19] Tao Ji, Kai Zhong, Luming Sun, Yiyan Li, Cuiping Li, and Hong Chen. 2025. LIOF: Make the Learned Index Learn Faster With Higher Accuracy. IEEE Transactions on Knowledge and Data Engineering 37, 6 (2025), 3499–3513. doi:10.1109/TKDE. 2025.3548298

[20] Konstantinos Kanellis, Cong Ding, Brian Kroth, Andreas Müller, Carlo Curino, and Shivaram Venkataraman. 2022. LlamaTune: Sample-Eficient DBMS Configuration Tuning. Proc. VLDB Endow. 15, 11 (2022), 2953–2965. doi:10.14778/ 3551793.3551844

[21] Alexey Kopytov. 2024. Scriptable database and system performance benchmark. (2024). Available at: https://github.com/akopytov/sysbench/.

[22] Jiale Lao, Yibo Wang, Yufei Li, Jianping Wang, Yunjia Zhang, Zhiyuan Cheng, Wanghu Chen, Mingjie Tang, and Jianguo Wang. 2024. GPTuner: A Manual-Reading Database Tuning System via GPT-Guided Bayesian Optimization. Proc. VLDB Endow. 17, 8 (2024), 1939–1952. https://www.vldb.org/pvldb/vol17/p1939- tang.pdf

[23] Viktor Leis, Andrey Gubichev, Atanas Mirchev, Peter A. Boncz, Alfons Kemper, and Thomas Neumann. 2015. How Good Are Query Optimizers, Really? Proc. VLDB Endow. 9, 3 (2015), 204–215. doi:10.14778/2850583.2850594

[24] Guoliang Li, Xuanhe Zhou, Shifu Li, and Bo Gao. 2019. QTune: A Query-Aware Database Tuning System with Deep Reinforcement Learning. Proc. VLDB Endow. 12, 12 (2019), 2118–2130. doi:10.14778/3352063.3352129

[25] Guoliang Li, Xuanhe Zhou, and Xinyang Zhao. 2024. LLM for Data Management. Proc. VLDB Endow. 17, 12 (Aug. 2024), 4213–4216. doi:10.14778/3685800.3685838

[26] Haoyang Li, Jing Zhang, Hanbing Liu, Ju Fan, Xiaokang Zhang, Jun Zhu, Renjie Wei, Hongyan Pan, Cuiping Li, and Hong Chen. 2024. CodeS: Towards Building Open-source Language Models for Text-to-SQL. Proc. ACM Manag. Data 2, 3 (2024), 127.

[27] Yiyan Li. 2025. AgentTune: A Multi-Agent Collaborative Framework for Database Knob Tuning. https://github.com/intlyy/AgentTune/. Accessed: 2025-10-27.

[28] Yiyan Li, Haoyang Li, Zhao Pu, Jing Zhang, Xinyi Zhang, Tao Ji, Luming Sun, Cuiping Li, and Hong Chen. 2024. Is Large Language Model Good at Database Knob Tuning? A Comprehensive Experimental Evaluation. arXiv:2408.02213 [cs.DB] https://arxiv.org/abs/2408.02213

[29] Zhaodonghui Li, Haitao Yuan, Jiachen Shi, Hao Zhang, Yu Rong, and Gao Cong. 2025. AMAZe: A Multi-Agent Zero-shot Index Advisor for Relational Databases. arXiv:2508.16044 [cs.DB] https://arxiv.org/abs/2508.16044

[30] Zhaodonghui Li, Haitao Yuan, Huiming Wang, Gao Cong, and Lidong Bing. 2024. LLM-R2: A Large Language Model Enhanced Rule-based Rewrite System for Boosting Query Eficiency. CoRR abs/2404.12872 (2024). arXiv:2404.12872 doi:10.48550/ARXIV.2404.12872

[31] Jie Liu and Barzan Mozafari. 2024. Query Rewriting via Large Language Models. CoRR abs/2403.09060 (2024). arXiv:2403.09060 doi:10.48550/ARXIV.2403.09060

[32] Microsoft Corporation. 2016. Microsoft SQL Server. https://www.microsoft. com/en-au/sql-server/sql-server-2016

[33] Microsoft Corporation. 2024. Database Engine Tuning Advisorr. https: //learn.microsoft.com/en-us/sql/relational-databases/performance/databaseengine-tuning-advisor?view=sql-server-ver17

[34] OpenAI. 2024. Hello gpt-4o. (2024). Available at: https://openai.com/index/hellogpt-4o/.

[35] OpenAI. 2025. Introducing GPT-4.1 in the API. (2025). Available at: https: //openai.com/index/gpt-4-1/.

[36] R. Malinga Perera, Bastian Oetomo, Benjamin I. P. Rubinstein, and Renata Borovica-Gajic. 2022. HMAB: self-driving hierarchy of bandits for integrated physical database design tuning. Proc. VLDB Endow. 16, 2 (Oct. 2022), 216–229. doi:10.14778/3565816.3565824

[37] Tarique Siddiqui and Wentao Wu. 2023. ML-Powered Index Tuning: An Overview of Recent Progress and Open Challenges. arXiv:2308.13641 [cs.DB] https://arxiv. org/abs/2308.13641

[38] Transaction Processing Performance Council (TPC). 2010. TPC Benchmark C Standard Specification. http://www.tpc.org/tpcc/ Version 5.11.0.

[39] Transaction Processing Performance Council (TPC). 2023. TPC Benchmark H Standard Specification. https://www.tpc.org/tpch/ Version 3.2.0.

[40] Alexander van Renen, Dominik Horn, Pascal Pfeil, Kapil Vaidya, Wenjian Dong, Murali Narayanaswamy, Zhengchun Liu, Gaurav Saxena, Andreas Kipf, and Tim Kraska. 2024. Why TPC Is Not Enough: An Analysis of the Amazon Redshift Fleet. Proc. VLDB Endow. 17, 11 (2024), 3694–3706. doi:10.14778/3681954.3682031

[41] Oleksii Vasyliev. 2024. Pgtune - tuning PostgreSQL config by your hardware. https://github.com/le0pard/pgtune. Accessed: 2025-07-22.

[42] Johannes Wehrstein, Roman Heinrich, Mihail Stoian, Skander Krid, Martin Stemmer, Andreas Kipf, Carsten Binnig, and Muhammad El-Hindi. 2025. Redbench: Workload Synthesis From Cloud Traces. arXiv:2511.13059 [cs.DB] https://arxiv.org/abs/2511.13059

[43] Zhenrong Xu, Pengfei Wang, Guoze Xue, Qitong Yan, Shenghao Gong, Yelan Jiang, Yuren Mao, Yunjun Gao, Shu Shen, Wei Zhang, Dan Luo, and Lu Chen. 2024. UniView: A Unified Autonomous Materialized View Management System for Various Databases. Proc. VLDB Endow. 17, 12 (Aug. 2024), 4353–4356. doi:10. 14778/3685800.3685873

[44] Shunyu Yao, Jefrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik R. Narasimhan, and Yuan Cao. 2023. ReAct: Synergizing Reasoning and Acting in Language Models. In The Eleventh International Conference on Learning Representations, ICLR 2023, Kigali, Rwanda, May 1-5, 2023. OpenReview.net. https://openreview. net/forum?id=WE\_vluYUL-X

[45] Ji Zhang, Ke Zhou, Guoliang Li, Yu Liu, Ming Xie, Bin Cheng, and Jiashu Xing. 2021. CDBTune: An eficient deep reinforcement learning-based automatic cloud database tuning system. VLDB J. 30, 6 (2021), 959–987. doi:10.1007/S00778-021- 00670-9

[46] William Zhang, Wan Shen Lim, Matthew Butrovich, and Andrew Pavlo. 2024. The Holon Approach for Simultaneously Tuning Multiple Components in a Self-Driving Database Management System with Machine Learning via Synthesized Proto-Actions. Proc. VLDB Endow. 17, 11 (July 2024), 3373–3387. doi:10.14778/ 3681954.3682007

[47] Xinyi Zhang, Hong Wu, Yang Li, Jian Tan, Feifei Li, and Bin Cui. 2022. Towards Dynamic and Safe Configuration Tuning for Cloud Databases. In SIGMOD ’22: International Conference on Management of Data, Philadelphia, PA, USA, June

12 - 17, 2022, Zachary G. Ives, Angela Bonifati, and Amr El Abbadi (Eds.). ACM, 631–645. doi:10.1145/3514221.3526176

[48] Xinxin Zhao, Haoyang Li, Jing Zhang, Xinmei Huang, Tieying Zhang, Jianjun Chen, Rui Shi, Cuiping Li, and Hong Chen. 2025. LLMIdxAdvis: Resource-Eficient Index Advisor Utilizing Large Language Model. arXiv:2503.07884 [cs.DB] https: //arxiv.org/abs/2503.07884

[49] Xinyang Zhao, Xuanhe Zhou, and Guoliang Li. 2023. Automatic Database Knob Tuning: A Survey. IEEE Trans. Knowl. Data Eng. 35, 12 (2023), 12470–12490. doi:10.1109/TKDE.2023.3266893

[50] Yue Zhao, Gao Cong, Jiachen Shi, and Chunyan Miao. 2022. QueryFormer: a tree transformer model for query plan representation. Proc. VLDB Endow. 15, 8 (April 2022), 1658–1670. doi:10.14778/3529337.3529349

[51] Xuanhe Zhou, Guoliang Li, Zhaoyan Sun, Zhiyuan Liu, Weize Chen, Jianming Wu, Jiesi Liu, Ruohang Feng, and Guoyang Zeng. 2024. D-Bot: Database Diagnosis System using Large Language Models. Proc. VLDB Endow. 17, 10 (2024), 2514– 2527. https://www.vldb.org/pvldb/vol17/p2514-li.pdf

[52] Yuqing Zhu, Jianxun Liu, Mengying Guo, Yungang Bao, Wenlong Ma, Zhuoyue Liu, Kunpeng Song, and Yingchun Yang. 2017. BestConfig: tapping the performance potential of systems via automatic configuration tuning. In Proceedings of the 2017 Symposium on Cloud Computing, SoCC 2017, Santa Clara, CA, USA, September 24-27, 2017. ACM, 338–350. doi:10.1145/3127479.3128605

![](images/356d62dc9c6d33136a586df6d67b3939530798d672c217c6a6796a43d079dce9.jpg)  
Figure A.1: Query execution times (JOB, Postgres).

## A In-Depth Analysis

We analyze the JOB benchmark on Postgres in more detail to better understand the performance gap observed in Figure 5 of the main paper. In particular, we examine a representative compositional baseline that sequentially combines UniView for materialized view selection and <sup>??</sup>-Tune for knob and index tuning.

Table A.1 reports the best configuration recommended by ID-STune and the baseline. For knobs, both approaches focus on improving data locality and enabling parallel query execution via setting effective\_cache\_size=12 GB, max\_parallel\_workers=8. IDSTune goes further by carefully tuning memory-related knobs (shared\_buffers=4 GB, temp\_buffers=128 MB) and worker settings (max\_worker\_processes=8) to match the hardware and workload characteristics. In addition, lowering random\_page\_cost to 2.5 steers the optimizer toward index-aware plans without excessively favoring index-driven nested-loop joins. Compared with the baseline, which aggressively reduces random\_page\_cost to 1.1 and increases work\_mem to 256 MB while leaving several other knobs at defaults, IDSTune adopts a more balanced cost model that is more robust for deep multi-way joins in the JOB workload.

The recommended indexes target frequent join and filter columns across tables such as title, movie\_info, movie\_companies, and cast\_info. Composite indexes like: (movie\_id, info\_type\_id) in movie\_info, (movie\_id, company\_id) in movie\_companies directly optimize the most common join patterns observed in the workload. In contrast, baseline methods typically construct a large number of single-column indexes to maximize coverage, which often results in higher maintenance overhead and reliance on bitmap operations. IDSTune instead prioritizes structure-aware composite indexes that align with join predicates, leading to more predictable execution plans.

IDSTune also produces five materialized views that precompute high-cost joins and frequently queried combinations, which frequently occur across analytical queries. For instance, mv\_company \_keyword\_movie\_title (View 1) pre-joins company, movie, and keyword relations, and mv\_cast\_info\_name\_title (View 3) resolves actor-role-movie relationships in advance. These MVs significantly shorten query execution paths and reduce repeated com putation, yielding low-latency analytical responses even without additional hardware. Compared with baseline materialized views that are often tied to specific constants or query predicates, IDSTune abstracts common join backbones of the JOB workload, enabling reuse across multiple queries rather than benefiting only a small subset.

Unlike traditional tuning methods that optimize knobs, indexes, or views independently, IDSTune explicitly considers the interactions among these configuration dimensions. For example, increasing shared\_buffers and effective\_cache\_size increases the utility of the newly added indexes, because more index blocks can now reside in memory. In addition, enabling parallel workers provides the most benefit when heavy joins are shifted to pre-joined materialized views, reducing intermediate data exchange overhead. This coordinated reasoning enables IDSTune to achieve a globally balanced configuration, avoiding the local optima often observed in phase-wise baselines. In contrast, the baseline materializes only a subset of joins while aggressively biasing the optimizer toward index-driven plans, which can lead to suboptimal execution strategies for queries dominated by deep multi-way joins.

Finally, we compare per-query execution times across the default setting, baseline method, and IDSTune for JOB. Figure A.1 reports corresponding results. It turns out that the performance gain via the configuration proposed by IDSTune translate to gains or at least equal performance, compared to the default setting and baseline method, for each single query.

## B Case Study: Multi-Agent Interaction in a Single Iteration

We present a case study to illustrate how the proposed multi-agent framework performs coordinated tuning in a single iteration under the JOB workload.

Knob Specialist. The Knob Specialist agent generates an initial configuration focusing on memory allocation and cost modeling. For instance, it sets shared\_buffers to 2 GB and effective\_cache \_size to 12 GB to improve caching, while increasing work\_mem to 64 MB to accelerate hash joins. It also adjusts cost knobs (e.g., random\_page\_cost=2.0) to better reflect storage characteristics, thereby guiding the optimizer toward more sequential access patterns.

Index Specialist. Based on observed access patterns, the Index Specialist agent proposes indexes on frequently joined columns. In particular, it reinforces indexes on high-cardinality foreign keys such as movie\_id and person\_id in large tables (e.g., cast\_info, movie\_info), which exhibit substantial scan counts. These indexes aim to reduce join costs and improve access locality.

View Specialist. To further reduce repeated computation, the View Specialist agent introduces several materialized views that precompute common aggregation and join patterns. For example, it constructs views that aggregate keyword counts per movie and summarize company-level statistics, efectively caching intermediate results shared across queries.

Supervisor. The Supervisor agent then evaluates the combined recommendations holistically. In this iteration, the proposal is rejected due to suboptimal configuration settings and potential redundancies. Specifically, the reviewer identifies that (i) memory-related knobs (e.g., shared\_buffers, work\_mem) are too conservative for the workload, (ii) index recommendations lack composite coverage, and (iii) some materialized views may overlap with index benefits. The feedback is subsequently propagated back to individual agents, enabling targeted refinements in the next iteration.

Table A.1: Configuration Comparison between IDSTune and Baseline for JOB (Postgres).  
![](images/31fefc0788735108604730b9cda24c874f5493c0bd2a5507ab06eb8b7bac150a.jpg)

![](images/5edb563219975a1c1f187c6a97d946d7c762f64c97675d2edc503eefbe66079d.jpg)

![](images/eeacba0a1def92eb3f8c1e2447ca51274b8073ce0d5bcbe28aec9aff929e2091.jpg)