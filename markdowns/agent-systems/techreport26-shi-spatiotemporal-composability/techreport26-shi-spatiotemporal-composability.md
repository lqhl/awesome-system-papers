# A Programming Paradigm for Spatiotemporal Composability

Yifan Shi<sup>1,2</sup>, Wei Zhang<sup>1</sup>, Tianyi Cui<sup>2</sup>

<sup>1</sup>Peking University <sup>2</sup>DeepSeek-AI

## Abstract

Modern software—from plugin systems to self-evolving agent harnesses—increasingly requires dynamic composition, yet its formal foundations remain underdeveloped. We identify two orthogonal dimensions of the problem: temporal composability, the ability to completely revert a component’s side efects upon removal, and spatial composability, the ability to declare and reactively manage inter-component dependencies. We address the two dimensions by lifting classical efect and coefect concepts to runtime mechanisms. In particular, we formalize revertible efects, in which every context transformation carries an inverse that the runtime tracks. We formalize reactive coefects, in which each change of the context notifies a component against its coefect specification. We unify the efect context and the coefect context into a single context type, which constitutes a programming paradigm. After that, we combine these mechanisms into the notion of a component and give a calculus of dynamic composition, whose metatheory carries spatiotemporal composability from a single component to a whole system of interleaved components. We implement these ideas in Cordis, a meta-framework of spatiotemporal composability that provides a core library with efect tracking and coefect resolution, as well as a declarative component loader with configuration reconciliation and hot module replacement.

## Contents

1. Introduction . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4   
1.1. Dimensions of Composability . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .   
1.2. Motivating Examples . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4   
1.2.1. Plugin Systems . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 4   
1.2.2. Self-Evolving Agent Harnesses . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5   
1.2.3. The Coarse-Grained Workaround . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 5   
1.3. Contributions . . . . . . . . . . . . . . . 6   
2. Preliminaries . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 7   
2.1. Efects . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 7   
2.2. Coefects . . . . . . . . . . . . . . 7   
2.3. Relationship to Dynamic Composability . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 8   
3. Revertible Efects and Reactive Coefects . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 9   
3.1. Revertible Efects . . . . . . . . 9   
3.1.1. Efect Context . . . . . . . . . . . . . 9   
3.1.2. Revertible Efect Functions . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 12   
3.1.3. Independence of Efects . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 15   
3.2. Reactive Coefects . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 17   
3.2.1. Coeffect Context ... . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 18   
3.2.2. Specification and Notification . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 19   
3.2.3. Isolation and Interception . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 20   
3.3. The Context Paradigm . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 22   
3.3.1. Unified Context . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 22   
3.3.2. Observational Equivalence . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 23   
3.3.3. Situating the Context Paradigm . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 27   
4. A Calculus of Dynamic Composition . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 28   
4.1. Components and Fibers . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 28   
4.2. The Base Calculus . . . . . . . . 30   
4.3. Transitions in Progress . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 33   
4.3.1. Withdrawal . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 34   
4.3.2. Iteration . . . . . . . 35   
4.3.3. Asynchrony . . . . . . . . . . 37   
4.3.4. Failure . . . . . . . 37   
4.4. Metatheory . . . . . . . . . 38   
4.4.1. Preservation . . . . . . . . . 42   
4.4.2. Temporal Composability . . . . . . 43   
4.4.3. Spatial Composability . . . . . . . . 45   
4.4.4. Progress . . . . 47   
4.4.5. Confluence . . . . . . . . 49   
5. Implementation and Case Study . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 54   
5.1. Core Library . . . . . 54   
5.1.1. Efect Tracking . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 56   
5.1.2. Coefect Operations . . . . . . 57   
5.1.3. Component Lifecycle . . . . . . . . . . . . . . . 58   
5.1.4. Context Access . . . . . . 61   
5.2. Component Loader . . . . . . . 61   
5.2.1. Declarative Configuration . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 62   
5.2.2. Hot Module Replacement . . . . . . . . . . . . . . . 64   
5.3. Case Study: Koishi . . . . . . 66   
6. Discussion . . . . . . . 67   
6.1. System Boundary . . . . 67   
6.2. Service Multiplexing . . . . . . 68   
6.3. Access Control and Sandboxing . . . . . . . . 69   
6.4. Language Independence and Selection . . . . . . . . . . . . 70   
6.5. Mutual Dependencies and Component Granularity . . . . . . . . . . . . . . . 71   
6.6. Dependency Typing and Versioning . . . . . . 72   
6.7. Co-Design with Languages and Operating Systems . . . . . . . . . . . . . . . . . . . 73   
7. Related Work . . . . . . . . . . . 74   
7.1. Efect and Coefect Systems . . . . . 74   
7.2. Programming Paradigms . . . . . . . . 75   
7.3. Temporal Composability . . . . . 76   
7.4. Spatial Composability . . . . . . 78   
8. Conclusion . . . . . . 79   
References . . . . . . . . 80

## 1. Introduction

Composition—assembling complex systems from simpler parts—is a foundational principle of software engineering [1]. Traditionally, composition is static: function calls, module imports, and class inheritance are resolved at compile time and remain fixed throughout execution. However, modern software increasingly demands dynamic composition, where components are loaded, unloaded, and reconfigured at runtime. Plugin architectures [2] and self-evolving agent harnesses both require systems that can safely add and remove functionality on the fly, yet current practice defers to coarse-grained mechanisms [3] that reconfigure only by restarting, discarding runtime state. Despite the growing practical importance of dynamic composition, its theoretical foundations remain underdeveloped, compared to the rich formal frameworks available for static composition.

## 1.1. Dimensions of Composability

To characterize the requirements of dynamic composition, we identify two orthogonal dimensions beyond the well-studied algebraic aspects of composition:

• Temporal composability addresses the time dimension: upon removal of a component, the modifications the component made to the shared environment must be completely and safely reversed. This requires tracking every resource allocation, event registration, and state mutation the component performs, and guaranteeing their orderly reclamation upon removal.

• Spatial composability addresses the space dimension: components must be able to declare, discover, and resolve their dependencies on one another in a structured and verifiable manner. This requires managing dependency topology and coordinating component lifecycles in response to dependency changes.

In the static setting, temporal composability reduces to lexical scoping (e.g., RAII [4], bracket patterns [5]), and spatial composability reduces to module import resolution [6]. In the dynamic setting, where components arrive and depart at runtime, both dimensions become significantly harder: temporal composability must handle long-lived, stateful efects whose scope is not lexically bounded; and spatial composability must handle dependencies that appear, disappear, or change identity during execution.

## 1.2. Motivating Examples

## 1.2.1. Plugin Systems

Plugin systems are a canonical instance of dynamic composition. We use Visual Studio Code (VSCode), one of the most widely-used extensible IDEs, as a representative example.

Temporal limitation. VSCode runs all extensions in a shared process called the extension host. Although extensions can be installed dynamically, this host provides no mechanism to unload an individual extension’s code at runtime. Once an extension’s activate function has executed, disabling or uninstalling it requires restarting the entire host, afecting all loaded extensions. Purely declarative extensions such as themes, keybindings, and snippets carry no code and can be removed freely. Among the top 100 extensions by install count, however, 87 contain executable code<sup>1</sup> and will therefore require such a restart upon removal. Although VSCode provides a deactivate hook, it serves only as a graceful shutdown callback during the host process’ termination, and thus does not enable live removal. Moreover, the hook separates efect disposal from efect creation (in activate), violating locality of concern and making complete cleanup dificult to verify.

Spatial limitation. VSCode does provide extensionDependencies for declaring dependen cies between extensions, but it sees little use: among the top 100 extensions by install count, only 7 declare extensionDependencies on non-built-in extensions.<sup>1</sup> This scarcity reflects the shape of the extension API, which exposes fixed, surface-level extension points such as commands, views, and language features. Extensions contribute to the host through these points rather than depending on one another, so inter-extension dependencies rarely arise. Moreover, VSCode’s mechanism for inter-extension interaction provides no structural contract: it exposes an extension’s functionality to others through vscode.extensions.getExtension(...).exports, but the returned value is untyped (any by default), so the dependent cannot rely on a checked interface. In short, VSCode steers extensions toward a fixed set of host-provided extension points, and ofers no safe, structured way for them to depend on one another.

These two limitations are not unique to VSCode; they recur across plugin systems generally [2, 7], difering only in degree.

## 1.2.2. Self-Evolving Agent Harnesses

Modern AI agents rely on runtime agent harnesses [8–10]. These systems may compose diverse tool suites [11] and execution environments, govern permissions and sandboxing, maintain session state and persistence, provide context management and memory systems [12], orchestrate subagents and multi-agent workflows [13], and expose interfaces to users and automation. A future harness may generate and deploy modifications to its own components while continuously serving requests. Model-synthesized reusable tools provide a narrower precursor to component-level self-modification [14]. Each such modification is itself an instance of dynamic composition.

Because these modifications occur continuously and with limited or no human oversight, dynamic composability becomes indispensable. Without temporal composability, each selfmodification forces a full restart that discards all process-local accumulated state; at such frequency the cumulative unavailability becomes substantial, and in-flight tasks are disrupted repeatedly; even worse, a faulty self-modification can disable the very process needed to recover. Without spatial composability, each module must itself detect and adapt to changes in the modules it depends on as they appear, disappear, or change identity, and can do so only by ad hoc means; even worse, a naive code-replacement strategy may silently break dependents or introduce circular dependencies that surface only at reload time.

## 1.2.3. The Coarse-Grained Workaround

One reason dynamic composability has received limited formal attention is that operating systems and container orchestrators already provide a coarse-grained substitute. Operating systems yield temporal composability at the granularity of a process; container orchestrators [3] yield spatial composability at the granularity of a service. In practice, most software tolerates the lack of fine-grained composability by deferring to these coarse-grained mechanisms: a misbehaving module is handled by restarting the process, and a service dependency is managed by the container orchestrator.

However, this workaround imposes substantial costs. Temporally, each restart discards all process-local accumulated state (e.g., caches, connections, partial computations), and rebuild ing it takes seconds to minutes [15]; maintaining availability in the interim requires redundant replicas, incurring resource overhead to compensate for the inability to recover a single component. Spatially, container-level orchestration cannot express dependencies between com ponents sharing an address space, and introduces network overhead for interactions that could be local function calls. Both mechanisms operate at the boundary of processes and containers, yet modern systems increasingly compose at a finer level. This granularity mismatch demands a compositional abstraction that manages efects and dependencies at the same level as the components themselves.

## 1.3. Contributions

The two dimensions of dynamic composability concern, respectively, how computations modify and how they depend on their environment. These two directions are what efect systems [16, 17] and coefect systems [18, 19] formalize: efects provide the formal vocabulary for reasoning about environmental modifications, and coefects for reasoning about environmental require ments. However, existing formulations restrict reasoning to compile-time analysis over lexically fixed scopes, and do not extend to dynamic scenarios where components arrive and depart at runtime. By lifting efects to a revertible runtime model and coefects to a reactive dependency resolution mechanism, we obtain a unified formal foundation for dynamic composability, one that is language-agnostic and applicable to any software architecture requiring dynamic composition. We make the following contributions:

1. We formalize revertible efects (Section  3.1): every context transformation carries an explicit inverse that the runtime tracks, and both tracking and recovery preserve composition, so the context is recovered upon component removal. This establishes local temporal composability.

2. We formalize reactive coefects (Section  3.2): a component declares the coefects it requires as a specification, and each change of the context notifies the component against that specification as activating, deactivating, or neutral. This establishes local spatial composability.

3. We unify the efect context and the coefect context into a single context type (Section 3.3), in which an observational equivalence on the coefects supplies the efects with independence, constituting a programming paradigm for spatiotemporal composability.

4. We give a calculus of dynamic composition (Section  4), which combines the two mechanisms into the notion of a component and equips its lifecycle with an operational semantics. Its metatheory carries spatiotemporal composability from a single component to a whole system of interleaved components.

5. We implement these ideas in Cordis (Section 5), a meta-framework of spatiotemporal composability that provides a core library realizing the formal model with efect tracking and coefect resolution, as well as a declarative component loader with configuration reconciliation and hot module replacement.

## 2. Preliminaries

This section provides a concise overview of efect and coefect systems—the two theoretical pillars underlying our work. We assume familiarity with basic type theory and category theory; the goal here is to fix notation and introduce the key abstractions that Section 3 will operationalize as runtime mechanisms.

## 2.1. Efects

In the simply typed lambda calculus (STLC) [20, 21], a typing judgment Γ ⊢ ?? : ?? states that term ?? has type ?? under context Γ. An efect system refines the type to describe what side efects a computation may produce, yielding judgments of the form

![](images/f7e352cae23cb9660c54336f8bd162b8f4620f4d548e36d373411c5a9d095833.jpg)

(1)

Here, the result type is annotated with an element of an efect algebra that describes which side efects the computation may produce, enabling compositional reasoning about stateful computations. This approach originates with Lucassen and Giford [22], who introduced a kinded type system distinguishing types, efects, and regions to discover scheduling constraints in parallel programs.

Monadic efects. Moggi [16] first modeled computational efects categorically via monads; Wadler [23] popularized the approach in Haskell. A monad (?? , ??, ??) on a category ??︀ encapsulates an efectful computation as a value of type ?? (??), with ?? : ?? → ?? (??) lifting pure values and ?? : ?? (?? (??)) → ?? (??) sequencing nested computations. Classic instances include the Maybe monad (for partiality), State monad (for mutable state), and IO monad (for external interaction).

Algebraic efects. Plotkin and Power [17, 24] showed that algebraic operations determine monads, establishing a framework in which efect interfaces are decoupled from their implementations. An efect signature Σ declares a set of operations (e.g., get : () → ??, put : ?? → () for state); programs invoke operations freely without committing to a particular interpretation. Plotkin and Pretnar [25] subsequently introduced efect handlers, which interpret operations by providing continuation semantics:

![](images/2a37199e283f6c2b1aaf0ac92d99057cfa77fa57fa5d5c416bdebb7449820b9b.jpg)

(2)

The handler receives the operation argument ?? and the delimited continuation ??, which it may invoke zero, one, or multiple times, enabling exceptions, coroutines, and non-determinism within a uniform framework [26]. Languages such as Koka [27, 28], Ef [29], and OCaml 5 [30] have adopted algebraic efects with varying design trade-ofs.

## 2.2. Coefects

Dually to efects, a coefect system [18, 31] enriches the context rather than the type, yielding judgments of the form

![](images/4c86d6851261ebc3cf2b1f07090c8131789a42e994511fe951a41d7887a58874.jpg)

(3)

Here, the context is annotated with an element of a coefect algebra describing what the computation requires from its environment, such as resources to access, permissions to hold, or services to depend on. While efects model a program’s impact on the world, coefects model the world’s constraints on the program.

Comonadic coefects. The idea of using comonads to structure context-dependent computation was first developed by Uustalu and Vene [32], who proposed symmetric (semi)monoidal comonads as the dual of Moggi’s monadic framework for efects, capturing notions such as dataflow and attribute evaluation. Petricek et al. [18] built on this foundation to propose coefects as a unified static analysis of context-dependence. A comonad (??, ??, ??) captures context-dependent computation: ?? : ??(??) → ?? extracts the current value from a context, and ?? : ??(??) → ??(??(??)) duplicates context for nested access. The Environment comonad ??(??) = ?? × ?? models dependence on a fixed environment ??; the Stream comonad ??(??) = ℕ → ?? models dependence on temporal data.

Graded coefects. For finer-grained tracking, graded coefect systems use a pre-ordered semiring ??︀ = (??, ≤, +, ×, 0, 1) as the coefect algebra [33], a discipline later unified with graded efects by Gaboardi et al. [19]. Elements of ?? annotate each variable binding to quantify its usage: 0 for unused, 1 for linear use, ?? for bounded use, ∞ for unrestricted use. The semiring operations compose coefects sequentially (×) and in parallel (+), enabling precise resource tracking, sensitivity analysis [34], and information-flow control [35, 36] within a unified alge braic framework [37].

## 2.3. Relationship to Dynamic Composability

Efect and coefect systems organize reasoning about computation along two complementary directions: efects describe how a computation modifies its environment, whereas coefects describe how it depends on its environment. These two directions correspond to the two dimensions of dynamic composability identified in Section 1:

• Temporal composability demands that a component’s modifications to the shared environment be revertible upon unloading. The relevant efects are the stateful ones, which durably transform that environment; undoing such a transformation requires it to admit an inverse.

• Spatial composability demands that inter-component dependencies be declared and managed reactively. Such dependencies are the very thing coefects capture, and manag ing them amounts to resolving each against what the environment supplies.

However, classical efect and coefect systems are static instruments: efects are tracked within lexically fixed scopes and discharged by compile-time handlers; coefect annotations are verified against contexts determined before execution. Dynamic composition, by contrast, requires these guarantees to hold for components that arrive and depart at runtime, against contexts that evolve continuously. No fixed lexical scope can delimit a plugin loaded after deployment; no compile-time context can anticipate dependencies that emerge from runtime configuration.

This motivates a shift in perspective: rather than extending static type systems with more annotations, we reify the conceptual structures of efects and coefects so that a runtime can operate on them directly, establishing dynamically the guarantees these systems provide statically.

## 3. Revertible Efects and Reactive Coefects

This section lifts the concepts of efects and coefects introduced in Section 2 to runtime mechanisms, constructing a theory of dynamic composition. The central idea is to turn the typing contexts carrying efects and coefects into context types, i.e., runtime-operable types that reify the context as a first-class entity. For the efect type, we model it as a context transformation paired with an inverse, achieving local temporal composability. For the coefect context, we model it as a type carrying dependency information, achieving local spatial composability. An observational equivalence on the coefects then supplies the efects with independence. The unified context that carries both efects and coefects constitutes a programming paradigm in its own right.

## 3.1. Revertible Efects

Temporal composability is the ability to load and unload components at runtime such that, upon unloading, the shared environment is recovered to its pre-composition state. This requires that every modification a component makes to the environment be both trackable and recoverable. We therefore model an efect as a function of type Γ → Γ × (Γ → Γ): applied to the current context, it yields the modified context together with an explicit inverse. Supplying that inverse is what lets the efect be reverted, and returning it to the runtime is what makes the efect trackable. We call such efects revertible: by tracking and composing these inverses during execution, complete environment recovery becomes a structural guarantee.

## 3.1.1. Efect Context

Given any impure function ??<sub>impure</sub> : ?? → ?? , we transform it into a pure form ?? : Γ × ?? → Γ × ?? , where Γ is the context and all possible side efects can be represented as transformations on Γ. For any fixed input ?? : ??, the induced map ?? ↦ pr<sub>1</sub>(??(??, ??)) captures the side efect of ?? independently of the return value. Efects on Γ therefore live in the monoid of transformations Γ → Γ under composition ∘, where each monoid axiom has a direct reading as a property of efects:

• Closure: the sequential composition of two efects is again an efect;

• Associativity: a composite efect is independent of how it is bracketed;

• Identity: id<sub>Γ</sub>, the identity function on Γ, acts as the unit of composition.

To model efects that can be undone, we pair each transformation ?? with another transformation ?? that undoes ??, and call ?? a left inverse of ??, abbreviated to inverse throughout the paper. Undoing is one-sided: what an inverse is held to is ?? ∘ ?? and never ?? ∘ ??. Pairs of transformations carry a multiplication of their own:

Definition 1. Define the twisted composition of pairs of context transformations by

![](images/2d66bfea657e8364e24a4f39445f33500a5ddbf80bc0c38c14fef77c74aaa8c1.jpg)

(4)

As for ∘ itself, the left operand acts after the right, and the inverses accumulate in the opposite order. It makes (Γ → Γ) × (Γ → Γ) a monoid with unit (id<sub>Γ</sub>, id<sub>Γ</sub>), the product of the monoid of transformations with its opposite, which we call the twisted composition monoid ??<sub>Γ</sub> over Γ.

To track efects within the context itself, we introduce the following definition:

Definition 2. Given a context Γ, define its efect context as:

![](images/ca45406d1609868e058e92c95a462ae3a8ce188bfe5df6923b0a4adccb4fcf9e.jpg)

(5)

It can be understood as a pair (??, ??), where:

• ?? : Γ is the current context state;

• ?? : Γ → Γ is the accumulator, the composite of the inverses of the efects performed so far, and the function that recovers the context to its initial state.

In particular, the initial efect context can be represented as (?? , id ).

We also write ??<sup>2</sup>Γ = ??Γ × (??Γ → ??Γ), and so on up the tower.

Given the presence of the accumulator ??, all efects performed on ??Γ can be tracked and recovered. We now give the concrete constructions for tracking and recovery.

Definition 3. Define the transformation track on pairs of context functions:

![](images/4ccc28d3446ec645341b25629b3d03904637defb1adfca62c79b1323e25a90c2.jpg)

(6)

This transformation converts a forward function ?? together with a candidate inverse ?? into a transformation of the efect context ??Γ. Applying track (??, ??) to a state (??, ??) transforms ?? by ?? and composes the inverse ?? onto ??, thereby tracking the efect of ?? in the context.

Theorem 4. For every (??, ??) ∈ (Γ → Γ) × (Γ → Γ) the following diagram commutes, that is,

![](images/d3b5de9c284d2d34187925e829a2b0b17d27189c9acc9f0cd1089853b7f144a7.jpg)

(7)

![](images/2ead028940242b6dcb48e0f297af34fb9a9d8e042337e64dc764bba150524fc0.jpg)

Proof. For all (??, ??) ∈ ??Γ:

![](images/d854bdc1e4031ca346a4ccb0f97332d1e75fd00e893d0748fb247fd2c3050973.jpg)

Theorem 5. track is a monoid homomorphism from ?? into ??Γ → ??Γ. That is,

1. track<sub>Γ</sub>(id<sub>Γ</sub>, id<sub>Γ</sub>) = id<sub>??Γ</sub>;

2. for all (??<sub>1</sub>, ??<sub>1</sub>), (??<sub>2</sub>, ??<sub>2</sub>) ∈ ??<sub>Γ</sub>,

![](images/708a3376eff318daee48302e44c723a113e08cb34a56f964d58f7467a793981a.jpg)

(8)

Proof.

1. The unit is carried to the unit, since track<sub>Γ</sub>(id<sub>Γ</sub>, id<sub>Γ</sub>)(??, ??) = (??, ?? ∘ id<sub>Γ</sub>) = (??, ??).

2. For the multiplication, take any (??, ??) ∈ ??Γ:

![](images/ff4946751de8e549073d31ee03946a3de82841040bf4b53fd94ca2b20e89a08e.jpg)

Definition 6. Define the transformation recover on ??Γ:

![](images/9e259271eb557560ba557547870834782744254a994388077e724921e67c80e0.jpg)

(9)

This transformation applies the recovery function ?? to the current state ?? and resets ?? to the identity. The following diagram illustrates how recover recovers the context to its initial state after a sequence of efects track(??<sub>1</sub>, ??<sub>1</sub>), ⋯, track(??<sub>??</sub>, ??<sub>??</sub>) has been applied to ??Γ:

![](images/e45f0f2b9805ffeac184375693c1cc6273c87040d80447d6edfff40f8437a290.jpg)

The diagram shows that the tracked efects followed by recover carry the initial efect context back to itself. What each tracking step preserves is the result of recovery itself, from whatever state it is taken:

Theorem 7. For every (??, ??) ∈ ??Γ and every pair (??, ??) with ??(??(??)) = ??,

![](images/44b515d38aab9b08eaedba5b2e757ad3f8a157c32de274b3921b5666d651c2f6.jpg)

(10)

Proof.

![](images/613799a59ae050baef04fcc3813af48564bf281e8578d31054b3b863623967b3.jpg)

A sequence of pairs needs no separate argument. Let (??<sub>1</sub>, ??<sub>1</sub>), ⋯, (??<sub>??</sub>, ??<sub>??</sub>) be applied in order from (??, ??), and write ??<sub>0</sub> = ?? and ??<sub>??</sub> = ??<sub>??</sub>(??<sub>??−1</sub>). By Theorem 5 the composite track<sub>Γ</sub>(??<sub>??</sub>, ??<sub>??</sub>) ∘ ⋯ ∘ track<sub>Γ</sub>(??<sub>1</sub>, ??<sub>1</sub>) is track<sub>Γ</sub> of the twisted composite (??<sub>??</sub> ∘ ⋯ ∘ ??<sub>1</sub>, ??<sub>1</sub> ∘ ⋯ ∘ ??<sub>??</sub>), and if ??<sub>??</sub>(??<sub>??</sub>) = ??<sub>??−1</sub> for every ?? then (??<sub>1</sub> ∘ ⋯ ∘ ??<sub>??</sub>)(??<sub>??</sub>) = ??<sub>0</sub> = ??. That pair therefore meets the hypothesis of Theorem 7 at ??, and one application of the theorem gives

![](images/cdb5f000cad9ce172549b8e441a6d09eb4507af1a8641a003595b84583d07692.jpg)

(11)

Taking (??, ??) = (??<sub>0</sub>, id<sub>Γ</sub>), recovery carries every state reached this way back to (??<sub>0</sub>, id<sub>Γ</sub>). A pair with ?? ∘ ?? = id meets the hypothesis at every state.

Recovery reads a state through the quantity ??(??), and we refer to ??(??) = ??<sub>0</sub> as the soundness invariant of a state in ??Γ.

## 3.1.2. Revertible Efect Functions

The track/recover model of the previous section takes inverses as given a priori: track<sub>Γ</sub>(??, ??) fixes ?? before any context state is seen, so one ?? has to serve every state the efect is applied at. In practice, however, the inverse of each efect is not known a priori: it must be supplied by the caller at the point of efect application. Moreover, recover is all-or-nothing: it cannot selectively undo one efect while retaining others. To address both issues, we enhance the model at both the input and output sides:

1. On the input side, we not only transform Γ but also return an inverse function alongside it, so that the inverse is supplied where the efect is applied: Γ → Γ × (Γ → Γ), i.e., Γ → ??Γ;

2. On the output side, we not only transform ??Γ but also return an inverse function alongside it, so that one efect can be undone while the others are retained: ??Γ → ??Γ × (??Γ → ??Γ), i.e., ??Γ → ??<sup>2</sup>Γ.

This enhancement preserves structural consistency between input and output, so we can still define corresponding theory that maintains the mathematical properties of track. The resulting types are the efect functions ??<sub>Γ</sub> and their witnessed refinement ??<sup>∗</sup><sub>Γ</sub>:

Definition 8. Define the efect function ?? and witnessed efect function ??<sup>∗</sup> as:

![](images/bca2d7d78c01d0713fd28716d4d03f2be813fdce8c32e99c328be6b145f869a3.jpg)

(12)

where ??(??) yields a pair (??, ??) representing:

• ?? : Γ is the new context;

• ?? : Γ → Γ is the inverse function of the current efect.

An element of ??<sup>∗</sup> chooses its inverse per state, and the constraint ??(??) = ?? holds that choice to reverting the efect where it was applied, leaving ?? unconstrained everywhere else. A single ?? with ?? ∘ ?? = id<sub>Γ</sub> meets the constraint at every state at once, and induces an element of ??<sup>∗</sup><sub>Γ</sub> by (??, ??) ↦ ?? ↦ (??(??), ??), which Theorem 11 shows to be a homomorphism. The constraint can be visualized as the following commutative diagram, ensuring that the inverse ?? returns indeed reverses the transformation at the state where ?? was applied:

![](images/621fb7bbb7d7a88fab36adfd1b322329ad0fe59b174c36569aa3d611cd804c6c.jpg)

Since efect functions ??<sub>Γ</sub> are no longer endomorphisms on the context, they cannot be directly composed. We therefore define a new operation for efect composition:

Definition 9. Given functions ??, ?? ∈ ??<sub>Γ</sub>, define their efect composition ?? ⋄ ?? as:

![](images/10113a28678a5fea2ed910959886967dab4eb13c2c5df3be2b7e48386098214c.jpg)

(13)

Theorem 10. Efect composition carries the monoid structure of ??<sub>Γ</sub> over to ??<sub>Γ</sub>. That is,

1. (??<sub>Γ</sub>, ⋄) is a monoid with unit ??<sub>Γ</sub> ≔ ?? ↦ (??, id<sub>Γ</sub>);

2. the assignment (??, ??) ↦ ?? ↦ (??(??), ??) is a monoid homomorphism from ??<sub>Γ</sub> into ??<sub>Γ</sub>.

Proof.

1. Associativity and the unit laws follow componentwise from those of ∘.

2. Write ?? = ?? ↦ (?? (??), ?? ); then (?? ⋄ ?? )(??) = (?? (?? (??)), ?? ∘ ?? ), which is the image of (??<sub>1</sub>, ??<sub>1</sub>) ∘ (??<sub>2</sub>, ??<sub>2</sub>), and (id<sub>Γ</sub>, id<sub>Γ</sub>) maps to ??<sub>Γ</sub>. □

Theorem 11. Witnessing survives efect composition, and a uniform inverse witnesses at every state. That is,

1. ??<sup>∗</sup><sub>Γ</sub> is a submonoid of ??<sub>Γ</sub>;

2. the homomorphism of Theorem 10 carries every pair with ?? ∘ ?? = id<sub>Γ</sub> into ??<sup>∗</sup><sub>Γ</sub>.

1. The unit lies in ??<sup>∗</sup> since id (??) = ??. For closure, take ??, ?? ∈ ??<sup>∗</sup> and any ?? ∈ Γ, and let (??, ??) = ??(??), (??, ??) = ??(??), so that (?? ⋄ ??)(??) = (??, ?? ∘ ??). Then ??(??) = ?? and ??(??) = ??, therefore (?? ∘ ??)(??) = ??(??) = ??.

2. ?? ∘ ?? = id<sub>Γ</sub> gives ??(??(??)) = ?? at every ??, so the image of such a pair is witnessed at every state. □

Just as track lifts a pair of transformations on Γ to ??Γ, we define effect to lift ??<sub>Γ</sub> to ??<sub>??Γ</sub>:

Definition 12. Define the efect function transformation effect<sub>Γ</sub> as:

![](images/82fbc8cbffcd5141f3512bcef9c59969dfb8e428b6aab309f1f09d987c41c571.jpg)

(14)

Since effect<sub>Γ</sub>(??) is itself ??<sub>??Γ</sub>, what it returns is an inverse in the sense of Definition 8 read one level up. That inverse is itself a track of the pair obtained by swapping the two directions of the efect. The ordinary tracking rule applies once more: undoing the efect is an efect in its own right, transforming the state by ??, and the way to undo that is to perform the efect again, which is what pr ∘ ?? does. The inverse therefore composes onto the accumulator it is handed, exactly as track prescribes.

We can now prove properties for effect analogous to those of track.

Theorem 13. effect preserves the ⋄ operation. That is, ∀??, ?? ∈ ??<sub>Γ</sub>:

![](images/69e638b6c8265e199d8df7ed88cf8c46dab1db2e1dae1326915dfa770cfc166b.jpg)

(15)

Proof. Take any (??, ??) ∈ ??Γ, and let (??, ??) = ??(??) and (??, ??) = ??(??), so that (?? ⋄ ??)(??) = (??, ?? ∘ ??) and pr ∘ (?? ⋄ ??) = (pr ∘ ??) ∘ (pr ∘ ??). Then

![](images/81d7294fa3355b2ed989ce530f32eaa130cad309e244478e5b22495fffe3b421.jpg)

where the first step unfolds Definition 12 at (??, ??) and at (??, ?? ∘ ??), the second is Theorem 5, and the third folds Definition 12. □

How the two levels relate is what the following diagram shows. Its upper triangle is the witness condition of ??, according to Definition  8, and its lower triangle is the question of whether ??<sup>′</sup> is witnessed the way ?? is.

![](images/40d8a0a546600038844447bf25799436e052e825788596b5fe2cb5bac5353016.jpg)

Between the levels, the projection pr relates each lifted map to the map it lifts, as it does for track in Theorem 4.

Theorem 14. Let ?? ∈ ??<sub>Γ</sub>, write ?? ≔ pr<sub>1</sub> ∘ ??, and let ??<sup>′</sup> ≔ effect<sub>Γ</sub>(??) with forward map ??<sup>′</sup> ≔ pr<sub>1</sub> ∘ ??<sup>′</sup>. Then

1. pr<sub>1</sub> ∘ ??<sup>′</sup> = ?? ∘ pr<sub>1</sub>;

2. for each (??, ??) ∈ ??Γ, the lifted inverse ??<sup>′</sup> ≔ pr<sub>2</sub>(??<sup>′</sup>(??, ??)) and the inverse ?? ≔ pr<sub>2</sub>(??(??)) witnessed there satisfy pr<sub>1</sub> ∘ ??<sup>′</sup> = ?? ∘ pr<sub>1</sub>.

Proof.

1. By Definition 12, ??<sup>′</sup>(??, ??) = (??(??), ?? ∘ ??), whose state is ??(??) = (?? ∘ pr<sub>1</sub>)(??, ??).

2. This is Theorem 4 applied to ??<sup>′</sup> = track<sub>Γ</sub>(??, ??).

Whether the lower triangle closes is settled by computing what the lifted inverse returns:

Theorem 15. Let ?? ∈ ??<sup>∗</sup><sub>Γ</sub> and write ?? ≔ pr<sub>1</sub> ∘ ??. Fix (??, ??) ∈ ??Γ, let (??, ??) = ??(??), and write (Δ, ??<sup>′</sup>) for the value of effect (??) at (??, ??). Then

![](images/c9c9a1a1a7db07032d751994f0502853a0f6abb8b6d2b4528a936bfdf1a5293c.jpg)

(16)

The state is recovered exactly. The accumulator is restored as well, equivalently effect<sub>Γ</sub>(??) ∈ ??<sup>∗</sup> , if and only if ?? ∘ ?? = id ; and in every case (?? ∘ ?? ∘ ??)(??) = ??(??), so the soundness invariant is preserved.

Proof. By Definition 12, Δ = (??, ?? ∘ ??) and ??<sup>′</sup> = track<sub>Γ</sub>(??, ??), so

![](images/f98d2a1979bb9f63d14a778b370debe0660413c76bdd376a0e96ad4b615606d2.jpg)

using ??(??) = ??. Membership in ??<sup>∗</sup> requires this to equal (??, ??) at every input; taking ?? = id turns the equality of accumulators into ?? ∘ ?? = id , and that condition conversely gives the equality of accumulators for every ??. Finally (?? ∘ ?? ∘ ??)(??) = ??(??(??)) = ??(??). □

The lower triangle therefore closes only when the inverse witnessed at ?? reverts ?? at every state, so effect<sub>Γ</sub> does not carry ??<sup>∗</sup><sub>Γ</sub> into ??<sup>∗</sup> . What holds in every case is agreement at ??: recover (??<sup>′</sup>(Δ)) = recover (??, ??), which is the whole of what Theorem 7 assumes of an accumulator, so reverting leaves the recovery target untouched.

Reverting efects in the reverse of the order in which they were applied requires nothing further, because each inverse then meets the state its own application produced:

Theorem 16. Let ??<sub>1</sub>, ⋯, ??<sub>??</sub> ∈ ??<sup>∗</sup><sub>Γ</sub> be applied in order from (??<sub>0</sub>, id<sub>Γ</sub>) and reverted in the reverse order. Then

1. each revert recovers the context state its application ran against;

2. every intermediate state satisfies the soundness invariant.

Proof. Each step is an application or a revert. An application carries (??, ??) to (??, ?? ∘ ??) with ??(??) = ??, so it preserves ??(??) by Theorem 7, whose hypothesis is exactly the witness of ??<sup>∗</sup><sub>Γ</sub>. Reverting in the reverse order hands each inverse the state its own application produced, so by Theorem 15 that revert recovers the preceding state exactly and preserves ??(??) as well; neither conclusion depends on the accumulator the inverse receives. □

## 3.1.3. Independence of Efects

Reverting an efect at the state its own application produced is what Theorem  16 covers; reverting one at any other state is what this subsection covers. Two situations call for the latter. An inverse may be run while later efects are still in place, which is what withdrawing one component from a running system amounts to; and one sequence may interleave the efects of several components, each keeping the inverses of its own, so that the inverses of one component are separated by the applications of another. In both an inverse meets a state that foreign efects have moved, and whether it still reverts what it was built to revert is a question of commutation: what has to commute is every transformation one efect can perform with every transformation the other can perform, forward map and yielded inverse alike. A single accumulator settles neither situation, ?? being a composite that runs every inverse it holds in one order and all at once.

Definition 17. For an efect function ?? ∈ ?? , the transformation monoid ??(??) is the submonoid of Γ → Γ generated by the forward map of ?? together with every inverse ?? yields, and the generators of ??(??) are the elements of that generating set:

![](images/480198531742e28dab5c85d1a5a632d76ad0f1fe1b680abd48c54743dc56eede.jpg)

(17)

An efect induced by a pair (??, ??) ∈ ??<sub>Γ</sub> has ?? and ?? for its generators, the inverse it yields being ?? at every state.

Lemma 18. Commutation is settled on the generators, and ⋄ enlarges no transformation monoid. That is,

1. if every generator of ??(??<sub>1</sub>) commutes with every generator of ??(??<sub>2</sub>), then every element of ??(??<sub>1</sub>) commutes with every element of ??(??<sub>2</sub>);

2. ??(??<sub>1</sub> ⋄ ??<sub>2</sub>) ⊆ ⟨??(??<sub>1</sub>) ∪ ??(??<sub>2</sub>)⟩.

Proof.

1. The maps commuting with every generator of ??(?? ) form a submonoid of Γ → Γ, since id lies in it and ?? ∘ ??<sup>′</sup> does where ?? and ??<sup>′</sup> do. That submonoid contains the generators of ??(??<sub>1</sub>) by hypothesis and hence contains ??(??<sub>1</sub>). Fixing ?? ∈ ??(??<sub>1</sub>), the maps commuting with ?? likewise form a submonoid containing the generators of ??(??<sub>2</sub>) and hence ??(??<sub>2</sub>).

2. By Definition 9 the forward map of ??<sub>1</sub> ⋄ ??<sub>2</sub> is (pr<sub>1</sub> ∘ ??<sub>1</sub>) ∘ (pr<sub>1</sub> ∘ ??<sub>2</sub>) and the inverse it yields at any state is ?? ∘ ?? for an ?? yielded by ??<sub>2</sub> and a ?? yielded by ??<sub>1</sub>. Every generator of ??(??<sub>1</sub> ⋄ ??<sub>2</sub>) is therefore a composite of generators of the two. □

Definition 19. Efect functions ??<sub>1</sub>, ??<sub>2</sub> ∈ ??<sub>Γ</sub> are independent when

1. every transformation of one commutes with every transformation of the other,

![](images/797bf654786f03d00fd35da37620f9af505a2d0786d56129b66fb9a66167b1fe.jpg)

(18)

2. neither one’s transformations disturb the inverse the other yields,

![](images/ad004fd8c452e47a738c773653fc13abac7797d2c4d05c5edc09cfbd67d939bc.jpg)

(19)

and the same with ??<sub>1</sub> and ??<sub>2</sub> exchanged.

A family (??<sub>??</sub>) is pairwise independent when ??<sub>??</sub> and ??<sub>??</sub>′ are independent for every ?? ≠ ??<sup>′</sup>. A family may repeat an efect function, and holding one independent of itself is holding ??(??) commutative.

For efects induced by pairs (?? , ?? ) and (?? , ?? ), clause (1) is by Lemma 18(1) the commutation of the four pairs ??<sub>1</sub>, ??<sub>2</sub>; ??<sub>1</sub>, ??<sub>2</sub>; ??<sub>1</sub>, ??<sub>2</sub>; and ??<sub>1</sub>, ??<sub>2</sub>, and clause (2) holds outright, an induced efect yielding one inverse at every state. Commutation under ⋄ is a diferent property. What ?? ⋄ ?? = ?? ⋄ ?? equates is the composite forward map of the two orders with each other and the composite inverse of the two orders with each other, each inverse entering the composite at the state its own application produced; independence instead relates each transformation of one efect to each transformation of the other, a forward map paired with a foreign inverse included.

Under independence an inverse may be run at a state later efects have moved, and what it withdraws there is its own contribution and nothing else:

Theorem 20. Let ?? , ⋯, ?? ∈ ??<sup>∗</sup> be pairwise independent and applied in order from ?? . Write ??<sub>??</sub> ≔ pr<sub>1</sub> ∘ ??<sub>??</sub>, let ??<sub>??</sub> ≔ ??<sub>??</sub>(??<sub>??−1</sub>) with ??<sub>0</sub> ≔ ??<sub>0</sub>, and let ??<sub>??</sub> ≔ pr<sub>2</sub>(??<sub>??</sub>(??<sub>??−1</sub>)) be the inverse ??<sub>??</sub> yields where it is applied. Fix ?? and write ??<sup>′</sup><sub>??</sub> ≔ (??<sub>??</sub> ∘ ⋯ ∘ ??<sub>??+1</sub>)(??<sub>??−1</sub>) for the states of the sequence with ??<sub>??</sub> omitted, so that ??<sup>′</sup><sub>??</sub> = ??<sub>??−1</sub>. Then for every ?? with ?? ≤ ?? ≤ ??,

1. ??<sub>??</sub> = ??<sub>??</sub>(??<sup>′</sup><sub>??</sub>) and ??<sub>??</sub>(??<sub>??</sub>) = ??<sup>′</sup><sub>??</sub>;

2. each ??<sub>??</sub> with ?? > ?? yields at ??<sup>′</sup><sub>??−1</sub> the same inverse ??<sub>??</sub> it yields at ??<sub>??−1</sub>.

Proof.

1. The first equation is an induction on ??. At ?? = ?? it reads ??<sub>??</sub> = ??<sub>??</sub>(??<sub>??−1</sub>), which is the definition of ?? . For the inductive step, ?? = ?? (?? ) = ?? (?? (??<sup>′</sup> )) = ?? (?? (??<sup>′</sup> )) = ??<sub>??</sub>(??<sup>′</sup><sub>??+1</sub>), the middle equality being clause (1) of Definition 19 for ??<sub>??+1</sub> and ??<sub>??</sub>, which are distinct efects of the family since ?? + 1 > ??. For the second equation, clause (1) carries ??<sub>??</sub> out through the forward maps applied after ??<sub>??</sub>, leaving the witness of ??<sub>??</sub> to be used at the one state it holds at:

![](images/abbbe8f94aeb6b2ea72729725e3ab62c06565a12705af2bcbe3ae34d5039b276.jpg)

the last equality resting on ??<sub>??</sub>(??<sub>??</sub>(??<sub>??−1</sub>)) = ??<sub>??−1</sub>, which is the witness Definition 8 requires of ??<sub>??</sub> at ??<sub>??−1</sub>.

2. By (1) the state ?? is ?? (??<sup>′</sup> ), and ?? ∈ ??(?? ), so clause (2) of Definition 19 for ?? and ??<sub>??</sub> gives pr<sub>2</sub>(??<sub>??</sub>(??<sub>??</sub>(??<sup>′</sup><sub>??−1</sub>))) = pr<sub>2</sub>(??<sub>??</sub>(??<sup>′</sup><sub>??−1</sub>)). □

Clause (1) locates the state an inverse reaches: it is the state the same sequence would have reached had the efect never been applied, whatever efects were applied after it. Clause (2) locates the inverses the others hold there, and together the two let the theorem be applied again to the shorter sequence:

Corollary 21. Let ?? , ⋯, ?? ∈ ??<sup>∗</sup> be pairwise independent and applied in order from ?? , and let ??<sub>1</sub>, ⋯, ??<sub>??</sub> be as above. Applying the ?? inverses at ??<sub>??</sub> in the order of any permutation of {1, ⋯, ??} reaches ??<sub>0</sub>.

Proof. By downward induction on ??. Let the permutation begin with ??. By Theorem 20(1) applying ??<sub>??</sub> at ??<sub>??</sub> reaches ??<sup>′</sup><sub>??</sub>, the state the sequence with ??<sub>??</sub> omitted reaches, and by Theorem 20(2) the inverses the remaining efects yielded there are the ??<sub>??</sub> in hand. That sequence is pairwise independent, being a subfamily, so the induction hypothesis applies to it and to the rest of the permutation; the empty sequence reaches ??<sub>0</sub>. □

LIFO order is one such permutation, and Theorem 16 reverts in it with no hypothesis at all. What independence buys is every other order, and with it the sequence that interleaves several components, which Section 4.4.2 carries to a trace of a whole system.

Together, these constructions constitute revertible efects: each efect function in ??<sup>∗</sup> explicitly provides its own inverse, effect tracks these inverses on the efect context ??Γ, and the ⋄ operation composes them while preserving revertibility. What they deliver is local temporal composability, local in that the guarantee is read of one component’s efects taken by themselves. We take that to be the following criterion: for every sequence of efect functions a component applies, the accumulator recovers the context it began at (Theorem 7), and reverting the sequence hands each inverse the state its own application ran against (Theorem 16). Loading a component is applying such a sequence and accumulating its inverses in ??; unloading it is applying ??.

Two things the criterion leaves out, and both arrive once several components are in play: reverting out of the order the accumulator imposes, and a sequence that interleaves the efects of others. Independence delivers them (Corollary  21), and it is a condition on the efects rather than a property of the construction, Section 3.3.2 being where the discipline that meets it is identified and Section 4.4.2 where the guarantee is read of a whole system’s trace. Where independence fails, the order has to be carried elsewhere: within one component by the accumulator, which reverts in LIFO order whatever the efects (Section 4.3.2), and across components by a declared coefect, which orders one activation against another (Section 4.3.1).

## 3.2. Reactive Coefects

Spatial composability is the ability for components to declare dependencies on one another and for the system to resolve, provide, and withdraw those dependencies at runtime. This requires that dependency satisfaction be re-evaluated whenever the shared context changes, so that a component activates when its dependencies become available and deactivates when they are withdrawn. We therefore model dependencies of a component as a specification and classify each change to the context, against that specification, as activating, deactivating, or neutral. Classifying against the specification is what detects a change in satisfaction; responding to that classification is what drives activation and deactivation. We call such coefects reactive: by classifying context changes and driving activation and deactivation from them, correct coefect ordering becomes a structural guarantee.

## 3.2.1. Coefect Context

Traditional inversion-of-control (IoC) containers [38] typically model dependencies as simple key-value mappings. This section formalizes IoC as a coefect context that synergizes with revertible efects to provide a mathematical foundation for dynamic composition.

Definition 22. Given a type family ??︀ : ?? → Type, define the coefect context as the dependent partial function type:

![](images/10b5b2d58711ff7428ed7078c77a41bee08fcc7d3991fa92e97cc3a8b71e02f9.jpg)

(20)

where ?? : Σ is a finite partial function assigning to each ?? ∈ dom(??) ⊆ ?? a value of type ??︀ . We write:

• ??(??) for application (defined when ?? ∈ dom(??));

• ??[?? ↦ ??] for the table binding ?? at ?? and agreeing with ?? elsewhere;

• ?? ∖ ?? for restriction (defined when ?? ∈ dom(??));

• ?? ∈ dom(??) for membership.

The use of a type family ??︀ ensures that each dependency key ?? is associated with a specific value type ??︀<sub>??</sub>, providing static type safety for dependency access. Extension and restriction carry preconditions, imposed by the operations below: a dependency cannot be provided twice (?? ∉ dom(??) for extension) nor revoked if absent (?? ∈ dom(??) for restriction). A violated precondition is signalled as an error and produces no transition, so the efect algebra, which describes the transitions that do occur, applies to these operations unchanged. A reader prefer ring to internalize the failure may read every Σ ⇀ Σ below as Σ → ??????????(Σ) and compose in the ?????????? monad (Section 2.1), at the cost of replacing each identity by the partial identity on the operation’s domain. Based on this context structure, we define two core operations:

Definition 23. The get and set operations on Σ are defined as:

![](images/110c70bdcd855fe01a7dc54c39f7be64177e8397ca9ff629c5ed80924ca5b28d.jpg)

(21)

where get(??) requires ?? ∈ dom(??) and set(??, ??) requires ?? ∉ dom(??) as preconditions.

Notably, set(??, ??) has type ??<sup>∗</sup> , precisely an efect function on the coefect context. We can therefore directly apply the efect machinery from Section  3.1: effect<sub>Σ</sub> provides automatic tracking and recovery of dependency registrations. This is the synergy between reactive coeffects and revertible efects: coefect operations are efects, and efects are revertible.

What get hands a component is a value, and what the component can do with that value is whatever the coefect at that key provides. A key therefore carries more than a value type:

Definition 24. A coefect at a key ?? is a triple (??︀<sub>??</sub>, ≃, ??︀<sub>??</sub>), where ??︀<sub>??</sub> is the value type of Definition 22, ≃ is an equivalence relation on ??︀<sub>??</sub> up to which values at ?? are compared (Section 3.3.2), and ??︀<sub>??</sub> is a set of coefect operations, the operations the value bound at ?? provides to a component holding it. An operation ?? ∈ ??︀<sub>??</sub> carries an argument type ??<sub>??</sub> and an outcome type ??<sub>??</sub>, and acts on the value alone:

![](images/8f09fa28aeb4e91c07bc7c330629fe639ef1b7c4edfe70aff5daffc602c0c277.jpg)

(22)

its first two constituents forming an efect function on ??︀ witnessed as Definition 8 requires,   
and its third an outcome. Each operation is required to respect ≃: at ≃-related values it is defined ?? ??   
at both or at neither, and where defined it yields ≃-related successors, inverses that again carry ??   
≃-related values to ≃-related values, and equal outcomes. An operation acts on the coefect   
?? ??   
context through its lift

![](images/dd7b3f257fdb20c88d18158710f4f713fd8ed763c5f872203a7bbe34bd104fa1.jpg)

(23)

defined when ?? ∈ dom(??), whose first two constituents are an efect function on Σ.

Typing an operation of ?? on ??︀ is what confines it to the binding at ??: the lift reads and writes that binding and leaves every other key as it stands, so no side condition is needed to say so. Where isolation is in force the binding it reaches is the one the realm resolves to (Definition 28), two keys sharing a realm sharing one binding. An operation whose behaviour turns on another key reads that key’s value into its argument ??<sub>??</sub>, and the reactive discipline of the next subsection is what holds the value fixed for as long as the component that read it runs (Theorem 63).

## 3.2.2. Specification and Notification

The preceding definitions describe how individual dependencies are registered and accessed. Accessing an absent dependency, however, is a runtime failure. A component should therefore activate only once all the dependencies it declares are present, rather than accessing them opti mistically and failing when one is missing. This raises two questions: whether a component’s declared dependencies are jointly satisfied, and how the system should respond when that status changes. The coefect context Σ carries a natural observational structure that makes both questions tractable: for any coefect specification ?? ⊆ ??, define the satisfaction predicate:

![](images/d6b4a2514341bd62ff7e4c6097692cc5a54e1482f5619b78b737bd4036b9d764.jpg)

(24)

This predicate is decidable (since dom(??) is finite). Since all mutations to ?? pass through efect functions (whose inverses recover the previous domain), changes to satisfaction are detectable at each efect boundary. This is the algebraic basis of reactivity: the efect system guarantees that every coefect change is observed.

Definition 25. A coefect specification is:

![](images/bca985eacfd5ee2ba6655f5d18c1d0eab55896acf99c59193ec103d3b3779ccc.jpg)

(25)

representing the set of dependencies a component declares from the environment.

What makes this specification reactive is how it classifies state transitions. Any efect that transforms ?? to ??<sup>′</sup> can be classified by a specification ?? ∈ ??<sub>Σ</sub> according to whether ??’s satisfaction status is altered:

Definition 26. Given a coefect specification ?? ⊆ ?? and states ??, ??<sup>′</sup> ∈ Σ, define:

![](images/26a56363532068f6531e1d2ea96411ebdc4949f7d23945982692c1a2b8cfeae2.jpg)

(26)

This is well-defined because ?? ⊧ ?? is decidable and all state transitions are mediated by efect functions. The reactive invariant is: an activating transition triggers execution of the component’s efects (with full efect tracking), whereas a deactivating transition triggers recovery by applying the accumulator. The precise operational semantics of these transitions depend on their interaction with control flows, and are developed in Section 4.

What set and notify deliver together is local spatial composability, local in the same sense as before, the guarantee being read of one component’s coefects taken by themselves. We take that to be the following criterion: a component activates only at a state satisfying its specification, so it never reads a binding that is absent, and every change to the context is classified against that specification, so a loss of satisfaction is detected where it happens and drives a deactivation. Both halves are immediate from the definitions above, satisfaction being a precondition checked where the component would activate and notify<sub>??</sub> being defined at every transition.

The criterion covers one direction of the coefect ordering and not the other. If component ?? provides a key ?? and component ?? declares ?? ∈ ?? , then ?? can activate only after ?? has activated and provided ??, since ?? ⊧ ??<sub>??</sub> requires ?? ∈ dom(??). The converse fails: unloading ?? removes ?? from dom(??) and so breaks ??’s satisfaction, but a notification cannot by itself keep ?? readable for as long as ??’s own teardown needs it, nor hold ??’s recovery back until ?? has finished. Ordering a withdrawal after the deactivations it causes is a condition on other components rather than on the one acting, so it belongs to the global form of the guarantee, and Section 4.3.1 supplies the machinery it takes.

## 3.2.3. Isolation and Interception

The basic coefect context Σ models a flat dependency table. In practice, however, the system may need to bind distinct values to the same logical dependency for diferent components. This section extends the coefect context with two mechanisms: coefect isolation (the same key resolves diferently in diferent contexts) and coefect interception (cross-cutting behavior on dependency access).

Realization. The two mechanisms difer from get and set in what they act on. A provision writes the shared table every component reads, so it is an efect on that table and carries an inverse to withdraw it. Isolation and interception instead adjust how a key is resolved for the components under one context, leaving the table itself as it stands. Typing an operation as an efect fixes its denotation, a successor state paired with an inverse, but not its realization, which determines how that inverse is carried out.

Definition 27. An efect function on a context admits two realizations:

• In-place realization mutates the context and returns a nontrivial inverse; the successor aliases the input, and recovery runs the inverse to undo the mutation.

• Derived realization leaves the input intact and returns a fresh context deriving from it, with the identity as its inverse; recovery discards the derived context. A context derived from another is what the recursive structure of Definition 32 carries.

In a purely functional setting the two coincide, and an imperative host may choose either per operation; Section 5.1.2 implements both. Isolation and interception are given derived realization outright: each produces a fresh context whose own table difers from the inherited one, so each is typed below as a map from context to context rather than as an efect function. Nothing in the shared table changes, so there is no inverse to track and nothing for Definition 12 to lift, and recovery discards the derived context along with the adjustment it carried. Assignment on a derived table overrides whatever the inherited table held at the key, which is why neither operation carries a precondition.

Coefect Isolation. By introducing isolation realms, coefect isolation allows the same dependency to bind to diferent values in diferent contexts. This has broad applications in multitenant systems, testing environments, and component sandboxes.

Definition 28. Define the coefect context with isolation as:

![](images/b33c27f0c254e2cd61cd5c9453863a6db22f1abe615810c84057539980cde946.jpg)

(27)

It can be represented as a pair (??, ??), where:

• ?? : ?? ⇀ ?? is the isolation realm table, assigning a realm identifier to each isolated key; a key outside dom(??) resolves to its own realm, so we write ??(??) = ?? there (?? ⊇ ??);

• ?? : (?? : ??) ⇀ ??︀<sub>??</sub> is the dependency table, a partial dependent function from realm identifiers to typed values.

The two-layer mapping structure decouples the logical layer from the storage layer, making dependency access context-aware. When accessing a key ??, the system first resolves ??(??) to obtain a realm identifier ??, then accesses ??(??) for the actual value.

Definition 29. The get, set, and isolate operations on Σ<sup>iso</sup> are:

![](images/c6395bd5bcc15cfc333a59a32b70c7e342ece2630bd41914c59e726af495368b.jpg)

(28)

where get and set carry the preconditions of Definition 23 transported along ??, namely ??(??) ∈ dom(??) and ??(??) ∉ dom(??). The context that isolate(??, ??) derives assigns the realm ?? to ?? and inherits the dependency table unchanged, so a key already isolated is reassigned rather than refused.

The coefect isolation mechanism essentially implements a runtime ad-hoc polymorphism system. Through isolation realm identifiers, the same dependency key can resolve to entirely diferent values in diferent contexts, and this polymorphism can be dynamically adjusted at runtime. Compared to traditional dependency injection, coefect isolation provides finergrained control, enabling customized isolation for specific components; set remains an efect function (??<sup>∗</sup> iso) and thus inherits revertibility, whereas isolate needs none, deriving a context instead of writing the shared table.

Coefect Interception. The second mechanism, coefect interception, attaches cross-cutting metadata to dependency access, adding behavior without modifying the dependency value. This metadata can be either context-carried or component-declared, so we extend both the coefect context and the coefect specification:

Definition 30. Define the coefect context and specification with interception as:

![](images/b090d78f741c869dc083a02ac4251c9deadeac8a464b2dcfcc417cbf6be9cced.jpg)

(29)

The context Σ<sup>inter</sup> is a pair (??, ??): ?? is the context-carried metadata installed on the context itself, empty (?? ) by default; and ?? maps each key ?? to a provider function from metadata ℳ︀ to value ??︀<sub>??</sub>. A specification ?? ∈ ??<sup>inter</sup> carries the component-declared metadata, assigning each key its metadata ??(??), with dom(??) serving as the dependency set. Each key equips its metadata with a monoid (ℳ︀<sub>??</sub>, ⊕<sub>??</sub>, ??<sub>??</sub>): the merge ⊕<sub>??</sub> is associative with identity ??<sub>??</sub> (the empty metadata).

Definition 31. The get, set, and intercept operations on Σ<sup>inter</sup> are:

![](images/23798f6f71b8050b80cd9d4948c98514722ec1dacac0bb852105ccc19df1c8a9.jpg)

(30)

where get and set carry the preconditions of Definition 23 on the provider table, namely ?? ∈ dom(??) and ?? ∉ dom(??). The context that intercept(??, ??) derives merges ?? onto the metadata inherited at ?? and inherits the provider table unchanged.

When a component with specification ?? accesses key ??, the system evaluates ??(??)(??(??) ⊕<sub>??</sub> ??(??)): the component-declared metadata is merged with the context-carried metadata ??, and the provider function is applied to the result. This merge follows each key’s own semantics (e.g. scalar fields are overwritten, set-valued fields unioned) and is right-biased, so ??(??) takes priority and can override the component’s declaration, letting an enclosing context constrain how a component uses a coefect without modifying that component (e.g. Section 6.3).

## 3.3. The Context Paradigm

Section 3.1 and Section 3.2 each act on a context, the first as the carrier of efects and the second as the carrier of coefects, leaving open what a single context carrying both looks like. This section gives that unification a concrete construction, assembles from the coefects an observa tional equivalence that supplies the efect independence Section 3.1.3 leaves open, and argues that the resulting context type constitutes a programming paradigm in its own right.

## 3.3.1. Unified Context

For a context Γ, the efect context ??Γ (Section 3.1) provides a higher-level abstraction, carrying the previous-level context and that level’s accumulator (Definition 2). Making this structure recursive and combining it with the coefect context Σ yields the following type:

Definition 32. The context type Γ<sub>∞</sub> is defined as:

![](images/f266241f402ed8f74d541bdd099293438dec89d02803d83ee3492eb225c6341f.jpg)

(31)

where the three projections are:

• Γ: the current context state (recursive);

• Γ → Γ: the accumulator, which recovers this level’s efects;

• Σ: the coefect context carrying dependency information.

Under this definition, effect maps ??<sub>Γ</sub> to itself, unifying the ??-tower into a single selfsimilar type. The coefect context Σ is structurally integrated: dependency operations (set, get) act on Σ, and the accumulator tracks their reversal. Since the type family ??︀ underlying Σ is unconstrained, any state the system needs to share across components can be encoded as a dependency with an appropriate value type—Σ subsumes all shared mutable states, not just inter-component dependencies. Every interaction between a component and its environment passes through this single entity.

Hierarchical composition. The recursive structure of Γ<sub>∞</sub> supports hierarchical control: a parent context aggregates multiple child-level efects, forming a tree-shaped control structure that maintains modularity while enabling unified cross-level management. The effect transformation realizes a literal “plug-in” metaphor:

• Loading a component corresponds to executing its efects (plugging in);

• Unloading a component corresponds to recovering its efects (unplugging, without afecting other running components);

• Components at diferent levels of the hierarchy are independently loadable and unloadable; a parent context aggregates and manages the efects of all its children, enabling arbitrarily nested composition.

## 3.3.2. Observational Equivalence

The recovery guarantee of Section 3.1 asserts an equality of states (Theorem 7), which is an idealization, because the physical state cannot be recovered as it stood. For example, free releases a block to the allocator without restoring the layout the heap had before malloc; and a generative name is not restored by the inverse that discards it, since the next creation draws a fresh one [39]. The equalities of Section 3 are therefore to be read up to an equivalence ≃, and we take ≃ to be an observational equivalence: two states are related when no observer can distinguish them. Comparing behaviour rather than representation is the established route to program equivalence [40], and the relation such a comparison yields depends on what the observer is given to work with [41]. What an observer of a context is given is the coefects it carries, each of which arrives with an equivalence of its own (Definition 24), so the relation on a context is assembled from theirs. Assembling it is the business of this subsection, and quotienting by it is what buys the independence Section 3.1.3 asks for.

Definition 33. Two coefect contexts are related when they bind the same keys to related values, and two states of a context when their coefect projections are:

![](images/449d46c822cc3b5f66cb2e3049d54819d506e810fa22dfc1c2b8e818564a4885.jpg)

(32)

writing ??<sub>??</sub> for the coefect projection of ?? (Definition 32).

The part of a state that no key binds is thereby forgotten, and forgetting it is what lets Theorem 7 be read up to ≃ at all: the heap layout and the generative name of the examples above lie outside the relation unless some key binds them. What Section  3.2.2 needs of ≃ follows rather than being assumed. Related states have the same domain, so they agree on the satisfaction predicate ?? ⊧ ?? and on the classification notify<sub>??</sub> of Definition 26, and reactivity is a property of Σ/ ≃.

Calling the relation observational is a claim about each ≃, namely that it separates no more than the operations of ?? can tell apart. An observer of a value runs those operations and reads their outcomes.

Definition 34. Let ?? carry a set ??︀ of operations in the sense of Definition 24, and write ??(??) for the transformation monoid (Definition 17) of the efect functions ??(??) over every argument ?? : ?? . A test over ??︀ is a finite word over the generators of the monoids ??(??), ?? ∈ ??︀, each letter applied to the value the letters before it left; its outcomes are those the letters that are forward maps of operations yield along the way, and it is undefined where a precondition fails. Values ??, ??<sup>′</sup> : ?? are indistinguishable, written ?? ≈ ??<sup>′</sup>, when every test over ??︀ is defined at both or at ??︀   
neither and yields the same outcomes at both.

Lemma 35. Indistinguishability is the coarsest relation the operations respect. That is,

1. every operation of ??︀ respects ≈ in the sense of Definition 24;

2. every equivalence that every operation of ??︀ respects is contained in ≈. ??︀ Every admissible choice of ≃ is therefore contained in ≈ , and ≈ is itself admissible. ?? ??︀<sub>??</sub> ??︀<sub>??</sub>

Proof.

1. Let ?? ≈ ??<sup>′</sup> and let ?? ∈ ??︀ be applied to an argument. Prefixing a test by one letter is again ??︀ a test, so the values the forward map reaches are indistinguishable, as are the values any one yielded inverse reaches from indistinguishable arguments; the one-letter test gives definedness at both or neither and equality of the outcome.

2. Let ?? be such an equivalence and ??????<sup>′</sup>. Each letter of a test is a forward map or a yielded inverse of an operation, and respect carries ?? along either, keeping the values reached related and the outcomes equal at every letter. Hence every test agrees at ?? and ??<sup>′</sup>. □

Substituting ≃ for = throughout is not by itself enough, because an efect function returns an inverse as well as a state, and two states that ≃ identifies have to yield inverses ≃ identifies as well.

Definition 36. A map ?? : Γ → Γ respects ≃ when

![](images/a943586f372395c2b2a3d44b4b4fb428b6e92d64b28977223bb7746eda228fa6.jpg)

(33)

Two maps are related when they agree at every state, and two pairs in ??Γ when both components are:

![](images/27d043a5da9a2e7e1fea158c43a658722e63fd3de9f480c0fda6191cfdf454c6.jpg)

(34)

A map respecting ≃ is one that descends to Γ/ ≃, and two maps related by ≃ are two that descend to the same map there. An efect function needs both: the first so that the state it computes is determined on the quotient, the second so that the inverse it returns is.

Definition 37. Read Definition 8 up to ≃: an ?? ∈ ?? lies in ??<sup>∗</sup> when ?? respects ≃ as a map Γ → ??Γ and, writing (??, ??) = ??(??), for every ?? ∈ Γ

1. ??(??) ≃ ??;

2. ?? respects ≃.

Taking ≃ to be equality on Γ recovers Definition 8.

Lemma 38. With ??<sup>∗</sup> read as in Definition 37, every equality of states asserted in Section 3.1 holds with = replaced by ≃, and the accumulator of every state reachable from (??<sub>0</sub>, id<sub>Γ</sub>) respects ≃.

Proof. An accumulator is a composition of inverses, each respecting ≃ by Definition 37(2), and a composition of maps respecting ≃ respects ≃, the base case being id . The proofs of Section 3.1 then go through unchanged, respect being what carries a relation through an inverse: from ??<sub>2</sub>(??<sub>2</sub>) ≃ ??<sub>1</sub> and ??<sub>1</sub>(??<sub>1</sub>) ≃ ?? respect gives (??<sub>1</sub> ∘ ??<sub>2</sub>)(??<sub>2</sub>) ≃ ??, which is the step each composition of inverses takes, and the soundness invariant of Theorem 7 reads ??(??) ≃ ??<sub>0</sub> by that step. □

The commutation Definition 19 asks for is read up to ≃ by the same lemma, and reading it that way is what makes it attainable at all: two operations may leave values that ≃ identifies and ?? still count as commuting. Of two operations it asks one thing more than of the efect functions their lifts induce, an operation yielding an outcome as well.

Definition 39. Operations ?? and ??<sup>′</sup> are independent when their lifts are independent as efect functions (Definition 19) at every pair of arguments, and neither one’s transformations disturb the outcome the other yields:

![](images/889a5d8ad59afe563c58b4e688197661c50cd9447b4e750cce4f79d1a38154bf.jpg)

(35)

and the same with ?? and ??<sup>′</sup> exchanged, writing ??(??<sup>Σ</sup>) for the transformation monoid of the lifts ??<sup>Σ</sup>(??) over every argument as Definition 34 writes ??(??) for that of the operation itself. A key ?? is commutative when any two operations of ??︀<sub>??</sub> are independent, an operation being held independent of itself as well.

Across distinct keys the condition holds outright.

Theorem 40. Operations at distinct keys are independent.

Proof. Let ?? lie in ??︀ and ??<sup>′</sup> in ??︀ ′ with ?? ≠ ??<sup>′</sup>. By Definition 24 every generator of ??(??<sup>Σ</sup>) is of the form ?? ↦ ??[?? ↦ ??(??(??))] for a map ?? on ??︀<sub>??</sub>, being either the lift of a forward map or the lift of a yielded inverse, and likewise for ??<sup>′</sup> at ??<sup>′</sup>. Two such maps commute, each reading and writing one key alone and the two keys difering, and Lemma 18(1) extends the commutation from the generators to the two monoids. For the second condition, what ??<sup>Σ</sup> yields at ??, inverse and outcome alike, is determined by ??(??), which every generator of ??(??<sup>′Σ</sup>) leaves as it stands.□

A key whose value is a table of entries added and removed independently is commutative, registration of a route or of an event listener being the representative case: two registrations in either order leave a table that answers every test alike, and either registration can be withdrawn while the other stands. A key whose value is an ordered chain is not, since a middleware inserted before another sees a diferent request, and neither order can be withdrawn without disturbing the other. The allocator of the opening example divides by what its interface publishes. Where the handles it hands out are compared by no operation of the key, ≃ may relate ?? two heaps up to a renaming of handles, which is how CompCert relates the memory states of a program and of its translation [42], and allocation is commutative; where the addresses are outcomes compared by equality, no admissible ≃ makes the two orders of allocation agree, and ?? the key is not commutative.

What a component performs is a sequence of operations in which each may depend on what the ones before it yielded, and efect functions of that shape are what the theorem below speaks of.

Definition 41. The coefect-mediated efect functions form the least set ??<sup>??︀</sup> ⊆ ??<sub>Σ</sub> that contains the unit ??<sub>Σ</sub> and is closed under the following: for a key ??, an operation ?? ∈ ??︀<sub>??</sub>, an argument ?? : ??<sub>??</sub>, and a family (??<sub>??</sub>) of members,

![](images/2420fff841f96c463d98e52e50c1f96c435e9c7fb5a91a85e63061727a880d2c.jpg)

(36)

is again a member. Each stage performs one operation and chooses what follows it by the outcome, so an argument may depend on the outcomes already obtained. The operations occurring in a member are the ones its stages perform, over every choice of outcome.

Theorem 42. Let ??<sub>1</sub>, ??<sub>2</sub> ∈ ??<sup>??︀</sup><sub>Σ</sub> and let every key at which operations of both occur be commutative (Definition 39). Then ??<sub>1</sub> and ??<sub>2</sub> are independent (Definition 19).

Proof. By induction on the construction of Definition 41, ??(?? ) lies in the submonoid generated by the generators of the operations occurring in ?? : the unit generates the trivial monoid, and a stage is a ⋄-composite of ??<sup>Σ</sup>(??) with a member, to which Lemma 18(2) applies.

For clause (1) of Definition 19 it is therefore enough, by Lemma 18(1), that a generator of an operation occurring in ??<sub>1</sub> commute with a generator of one occurring in ??<sub>2</sub>. Where the two operations lie at distinct keys this is Theorem 40, and where they lie at one key that key carries operations of both and is commutative by hypothesis.

For clause (2), take ?? ∈ ??(??<sub>2</sub>), a composite of generators of the operations occurring in ??<sub>2</sub>, and induct on the construction of ??<sub>1</sub>. The unit yields id<sub>Σ</sub> at every state. At a stage, let (??, ??, ??) = ??<sup>Σ</sup>(??)(??) and (??, ??) = ?? (??), so that the stage yields ?? ∘ ?? at ??. Independence of the operations, applied to one generator of ?? at a time, yields ?? and ?? again at ??(??), so the same continuation ??<sub>??</sub> is chosen, and clause (1) puts the state it runs from at ??(??), where the induction hypothesis yields ?? again. The stage therefore yields ?? ∘ ?? at ??(??). □

Every interaction between a component and its environment passes through the context, and the type family ??︀ is unconstrained, so a system may bind every location it shares across components at a key of its own (Section 3.3.1). A component’s efect function is then the lift of a coefect-mediated one along the coefect projection, and independence transfers to that lift, whose transformations move the projection alone. The assumption Section 3.1.3 leaves open is met that way, and with it the temporal composability of a whole system of components.

What the decomposition divides is a computation’s commuting part from its order-sensitive part. The commuting part is carried by the efects: a component performs them in whatever order its task calls for, and Corollary 21 reverts them in whatever order the system finds conve nient, no two components constraining each other. The order-sensitive part is carried by the coefects, since a key whose operations do not commute is one whose order has to be imposed from outside the efects, and two places are available for imposing it. Within one component the accumulator imposes it, reverting in LIFO order whatever the efects (Theorem 16). Across components a declared coefect imposes it, one component providing what another declares and the provision preceding the declaration’s satisfaction (Section  3.2.2). Composability is thereby had at the grain of components rather than of single efects, which is the scale Section 4 works at.

Two limits of the theorem are worth naming. Binding every shared location at a key is the paradigm’s discipline and not a property of the construction, so a location the system cannot reify as a coefect lies outside the boundary of Section 6.1 and outside the theorem with it. And commutativity of a key is a property of the interface that key publishes, so meeting it is an obligation on the component providing the key rather than on the components consuming it.

## 3.3.3. Situating the Context Paradigm

Programming paradigms difer fundamentally in how they handle side efects. Two established poles define the spectrum:

Explicit state threading (functional). To preserve referential transparency, purely functional languages model side efects as explicit transformations on state. The State monad ?? → (??, ??) [23] threads an environment through every computation. This approach yields strong compositional guarantees: efects are visible in types and amenable to equational reasoning. However, it imposes significant ergonomic costs: every function in the call chain must accept and return the state parameter, even when it merely passes the state through unchanged. As the number of efect dimensions grows (logging, configuration, I/O), monadic stacking or efecthandler boilerplate proliferates.

Implicit mutation (imperative/OOP). Mainstream imperative languages permit components to modify shared state and access dependencies without explicit declaration at the call site. On the efect side, a representative example is React’s useEffect hook: it registers a persistent side efect on the component’s internal fiber, yet neither the efect target nor the regis tration mechanism appears as an explicit parameter—identification relies on call-order position within hidden runtime state. On the coefect side, Java’s service locator pattern (e.g., Spring’s ApplicationContext.getBean(...)) retrieves dependencies from a process-wide registry at runtime, requiring null checks and type casts at each call site; dependency relationships are implicit and scattered across the codebase. More generally, understanding how f() modifies or depends on the system requires reading its implementation transitively. Refactoring becomes fragile because moving or removing a call may silently break distant invariants.

The context paradigm combines the traceability of the functional approach with the ergonomics of the imperative approach. Efects and coefects are both mediated through an explicit context parameter. Each operation is therefore attributable to the specific context on which it was invoked, and hence to the component that context belongs to.

Beyond combining the strengths of both poles, the context paradigm lets the developer handle each efect and dependency individually and composes them into the system’s behavior automatically. For revertible efects, the developer supplies the inverse of each atomic operation, and the inverse of any composite follows by composition (Section 3.1), so a component’s teardown is derived from its loading rather than written alongside it. For reactive coefects, a component declares only the dependencies it needs, and the runtime resolves and re-wires them automatically (Section  3.2), keeping them consistently wired as providers are added, removed, or replaced. In both directions, correctness that would otherwise rest on developer discipline becomes a structural property of the paradigm.

## 4. A Calculus of Dynamic Composition

Section 3 establishes spatial and temporal composability in their local form alone. Carrying them to a whole system takes a decomposition of the system into components, each pairing a coefect specification with a witnessed efect function, so that every interaction with the shared environment is attributable to one of them. The sections below give that decomposition an operational semantics, and establishes spatial and temporal composability in their global form.

Section 4.1 and Section 4.2 present the smallest calculus in which the lifecycle can be given rules, one that takes each transition to be atomic, immediate, and infallible; Section 4.3 drops the three assumptions, atomicity once for each direction a transition may run in, admitting the forms of control flow a runtime interposes between the start of a transition and its end, and arrives at the calculus a real runtime implements; and Section 4.4 establishes the metatheory of that calculus, namely preservation, global temporal and spatial composability, progress, and confluence.

## 4.1. Components and Fibers

This section fixes the objects the rules act on: the component; the fiber, an instantiation of a component carrying a lifecycle state of its own; and the registry, which holds the fibers a state carries and from which the coefect context is read of.

Components. A component is given as a triple, its coefect side split into what it reads from the environment and what it provides to it.

Definition 43. A component over a context Γ carrying both efects and coefects (Definition 32) is defined as:

![](images/bc04aa210b11532d3de4b68cd8cad375f2e41ffa77a63f27ff363059337e5683.jpg)

(37)

representing a triple (??, ??, ??), where:

• ?? : ??<sub>Γ</sub> is the coefect specification of Definition 25, declaring the dependencies required from the environment;

• ?? : ??<sub>Γ</sub> ≔ ??????(??) is the provision, declaring the coefect keys the component may provide, and no key outside ?? is one its efect function writes;

• ?? : ??<sup>∗</sup> is the witnessed efect function of Definition  8, defining the efects contributed when the component is active together with the inverse that withdraws them.

The two declarations are the two directions of one interface, ?? what the component reads from the environment and ?? what the component writes to the environment, and Section 4.2 admits no two fibers of one registry whose provisions meet. Subscripts are taken on Γ throughout, the coefect context being one of its projections (Definition 32), so the ??<sub>Σ</sub> of Definition 25 is written ??<sub>Γ</sub> here.

Disjointness of provisions is where this chapter parts company with Section  3.2.3. The isolation of Definition 28 lets one key resolve through a realm table, so that two fibers may provide the same key in diferent realms; a calculus carrying realms would relax disjointness to disjointness within a realm and would resolve a declared key against the realm of the fiber declaring it. We do not introduce realms here, and read every key at one shared realm instead, which is what makes the disjointness above the right condition and each key’s provider unique (Definition 45). What it restricts is how often a component may be instantiated: one with a nonempty provision has one fiber at a time, so the many instantiations below are of components providing nothing, which is the common case of a component that only consumes, or that registers others.

A component instantiated in a running system is activated and deactivated over time, so it carries a lifecycle state, and a transition is what moves it from one lifecycle state to another: an activation executes ??, accumulating side efects on the context, and a deactivation applies the accumulator to recover the context. In its simplest form the lifecycle is the two-state model of Figure 1, which Section 4.2 gives rules for; Section 4.3 refines it as each control-flow feature is admitted.

![](images/77136120907e3c87bfeba2f1bd180e6458755014c41db379bfbb21f498366ea1.jpg)  
Figure 1 | Base component lifecycle

Fibers. One component may be instantiated many times over, each instantiation carrying a lifecycle state of its own. We name such an instantiation a fiber. A fiber records the component that produced it, the fiber it was instantiated under, the coefects it provides, and where in its lifecycle it stands.

Definition 44. Fix a set ?? of fiber names. A fiber instantiating the component (??, ??, ??) ∈ ℭ<sub>Γ</sub> is a tuple ⟨??, ??, ??, ??, ??, ??, ??⟩, where

• ?? : ??<sub>Γ</sub>, ?? : ??<sub>Γ</sub>, and ?? : ??<sup>∗</sup><sub>Γ</sub> are the coefect specification, provision, and efect function of Definition 43;

• ?? : ?? ∪ {????????} is the parent, the fiber this one was instantiated under, or the root marker ????????;

• ?? : Σ is the fiber’s own coefect table (Definition 22), empty until it activates and written by its efects as they run;

• ?? : {⊥, ⊤} is the retirement flag, ⊥ in a fresh fiber and ⊤ once the orchestrator has retired the fiber;

• ?? : Θ is the lifecycle state, which in the two-state model of Section 4.2 is

![](images/0827919e067a5e4028dcd1ab32d3b37cae45e539dd5d142de277d537d0194284.jpg)

(38)

where ?? : Γ → Γ is the accumulator and ?? : ?? → ?? the committed view.

The committed view ?? sends each key the fiber declares to the name of the fiber that provided it when the transition committed. Section  4.3 replaces Θ<sub>Γ</sub> by the extension that transitions in progress require; the rest of Definition 44 is given once for both, save that ?? is read at the richer efect type each layer of Section 4.3 introduces.

Registry. A state holds its fibers under their names, and both the identity of a fiber and the coefect context of Section 3.2 are read of that arrangement.

Definition 45. Write ?? for the set of fibers over Γ. A state ?? ∈ Γ carries a registry

![](images/55a7081a83915675ebfe47d4296455328866c9d1f92569d03ed65fb61caf93da.jpg)

(39)

a finite partial function whose parent pointers form a tree rooted at ????????, together with whatever else in Γ no fiber’s ?? names. We write ??(??) for ??<sub>??</sub>(??), and abbreviate a field of ??(??) by subscripting it with ?? where the state is clear, so that ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub> are the fields of Definition 44 and ??<sub>??</sub>, ??<sub>??</sub> the accumulator and committed view that ??<sub>??</sub> carries; ??[??<sub>??</sub> ↦ ??<sup>′</sup>], ??[?? ↦ ⟨⋯⟩], and ?? ∖ ?? are the states difering from ?? in one field, one fiber, and the presence of one fiber respectively.

A fiber’s name is what gives it an identity that survives its own mutation: every rule below rewrites the lifecycle state of one fiber and leaves the others alone, so the rule has to say which one, and two fields refer to fibers rather than describe them, the parent ?? and the committed view ??. Names are atoms: no rule computes one, inspects its structure, or relates two of them by anything but equality, and introducing a fiber simply draws one not already in use. This is the discipline of dynamically created local names [39], used here for fiber identity.

Each fiber owning a table means the coefect context is derived rather than stored: it is what the active fibers jointly provide.

![](images/9c6bb43830ac982f99c453943938e2ae0121c0b431c5886028659383c4be1b7e.jpg)

(40)

The union is well defined because a fiber writes only the keys it declares, dom(??<sub>??</sub>) ⊆ ??<sub>??</sub>, and the provisions of distinct fibers are disjoint (Definition 43), so each ?? ∈ dom(?? ) lies in the table of exactly one ???????????? fiber, whose name we write provider (??) ∈ ?? and call the provider of ??. Each key therefore has one possible provider, fixed by the provisions and not by the state. No rule writes ?? directly: a fiber’s provisions are the set operations its own efect function performs, which land in ??<sub>??</sub> and so are already part of the state ??<sub>??</sub> returns, and they leave again with the accumulator. Only the coefect part of an efect is recorded this way, because only the coefect part is what other fibers declare against; efects that mutate state elsewhere in ?? are tracked by ?? like any other, but no fiber can name them in a specification, so they contribute no ordering constraint.

The satisfaction relation of Section 3.2.2 then applies unchanged, with ?? ⊧ ?? abbreviating ??<sub>??</sub> ⊧ ??. A key lies in dom(??<sub>??</sub>) exactly when some ???????????? fiber has installed it, its provision being the keys it may install rather than the ones it has, so ?? ⊧ ?? already requires that every declared key have an ???????????? provider. Taking the union over ???????????? fibers alone is what lets a fiber cease to provide before it has withdrawn anything, which Section 4.3.1 turns into the ordering discipline.

## 4.2. The Base Calculus

This section gives the calculus of the two-state lifecycle of Figure 1 and nothing more: the target each fiber is compared against, and the five rules that move it.

Target views. The rules compare each fiber against a target, namely whether it ought to be running and against which resolution of its dependencies. The target is not a property of the fiber alone, since the keys a fiber declares are resolved against the whole state, so it is a predicate on that state.

Definition 46. The target view of ?? at ?? maps each declared key to its provider, so it is a total map ??<sub>??</sub> → ??, and is ⊥ when ?? ought not to be running at all:

![](images/57131f073c54028b666918a0849ffcfb5b13434e82fa21954e1ef4a70888251e.jpg)

(41)

A state is quiescent when every fiber has reached its target view:

![](images/95560d20dc5e5f6effe2ec35e0e61397522bbaf2bd17ec8fe68c737d3331aab3.jpg)

(42)

The target answers to two things and to nothing else: retirement, through ?? , and coefect resolution, through ?? ⊧ ??<sub>??</sub> and provider<sub>??</sub>, each declared key being read of ??<sub>??</sub> at the one shared realm of Definition 43.

The committed view of Definition 44 has the same type as the target view, and the lifecycle is driven by comparing them: ?? is the resolution ?? activated against, target (??) the one it should be running against, and every rule below fires on their agreeing or difering. Recording a provider rather than a value is what makes the comparison usable, since a diferent fiber providing an equal value would otherwise compare equal. The value a component reads is reached through the view, since the provider’s table holds that value, and the implementation holds the map in fiber.committed and a hash of it in fiber.target (Section 5.1.3).

Rules. The base calculus takes each transition to be atomic, immediate, and infallible: an activation applies its efect function in one step, a deactivation applies the accumulator in one step, and both succeed in doing so. Section 4.3 drops all three.

Five rules generate two relations. An orchestration rule, prefixed O- and written ?? ⇒ ??, is an action the orchestrator may perform; its premises say when the action is legal, not when it occurs. A lifecycle rule, prefixed L- and written ?? ⟶ ??, is a step the system takes unprompted whenever its premises hold. A sequence of steps interleaves the two, and ⟶ below means lifecycle steps alone.

![](images/62d30b0e41fcdb4c7d17a147a0a9186e9add072bc61db911b99529f429ab8654.jpg)

Insertion and retirement are the only external inputs: the orchestrator asks for a fiber to exist or to stop existing, and never sets its lifecycle state directly. O-Retire is unconditional on the fiber’s state because retiring is a request, and the lifecycle rules are what carry it out. Retirement is separated from removal for the same reason: a retired fiber that is still ???????????? must first be deactivated, and removing it earlier would discard the accumulator and leak. The premise ∀??. ??<sub>??</sub> ≠ ?? keeps the tree well-formed by removing children before their parent. The last premise of O-Insert is where the single-source discipline is imposed: a key has one possible provider because the orchestrator may not admit a second component declaring it.

![](images/6d899288e0b961639db2109649a331c85677627c9fa4dc68bc1846b502c751f8.jpg)

L-Reload installs the committed view alongside the inverse; L-Unload applies the inverse and discards the committed view. Both are driven by the same comparison: L-Reload fires when a fiber holds no committed view and its target view is not ⊥, L-Unload when the committed view it holds is not its target view. This is the reactive discipline of Section 3.2, read of a target that answers to retirement as well as to the coefects: a transition is initiated whenever the target view changes, regardless of which of the two moved it.

Instantiation. A component may instantiate another while installing its efects, which is what a plugin host does when a plugin loads plugins of its own. The rules so far leave the registry to the orchestration rules alone, so such an instantiation has nowhere to happen. One primitive gives it somewhere.

Definition 47. An application of ?? , or one of its iterations where Section 4.3.2 applies, may register a component (??, ??, ??) ∈ ℭ<sub>Γ</sub>. In place of a state map it takes the O-Insert of that component with ?? = ??, and it yields as its inverse the O-Retire of the fiber so registered. The rule draws the name, subject to the freshness premise of O-Insert, and hands it to the efect function.

The inverse retires rather than removes, and the reason is that an inverse has to apply wherever it is reached. O-Remove carries premises, so an inverse built from it can fail to: a parent whose child is still ???????????? could not run its accumulator, and no rule would move the child, since Definition 46 does not read the fiber tree. O-Retire has ?? ∈ dom(??<sub>??</sub>) as its only premise. The entry it leaves behind at the state the registration was taken is retired, ????????????????(⊥), and holds an empty table, which is the vestigial entry of Lemma 57: it difers from the absence of the fiber in control fields alone, and no rule tells the two apart.

Retiring a child sets ?? and so takes its target view to ⊥, after which the ordinary rules carry it back to ????????????????. The parent is not made to wait, O-Retire being unconditional, so L-Unload applies to the parent whether or not the child has left. A grandchild is reached one level at a time, the child’s own accumulator retiring what the child registered. Theorem 66 covers this cascade and the one Section 4.3.1 imposes along coefects together.

Confinement. With the one exception in hand, the discipline an efect function is held to can be given. It bounds what an application writes, so that the rule applying it accounts for every other change, and what an application reads, so that a fiber sees the coefects it declared and no more of the registry. Bounding the writes is what lets Section 4.4 read Table 1 as a complete inventory of them.

Definition 48. A map ?? : Γ → Γ is confined to ?? when for every ?? ∈ Γ with ?? ∈ dom(??<sub>??</sub>), writing ?? = ??(??),

1. (Writes.) dom(??<sub>??</sub>) = dom(??<sub>??</sub>), ??(??) = ??(??) for every ?? ∈ dom(??<sub>??</sub>) with ?? ≠ ??, and ??(??) and ??(??) difer in ?? alone;

2. (Reads.) two states agreeing on ??<sub>??</sub>, on the restrictions ??<sub>??</sub>|<sub>??</sub> for every ?? ∈ dom(??<sub>??</sub>), and on the part of the state that no fiber’s table names are carried by ?? to states agreeing on the same three.

An efect function ?? is confined to ?? when every application of it, and of each of its iterations where Section 4.3.2 applies, either registers a component (Definition 47) or has both its state map pr ∘ ?? and the inverse it yields confined to ??. Every fiber’s efect function is required to be confined to that fiber.

A registration writes the entry O-Insert writes, at the one name it draws, and nothing else; the O-Retire it yields as its inverse writes the ?? of that name and nothing else. An application of either kind therefore writes no control field of a fiber already present, save that one ??, and reads none at all.

Clause (2) is why a component may read the values it declared: those lie in the tables of its providers, so an efect function that reads no table but ?? would be unable to use its own coefects. What it may not read is a table outside ??<sub>??</sub>, or any control field, which is what keeps a component from branching on the lifecycle state of a fiber it did not declare.

The rules are nondeterministic: several fibers may hold a committed view difering from their target view, and the relation commits to no order among them. They are also reactive only, in that no rule mentions a scheduler; the steps are any sequence of rule applications, so a theorem proved over all such sequences holds for every scheduling policy a runtime might adopt.

## 4.3. Transitions in Progress

This section extends the base calculus in four settings. The first supplies something Section 3.2 requires and Section 4.2 cannot express, a deactivation spread over an interval its dependents may occupy; the other three drop the idealization that a transition is atomic, immediate, and infallible, none of which a transition in a real runtime is. What is dropped is that a whole transition is one step, not that a step is one application of one rule, and the four share one structural consequence, taken here once: a transition that is not a step needs a state to occupy while it is under way, one for each direction it may run in.

Definition 49. The lifecycle states of this section replace Θ<sub>Γ</sub> by

![](images/6579b411010807b81e389b2da910a7a9333889ea54f12560be260cadf91c6205.jpg)

(43)

where ?? : ??<sup>iter∗</sup> is the remaining efect iterator (Definition 51 below), ?? : Γ → Γ the accumulator built so far, ?? : ?? → ?? the committed view, and ?? : {⊥} ∪ Ξ the outcome, carried by ?????????????????? as the one its deactivation is headed for and by ???????????????? as the one it reached, either ⊥ or an error drawn from the set Ξ of errors that Section 4.3.4 supplies.

A fiber is installed when it is in one of the three states carrying an accumulator and a committed view, and failed when it carries an error outcome:

![](images/d099a0bc7495366946f293db69b75c67308e0e41a89f29d1522769d871ce29fd.jpg)

(44)

An installed fiber ?? resolves ?? to ?? when ??<sub>??</sub>(??) = ??. The quiescence of Definition 46 is read on the wider state space as

![](images/3dbaddfc4235d80a26d2e282c09fa85f7cadaa0bfa65c71d4878444b30d920a4.jpg)

(45)

The definitions of Section 4.1 carry over to this state space, with two readings to fix. First, the ???????????????? of Section 4.2 is read as ????????????????(⊥) in the conclusion of O-Insert and as ????????????????(−) in the premise of O-Remove. Second, ?? still unions the tables of ???????????? fibers alone, so a fiber whose transition is under way in either direction reads its coefects through the ?? it holds and provides none of its own; a key that its transition has already written is therefore not yet one a dependent may activate against. In the two-state calculus the distinction is empty, every installed fiber being ???????????? there.

Figure 2 draws the lifecycle these states form, and the four subsections below supply the rules on its edges.

![](images/89d8cf3f740258f00dcc460a09fe33e6cc022a0913605b9e8559a004d49c16ba.jpg)  
Figure 2 | Lifecycle with transitions in progress; the two transition states are outlined

## 4.3.1. Withdrawal

Section 3.2 requires that dependents activate after their dependencies and that dependencies withdraw their provisions only after their dependents have deactivated. The first half holds in the base calculus already: an activation requires ?? ⊧ ?? , so a fiber declaring ?? cannot activate before some fiber is actively providing ??. The second half is the substantive one, and it must deliver more than an ordering of state changes. A component being torn down because its provider is going away is running its own teardown code, which may need the very coefect that is being withdrawn; closing a connection pool typically means handing the connections back to whatever provided them. What the second half must deliver is that a consumer can still read ?? throughout its own deactivation, and that the provider’s withdrawal of ?? takes efect only afterwards. The base calculus cannot deliver it at all: its L-Unload removes the provisions and runs the inverse together, leaving no interval between them for a consumer’s teardown to occupy.

This layer splits that step in two, and guards the second half by the following condition.

Definition 50. The fiber ?? is relied upon at ?? when some other installed fiber resolves a key to it:

(46)

![](images/aecbc235ad055603e34c111c474b2a2d879c84c93c022659530322b5aed3e486.jpg)

L-Leave records the decision to deactivate without acting on it, which stops the fiber providing its coefects while leaving its own committed view and everyone else’s intact. L-Unload applies the accumulator, discards the committed view, and leaves the fiber ???????????????? on the outcome it carries; the outcome is ⊥ until Section 4.3.4 supplies the other case. It is the only rule in the calculus that applies an accumulator.

The two halves of the ordering are then carried by diferent parts of the form: the visibility half by the committed view, which L-Unload discards as its last act, and the ordering half by the premise ¬ relied (??), which we call the guard and which holds the withdrawal of ?? back until every consumer that resolves it to ?? has gone. Theorem 63 establishes both.

The guard is imposed per binding rather than per fiber: relied (??) tests whether some committed view names ??, so a fiber that declares none of ??’s keys is no obstacle, and neither is one that resolved a key of ??’s in another realm (Section  3.2.3). Under the single-source discipline of Section 4.2 the per-binding reading coincides with the coarser test ∃?? ≠ ??, ?? ∈ ?? . installed (??) ∧ ?? ∈ ?? , a key having one possible provider there.

A guard of this kind ordinarily deadlocks. What keeps it from doing so is ?????????????????? together with ?? being the union over ???????????? fibers alone: once L-Leave has marked ??, its table leaves ??<sub>??</sub>, so no target view can name ?? any longer, and every consumer that committed to ?? is itself on its way out. Theorem 66 turns that into the claim that the guard always releases.

The guard orders deactivations along coefects and not along the fiber tree: a parent may run its inverse while a child of it is still ??????????????????, since relied speaks only of committed views. Parent and child are accordingly ordered more weakly than Theorem 63 orders a provider and its consumer, and a parent and a child whose efects meet in the ambient state are governed by the independence hypothesis of Definition 60 instead.

## 4.3.2. Iteration

An activation may execute multiple efects in sequence, and the deactivation must recover them. We model such an activation with an efect iterator, each of whose iterations yields the modified context, an inverse, and a continuation:

Definition 51. Define the efect iterator ??<sup>iter</sup><sub>Γ</sub> and witnessed efect iterator ??<sup>iter∗</sup><sub>Γ</sub> as the following recursive types:

![](images/75cd4ba17fb21e6f18d0285909b3fe720c2bfa0fb7b3ebc756c47ab0e5443610.jpg)

(47)

where ??(??) yields a triple (??, ??, ??) representing:

• ?? is the new context;

• ?? is the inverse function of the current efect;

• ?? indicates the continuation:

‣ ?????????????? signals iteration termination;

‣ ????????(??) provides the next iteration.

The witness is read at the ≃ of Definition 33, as Definition 37 reads that of ??<sup>∗</sup> : an ?? ∈ ??<sup>iter</sup> lies in ??<sup>iter∗</sup> when ?? respects ≃ and each ?? it yields respects ≃ and satisfies the clause above. A triple is compared componentwise, ?????????????? with ?????????????? alone and ????????(??) with ????????(??<sup>′</sup>) when ?? ≃ ??<sup>′</sup>, and ≃ on iterators is the greatest relation meeting those clauses. Taking ≃ to be equality on Γ recovers the reading on the nose.

The efect iterator transformation effect<sup>iter</sup><sub>Γ</sub> extends effect<sub>Γ</sub> to the iterator structure through recursive invocation:

Definition 52. Define the efect iterator transformation effect<sup>iter</sup><sub>Γ</sub> as:

![](images/f4f18525383de34e657c886255adc7648b6185791bb1f86ef9531c41dc9f89ca.jpg)

(48)

At each iteration, the inverse ?? is composed onto ?? in application order, so the accumulator ?? ∘ ?? ∘ ⋯ ∘ ?? naturally recovers efects in LIFO order when applied. Because effect<sup>iter</sup> lands in the same ??Γ → ??<sup>2</sup>Γ as effect does, an iterator is an efect in its own right and can be used wherever an efect can. A component’s whole activation is one such use, which is what the rest of this section formalizes, and the implementation admits an iterator at every mutation site (Section 5.1.1). The ??????????(??<sup>iter</sup>) continuation makes a boundary available between any two consecutive iterations, at which the context is whatever the iterations so far have made it and the accumulator recovers those and nothing more. In this sense the efect iterator is a reified delimited continuation, the structure that mainstream languages expose through the yield operator [43], so the model maps directly onto the generators they already provide.

In the calculus, the ??<sub>??</sub> of Definition 44 is read at ??<sup>iter∗</sup><sub>Γ</sub> from here on, and replacing the atomic efect function by an iterator splits the base L-Reload into a begun state that the trace passes through, and gives the fiber a second way out of that state.

![](images/f39b2fefcf429375d66f97234bbe70e1841d7018b03215f00f10a5d15804b6fd.jpg)

Each iteration composes the newly yielded inverse onto the accumulator as ?? ∘ ℎ, following Definition 52, so that the accumulator applies the inverses in last-in-first-out order. Between any two consecutive iterations the system may divert the transition if its target view has changed, applying the inverse accumulated so far to recover the context. L-Divert routes through ?????????????????? like every other deactivation rather than applying the accumulator where it stands, and the guard it meets there is vacuous, a fiber that has never been ???????????? providing nothing and appearing in no committed view. The first of its two alternatives aborts the iteration the fiber is holding, which only an iteration boundary makes possible, so the granularity at which a divert may fall is that of the iterator; the second lets that iteration land, and Section 4.3.3 is where it is needed.

A plain efect function (??<sub>Γ</sub>) is the degenerate case where the first iteration already yields ??????????????. Such a transition still passes through ?????????????????? and L-Divert still applies there, but the accumulator is id and no iteration has run, so nothing is restored and the transition installs either all of its efects or none of them.

## 4.3.3. Asynchrony

The layers so far let the environment move between one iteration and the next, and assume that each iteration itself completes instantaneously, its launch and its landing being one step. We model non-immediacy abstractly: an iteration yields a value of type ????????????(??), where ???????????? is an opaque type constructor whose defining property is that between submission and resolution, external state may change.

Under this model an iteration is launched at one state and lands at another, and the fiber is ?????????????????? while it is in flight. What the layer adds is inertia: once launched, an iteration lands, and its landing cannot be declined. A target view that turns during the flight therefore cannot be answered by aborting the iteration, and only the alternative of L-Divert that lands one remains available: the iteration lands, and the fiber deactivates afterwards. This layer therefore adds no rule and no type that a rule matches on; at the granularity of Γ inertia is its whole content, and it takes the form of a restriction on which alternative of L-Divert a host may take.

That alternative is what the base calculus could not express. There, a transition whose target view had turned was undone in the same step that discovered it; here the iteration in flight must land first, so the fiber needs somewhere to be while its inverse runs, and the only sound place is ?????????????????? holding the inverse the iteration produced. Routing through ???????????? instead would let the fiber provide its coefects for the length of one step and oblige its dependents to activate against a component that is already leaving. This is the mutual chaining of reload and unload in the implementation.

A deactivation may also chain straight back into an activation, by a composite rather than a rule. L-Unload carries no premise on the target view, so whatever the target view has become while the fiber was deactivating, the accumulator runs and the fiber becomes ????????????????, from which L-Begin may immediately start a new transition.

## 4.3.4. Failure

Every rule so far assumes the efect it runs succeeds, and a runtime cannot. The efects a component installs reach outside the context that tracks them, and what they reach may refuse: a port already bound, a file that is not there, a peer that does not answer. A failing transition must still leave the fiber’s efects recovered rather than stranded.

Let Ξ be a set of errors and refine the efect iterator of Definition 51 so that an iteration may raise in place of yielding a triple:

![](images/ca69f6ef5bdab47b0e8252e2183803887cf1c6f98613dd4477d1ce279e3676d5.jpg)

(49)

The witness constrains the ?????????? case alone, being vacuous where the pattern does not match, a raise having nothing to undo, and the ?? that ?????????????????? carries is read at ??<sup>fail∗</sup><sub>Γ</sub> from here on. The lift of Definition 52 carries over with a raise propagated in place of a triple, so a raising iterator is usable wherever an efect is, as an ordinary one is. The layer adds one rule and puts the second outcome of Definition 49 to use, O-Remove needing no widening to admit it. The premises of L-Iter, L-Finish, and L-Divert are read with ?????????? around the triple they match. A raise is something an iteration does, so the rule is an exit from ??????????????????.

![](images/87ea62ea557c4d0abfe17fc77af55f94bf6acf5eb34ac212a6ae13f5da480518.jpg)

L-Raise recovers before it records. The fiber routes into ?????????????????? carrying the error as its outcome, the accumulator built up to the failing iteration is applied there, and the fiber arrives at ????????????????(??) having installed nothing, at a state difering from the one an aborting L-Divert would have produced only in the outcome the fiber carries. Routing a failure like every other deactivation is what makes every outcome reachable only through L-Unload, which is the single fact Theorem 59 turns on. L-Begin has ????????????????(⊥) as a premise, so the lifecycle is not re-entered from an error outcome; this is the substance of the outcome, which withholds a fiber whose efect function has shown itself to be unsound in the state it ran against rather than retrying it against an unchanged environment. A failed fiber also obstructs nothing: it is ????????????????, so it carries no committed view and cannot make relied hold.

A failure is recorded on the fiber rather than propagated to its parent, so a component whose transition fails leaves its siblings running, which is the behavior a plugin host wants and the reason the outcome is per-fiber rather than a property of the whole state.

## 4.4. Metatheory

Section  4.3 supplies ten rules: the three orchestration rules of Section  4.2; L-Begin, L-Iter, and L-Finish for an activation; L-Divert and L-Raise for the two ways an activation may end early; and L-Leave and L-Unload for a deactivation. This section reads the two dimensions of composability of those rules in their global form, one fiber’s guarantee holding whatever the other fibers do in between, and adds what only a whole system can be asked for: that it always reaches the configuration its targets call for, and that the configuration is the one a static assembly would have produced. Every property below is a property of a sequence of steps, so we index the steps and read the fields of a state of that index.

Two conventions carry Section 3.3.2 into this section. Every equality between states below is read up to the observational equivalence ≃ of Definition 33, as Lemma 38 reads those of Section 3.1, and the witness condition an efect function is held to is the one Definition 37 gives, read of an iterator as Definition 51 gives it and of a registering iteration at the ≈ below.

Definition 53. Index the steps by ??, so that ??<sup>??</sup> is the state the first ?? of them reach, and write

![](images/e3512247db0cb8ad83a59d0da5dab0ead43213383828fa3f74bbf10618b47278.jpg)

(50)

for the step taken at ??<sup>??</sup>: the rule ?? it applies, one of the ten, and the name ?? ∈ ?? it applies that rule at. The sequence starts at a ??<sup>0</sup> with dom(?? <sup>0</sup>) = ⌀, so every fiber comes into existence by an O-Insert, whether the orchestrator’s or one an iteration takes (Definition 47). A field of ??<sup>??</sup> carries the index as a superscript, so that ??<sup>??</sup><sub>??</sub>, ??<sup>??</sup><sub>??</sub>, ??<sup>??</sup><sub>??</sub>, ??<sup>??</sup><sub>??</sub>, and ??<sup>??</sup><sub>??</sub> are the lifecycle state, committed view, table, accumulator, and remaining iterator of ?? at ??<sup>??</sup>, and ?? <sup>??</sup> and ??<sup>??</sup> the registry and coefect context of ??<sup>??</sup> itself, the ?? and ?? of Definition 45 read there. Predicates take the state as their argument and everything else as a subscript, so installed<sup>??</sup><sub>??</sub>, target<sup>??</sup><sub>??</sub>, relied<sup>??</sup><sub>??</sub>, and quiet<sup>??</sup> are the predicates of Definition 46, Definition 49, and Definition 50 at ??<sup>??</sup>. An episode of ?? is a maximal interval [??, ??] of indices throughout which installed<sup>??</sup> holds. It opens at ??, where ?? > 0 and ¬ installed<sup>??−1</sup><sub>??</sub> , the empty ?? <sup>0</sup> leaving no fiber installed at the outset; it closes at ?? when installed<sup>??</sup><sub>??</sub> and not installed<sup>??+1</sup><sub>??</sub> , which a final episode need not do.

Every rule of Section 4.3 concludes in the shape ?? ⟶ ??[⋯], where the premises compute ?? from ?? and leave it as ?? where they compute nothing, and the bracket edits named fields of the registry. The two halves are named separately, and both are maps on all of Γ. The state map of a step taken at ??<sup>??</sup> by a rule acting on ?? is

![](images/0a85b1cbaad218dad53331092f1de8e2fc50d89a04123cdec20ddb3547303211.jpg)

(51)

where ?? and ?? are the iterator and the accumulator that ??<sup>??</sup> carries, and the edit edit<sup>??</sup> : Γ → Γ is the bracket read as a function, assigning to the fields it names the values the premises computed at ??<sup>??</sup>. Both are therefore fixed by step<sup>??</sup> together with ??<sup>??</sup> and defined at every state, which is what lets Theorem 61 and Lemma 71 evaluate them away from ??<sup>??</sup>. Each step factors as

![](images/18521d518d753dd1111577ee272d7cb33babe3b832eec3021b0f782a57d43243.jpg)

(52)

At L-Unload, for instance, edit<sup>??</sup> is [?? ↦ ????????????????(??)], and at O-Remove it is the removal ∖ ??, which is why the second half is an edit rather than an assignment. The fields divide along the same seam: the tables ??<sub>??</sub>, which no edit<sup>??</sup> writes once the O-Insert creating ?? has set it empty, and the control fields ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub> together with dom(??<sub>??</sub>), which no Ψ<sup>??</sup> writes save through the primitive of Definition 47. Write ?? ≈ ?? when two states agree on everything but the control fields.

The relation ≈ is not the ≃ of Definition 33, and neither refines the other, because each forgets what the other has to keep. Recovery exactness is a claim about efects, so ≈ compares the tables and the ambient state exactly and forgets only the registry’s record of which fiber installed them. A rule reads the control fields to decide whether it applies, so ≃ has to keep them, and this section reads it as the conjunction of Definition  33 with agreement on the registry’s domain and on every control field of every fiber:

![](images/483671f3fd52410433e0515fd9fb1214a52a27b9c9d7c8baf66863148e136e5c.jpg)

A field of function type, as ??<sub>??</sub> and the ?? inside ??<sub>??</sub> are, is compared as Definition 36 compares maps, an iterator as Definition 51 compares two, and a field of any other type by equality. The results below hold up to both relations, one for each half of the state, Lemma 55 establishing the ≃ half once for all ten rules.

Table 1 is the ten rules of Section 4.3 read as such writes. The accumulator, the committed view, and the remaining iterator are constituents of ?? , so the third column records the writes to them as well, and ℎ there names the inverse the iteration of the fourth column yields, id where L-Divert aborts that iteration. Where a Ψ<sup>??</sup> built from an iterator registers a fiber (Definition 47), that registration carries the writes of the O-Insert row at the name it draws, and an L-Unload whose accumulator retires one carries those of the O-Retire row. Every case analysis below is a lookup in the table, and five lookups recur often enough to name.

![](images/f471d8771955768c7862254f7e483fedf4f1278c7abd9189202bd99fa3ecaa05.jpg)  
Table 1 | The rules as writes on the fiber ?? they act on, where step<sup>??</sup> is that rule applied at ??.  
Lemma 54. Reading Table 1 together with Definition 48, for every step ?? and all fibers ??, ?? present at ??<sup>??</sup>:  
1. ??<sup>??+1</sup><sub>??</sub> ≠ ??<sup>??</sup><sub>??</sub> only where step ?? acts on ??, the write lying inside Ψ<sup>??</sup>;  
2. ?? comes into existence only where step<sup>??</sup> = L-Begin(??) and ceases only where step<sup>??</sup> = L-Unload(??), so ??<sup>??</sup> is constant for ?? in an episode of ??;  
3. Ψ<sup>??</sup> = ??<sup>??</sup><sub>??</sub> only where step<sup>??</sup> = L-Unload(??), and no other step applies ??<sub>??</sub> to the state;  
4. ¬ installed<sup>??</sup><sub>??</sub> ∧ installed<sup>??+1</sup><sub>??</sub> ⇒ step<sup>??</sup> = L-Begin(??), and installed<sup>??</sup><sub>??</sub> ∧ ¬ installed<sup>??+1</sup><sub>??</sub> ⇒ step<sup>??</sup> = L-Unload(??);  
5. ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, and ??<sub>??</sub> come into existence with the entry of ?? and are never written again, and ??<sub>??</sub> is monotone, written only at ⊤ and only by an O-Retire.

Proof. Let step ?? apply ?? at ??. By Definition 53 it factors as edit<sup>??</sup> ∘ Ψ<sup>??</sup>, where edit<sup>??</sup> writes the fields the fifth column of Table 1 names and nothing else, and Ψ<sup>??</sup> is id<sub>Γ</sub>, an application of one of ??’s iterations, or the accumulator ??<sup>??</sup> , which is a composite of the inverses those iterations yielded. Each of the three is confined to ?? by Definition 48, so Ψ<sup>??</sup> writes no field of a fiber present at ??<sup>??</sup> but ?? , together with the entry a registration adds and the ?? its inverse writes. The two halves therefore partition the writes, and each clause is that partition read at one field. One reading of the second and third columns is used twice: ???????????????? is the one lifecycle state carrying no committed view, L-Begin the one rule leading out of it, and L-Unload the one rule leading into it, while every other row carries the ?? of its premise into its conclusion unchanged.

(1) An edit<sup>??</sup> writes no table, the fifth column naming none, and a Ψ<sup>??</sup> writes no ??<sub>??</sub> for a present ?? ≠ ??. So ?? can move only at ?? = ??, and only inside Ψ<sup>??</sup>.

(2) ??<sub>??</sub> is a constituent of ??<sub>??</sub>, which only an edit<sup>??</sup> writes and only at the fiber the step acts on, so by the reading above ?? comes into existence at an L-Begin of ?? and ceases at an L-Unload of ??. An episode of ?? is an interval on which installed holds, hence one throughout which ?? is defined, so neither rule falls in its interior.

(3) The fourth column, where an accumulator appears at L-Unload alone: the other rules take a forward map pr<sub>1</sub> ∘ ?? or id<sub>Γ</sub>, and no edit<sup>??</sup> applies a map to the state at all.

(4) installed<sub>??</sub> is ??<sub>??</sub> ≠ ????????????????(−), and by the reading above L-Begin and L-Unload are the only rules whose premise and conclusion difer in whether ??<sub>??</sub> is ????????????????. A step acting on some ?? ≠ ?? writes no ??<sub>??</sub>, and the entry a registration adds is at a name not present at ??<sup>??</sup>.

(5) No row of the fifth column names a ??, ??, ??, or ??; those come into existence with the entry O-Insert adds, which its conclusion writes, as does the O-Insert a registration takes. Only O-Retire writes a ??, at ⊤, whether taken by the orchestrator or as the inverse of a registration (Definition 47); O-Insert sets ?? = ⊥ at a name not already present, so no step returns a ?? to ⊥.□

Three further lookups say what the rules cannot see. The first is that they read the state only through the observations above, so that the whole calculus descends to Γ/ ≃.

Lemma 55. (≃-invariance.) Let ?? ≃ ??<sup>′</sup> as read above. Then a rule of Section 4.3 applies at ?? acting on ?? if and only if it applies at ??<sup>′</sup> acting on ??, and the states the two applications reach are again related by ≃.

Proof. Every premise of Section 4.3 is of one of four kinds, and each reads a constituent the relation keeps. A premise matching ??<sub>??</sub> or ??<sub>??</sub> against a pattern, and the premise ∀??. ??<sub>??</sub> ≠ ?? of O-Remove, read control fields. The premises (??, ??, ??) ∈ ℭ<sub>Γ</sub> and ∀??. ?? ∩ ??<sub>??</sub> = ⌀ of O-Insert read ??, ??, and ??. A premise mentioning target<sub>??</sub> or relied<sub>??</sub> reads ??<sub>??</sub>, the committed views inside the ?? , and dom(?? ), which Definition 45 computes from the ?? and the dom(?? ), and Defin ition 33 relates two coefect contexts only where their domains agree. The remaining premises read dom(??<sub>??</sub>). None reads a value ??<sub>??</sub>(??) otherwise than up to ≃, so no premise separates two ??   
≃-related states.

For the conclusion, ??<sup>??+1</sup> = edit<sup>??</sup>(Ψ<sup>??</sup>(??<sup>??</sup>)) by Definition 53. The values an edit<sup>??</sup> assigns are the constituents of the premises it matched, related at the two states by the paragraph above and by Definition 51, which relates the triples an iterator yields at ≃-related states. And Ψ<sup>??</sup> respects ≃: it is id , or an iteration of ?? , which Definition 51 requires to respect ≃, or the accumulator inside ?? , a composite of inverses each respecting ≃ by the same definition. □

The names a state carries are read by two of those observations, dom(??<sub>??</sub>) and the indexing of the control fields, and the rule that draws a name draws any name not already in use (Definition 47). Reading the results below up to ≃ therefore also calls for reading them up to a renaming, which is the discipline of Section 4.1 cashed out.

Lemma 56. (Equivariance.) Let ?? : ?? → ?? be a bijection and let ?? ⋅ ?? be the state carrying the registry ?? ∘ ??<sup>−1</sup>, with every name occurring in a ?? or an ?? replaced by its image. Then ?? ⋅ ?? is a state, well formed where ?? is, and step<sup>??</sup> = ??(??) carries ??<sup>??</sup> to ??<sup>??+1</sup> if and only if ??(??(??)) carries ?? ⋅ ??<sup>??</sup> to ?? ⋅ ??<sup>??+1</sup>.

Proof. A premise reads a name only by comparing it with another, whether directly, as in the freshness ?? ∉ dom(?? ) of O-Insert and the ∀??. ?? ≠ ?? of O-Remove, or through a table of names, as target<sub>??</sub> and relied<sub>??</sub> read the ??<sub>??</sub> and the ??<sub>??</sub>. A bijection preserves each such comparison. The only names a rule writes are the ?? that O-Insert sets and the ?? that L-Begin sets, both taken from what its premises read, so the writes commute with ??; an efect function writes no name at all, drawing one only through the primitive of Definition 47, which Definition 48 confines to the entry that primitive adds. Well-formedness (Definition 58) is four conditions comparing names with names. □

A sequence and its renaming therefore take the same rules in the same order and reach states difering by ?? alone. Two sequences agreeing save in the names their registrations draw are accordingly identified, and the results below are read up to the renaming that identifies them.

The second lookup is that an entry stripped of everything but its name is invisible to the rules, which is what lets Definition 47 retire a fiber where the state it recovers has none, and Lemma 72 remove the registrations a deleted episode made.

Lemma 57. (Vestigial entries.) Call ?? vestigial at ?? when ??<sub>??</sub> = ⊤, ??<sub>??</sub> = ????????????????(⊥), ??<sub>??</sub> = ⌀, and no ?? has ?? = ??; a vestigial entry satisfies ?? ≈ ?? ∖ ??. If ?? is vestigial at ?? then for every rule and every ?? ≠ ??:

1. a rule applying at ?? acting on ?? applies at ?? ∖ ?? acting on ??, and the states the two reach difer in the entry at ?? alone, which stays vestigial;

2. conversely a rule applying at ?? ∖ ?? acting on ?? applies at ??, unless it is an O-Insert drawing the name ?? or claiming a key of ??<sub>??</sub>.

Proof. A vestigial ?? contributes to no observation a premise of a rule acting on ?? ≠ ?? reads. It is not ????????????, so ??<sub>??</sub> enters no ??<sub>??</sub> and ?? is the provider of no key, leaving ?? ⊧ ??<sub>??</sub> and target<sub>??</sub> unmoved; installed fails, so ?? contributes no disjunct to relied ; no ?? ′ names ??, so the premise ∀??<sup>′</sup>. ??<sub>??</sub>′ ≠ ?? of an O-Remove of ?? is unmoved; and ??<sub>??</sub>, ??<sub>??</sub>, and ??<sub>??</sub> are read by rules acting on ?? alone. The two premises clause (2) excepts are the two the removal relaxes, an absent name being fresh and an absent provision meeting every other. By Lemma 54 no rule acting on ?? ≠ ?? writes a field of ??, so the entry survives, and the state map of the step is confined to ?? by Definition 48, so it leaves ??<sub>??</sub> empty. □

Simplifying the lifecycle states, together with the rules that match on them, yields a subcalculus, and not every result survives the simplification. Dropping Section 4.3.1 is the case that matters, which is the division Section 4.3 opens with, read from the metatheory’s side: its guard is what establishes clauses (3) and (4) of Definition 58, and Theorem 63 rests on the interval the guard creates, so those three fail without it. What the other three subsections add can be simplified away without disturbing the results below, each of them only adding rules to the one state space Definition 49 fixes.

## 4.4.1. Preservation

Definition 45 fixes the shape of a registry, and the rules have to be checked against it before the results below can add to it. This subsection identifies the invariant the rules preserve, of which the first clause is that shape and the rest what those results assume.

Definition 58. A registry ??<sub>??</sub> is well formed when, for all ??, ?? ∈ dom(??<sub>??</sub>) and all ?? ∈ ??,

1. ??<sub>??</sub> ∈ dom(??<sub>??</sub>) ∪ {????????};

2. ?? ≠ ?? ⇒ ??<sub>??</sub> ∩ ??<sub>??</sub> = ⌀;

3. installed<sub>??</sub>(??) ⇒ ??<sub>??</sub> is total on ??<sub>??</sub> and valued in dom(??<sub>??</sub>);

4. installed<sub>??</sub>(??) ∧ ?? ∈ ??<sub>??</sub> ∧ ??<sub>??</sub>(??) = ?? ⇒ installed<sub>??</sub>(??).

Clause (1) is the tree of Definition 45 read one edge at a time, keeping a parent pointer landing in the registry. The acyclicity that definition also requires needs no clause, since the fiber a pointer names is registered before the fiber naming it.

Theorem 59. (Preservation.) If ?? <sup>??</sup> is well formed then so is ?? <sup>??+1</sup>, whichever rule step ?? applies.   
Each clause is established at ??<sup>??+1</sup> from all four at ??<sup>??</sup>.

Proof. Let step ?? act on ??.

(1) By Table 1 only O-Insert and O-Remove write a ?? or dom(??<sub>??</sub>). O-Insert has ??<sub>??</sub> ∈ dom(?? <sup>??</sup>) ∪ {????????} as a premise, which is the clause for the fiber it adds, and it leaves every other ?? alone while enlarging dom(??<sub>??</sub>). O-Remove has ∀??. ??<sub>??</sub> ≠ ??, so no surviving ??<sub>??</sub> names the fiber it takes away.

(2) The last premise of O-Insert is ∀??. ?? ∩ ?? = ⌀, which is the clause for the fiber it adds, and by Table 1 no other rule writes a ?? or enlarges dom(?? ). Two consequences are used below: dom(??<sub>??</sub>) ⊆ ??<sub>??</sub> by Definition 43, so distinct tables are disjoint and ??<sub>??</sub> is a function; and ?? ∈ ??<sub>??</sub> ∩ ??<sub>??</sub>′ forces ?? = ??<sup>′</sup>, so ?? has at most one possible provider.

(3) By Lemma 54(2) the only rule that writes an ??<sub>??</sub> is L-Begin, whose premise ?? = target<sup>??</sup><sub>??</sub> ≠ ⊥ makes it total on ??<sub>??</sub> and valued in dom(?? <sup>??</sup>), target naming providers. By Table 1 the only rule that shrinks dom(?? ) is O-Remove, whose premise ??<sup>??</sup> = ????????????????(−) gives ¬ installed<sup>??</sup> , whence by clause (4) at ??<sup>??</sup> no ?? has ??<sup>??</sup> (??) = ?? for a ?? ∈ ?? while installed<sup>??</sup> ; and ?? itself carries no ??.

(4) By Lemma 54(2) and (4) the clause can fail at ??<sup>??+1</sup> only where some installed has fallen, some ?? has been written, or a fiber some ?? names has left dom(?? ). The last is an O-Remove, whose removed fiber is not installed and hence, by clause (4) at ??<sup>??</sup>, is named by no ??<sup>??</sup><sub>??</sub> of an installed ??. The first is an L-Unload of ??, whose premise ¬ relied<sup>??</sup> reads

![](images/c8a07b40537b22edbd6d2dcf28c725bea7dd0ff27ef269584aea4627f43a746c.jpg)

and which writes no ?? for ?? ≠ ?? and leaves ¬ installed<sup>??+1</sup>, so the clause holds of ?? as well. The second is an L-Begin of ??, writing target<sup>??</sup> , whose values are the providers of the keys of ?? and hence ???????????? at ??<sup>??</sup>; the step alters no other fiber’s ??, so they are installed at ??<sup>??+1</sup> too. □

The guard on L-Unload is what carries clauses (3) and (4). The premise ∀??. ??<sub>??</sub> ≠ ?? of O-Remove speaks only of parent pointers; what keeps a committed view from naming a removed fiber is the guard, imposed several steps earlier and for a diferent reason. Because a failure is routed through ?????????????????? as well, the argument does not have to be repeated for an error outcome. Two things follow that the base calculus does not enjoy. A name freed by O-Remove may be reissued by O-Insert, since no stale committed view can name it; and a fiber may be removed as soon as it is ????????????????, without a separate check that nobody depends on it.

## 4.4.2. Temporal Composability

Local temporal composability recovers one sequence of efects with one accumulator (Sec tion 3.1.3). The registry holds one accumulator per fiber and the fibers interleave: between the moment ?? composes an inverse onto ?? and the moment ?? runs, other fibers have moved the state. Whether ?? still undoes what it was built to undo there is what the global form of the guarantee asserts, and the condition it turns on is that the intervening steps commute with ??<sub>??</sub>.

Definition 60. For ?? ∈ ??<sup>iter∗</sup><sub>Γ</sub> let reach(??) be the least set of iterators containing ?? and closed under continuation, and read the transformation monoid ?? of Definition 17 at an iterator by taking for its generators the forward maps and the yielded inverses of every iterator in reach(??):

![](images/43901e8881004c0e5a27f713a59941da4806003111cd0121266ef403e7157c74.jpg)

(54)

reading ?????????? around the triple where Section 4.3.4 applies, and write len(??) for the supremum of |??| over the chains ?? ⊆ reach(??) that continuation orders. Two iterators ??, ?? are independent when they are so in the sense of Definition 19, read with these transformation monoids and with the yield of an iteration being its inverse together with its continuation:

![](images/b7244ab09886c882733fae053dbb79ac06b564ac8d21856c4fefb26d9f583805.jpg)

(55)

and symmetrically in ??, reading ≃ on maps as Definition 36 does, on a continuation as Definition 51 does, and on a registering iteration (Definition 47) as agreement of the component it names. A family (??<sub>??</sub>)<sub>??∈??</sub> of iterators is pairwise independent when ??<sub>??</sub> and ??<sub>??</sub>′ are independent for every ?? ≠ ??<sup>′</sup>, and a sequence of steps is pairwise independent when (??<sub>??</sub>) is, where ?? is the set of names the sequence ever holds, one for each fiber the orchestrator inserts and each fiber an iteration registers.

Independence in this sense is what trace theory takes as primitive: commuting actions generate an equivalence on sequences under which reordering two adjacent independent actions preserves the endpoint [44], and Lemma 71 is that reordering for these rules. A family rather than a set is what keeps two names of one component in scope: the condition then requires that component’s efect function to be independent of itself, which is to require that ??(??) be commutative. The first condition is what Theorem 61 uses and the second what Theorem 73 needs in addition: reordering the steps of two fibers evaluates an iterator at a state the other fiber moved, and commuting the maps does not by itself say that the iterator yields the same inverse and the same continuation there. Checking the first condition calls for no more than the iterations themselves, since Lemma 18(1) carries commutation from the generators to the monoids they generate.

Under these conditions the single-accumulator invariant of Theorem  7 survives the interleaving, in the form that gives temporal composability its content: running an inverse withdraws the fiber’s contribution and nothing else.

Theorem 61. (Recovery exactness.) Let the sequence of steps be pairwise independent, let an episode of ?? open at ??, let ?? ≥ ?? lie in it, and let ??<sub>1</sub> < ⋯ < ??<sub>??</sub> be the indices in [??, ??) at which the acting fiber is not ??. Then

![](images/c4ebc0afcd3bf2f6210d15817d06d5d0b4092d64f5a0d8c0d9b86a7cea657abd.jpg)

(56)

That is, applying ??’s accumulator at ??<sup>??</sup> yields, up to the control fields, the state those same steps would have produced from ??<sup>??</sup>. Reading the right side as the state reached had ?? never begun assumes in addition that no fiber ?? registers take a step in [??, ??), since a fiber ?? registers is one that would not be there to take it.

Proof. By induction on ??, over the indices ?? with ?? + 1 in the episode. At ?? = ?? the step at ?? − 1 is an L-Begin, the episode opening by Definition 53, so ??<sup>??</sup><sub>??</sub> = id<sub>Γ</sub> by Table 1, the index set is empty, and the claim is ??<sup>??</sup> ≈ ??<sup>??</sup>. Two facts are used at each step. Since edit<sup>??</sup> writes control fields only,

![](images/08ec78b37a5036b43faea591e039f455863c729a26905ea9b522f98846e84113.jpg)

and since every map in ??(?? ) writes no control field but those a registration adds, by Defin ition 48 together with Definition 47, each such map carries ≈-equal states to ≈-equal states.

Let step ?? act on ??. Since the episode is open at ?? and ?? + 1, Lemma 54(4) excludes an L-Begin and an L-Unload of ??, and O-Insert and O-Remove read a ??<sub>??</sub> that installed<sup>??</sup><sub>??</sub> denies, leaving two cases. Where the rule is L-Iter, L-Finish, or a landing L-Divert, Table 1 gives Ψ<sup>??</sup> = pr<sub>1</sub> ∘ ??<sup>??</sup><sub>??</sub> and ??<sup>??+1</sup><sub>??</sub> = ??<sup>??</sup><sub>??</sub> ∘ ℎ for the inverse ℎ that iteration yields. The witness condition of Definition 51 reads ℎ(Ψ<sup>??</sup>(??<sup>??</sup>)) = ??<sup>??</sup>, up to ≈ where the iteration registers a fiber (Lemma 57), and ??<sup>??</sup><sub>??</sub> carries ≈ by the equation above, so

![](images/229af6115dd4630045576c956bb662e97c64c2d716f8ca398c7475f1d98c0b29.jpg)

Where the rule is L-Leave, L-Raise, an aborting L-Divert, or an O-Retire of ??, Table 1 gives Ψ<sup>??</sup> = id<sub>Γ</sub> and ??<sup>??+1</sup><sub>??</sub> = ??<sup>??</sup><sub>??</sub>, so the same equation holds with ℎ = id<sub>Γ</sub>. Either way the induction hypothesis carries over with the index set unchanged, which is the computation of Theorem 7 one step at a time.

Let step ?? act on ?? ≠ ??. Then ??<sup>??+1</sup> = ??<sup>??</sup> by Table 1, and Ψ<sup>??</sup> ∈ ??(?? ), or Ψ<sup>??</sup> = id where the rule is an orchestration rule, so independence gives

![](images/6571c1069b0ef7861248e47fa2b2d47ff45953aac32656c6cdef2e8433583048.jpg)

which is the induction hypothesis with Ψ<sup>??</sup> appended.

Corollary 62. (Terminal recovery.) Let the sequence of steps be pairwise independent and let an episode of ?? open at ?? and close at ??, whatever outcome ?? arrives at. Then, with ?? < ⋯ < ?? as in Theorem 61,

![](images/9babe60d6db22d8175e925f6d720ae5f76a7bccdb47801b53fc0f548488173f4.jpg)

(57)

A fiber removed by O-Remove leaves nothing behind either, its premise admitting only ??<sub>??</sub> = ????????????????(−).

Proof. By Lemma 54(4) step ?? is an L-Unload of ??, whose Ψ<sup>??</sup> is ??<sup>??</sup> by Lemma 54(3), so ??<sup>??+1</sup> ≈ ??<sup>??</sup>(??<sup>??</sup>) and Theorem 61 applies. Neither the statement nor ≈ mentions ??, which by Table 1 is the one field in which the states L-Divert and L-Raise lead to difer. □

Pairwise independence is assumed of the components by the results above, and Section 3.3.2 is what discharges it: where every efect a component performs is an operation of a key and every key is commutative, any two efect functions built from those operations are independent (Theorem 42). Carrying that result from efect functions to iterators calls for nothing new, a coefect-mediated efect function (Definition 41) already choosing what follows each stage by the outcome that stage yields, which is what an iterator carries in its continuation. The coefect operations of Section 3.2 are the case that needs no hypothesis at all: the maps a component contributes there are composites of set operations and of the corresponding restrictions, two such commute whenever they touch disjoint keys, and clause (2) of Definition 58 makes the provisions of distinct fibers disjoint.

## 4.4.3. Spatial Composability

Local spatial composability holds a component to its own specification, activating it only where its dependencies are provided and classifying every context change against them (Section 3.2.2). The global form adds what quantifies over other fibers: a provider withdraws a binding only after every dependent that resolved it has deactivated, and the resolution a transition installs its efects against does not shift under it. Two properties of the coefect side deliver the two, and they are proved together, being two halves of one invariant, namely the fixity of ?? over an episode that Lemma  54(2) establishes. The ordering theorem is what that fixity buys over the part of the episode in which ?? is ???????????? and then ??????????????????, and the coherence theorem what it buys over the part in which ?? is installing its efects.

Theorem 63. (Ordering.) A fiber begins a transition only where its dependencies are provided:

![](images/a7ef91440d0aff81aeeee6844b90bcc9f56caa7bf33861d6784ddea8804b081a.jpg)

(58)

Let further [??<sup>′</sup>, ??<sup>′</sup>] be an episode of ?? with ??<sup>??′</sup><sub>??</sub>(??) = ?? for some ?? ≠ ?? and ?? ∈ ??<sub>??</sub>, let [??, ??] be the episode of ?? containing ??<sup>′</sup>, and let ?? range over [??<sup>′</sup>, ??<sup>′</sup>]. Then

1. ??<sup>??</sup><sub>??</sub>(??) = ??;

2. ?? < ??<sup>′</sup>, and ??<sup>′</sup> < ?? if [??, ??] closes;

3. ?? ∈ dom(??<sup>??</sup><sub>??</sub>) and ??<sup>??</sup><sub>??</sub>(??) = ??<sup>??′</sup><sub>??</sub> (??).

Proof. The first claim is the premise target<sup>??</sup> ≠ ⊥ of L-Begin, which by Definition 46 gives ??<sup>??</sup> ⊧ ??<sub>??</sub>.

(1) is Lemma 54(2).

For (2), the L-Begin at ??<sup>′</sup> − 1 writes ??<sup>??′</sup><sub>??</sub> = target<sup>??′−1</sup><sub>??</sub> , whose values are providers, so ??<sup>??′</sup><sub>??</sub> = ????????????(−, −); the L-Begin at ?? − 1 leaves ??<sup>??</sup><sub>??</sub> = ??????????????????(−, −, −), so ?? ≠ ??<sup>′</sup> and hence ?? < ??<sup>′</sup>, both episodes opening by Definition 53. Let [??, ??] close and suppose ?? ≤ ??<sup>′</sup>. Then ?? ∈ [??<sup>′</sup>, ??<sup>′</sup>], so installed<sup>??</sup><sub>??</sub> and, by (1), ??<sup>??</sup><sub>??</sub>(??) = ??; that is relied<sup>??</sup><sub>??</sub>, which the L-Unload at ?? denies. Hence ??<sup>′</sup> < ??.

For (3), ?? is the provider of ?? at ??<sup>??′</sup>, so ?? ∈ dom(??<sup>??′</sup><sub>??</sub> ). No L-Unload of ?? falls in [??<sup>′</sup>, ??<sup>′</sup>]: where [??, ??] closes it falls at ?? > ??<sup>′</sup> by (2), and where it does not, Lemma 54(4) leaves ?? with no L-Unload at all. Since ??<sup>??′</sup> = ????????????(−, −), Table 1 therefore leaves L-Leave as the only rule ?? can be acted on by within [??<sup>′</sup>, ??<sup>′</sup>], and its Ψ<sup>??</sup> is id<sub>Γ</sub>; by Lemma 54(1) ??<sub>??</sub> is constant there. □

A transition spread over steps could otherwise install efects computed against a resolution that has changed under it, and two premises prevent that. L-Iter and L-Finish carry target<sub>??</sub>(??) = ??, so a transition proceeds only while its committed view is still its target view, and L-Divert carries the negation, so any change to the target view takes the fiber out of the transition. L-Raise is not conditioned on the target view at all, a raise being something the iteration does rather than something the environment asks for, and it exits the transition in any case. The two directions of change are not distinguished: a component whose dependency has gone and one whose dependency has been replaced leave by the same route, because a target view that has become ⊥ and one that has become some other fiber are equally unequal to ??.

Inertia is what stops this from being a guarantee about every step. An iteration already in flight when the target view turns lands regardless, by L-Divert, and that landing installs an efect computed against a resolution that no longer holds. What the rules deliver is therefore a disjunction, and the second branch is what makes the first safe.

Theorem 64. (Resolution coherence.) Let an episode [??, ??] of ?? open at ?? with ??<sup>??</sup><sub>??</sub> = ??. Then ??<sub>??</sub> is ??????????????????(−, −, −) on an initial interval [??, ??] of the episode, and every iteration of the transition runs against the one resolution ??:

![](images/0dfbfe62ecf0f2fdd5de758c3a5faa1feb094e1413befb36a54c24ec98d83f7a.jpg)

(59)

Where the fiber leaves that interval, so that ?? < ??, exactly one of the following holds:

1. step<sup>??</sup> = L-Finish(??) and ??<sup>??+1</sup><sub>??</sub> = ????????????(−, ??);

2. step<sup>??</sup> ∈ {L-Divert(??), L-Raise(??)}, and the episode closes at some ?? > ?? with ??<sup>??+1</sup> ≈ (Ψ<sup>??</sup>?? ∘ ⋯ ∘ Ψ<sup>??</sup>1 )(??<sup>??</sup>) as in Corollary 62.

Proof. The L-Begin at ?? − 1 writes ??????????????????, and by Table 1 it is the one rule leading into that lifecycle state; its premise ??<sub>??</sub> = ????????????????(⊥) and Lemma 54(4) put any second application of it outside the episode. So ?????????????????? occupies an initial interval [??, ??] of [??, ??] and is not re-entered.

The first claim is then the premise target (??) = ??<sup>′</sup> that Table  1 gives L-Iter and L-Finish, together with ??<sup>′</sup> = ?? by Lemma 54(2).

For the dichotomy, step<sup>??</sup> is a rule whose premise has ??<sub>??</sub> = ??????????????????(−, −, −) and whose conclusion does not, of which Table 1 ofers L-Finish, L-Divert, and L-Raise; the first lands in ????????????(−, ??) and the other two in ??????????????????(−, ??, −), from which Lemma 54(4) makes an L-Unload the only exit and Corollary 62 supplies the equation. The iteration a landing L-Divert contributes is one of ??’s own, hence among the maps that accumulator withdraws. Where instead ?? = ??, the sequence ends with the transition still in flight and the first claim is all that is asserted. □

## 4.4.4. Progress

A guard that defers a provider’s withdrawal until its dependents are gone delivers Theorem 63 only if it eventually releases. One relation on the fibers of a registry carries the argument.

Definition 65. The precedence relation on the names of a registry is

![](images/a34e90fd0d42e80b0fab39c1a2c8a5b7f01048ed5f108d5bd3872e60fc2d7859.jpg)

(60)

so that ?? may provide a key ?? declares. It reads ?? and ?? alone, which by Lemma 54(5) come into existence with a fiber’s entry and are never written again.

Theorem 66 and Theorem 73 are established on the hypothesis that ≺ is acyclic, which is an assumption and not something the definition delivers, ?? ≺ ?? holding of a component that declares a key it provides itself. What ≺ orders is the two fibers’ activations and not their lifetimes: ?? ≺ ?? says that ?? has to become ???????????? before ?? can, whereas that a provider outlives its consumer is Theorem 63(2), a theorem about the guarded calculus.

A fiber’s target view answers to the fiber that created it as well as to its providers. What a creator writes is ?? , through the primitive of Definition 47, and ?? is monotone by Lemma 54(5). A creator can therefore turn its child’s target view at most once over that child’s whole existence.

Progress is a claim that some rule applies, so it is formulated over the rules a host must ofer: L-Begin, L-Leave, L-Unload, the landing rules L-Iter, L-Finish, and L-Raise, and L-Divert. It appeals to the aborting alternative of L-Divert nowhere, so a host bound by the inertia of Section 4.3.3 is covered as well.

Theorem 66. (Progress.) Assume ≺ acyclic, len(??<sub>??</sub>) ≤ ?? for every ??, and the set ?? of names of Definition 60 finite; and let every step apply a lifecycle rule. Write ??(??) for the number of steps acting on ?? and

![](images/2fe4649aede9c1fe13fc3431109da297c2732608f79cfa1944a181fda8ce2f7d.jpg)

(61)

for the number of times its target view turns. Then

1. (No deadlock.) ¬ quiet<sup>??</sup> implies that some lifecycle rule applies at ??<sup>??</sup>;

2. (Termination.) ??(??) ≤ (?? + 4)(?? (??) + 1), and both ?? (??) and ∑ ??(??) are finite. Consequently every maximal sequence of lifecycle steps ends in a quiescent state.

Proof. No deadlock. Let ¬ quiet<sup>??</sup>, so some fiber ?? satisfies neither clause of the quiet of Defini tion 49. Reading Table 1 against the four kinds it can then be:

• ??<sup>??</sup><sub>??</sub> = ????????????????(⊥) with target<sup>??</sup><sub>??</sub> ≠ ⊥: L-Begin applies;

• ??<sup>??</sup> = ??????????????????(−, −, ?? ) with target<sup>??</sup> = ?? : whichever of L-Iter, L-Finish, and L-Raise the value of ??<sup>??</sup> (??<sup>??</sup>) selects applies;

• ??<sup>??</sup><sub>??</sub> = ??????????????????(−, −, ??<sub>??</sub>) with target<sup>??</sup><sub>??</sub> ≠ ??<sub>??</sub>: L-Raise applies if ??<sup>??</sup><sub>??</sub>(??<sup>??</sup>) raises, and otherwise L-Divert does, landing that iteration rather than aborting it;

• ??<sup>??</sup><sub>??</sub> = ????????????(−, ??<sub>??</sub>) with target<sup>??</sup><sub>??</sub> ≠ ??<sub>??</sub>: L-Leave applies.

Let no fiber be of any of these kinds, leaving some ??<sub>0</sub> with ??<sup>??</sup><sub>??0</sub> = ??????????????????(−, −, −). Construct ??<sub>0</sub>, ??<sub>1</sub>, … as follows: given ??<sub>??</sub> in ??????????????????, either ¬ relied<sup>??</sup><sub>??</sub> , in which case L-Unload applies to ??<sub>??</sub> and the construction stops, or there are ??<sub>??+1</sub> ≠ ??<sub>??</sub> and ??<sub>??</sub> with installed<sup>??</sup><sub>????+1</sub> and ??<sup>??</sup><sub>????+1</sub>(??<sub>??</sub>) = ??<sub>??</sub>. In the latter case

![](images/b246d3e7ae5822e4eebb120a436c38f8c1a6eecdedc8a6210d951fd842e60aef.jpg)

the second membership being Theorem 63(3) at the episode of ??<sub>??+1</sub> that ?? lies in, so that ??<sub>??</sub> ≺ ??<sub>??+1</sub>. Moreover target<sup>??</sup><sub>??</sub> ≠ ??<sup>??</sup><sub>??</sub> : an ?????????????????? fiber is outside the union defining ??<sub>??</sub>, so ??<sub>??</sub> at ??<sup>??</sup> is unprovided or provided by a fiber other than ??<sub>??</sub>. Were ??<sub>??+1</sub> in ???????????? or ?????????????????? it would then be of one of the four kinds excluded, so it is in ?????????????????? and the construction continues. The ??<sub>??</sub> are ≺-increasing, hence distinct by acyclicity, and dom(?? <sup>??</sup>) is finite, so the construction stops.

Termination. Two claims bound ??(??).

(A) Over a maximal interval on which target<sup>??</sup> is constant at ??<sup>∗</sup>, at most ?? + 4 steps act on ??. Reading the ?? columns of Table 1, from ????????????(−, ??) with ?? ≠ ??<sup>∗</sup> the fiber takes an L-Leave and an L-Unload and then, if ??<sup>∗</sup> ≠ ⊥, an L-Begin and at most len(?? ) ≤ ?? landings, plus a second L-Unload where the last landing is an L-Raise; from ?????????????????? against an ?? ≠ ??<sup>∗</sup> it takes an L-Divert in place of the L-Leave, and from any other state a sufix of that sequence. No further L-Divert or L-Leave falls in the interval, the ?? that the L-Begin writes being target<sup>??</sup><sub>??</sub> = ??<sup>∗</sup> itself, and at ????????????(−, ??<sup>∗</sup>), at ????????????????(⊥) with ??<sup>∗</sup> = ⊥, and at ????????????????(??) no rule applies at all.

(B) If target<sup>??</sup><sub>??</sub> ≠ target<sup>??+1</sup><sub>??</sub> and step ?? acts on ??, then either ?? ≺ ?? or step ?? writes ??<sub>??</sub>. By Definition 46 the value of target is a function of ?? and of the tables of the providers of the keys of ??<sub>??</sub>; a provider satisfies ?? ∈ dom(??<sub>??</sub>) ∩ ??<sub>??</sub> and hence ?? ≺ ??, and a table changes only at a step acting on its own fiber by Lemma 54(1). Acyclicity gives ?? ≠ ?? in the first case, and the monotonicity of Lemma 54(5) admits the second at one ?? per fiber.

By (A) the interval count bounds ??(??) as ??(??) ≤ (?? + 4)(?? (??) + 1), and by (B) each turn of target either consumes a step of a fiber strictly ≺-below ?? or is the one turn ?? afords, so ?? (??) ≤ 1 + ∑ ??(??). Since ≺ is acyclic and ?? is finite, the recursion

![](images/0f998fb9b296d3405b1a443be7352648f0f9eb365325408f19a463a6fd68df0e.jpg)

is well founded and defines ?? with ??(??) ≤ ??(??); hence ?? (??) is finite and ∑ ??(??) ≤ ∑ ??(??). By (1) a sequence that cannot be extended is quiescent. □

Finiteness of ?? is assumed rather than derived, and one condition on the components delivers it. The components a host holds are finitely many programs given before anything runs, so if no component can register, however indirectly, a fiber of a component that registers one of its own, the registrations form a tree of bounded depth, and len(?? ) ≤ ?? bounds its branching. What the assumption rules out is a component that registers instances of itself without bound.

The target records the providing fiber rather than a boolean, and under the single-source discipline of Section 4.2 the two drive the same transitions, a key having one possible provider there. What the view buys is the vocabulary of the results above, Theorem 63 and Theorem 64 both speaking of the resolution a fiber activated against, and it is what makes those results survive the scoped resolution of Section  3.2.3, under which one key resolves to diferent providers in diferent realms and the provisions no longer force the view. The implementation carries that scoping and holds the view in fiber.committed (Section 5.1.3).

## 4.4.5. Confluence

The results so far are about individual fibers. The property that characterizes the system as a whole is that its dynamic history leaves no trace: whatever sequence of activations and deactivations a running system has been through, the state it quiesces at is the one the same insertions and retirements would have produced had each component that ends up active been loaded once, in dependency order, and none ever unloaded. The lifecycle relation is confluent, and the normal form it converges on is the statically assembled one. This is the analogue, for dynamic composition, of the consistency with a from-scratch evaluation that change propagation establishes for incremental computation [45].

The claim is about ⟶ alone. Orchestration steps are inputs, and two sequences given diferent inputs land in diferent places for no interesting reason; what is at issue is whether the lifecycle rules, which are nondeterministic in which fiber steps next and in which exit a ?????????????????? fiber takes, can be made to disagree.

Three lemmas are needed first. The first fixes the set of fibers that end up ???????????? without reference to any sequence of steps, which is what makes it a function of the input rather than of the schedule.

Definition 67. A fiber is supported at ?? when it is not retired, the fiber registering it is supported, and every key it declares is provided by a supported fiber. The support relation on dom(?? ) is the union of the two relations those clauses read,

![](images/c0b59e0d65df46cbab6b762f4d7ea2dbef828f9b11ebd306827a7aaff217561f.jpg)

(62)

and where it is well founded (Lemma 68) we write ?? for the support set, the fibers supported at ??:

![](images/0737645566d2708c7e5af5b3273b612d8d76c3383e35955b9657e9b81ff0cd17.jpg)

(63)

where ?? = ???????? marks a fiber the orchestrator inserted and ?? otherwise the fiber whose activation registers ??. The clauses read no field but ??, ??, ??, ??. Both halves relate a fiber to one immediately below it, a parent rather than an ancestor and a direct provider rather than a transitive one, since that is what the clauses read; where the results below want an order they take the transitive closure, whose minimal elements, maximal elements, and linearizations are those of ⊲.

The clauses refer to ?? itself, so the definition is a recursion along ⊲, and it is the following that makes it one with a solution.

Lemma 68. (Support is well founded.) Let ≺ be acyclic and let ?? be reached by a sequence of steps. Then ⊲ is well founded, and ?? is the one solution of Definition 67, a function of ??, ??, ??, and ?? alone.

Proof. Order the names of dom(?? ) by the index of the step that registered each, which Definition 53 supplies by starting the sequence at an empty registry. The parent half of ⊲ descends in that index: an O-Insert has ?? ∈ dom(??<sub>??</sub>) as a premise, so a parent pointer names a fiber registered earlier, and iterating it reaches the whole ancestry of a name in finitely many steps. A cycle therefore has to use ≺, and since ≺ is acyclic it has to mix the two, which needs some ?? to declare a key that a fiber of ??’s own subtree may provide. Such a fiber is registered by an activation of ?? or of one of ??’s descendants, hence at a step after the L-Begin of ??; that L-Begin has ?? ⊧ ??<sub>??</sub> as a premise, so a fiber providing the key is ???????????? already before it, and clause (2) of Definition 58 leaves the key no second possible provider. The fiber that would close the cycle is therefore never registered, and the edge is absent from dom(?? ). A well-founded recursion has one solution, and the clauses read the four fields alone. □

The last clause reads ??, the keys a component may provide, whereas the target reads dom(??<sub>??</sub>), the keys its fibers have installed, and Definition 43 relates the two by dom(??<sub>??</sub>) ⊆ ??<sub>??</sub> alone. The support set therefore over-approximates the ???????????? fibers in general, and the condition that closes the gap is the following.

Definition 69. A component (??, ??, ??) is total on its provision when an activation of it that finishes has installed every key of ??, so that dom(??<sub>??</sub>) = ??<sub>??</sub> at every ???????????? fiber instantiating it.

Like independence (Definition 60) this is a condition on the components alone, mentioning no lifecycle state and no step, and independence already bounds how far it can fail: were a component to install a key only at context states another component’s efects reach, its forward map would not commute with that component’s, so the keys a fiber installs are fixed by its component rather than by the schedule. What totality adds is that the fixed set is all of ?? rather than a proper subset of it.

Lemma 70. (Support at quiescence.) Let ≺ be acyclic, let quiet(??), let no fiber of ?? be failed, and let every component of ?? be total on its provision (Definition 69). Then the support set is the set of ???????????? fibers:

![](images/355c017b3153921f24b15655e74d578eb8e19b9fec2365e9bd04a22e7e35958d.jpg)

(64)

Proof. Write ??<sup>′</sup> for the right-hand side. No fiber being failed, the quiet of Definition 49 leaves ????????????????(⊥) and ???????????? as the only states and reads

![](images/bda063396fa826d4dc7e64021404b19d879234d18c66035ea8e0d286c95d4506.jpg)

By Definition 46 the right side holds exactly when ¬??<sub>??</sub> and every ?? ∈ ??<sub>??</sub> lies in dom(??<sub>??</sub>), and dom(??<sub>??</sub>) = ⋃ <sub>′</sub> ??<sub>??</sub> by Definition 69. The middle clause is the one the target no longer carries, and registration supplies it: a fiber with ??<sub>??</sub> ≠ ???????? is registered only by an activation of ??<sub>??</sub>, and if ??<sub>??</sub> ∉ ??<sup>′</sup> then ??<sub>??</sub> is not ????????????, so its accumulator has run and retired ?? by Definition 47, giving ??<sub>??</sub>. Hence ??<sup>′</sup> satisfies the clauses of Definition 67, and Lemma 68 gives them one solution, so ?? = ??<sup>′</sup>. □

Lemma 71. (Transposition.) Let the steps be pairwise independent and ?? <sup>??</sup> well formed, and let steps ?? and ?? + 1 act on distinct fibers ?? and ??.

1. If both apply an activation rule, namely L-Begin, L-Iter, or L-Finish, and step ?? + 1 is applicable at ??<sup>??</sup>, then step ?? is applicable at the state step ?? + 1 produces from ??<sup>??</sup>, and the two orders reach the same ??<sup>??+2</sup>.

2. If step ?? applies an activation rule at ??, step ?? + 1 an orchestration rule at ??, and step ?? does not register ??, then the same holds of the two.

Proof. For (1), by Table 1 the step of ?? writes ?? and, within Ψ<sup>??</sup> ∈ ??(?? ), the table ?? and the efect part. It therefore leaves ?? and ?? alone, and by the second condition of Definition 60 leaves the inverse and the continuation that ?? yields alone as well, so only the premises of step ?? + 1 that mention target<sub>??</sub> remain to be checked. Its retirement half cannot fall, no activation rule writing a ??. Its resolution half cannot move either: step ?? + 1 being applicable at ??<sup>??</sup> puts every ?? ∈ ?? in dom(??<sup>??</sup>), and clause (2) of Definition 58 makes the fiber providing such a ?? the only one that can, so ?? ∉ ??<sub>??</sub> and no write of ??<sub>??</sub> reaches a key of ??<sub>??</sub>. The same argument in the other direction leaves step ?? applicable. Finally Ψ<sup>??</sup> ∈ ??(?? ) and Ψ<sup>??+1</sup> ∈ ??(?? ) commute by the first condition of Definition 60, and the two edits write control fields of distinct fibers, so the composite is the same in either order.

For (2), the orchestration step has Ψ<sup>??+1</sup> = id by Table  1, so the two state maps commute outright, and its edit<sup>??+1</sup> writes ?? or dom(?? ) at ?? alone, which the activation step neither reads nor writes: the premises of the latter read ??<sub>??</sub>, ??<sub>??</sub>, ??<sub>??</sub>, and target<sub>??</sub>, and an O-Insert of a fresh ?? moves no target, a fresh fiber providing nothing, whereas an O-Retire or O-Remove of ?? leaves ?? where it was, ?? being ???????????????? in the one case and unafected in its table in the other. So step ?? remains applicable. Conversely each premise of the orchestration step is either read at ??, which step ?? does not write, or is one of the two premises of O-Insert that a smaller registry only relaxes, whence its applicability at ??<sup>??+1</sup> gives its applicability at ??<sup>??</sup>; here step ?? not registering ?? is what keeps ?? present at ??<sup>??</sup> where O-Retire and O-Remove require it. □

Lemma 72. (Deletion.) Let the sequence of steps be pairwise independent, let every component be total on its provision (Definition 69), let it reach a quiescent ??<sup>??</sup> at which no fiber is failed, let [??, ??] be an episode of ?? that closes, let no episode of any ?? with ?? ≺ ?? close in the sequence, and let no fiber ?? registers during [??, ??] have an episode. Write ?? for the names those registrations draw. Then deleting the steps that act on ?? in [??, ??], together with every step acting on a name of ??, leaves a sequence of steps reaching a state ≈-equal to ??<sup>??</sup> and ≃-equal to it outside ??.

Proof. The deleted steps leave the state where they found it. Let ?? < ⋯ < ?? be the steps of [??, ??] that act on fibers other than ??. Corollary 62 reads

![](images/69f9686495f36d1be7e8cb4a2595e22ef4e3d55e4cff6719cea9ba83519eaa96.jpg)

whose right side is what the surviving steps of [??, ??] produce on their own, ??<sup>??−1</sup> ≈ ??<sup>??</sup> and their edits writing control fields of fibers other than ?? that the deletion does not touch. By Table 1 the deleted steps of ?? write no field but ??<sub>??</sub>, which Lemma 54(4) restores to ????????????????(⊥) at ??, no fiber being failed, and which it held at ??<sup>??−1</sup>.

An invariant carries the sufix. Write ??<sup>′??</sup> for the state the surviving steps reach at the point corresponding to ??. We claim, for every ?? > ??, that ??<sup>??</sup> ≈ ??<sup>′??</sup>, that every name of ?? is vestigial at ??<sup>??</sup> and absent from ??<sup>′??</sup>, and that the two states agree on every field of every name outside ??. At ?? = ?? + 1 this is the paragraph above together with Definition 47, which leaves each name of ?? retired by the accumulator that ran at ??, ????????????????(⊥) and holding an empty table, the fibers of ?? having no episode by hypothesis. The induction step is Lemma 57(1) applied at each name of ?? in turn: a step acting outside ?? has the same premises at the two states, reaches states again ≈-equal, and leaves the entries of ?? vestigial. A step acting on a name of ?? is one of the deleted ones, and Lemma 57(2) is why it has to be deleted rather than kept, an O-Retire or O-Remove of an absent name having no fiber to act on; by (1) again such a step moves no field outside ??, so dropping it preserves the invariant. Hence the final states are ≈-equal, and equal outside ??.

No surviving step loses a premise. A step acting on ?? ∉ ?? ∪ {??} reads ?? only through target (??) or relied (??). The first depends on ?? when ?? declares a key ?? provides, hence ?? ≺ ??, and when ?? registered ??, which puts ?? ∈ ??. In the first case ??’s episode does not close, by hypothesis, so it is open at ??<sup>??</sup> , where quiet gives ??<sub>??</sub> = target<sup>??</sup><sub>??</sub> and Lemma 70 puts its values among the ???????????? fibers, which ?? is not; since a key has at most one possible provider, ?? provided no key of ??<sub>??</sub> at ??’s L-Begin either. The second reads ?? only through the values of ??<sub>??</sub>, and deleting the episode can only make relied false, which relaxes the guard on L-Unload rather than blocking it. What such a step reads of a name of ?? is covered by the invariant. Pairwise independence is a property of the efect functions, so deleting steps preserves it. □

Theorem 73. (Confluence.) Let a sequence of steps reach a quiescent ??<sup>??</sup> at which no fiber is failed, let the steps be pairwise independent and every component be total on its provision (Definition 69), and let ?? be as in Definition 67. Then

1. (Canonical form.) ??<sup>??</sup> is reached, up to the names whose entries the reduction withdraws, from ??<sup>0</sup> by a sequence that takes the same orchestration steps in their original order, those at a fiber the orchestrator inserted preceding every lifecycle step and each of the rest following the step that registered the fiber it acts on, and that takes, for an enumeration ??<sub>1</sub>, …, ??<sub>??</sub> of ?? linearizing ⊲, one episode of each ??<sub>??</sub> in that order.

2. (Confluence.) Any two such sequences from ??<sup>0</sup> taking the same orchestration steps reach states related, after a renaming as in Lemma 56, by ≃ and by ≈.

Proof. For (1), the episodes of the sequence are of two kinds: those that close and those still open at ??<sup>??</sup> , which by quiet<sup>??</sup> and Lemma 70 are one episode of each fiber of ??.

Closing episodes go first, by induction on their number. At each stage pick a closing episode of a fiber ?? that is ⊲-maximal among the fibers whose episodes still close; one exists by Lemma 68 and the finiteness of ??. The three hypotheses of Lemma 72 are then met. No ?? with ?? ≺ ?? has a closing episode, by maximality. And no fiber ?? registers during [??, ??] has an episode: such a fiber is retired by the accumulator that ran at ?? (Definition 47) and by Lemma 54(5) stays retired, so its target view is ⊥ and Lemma 70 puts it outside ??, whence it has no episode open at ??<sup>??</sup> ; and ⊲ relates it to ?? through its parent pointer, so by maximality it has no closing one either. The lemma removes the episode, together with the steps of the names it registered, leaving ??<sup>??</sup> where it was up to those names. The measure drops by one, so no closing episode remains.

A fiber outside ?? takes no lifecycle step. It has no open episode at ??<sup>??</sup> , by Lemma 70 and quiet<sup>??</sup> , and no closing one now remains, so it has no episode at all and is ????????????????(⊥) throughout; L-Begin is the only rule that applies there, and applying it would open an episode.

Orchestration steps go next. An orchestration step at a fiber the orchestrator inserted moves one place earlier past a lifecycle step of a diferent fiber by Lemma 71(2), which applies because a step of a fiber of ?? registers no such name: registrations draw fresh names, whereas the name here is one an O-Insert of the original sequence introduced. With a lifecycle step of the same fiber there is nothing to exchange, an O-Insert of ?? already preceding every step of ?? and an O-Retire or O-Remove of ?? applying only outside ??, which takes no lifecycle step. Moving each to the front in turn preserves their relative order. An orchestration step at a fiber some activation registered cannot go to the front, its premises requiring that fiber to be present, so it stays where the registration put it; it acts outside ?? by the paragraph above and therefore commutes with everything between it and the registration by the same clause of Lemma 71.

Episodes are sorted and made contiguous, by induction on |??|. Let ?? be ⊲-minimal in ??. Then ?? ⌀ and ??<sub>??</sub> = ????????, since Definition 67 puts a provider of a key of ??<sub>??</sub> and the fiber registering ??<sub>1</sub> in ?? while ⊲ puts both below ?? . So target reads no field of another fiber and, no orchestration step remaining to write ?? and no fiber below ?? remaining to retire it, is constant. Every step acting on ??<sub>1</sub> is an activation step, no episode closing, and its remaining premises read ??<sub>??</sub> and ??<sub>??</sub> , which by Table 1 only ??<sub>1</sub> writes; each is therefore applicable at every earlier state, and Lemma 71 moves it one place earlier without moving the endpoint. The number of steps of other fibers preceding a step of ??<sub>1</sub> drops by one at each application, so the episode of ??<sub>1</sub> becomes an initial contiguous block. The argument repeats on ?? ∖ {?? } over the sufix that follows the block, where ?? is ???????????? throughout and takes no further step, so it too contributes a constant target. The enumeration this produces linearizes ⊲ by construction.

For (2), both sequences reduce by (1) to a canonical one, and the two reductions run over the same ?? up to a renaming. Definition 67 reads ??, ??, ??, and ??, of which the last three are written once with a fiber’s entry (Lemma 54(5)), so what has to be seen is that the same names come into existence carrying the same ??, ??, and ??, and that the same names are retired. Insertions the two sequences share by hypothesis. Registrations they share as well: an activation of a fiber of ?? registers, at each of its iterations, the component the iterator names there, which the second condition of Definition 60 holds fixed across interleavings, so the tree of registrations below an ??-fiber is a function of that fiber’s component; the names those registrations draw are not shared, and it is here that Lemma 56 is applied, matching the two trees by a bijection. And a retirement is either an orchestration step, shared, or the O-Retire an accumulator takes, which retires exactly the names the same activation registered. Two enumerations linearizing ⊲ difer by transpositions of incomparable episodes, which Lemma 71 again leaves the endpoint unchanged by, so the two canonical sequences agree. With the termination of Theorem 66, the lifecycle relation therefore has unique normal forms. □

Failure is excluded from the statement because it is a genuine source of divergence, and the calculus should not be read as denying it: whether a step raises depends on the state it ran against, so one schedule may fail a fiber where another completes it, and the two quiescent states then difer in that fiber’s lifecycle state. They do not difer in anything else, by Corol lary 62, which puts a failed fiber’s contribution to the state at nothing.

In the base calculus of Section 4.2 the same theorem holds, and the proof needs no substi tution beyond dropping one clause. L-Unload carries no guard there, so the last paragraph of Lemma 72 is vacuous; the rest of that lemma appeals to quiet<sup>??</sup> alone, which the base calculus supplies unchanged.

The theorem is what licenses reasoning about a Cordis application as though it were statically assembled. An orchestrator that adds a component, removes it, replaces a provider, and reverts the replacement is guaranteed to arrive at the state it would have obtained by writing the final composition down at the outset, and a component author reasoning about which coefects are in scope may reason about the quiescent state alone. It also delimits the guarantee: it speaks of the state, not of the emissions the system produced along the way, which is the distinction Section 6.1 draws between an acquisition, tracked inside the boundary, and an emission, which crosses it.

## 5. Implementation and Case Study

This section presents Cordis, which realizes the formal models of Section  3 as a practical programming abstraction. Cordis is a meta-framework of spatiotemporal composability: unlike application frameworks that target a specific domain (e.g., web routing, ORM, UI rendering), it prescribes no concrete scenario; its sole responsibility is to supply universal dynamic composition semantics. The implementation is layered into three tiers: (1) the core library (Section 5.1) implements the efect and coefect systems directly; (2) the component loader (Section  5.2) extends the core with configuration reconciliation and hot module replacement; and (3) application frameworks such as Koishi (Section 5.3) build domain-specific functionality on top of the former two tiers.

## 5.1. Core Library

Table  2 summarizes the correspondence between theoretical constructs and their runtime counterparts. In particular, we use the runtime names introduced below throughout this section, reserving the theoretical symbols for the formal correspondence. We also write @@name for a framework-internal symbol key, so the brackets in ctx[@@store] denote symbol-keyed access to an opaque slot on the context, rather than indexing into a string-keyed map.

![](images/4133c28ec80f46495b19a550d75c3a2d938e3a6baab4665c826743d8e37d72f4.jpg)  
Table 2 | Theory-to-implementation correspondence

The remainder of this section builds the core library from the bottom up. Section  5.1.1 realizes revertible efects, the sole primitive through which a context is mutated; Section 5.1.2 realizes reactive coefects over it; Section 5.1.3 composes both into the component lifecycle; and Section 5.1.4 exposes the context-level operations built on them.

## 5.1.1. Efect Tracking

This section realizes revertible efects (Section 3.1). Every context mutation in Cordis flows through a single primitive, ctx.effect: coefect provision, component instantiation, and every other context-mutating operation reduces to a ctx.effect call, so any operation performed through the context is automatically tracked and recovered upon component unloading. Operationally, ctx.effect is the realization of effect<sup>iter</sup> (Definition 52): it takes a callback of type ??<sup>iter</sup> and lifts it to ??<sup>iter</sup><sub>??Γ</sub> , yielding a dispose closure that, when invoked, recovers the efect. Cordis accepts both ??<sub>Γ</sub> and ??<sup>iter</sup><sub>Γ</sub> through this one operation (ad-hoc polymorphism); we take the iterator form as representative, since a plain efect function is the degenerate iterator that yields a single inverse. What the operation does not check is the witness that ??<sup>∗</sup> carries: the callback supplies an inverse, and that the inverse recovers the efect it accompanies is an obligation on the component author rather than a property the runtime verifies. Theorem 61 is where the calculus appeals to it, and Section 6.1 is where the obligation is delimited.

Algorithm 1 shows the construction of ctx.effect. We write ?? ∘ ?? for the disposer that runs ?? after ??, and id for the no-op; prepending each new inverse therefore yields LIFO recovery.

Algorithm 1 Efect tracking   
1 async function execute(callback, guard)   
2 iter ← callback()   
3 inverse ← id   
4 while guard()   
5 (value, done) ← await iter.next()   
6 if value then inverse ← value ∘ inverse   
7 if done then break   
8 return inverse   
9 function efect(ctx, callback)   
10 armed ← true   
11 task ← execute(callback, () ↦ armed)   
12 async function dispose()   
13 if not armed then return   
14 armed ← false   
15 recover ← await task   
16 recover()   
17 ctx.dispose ← dispose ∘ ctx.dispose   
18 return dispose

The engine execute drives the callback as an efect iterator (??<sup>iter</sup>, Definition 51) and folds the inverse yielded at each step into a single composite. Before each step it consults a callersupplied guard; once the guard trips, iteration stops and only the inverses accumulated so far remain. This is the step-boundary interruption of Section 4.3.2: the ??????????(??<sup>iter</sup>) continuation is realized by the iterator’s done flag together with guard.

ctx.effect is a thin wrapper over execute that adds two things. First, self-disposal: the guard reports the armed flag, and the returned dispose flips armed to false, which simultaneously halts any in-flight iteration and makes recovery fire at most once. Firing twice would apply an inverse at a state no application of the efect produced, where nothing holds it to reverting anything. Second, parent composition: dispose is prepended to the enclosing context’s accu mulated inverse ctx.dispose, so a child efect’s inverse is itself an efect on the parent, which is the recursive structure of ??<sup>2</sup>Γ. The component level (Section 5.1.3) reuses the same execute with a guard that tests the stability of fiber.target instead of armed.

## 5.1.2. Coefect Operations

This section realizes reactive coefects (Section 3.2). All coefect operations act on three symbolkeyed slots that each context carries:

• @@store: the value store ?? : (?? : ??) ⇀ ??︀ from realm symbols to typed values;

• @@isolate: the realm table ?? : Map(??, ??) from coefect keys to realm symbols;

• @@intercept: the interception table ?? : (?? : ??) → ℳ︀<sub>??</sub> assigning each key its metadata.

The first two compose into the two-layer resolution ?? → ??(??) → ??(??(??)): ctx.get(key) (Algorithm 2) reads the realm symbol ??(??) from @@isolate, then the bound value ??(??(??)) from @@store. The ?? indirection lets isolation redirect a key to an independent binding, whereas @@intercept is consulted only when a binding is accessed, adjusting how it is used rather than what it resolves to. We realize these operations in two parts: (1) provision and notification, which install or retract bindings and propagate the change to dependents; and (2) isolation and interception, which reshape how a key resolves.

Provision and notification. Since set(??, ??) has type ?? (Section 3.1), coefect provision is a ctx.effect call and inherits its automatic tracking and recovery. Algorithm 2 implements ctx.set(key, value), the concrete set(??, ??): the callback binds a value into the store under the realm symbol ??(??), and the returned dispose function removes it. Both installation and removal invoke notify to propagate the change to dependent components.

Algorithm 2 Coefect operations   
1 function get(ctx, key)   
2 realm ← ctx[@@isolate][key] ▷ ??(??)   
3 return ctx[@@store][realm] ▷ ??(??(??))   
4 function set(ctx, key, value)   
5 function callback()   
6 realm ← ctx[@@isolate][key] ▷ ??(??)   
7 ctx[@@store][realm] ← value ▷ ??[??(??) ↦ ??]   
8 notify(ctx, [key])   
9 return function()   
10 delete ctx[@@store][realm] ▷ ?? ∖ ??(??)   
11 notify(ctx, [key])   
12 return ctx.efect(callback)

Algorithm 3 propagates each binding change to dependents by testing, for each live fiber, whether a changed key appears in its fiber.inject and resolves to the same realm; if so, it calls refresh (Section 5.1.3) to re-evaluate that fiber against the new state, and it returns the fibers it re-evaluated so that a caller can wait for them. This is the reactive classification of Definition 26: a change that flips satisfaction activates or deactivates the fiber, and refresh’s idempotence renders a neutral change harmless. The interaction of this re-evaluation with diverse control flows is developed in Section 5.1.3.

Algorithm 3 Reactive notification   
1 function notify(ctx, keys)   
2 afected ← ⌀   
3 for fiber in all\_fibers do   
4 for key in keys do   
5 if key ∈ fiber.inject and fiber.ctx[@@isolate][key] = ctx[@@isolate][key] then   
6 refresh(fiber)   
7 afected ← afected ∪ {fiber}   
8 break   
9 return afected

A binding counts as available to a dependent only while the fiber that installed it is ACTIVE, so refresh resolves each declared key against an active provider rather than against the store alone. This is the provided by relation of Definition  46, and it is what makes a withdrawal visible to dependents one step before it happens: a provider that has entered UNLOADING has stopped providing, so its dependents recompute an unsatisfied target view and begin their own teardown while its bindings are all still in place.

Isolation and interception. The two operations do structurally the same thing: each derives a child context that adjusts one inherited table for key, leaving the parent untouched, so recovery is implicit: discarding the child context sufices, with no explicit inverse to run. ctx.isolate(key, realm) overrides the realm mapping ?? with realm, or a freshly generated symbol by default (realizing isolate, Definition  29), so two contexts that assign diferent symbols to the same key resolve to independent bindings. ctx.intercept(key, metadata) merges metadata into the interception table ?? (realizing intercept, Definition 31): following that definition, the new metadata is combined with whatever the context already carries for key and takes priority over it.

## 5.1.3. Component Lifecycle

A component is instantiated as a fiber by ctx.use. This section gives the fiber (introduced in Section 5.1) operational meaning as the inertial state machine of Section 4.3.3. Two fields drive the algorithm below: fiber.parent, the parent context of fiber.ctx that forms the component hierarchy (the recursive structure of Γ , Section 3.3.1), and fiber.inertia, a handle to the inflight asynchronous transition (or null if idle).

Algorithm  4 shows component instantiation. A component pairs a coefect specification component.inject (??) with an efect function component.apply; instantiation binds the component’s config into fiber.apply (Line 9), the config-applied efect function (??) that the lifecycle then runs. The callback function (Line 2) is the efect tracked in the parent fiber: when executed, it initiates the child’s lifecycle by calling refresh (Algorithm  5); when recovered, it forces the child’s target to ⊥ and triggers unload. This is the registration primitive of Definition 47, with callback as its O-Insert and the closure callback returns as its O-Retire: an instantiation is an ordinary tracked efect of the parent, so unloading a parent cascades to its children.

2 function callback()   
3 refresh(fiber)   
4 return function()   
5 fiber.target ← ⊥   
6 unload(fiber)   
7 fiber ← Fiber(parent: ctx, inject: component.inject)   
8 fiber.ctx ← ctx[fiber ↦ fiber]   
9 fiber.apply ← () ↦ component.apply(fiber.ctx, config)   
10 ctx.efect(callback)   
11 return fiber

Algorithm 5 realizes the inertial state machine of Section 4.3.3, in which reload and unload are inertial: once entered, a transition runs to completion before the system responds to a targetstate change. It uses two auxiliary lookups over the coefect store: resolve(inject) returns the bindings the declared keys currently resolve to, and provided(fiber) returns the keys whose binding this fiber installed. The refresh function recomputes fiber.target from the coefect store and, if the fiber is not already in a transition, initiates either a reload or unload task<sup>2</sup>. The reload function records the current target and executes the component’s efect function apply. Upon completion, it checks whether the target still matches: if so, the fiber enters ACTIVE; if not (regardless of whether the new target is ⊥ or a diferent set of providers), it chains into unload. Symmetrically, unload recovers all tracked efects in LIFO order and then either enters INACTIVE or chains into reload. This mutual recursion implements the inertial property: once a transition begins, it completes before any new transition can start.

Algorithm 5 Component lifecycle   
1 function refresh(fiber)   
2 target ← target(??, ??)   
3 if target = fiber.target then return   
4 fiber.target ← target   
5 if fiber.inertia then return   
6 if target ≠ ⊥ then   
7 fiber.state ← LOADING   
8 fiber.inertia ← create\_task(reload(fiber))   
9 else   
10 fiber.state ← UNLOADING ▷ out of service before any inverse is scheduled   
11 fiber.inertia ← create\_task(unload(fiber))   
12 async function reload(fiber)   
13 target<sub>0</sub> ← fiber.target   
14 fiber.committed ← resolve(fiber.inject) ▷ commit the view   
15 recover ← await execute(fiber.apply, () ↦ fiber.target = target<sub>0</sub>)   
16 fiber.dispose ← recover ∘ fiber.dispose   
17 if fiber.target = target<sub>0</sub> then   
18 fiber.state ← ACTIVE

19 notify(fiber.ctx, provided(fiber))   
20 fiber.inertia ← null   
21 else   
22 fiber.state ← UNLOADING   
23 fiber.inertia ← create\_task(unload(fiber))   
24 async function unload(fiber)   
25 await all(notify(fiber.ctx, provided(fiber)).map(f ↦ f.await())) ▷ drain dependents   
26 await fiber.dispose()   
27 fiber.dispose ← id   
28 fiber.committed ← ⊥   
29 if fiber.target = ⊥ then   
30 fiber.state ← INACTIVE   
31 fiber.inertia ← null   
32 else   
33 fiber.state ← LOADING   
34 fiber.inertia ← create\_task(reload(fiber))

fiber.target is computed by resolving each declared key against the current coefect store and tupling the uid of the fiber that provides it, so it is a digest of target(??, ??) (Definition 46). Identifying a binding by its provider rather than by its value is what makes a single comparison against the recorded target suficient: a uid is drawn fresh and never reused, so a provider that is replaced cannot be mistaken for the one it replaced, even when the two provide equal values. Since notify (Section 5.1.2) recomputes the target on every coefect change, a fiber reloads precisely when one of its declared keys comes to be provided by a diferent fiber. A provider that overwrites its own binding in place is therefore not observed; a component that wants its replacement to propagate withdraws the binding and installs it afresh.

The algorithm operates at two complementary levels. At the transition level, reload and unload check the target at completion, enabling inertial chaining across transitions. At the iteration level within each transition, the efect execution (Algorithm 1) checks the target at each iteration boundary, enabling partial rollback within a single transition. These two mechanisms correspond to the inter-transition chaining of Section 4.3.3 and the intra-transition staleness check that Theorem 64 rests on.

Three lines carry the coefect ordering of Theorem 63, and where each of them sits is what makes the ordering hold. reload commits the resolved view at Line 14 and unload discards it only after every inverse has run, so a fiber reads the same bindings for as long as it is loaded, its own teardown included. refresh marks the fiber UNLOADING at Line 10 before the transition task is created, which is the L-Leave step: the fiber stops providing, and the dependents recompute against that before any of its inverses is scheduled. unload then waits at Line 25 for each notified dependent to reach INACTIVE, which is the guard on L-Unload; notify admits a dependent only when its declared key resolves to the same realm symbol as the provider’s, which is the runtime form of the guard’s demand that the dependent see the key from this fiber rather than merely declare it. The wait sits ahead of the whole recovery rather than inside one of the inverses being waited on, since fiber.dispose initiates a fiber’s efects concurrently and a wait placed within one of them would leave the rest unordered. Termination follows Theorem 66: a fiber only ever waits on dependents that have already stopped being satisfiable, and a dependent that is itself a provider waits the same way for its own, so the provider graph is traversed on demand rather than analyzed in advance.

## 5.1.4. Context Access

The coefect operations of Section  5.1.2 form a reflective API: a coefect is written with ctx.set(key, value) and read with ctx.get(key), both keyed by name. Cordis layers a second, more native way to extend and consume the context on top of this reflective API: property access. A component can access a coefect as the property ctx[key], as if it were native structure of the context, rather than through a method call. In TypeScript, Cordis realizes this with a Proxy whose get trap mediates every property access. Algorithm 6 shows how a context resolves such an access to a coefect, atop the primitive get of Section 5.1.2.

Algorithm 6 Proxy-mediated context access   
1 function resolve(ctx, key)   
2 fiber ← ctx.fiber   
3 repeat   
4 if key ∈ fiber.committed then return fiber.committed[key]   
5 if key ∈ fiber.inject then throw INACTIVE\_ACCESS   
6 if fiber = root then throw UNDECLARED\_ACCESS   
7 fiber ← fiber.parent.fiber

Algorithm  6 walks the fiber chain upward from the accessing context: at the first fiber whose committed view binds key, the access is authorized and that binding is returned; if the walk reaches a fiber that declares key without having committed it, the fiber is not loaded and the access fails; and if it reaches the root without any declaration, the access is rejected as undeclared. This is where the proxy difers from the bare ctx.get: ctx.get(key) is a lookup against the store that returns the bound value or nothing and never fails, whereas the proxy resolves against the accessing fiber’s own view and enforces the coefect specification ?? at the point of use. Reading the view rather than the store is also what Theorem 63 rests on, since it is what keeps a dependency readable to a component whose teardown was triggered by that dependency going away.

This rejection is a runtime check performed at the point of access. Because a component’s coefect specification ?? is declared statically, the same violation is in principle detectable at compile time, by resolving each ctx[key] against the declared ?? before execution; Section 6.4 discusses how a host language’s type-level dependency declarations and compile-time metaprogramming can carry out exactly this mediation.

## 5.2. Component Loader

The core library equips component developers with imperative primitives for dynamic composition, such as ctx.effect, ctx.use, and ctx.set. A separate concern arises for application orchestrators, who assemble pre-existing components into a running system and adjust the composition over its lifetime. The component loader addresses this concern by introducing a de clarative configuration layer: the orchestrator specifies the desired composition as a persistent data structure, and the loader translates changes to this specification into the corresponding imperative fiber operations.

## 5.2.1. Declarative Configuration

Section 4 decomposes a running system into fibers, each an instantiation of one component. Everything an instantiation needs can be declared, so an orchestrator can describe a whole system as a declarative configuration: a persistent record that the loader realizes as fibers and keeps in step with them.

Entries. A configuration consists of entries. Each entry specifies a fiber and manages it, and the binding runs in both directions: the loader responds to a change in an entry’s fields by adjusting the fiber, and a component that revises its own configuration or disables itself has the change written back to its entry.

Definition 74. An entry declares a single fiber, recording:

• id — a stable identifier, used as the reconciliation key when its group’s child list changes;

• url — the URL of the component module to instantiate;

• isolate — an isolation annotation applied to the entry’s context;

• intercept — an interception annotation applied to the entry’s context;

• config — the configuration bound into the component to form its efect function apply;

• disabled — whether the entry is administratively turned of.

An entry can serve as a faithful specification because what supports a fiber is exactly what an entry records. The support set of Definition 67 reads ??, ??, ??, and ?? and nothing else, and an entry gives all four: disabled gives ??, the entry’s parent in the tree gives ??, and url selects the component which declares ?? and ??. The fields the support set leaves unread are the fiber’s runtime state, which an instantiation does not need either, and Lemma 70 identifies the support set with the ???????????? fibers of a quiescent state (Definition 49) as far as each component installs every key it declares (Definition 69).

These entries form a configuration tree that is the authoritative record of what the system loads. An entry may be a leaf mapping to a single fiber, or its component may in turn load further components, making the entry a branch node. Cordis provides components for such grouped and nested loading: @cordisjs/group takes a list of child entries as its configuration and loads them as a subgroup, and @cordisjs/include loads an external configuration file (YAML or JSON) and grafts its entries in as a nested subtree. Both are ordinary components resting on the registration primitive of Definition 47 (Algorithm 4), so a nested tree stays within the calculus and the results below hold of it.

Reconciliation. When an entry’s record changes, the loader reconciles incrementally rather than tearing the fiber down and rebuilding it wholesale. Reconciling this way is sound for reasons the metatheory supplies.

• Theorem 73 makes the quiescent state a function of the final configuration alone: whatever instantiations and retirements the loader performs on the way, and in whatever order, the system quiesces where a load of the final configuration from scratch would have left it. Which components end up loaded is read of the declarations only as far as each of them installs every key it declares (Definition 69); a component that declares a key and installs it under some configurations alone is one the loader can still reconcile, but the set of loaded components then answers to those configurations as well.

• Theorem 66 proves that the system does quiesce, so a reconciliation is complete once its instantiations and retirements have been issued.

• Corollary 62 puts a departing fiber’s contribution to the state at nothing, so rebuilding one entry withdraws what its fiber installed and leaves the fibers around it as they were.

• Theorem 63 lets the entries be instantiated together, with no load order for the orchestrator to arrange: a fiber whose declared keys are not yet provided waits at its L-Begin, and one whose provider leaves is deactivated ahead of it. A dependency therefore constrains when a fiber activates rather than when its module is fetched and evaluated, so the loader loads modules concurrently, where bringing up a large configuration spends its time.

On top of the fiber that an entry declares, the loader dispatches on which of the entry’s fields changed and applies the least disruptive operation for each.

• id, url — rebuilds the entry, since its identity or its component has changed;

• isolate — reassigns the entry’s realms (Algorithm 7);

• intercept — updated in place, as interception metadata is consulted at read time and needs no reload;

• config — handed to the component, which decides how to apply the new payload, typically by difing it against the previous one and reloading only on a material change. In particular, an @cordisjs/group entry’s config is its list of child entries, so it applies the update as a keyed dif over child ids, creating, removing, or updating each child; since updating a surviving child re-enters this same per-field dispatch, group reconciliation and entry update recurse together down the tree;

• disabled — unloads the fiber when set and reloads it when cleared.

Managed realms. Isolation in the core derives a child context overriding the realm table ?? at one key (Section 5.1.2), which sufices while the context tree stands still. An entry may be moved between groups at runtime, so the loader manages realms of its own, and the isolate field selects between two scoping rules per key. A value of true asks for a local realm, private to the entry and tagged by its id, which the entry carries with it wherever it moves; a string asks for a global realm shared by every entry naming that string, so moving such an entry changes which entries it shares a binding with rather than which realm it belongs to. A realm is discarded once no entry names it.

Reassigning an entry’s realms turns on which keys changed realm, whether the entry is itself the provider at a changed key, and which dependents to notify. The middle question is the hard one, since a realm symbol may be shared by several fibers of which only one is the provider. The loader answers it with delimiters: one symbol ??<sub>??</sub> per key, under which each context stores a tag of its own. A delimiter is written on a context and inherited by its descendants, so the entry’s tag and the provider’s agree exactly when the two were derived within one isolate scope for ??, which is the case in which the binding at ?? is the entry’s own and has to move with it.

Algorithm 7 Isolation realm reassignment   
1 function patch\_isolation(entry, ??<sup>′</sup>)   
2 ?? ← entry.ctx[@@isolate]   
3 store ← entry.ctx[@@store]   
4 Δ ← {?? | ??(??) ≠ ??<sup>′</sup>(??)} ▷ keys whose realm changes   
5 for ?? in Δ do   
6 entry.ctx[??<sub>??</sub>] ← fresh tag   
7 dif[??] ← (??(??), ??<sup>′</sup>(??), entry.ctx[?? ], store[??(??)].fiber.ctx[?? ])   
8 entry.ctx[@@isolate] ← ??<sup>′</sup>   
9 reload(entry.fiber)   
10 for ?? in Δ do

11 (?? , ?? , ?? , ?? ) ← dif[??]   
12 if ?? = ?? and store[?? ] and not store[?? ] then ▷ the binding is the entry’s own   
13 store[?? ] ← store[?? ]   
14 delete store[?? ]   
15 function afected(fiber, ??)   
16 (??<sub>1</sub>, ??<sub>2</sub>, ??<sub>1</sub>, ??<sub>2</sub>) ← dif[??]   
17 return fiber.ctx[@@isolate][??] ∈ {??<sub>1</sub>, ??<sub>2</sub>} and (fiber.ctx[??<sub>??</sub>] = ??<sub>1</sub>) ≠ (??<sub>2</sub> = ??<sub>1</sub>)   
18 notify(entry.ctx, Δ, afected) ▷ in place of the realm test of Algorithm 3

The test turns on one property of delimiters. The tag under ??<sub>??</sub> is written on the entry’s context and inherited by every context derived from it, and it is drawn afresh at each reassignment, so for a context ??<sup>′</sup>

![](images/f401b4675e0fbc9c1b0714ceac0ae9dd3d679d4264eed36b20289003f7ddcfb4.jpg)

(65)

Write own(??<sup>′</sup>) for that condition, of which ?? = ?? is the instance at the provider. The reassignment moves the contexts satisfying own from ?? to ?? and leaves the others where they are, and by the loop above it moves the binding to ?? exactly when the provider satisfies own. A dependent sees the binding while its own realm at ?? is the realm the binding sits in. Where own agrees on the dependent and the provider, both move or neither does, so the dependent sees the binding afterwards exactly when it saw it before. Where own separates them, one side moves and the other stays, so the dependent gains or loses the binding. The inequality is that separation, and the membership test drops the dependents resolving ?? in neither realm, which no part of the move reaches.

## 5.2.2. Hot Module Replacement

Hot module replacement (HMR) applies the revertible-efect pattern at the module level: when source files change, typically during development, the system replaces the afected modules in-place without restarting the process. Because a fiber already bounds all of its component’s efects and coefects, a module that is itself a component can be replaced through fiber operations alone: disposing the old fiber recovers everything the component installed, and a new fiber instantiated from the reloaded module reinstalls it. HMR therefore needs no developerannotated acceptance boundaries, as opposed to Webpack [46] or Vite [47] HMR.

The @cordisjs/hmr component provides the HMR engine, which operates in three phases.

Phase 1: Module classification. The engine takes two inputs: the stashed set (file URLs whose contents have changed since the last reload) and the externals set (modules that cannot be hot-replaced and instead trigger a full restart). Writing get\_imports(url) for the modules that url directly imports, it classifies the changes’ dependency subgraph, marking each module accepted or declined:

Algorithm 8 Module classification   
1 function classify(stashed, externals)   
2 accepted ← stashed   
3 declined ← externals   
4 pending ← ⌀   
5 for url in stashed do

6 pending ← pending ∪ (get\_imports(url) ∖ (accepted ∪ declined))   
7 repeat   
8 progress ← false   
9 for url in pending do   
10 if get\_imports(url) ∩ accepted ≠ ⌀ then   
11 accepted ← accepted ∪ {url}   
12 pending ← pending ∖ {url}   
13 progress ← true   
14 else if get\_imports(url) ⊆ declined then   
15 declined ← declined ∪ {url}   
16 pending ← pending ∖ {url}   
17 progress ← true   
18 else   
19 pending ← pending ∪ (get\_imports(url) ∖ (accepted ∪ declined))   
20 until not progress   
21 declined ← declined ∪ pending   
22 return (accepted, declined)

Seeded with the imports of the stashed files, the fixed point accepts a module once one of its imports is accepted and declines one once all of its imports are declined; any module left undecided, caught in an import cycle, defaults to declined.

Phase 2: Stale-entry detection. Using accepted and declined, the engine then filters the component entries down to the stale ones, whose dependency tree reaches a changed module. It walks each entry’s tree with get\_dependencies, which collects the transitive imports of a module while respecting declined as a boundary:

Algorithm 9 Stale-entry detection   
1 function get\_dependencies(root, declined)   
2 deps ← ⌀   
3 function traverse(url)   
4 if url ∈ deps or url ∈ declined then return   
5 deps ← deps ∪ {url}   
6 for child in get\_imports(url) do traverse(child)   
7 traverse(root)   
8 return deps   
9 function detect(entries, accepted, declined)   
10 stale\_entries ← ⌀   
11 for entry in entries do   
12 tree ← get\_dependencies(entry.url, declined)   
13 if tree ∩ accepted ≠ ⌀ then   
14 accepted ← accepted ∪ tree   
15 stale\_entries ← stale\_entries ∪ {entry}   
16 return stale\_entries

An entry is stale exactly when its tree intersects accepted; that tree is then folded into accepted, so every stale module along it is invalidated in the next phase.

Phase 3: Transactional reload. Finally, the engine reloads the stale entries. It invalidates the accepted modules’ caches<sup>3</sup>, backing up each removed module to enable rollback, then reimports each stale entry’s component module by its url and swaps in a fresh fiber:

Algorithm 10 Transactional module reload   
1 function reload(ctx, accepted, stale\_entries)   
2 backup ← invalidate\_caches(accepted)   
3 try   
4 for entry in stale\_entries do   
5 entry.fiber.dispose()   
6 entry.fiber ← ctx.use(import(entry.url), entry.config)   
7 catch error   
8 restore\_caches(backup)   
9 for entry in stale\_entries do   
10 entry.fiber.dispose()   
11 entry.fiber ← ctx.use(backup[entry.url], entry.config)   
12 throw error

The transactional guarantee ensures that the system never enters a half-reloaded state: if any module fails to import (e.g., due to a syntax error), the caches are restored and every stale entry is rebuilt from backup[entry.url], the previous component whose cache was just restored, undoing the swaps already made.

## 5.3. Case Study: Koishi

Koishi is an open-source chatbot application framework built on Cordis<sup>4</sup>. Over four years of development, it has accumulated over 4000 community-contributed plugins<sup>5</sup>, ranging from instant-messaging (IM) adapters and database drivers to administrative consoles and enduser features. Its scale and diversity make it a representative validation of Cordis’s dynamic composability in a production setting.

Expressiveness and generality of the meta-framework. Koishi runs as a server-side bot whose every feature is realized as a plugin over the context primitives of Section 5.1; Koishi itself contributes only the chatbot-domain vocabulary. The same model reappears in a wholly diferent runtime: Koishi’s web console is a second, independent Cordis application whose plugins compose the primitives of the browser and its user interface rather than those of the server. The disparate settings above establish two properties of the model of Section 3. (1) It is expressive: its primitives sufice to carry a complete production system, the host framework supplying only domain vocabulary. (2) It is general: it fixes how efects and coefects compose while leaving their meaning to each application, and so presupposes neither a particular domain nor a particular runtime.

Temporal composability without cognitive overhead. The plugin systems surveyed in Section 1.2.1 cannot unload an individual extension’s efects without restarting the extension host. Koishi routinely performs this operation: an orchestrator disables a plugin from the console and its efects are withdrawn in place; during development, the HMR engine re-applies edited plugins on save while preserving cache state and live connections elsewhere in the system. Cordis makes such removal not merely possible but efortless for the plugin author. Because efects performed through the context are tracked and their inverses composed automatically (Section 3.1), even an inexperienced author obtains ordered cleanup for a plugin’s context-mediated efects without writing an uninstall path. This achieves the locality of concern whose absence Section 1.2.1 identifies: correctness that would otherwise rest on each author’s diligence is instead discharged once, by the abstraction.

Spatial composability across an open ecosystem. In contrast to the plugin systems of Section 1.2.1, where inter-plugin dependencies are largely absent, Koishi’s ecosystem exhibits a genuine dependency topology: IM adapters provide access to each messaging platform, database drivers provide persistent storage, and functional plugins declare these as coefects and access them. Reconfiguring a provider at runtime, such as switching the storage backend or reconnecting an adapter, reactivates only the dependents whose resolved dependency changed (Section 3.2); a plugin whose dependency is unavailable stays inactive until it appears, without erroring. What the case study substantiates is that this composition holds across independently authored code: a plugin and its dependencies are typically written by diferent authors who coordinate on nothing beyond the coefect that connects them, so reactive coefects keep the assembly consistent across an open ecosystem of independent contributors.

Threats to validity. The evidence here is drawn from a single ecosystem in a single host language, so it cannot separate the merits of the paradigm from those of its TypeScript realization or of Koishi’s particular domain, and it is observational rather than a controlled comparison against an alternative architecture. What the case study establishes is thus an existence-andadoption result rather than a quantitative one; measuring the abstraction’s overhead and its efect on developer productivity against a baseline remains future work.

## 6. Discussion

The formal model and implementation presented in the preceding sections introduce a programming paradigm for dynamic composability. This section examines how the paradigm extends to broader engineering concerns, and discusses the design tensions and open prob lems.

## 6.1. System Boundary

Every efect in Section 3.1 carries an inverse, and what that inverse amounts to is settled by the system boundary. The boundary divides the environment a system runs against into two parts. (1) A location lies inside when the system is able to modify it exclusively and to restore the state before that modification, so an operation on it is tracked in Γ and can be recovered later. (2) A location lies outside when either ability fails, so an operation on it acts as id and is therefore neither tracked nor recovered. This section develops the properties of this boundary and their consequences for recovery.

Boundaries from coefects. A coefect moves the boundary by reifying an external location: it confines every access to that location to a set of operations it provides, each of which it can supply an inverse for, so operations that acted as id come to be tracked in Γ and recovered. The boundary is therefore drawn per location rather than per medium, since both aforementioned abilities are properties of a location, and reification changes how a location is accessed while leaving its medium as it was. For example, a memory region lies inside when the system alone writes it, and outside when other processes write it too; a file lies inside when only the system can reach it, as with a scratch file under a private path, and outside when it is a path other programs read or write. Moving the boundary is itself a trade-of, between whether the environment provides revertible semantics for a location and what supplying those semantics costs on every access. We take up the co-design this suggests in Section 6.7.

Acquisition and emission. An operation that reaches outside the boundary generally proceeds in two stages. (1) In the acquisition stage, the operation obtains access and installs a record inside the boundary: open installs a descriptor that close removes, malloc reserves a block that free releases, fork starts a child process that kill terminates. The record itself is part of the coefect that reifies the location, e.g. an entry in a map it keeps, and installing that entry is a revertible efect. That record is at the same time the channel along which data can leave. (2) In the emission stage, the operation pushes data through that channel, as with the bytes a write hands to the file or the datagram a send puts on the wire, and the push acts as id<sub>Γ</sub>, leaving the data where other parties may read and write it. The two stages therefore fall on opposite sides of the boundary: the acquisition stays inside it, whereas the emission crosses to the outside.

Withholding and compensation. A system that must nonetheless recover from an emission has two approaches available. One is to withhold an emission until the state that produced it is certain to persist, which is the output commit problem of rollback-recovery [48]. The other is compensation [49]: an action that restores the state up to an equivalence the application supplies, coarser than the ≃ of Definition 33, as in deleting a file that was created or refunding a charge that was made. Such actions compose in the same LIFO order as inverses do, so the composition of Section 3.1 transfers to them. The metatheory does not: the commutation of Definition 60 is proved against ≃ and has to be re-established against the coarser one.

## 6.2. Service Multiplexing

Dynamic component platforms such as OSGi [50] organize composition around services: units of functionality that a provider publishes under an interface and a consumer binds to. The Cordis coefect model echoes this notion, with a service corresponding to the interface behind a key. Components that provide a service are its providers, and components that inject a service are its consumers. A single service may be implemented by multiple providers, and this multiplicity can be realized in two forms. (1) Exclusive binding: several implementations share one interface but at most one is bound at a time; the orchestrator selects which implementation is bound, and switching between them requires unloading one provider and loading another, momentarily perturbing every consumer’s dependency. (2) Service broker: a central service that acts as the entrypoint for the interface is injected by both the backing providers and the consumers, so that multiple providers coexist and the broker dispatches each request among them. Compared to exclusive binding, the broker absorbs this perturbation: updating a backing provider leaves the broker in place, so consumers see no change to their dependency and no reload is triggered.

The service broker underlies three capabilities: load balancing, rolling updates, and crossprocess invocation.

Load balancing. When several providers coexist, the broker distributes requests among them according to a configurable policy (e.g., round-robin, least-loaded, latency-weighted) or an explicit target named by the consumer. Because providers are ordinary components, they can be added or removed to scale capacity up or down; each provider registers with the broker through a revertible efect, so unloading it reverts the registration and drops it from the broker’s routing set automatically.

Rolling updates. Upgrading a service implementation at runtime reduces to a controlled provider transition [51, 52]. To carry out the transition, the new provider is loaded as an additional fiber and registers with the broker; once it becomes ACTIVE, trafic is gradually shifted from the old providers to the new one (e.g., by adjusting selection weights), and the old providers are unloaded once they no longer carry in-flight requests. This provider transition turns what is traditionally an infrastructure-level operation (e.g., container orchestration, bluegreen deployment) into an application-level composition pattern.

Cross-process invocation. The service broker can also be applied across process boundaries [53]. Each process hosts its own Cordis context with local providers; a coordinating component links them, treating each as a remote provider. Cross-process service access is mediated by an RPC mechanism that preserves the interface, making the distribution transparent to consumers. One caveat is that a cross-process call incurs latency and may fail mid-flight, so exposing it synchronously would block the caller. An interface intended to be exposed across processes must therefore be designed against an asynchronous contract.

## 6.3. Access Control and Sandboxing

Given an application assembled from independent components, securing the application calls for two complementary mechanisms: (1) constraining what dependencies a component may access, and (2) sandboxing untrusted code from the host environment. Cordis supports the first through dependency declarations and interception; the second requires an external sandbox.

Capability-based access control. The dependency access mechanism (Section  5.1.4) already constitutes a form of access control over proxy-mediated properties: a component can only access dependencies it has declared; an undeclared access raises an error. This is structurally similar to capability-based security [54–56], where authority is conferred by possession of a reference rather than by ambient authority. The inject declaration acts as a capability request, and the context proxy acts as a capability mediator. Since these requests are declared statically, the complete set of proxy-mediated capabilities a component requires is known before it runs, letting the orchestrator review and approve them at load time rather than discovering accesses as they happen.

This mediation generalizes to fine-grained policy through the interception mechanism. Access-control metadata can be carried by contexts or declared by components (Definition 30), and the provider consults it when the dependency is invoked to decide whether a request is permitted. For example, a filesystem dependency may carry metadata declaring which paths a component may read or write, and the provider checks each call against the metadata. Because this interception lives on the context rather than in either party’s code, an orchestrator can adjust it to constrain any component’s access to a dependency without modifying the provider, e.g., granting read-only database access to a community component whereas a core component retains full access. Moreover, since interception afects only how a dependency is invoked, not whether it is satisfied, it can be installed, reconfigured, or removed at runtime without triggering any reload or perturbing the dependency graph.

Sandboxing untrusted components. When a component’s code cannot be trusted, lan guage-level access control is insuficient, since a malicious component with access to the host runtime can reach the underlying objects directly, rendering such checks moot. Sandboxing requires an execution boundary beyond the reach of language-level means, such as software fault isolation [57], a separate language runtime, a sandboxed process, or a virtualized con tainer [58]. Whatever the mechanism, the untrusted component runs in its own sandboxed context and reaches host-provided dependencies through a bridge, generalizing the crossprocess invocation of Section 6.2: the same transparency argument renders this bridged access indistinguishable from local injection. On the host side, the bridge is an ordinary fiber whose capabilities can be attenuated by the access control described above.

## 6.4. Language Independence and Selection

Although Cordis is implemented in TypeScript, the context paradigm is language-agnostic: spatiotemporal composability is defined only by its two composability dimensions, and thus can be realized in any language that meets certain requirements along both. We analyze these requirements along each dimension in turn.

Temporal composability. At its most basic, temporal composability requires closures: a revertible efect pairs an action with an inverse, and that inverse must be captured as a value, along with the state it restores, so it can be replayed on teardown. Beyond this, a component’s code and the side efects of loading it must be introducible and retractable at runtime.

How a language meets this second requirement depends on its execution model. In managed runtimes, this takes the form of a programmatic module registry, where a loaded module can be evicted from the registry and garbage-collected once unreferenced; Node.js, for instance, exposes such a registry.<sup>6</sup> Native code exposes no module registry, so introduction and retraction take the form of explicit dynamic linking and unlinking (e.g., dlopen/dlclose on Unix, LoadLibrary/FreeLibrary on Windows) [59], i.e., loading object code into a running process and later detaching it. WebAssembly takes one path or the other depending on its embedder: a module instance is reclaimed by the host’s collector under a managed embedder (e.g., a JavaScript host), or released when a native embedder drops it (e.g., Wasmtime). Across these mechanisms, the revertible efects model treats loading as an efect on the context, with inverses that undo the registration of symbols, types, or handlers the module introduced.

Spatial composability. Spatial composability requires a mechanism for components to declare their dependencies and for the runtime to provide and inject these dependencies. This reduces to a dependency injection (DI) problem [38], which manifests at two levels that difer across languages: how dependencies are typed and how their access is mediated.

At the type level, the language should provide a way for developers to express well-typed dependency access. A consumer obtains a coefect by reading its key from the context, so the context type (Section 3.2.1) must record each key’s coefect. Typeclasses (Haskell) [60] and traits (Rust) [61] achieve this by letting a provider extend the context type from its own module through an instance or impl [62]. TypeScript’s module augmentation [63] likewise lets a provider module merge declarations into the context type.

At the runtime level, dependency access must be dynamically mediated: the coefect behind a key may change as providers are loaded and unloaded, and may be resolved diferently across contexts. The language therefore needs a way to interpose on access transparently, leaving the consumer’s code unchanged, e.g., via JavaScript’s Proxy object [64] or Python’s descriptor protocol (\_\_get\_\_) [65]. Absent such a primitive, runtime reflection [66, 67] can mediate access dynamically, at the cost of type safety and developer experience.

Across both levels, metaprogramming facilities supply the typing and the mediation together. Annotations [68] and decorators attach metadata to a declaration, which a processor expands into the accessor that mediates access; compile-time metaprogramming (e.g., Rust procedural macros, Scala macros [69], Zig comptime) emits, for each dependency, a typed declaration together with such an accessor, dispensing with a general-purpose interception primitive.

## 6.5. Mutual Dependencies and Component Granularity

In the reactive coefect model, a dependency cycle simply leaves the involved components permanently inactive: given two components ?? and ??, if ?? requires a key provided by ?? and ?? a key provided by ??, neither’s satisfaction predicate can ever become true. Unlike deadlock in concurrent systems, which depends on the schedule and must be detected as it happens, this condition is predictable from the dependency declarations alone, so a runtime can report it when components are loaded.

In practice, most apparently mutual dependencies can be decomposed into finer-grained components that eliminate the cycle. Consider two components: a server (providing a network interface) and an access controller (enforcing authorization policies). The two components interact bidirectionally: the access controller mediates requests arriving at the server, and the server exposes an endpoint for modifying access-control policies. A monolithic design would make each component depend on the other. However, the two interaction directions are logi cally independent concerns. Decomposing them yields four components: server-core, accesscontrol-core, request-mediation (depending on both cores to apply access control to incoming requests), and policy-management (depending on both cores to expose policy modification via the server). Through this approach, the cycle is eliminated because neither core depends on the other; only the integration components depend on both.

This decomposition is always possible in principle, since every bidirectional interaction can be factored into independent unidirectional bindings, but it increases the number of components: in the general case, given ?? mutually interacting components, the number of integration components can grow quadratically with ??, since each pair of interacting compo nents may require a distinct component for each direction of interaction. This does not afect correctness or runtime performance (components are lightweight), and finer granularity can be beneficial: users gain the ability to load only the specific integration bindings they need, efectively increasing the system’s composability. However, it may afect developer experience: more components require more configuration, more naming, and more cognitive overhead in understanding the dependency graph.

Mitigating this granularity cost is an engineering concern rather than a theoretical one. Practical strategies include package bundling (i.e., grouping related fine-grained components into a single installable unit), convention-based wiring (i.e., automatically connecting components whose names or types match a pattern), and scafold tooling (i.e., generating boilerplate integration components from declarative specifications). These strategies preserve the formal guarantees of the acyclic model while reducing the authoring burden to something closer to the monolithic case.

## 6.6. Dependency Typing and Versioning

In the formal model, a dependency link is established purely by key identity: a component providing key ?? satisfies any component declaring ?? in its dependency set. The type family ??︀ ensures type-level agreement within a single compilation unit, but this guarantee breaks down when components are developed and built independently, which is a common scenario in component ecosystems. This breakage leads to two distinct problems.

Interface drift. A provider may modify the interface associated with ?? (adding fields, changing method signatures, altering behavioral contracts) between versions, while a consumer compiled against an earlier interface continues to declare the same key ??. The dependency is satisfied at the coefect level (?? ∈ dom(??)), yet the runtime value no longer conforms to the consumer’s expectations, leading to type errors, method-not-found failures, or silent behavioral divergence [70].

Key collision. Two independently developed providers may use the same key name ?? to denote entirely unrelated interfaces. Since key identity alone establishes the link, a consumer expecting one provider’s interface will accept the other’s value without any compatibility check. Unlike interface drift, where the provider and consumer at least share a common lineage, key collision involves no relationship whatsoever between the expected and actual types, making the resulting failures unpredictable and dificult to diagnose.

Both problems point to the same gap: the coefect model provides only nominal linking (by key name) but no versioned or structural linking (by interface compatibility) [71]. We discuss three approaches to the gap, from most infrastructure-coupled to most language-agnostic.

Key namespacing. Extending the key space from ?? to ?? × ?? , where ?? identifies the interface-defining package, eliminates key collision by construction: independently developed interfaces with the same local name occupy distinct keys. This is the most direct solution but also the most coupled: it embeds the package namespace into the formal model itself, making the system dependent on an external package registry for key identity.

Peer dependencies. A lighter coupling is to declare version constraints through the hostlanguage package manager [72]. This is the approach Cordis currently adopts. Component dependencies are semantically peer dependencies: a component does not bundle its dependen cies internally but expects the runtime context to supply them. Package managers with peer dependency support (e.g., npm) can enforce version compatibility: if the version of the package providing a key falls outside a consumer’s declared peer range, the incompatibility is caught at install time rather than surfacing as a runtime failure. However, this approach has two limitations: (1) it depends on providers faithfully adhering to semantic versioning, which is an unenforceable convention; (2) package managers typically resolve each dependency to a single version, which prevents loading components from multiple versions of the same package within one application.

Structural compatibility. A fully language-agnostic approach would replace the membership check ?? ∈ dom(??) with a compatibility predicate that verifies the provider’s actual interface structurally subsumes the consumer’s expectation. This is analogous to structural subtyping [73]: a provider satisfies a consumer if the provided interface is a subtype of the re quired interface. The challenge lies in defining this predicate language-agnostically: structural compatibility is straightforward for record types (width subtyping) but becomes complex for behavioral contracts (e.g., pre/postconditions [74], efect specifications [22]), and undecidable once parametric polymorphism introduces bounded quantification [75].

These three approaches address diferent aspects of the problem. Designing a unified dependency model that combines these approaches while preserving the dynamic composition guarantees of the coefect model remains an open problem.

## 6.7. Co-Design with Languages and Operating Systems

Section 6.4 identifies the minimum a host language must supply for the context paradigm. This section takes up the converse question, what a language or operating system co-designed with the paradigm can ofer beyond that minimum.

Co-design with languages. A language designed around the context paradigm can improve on a library in two respects: the semantics it gives to contexts, and the primitives it gives to efects and coefects.

Such a language can make the context implicit again while preserving the context semantics of Section 3.3. An imperative language already runs every statement against an implicit context, and that single context neither tracks efects nor resolves coefects. The context paradigm instead distinguishes multiple contexts, where an operation either modifies the context it runs against or derives another from it (Definition 27). An in-place realization modifies the ambient context, just as an imperative language does. A derived realization instead introduces a separate context, for which the language must provide a construct. Making the context implicit brings both an ergonomic and a safety benefit. (1) In a library realization, every function involving efects or coefects takes the context as an ordinary argument or a receiver, as in Section 5.1. Where the language supplies the context implicitly, functions no longer need to take it. (2) Every context carries its own lifecycle state and committed view (Section 4.1). A library realization passes a context as an ordinary variable, so a component may reach another component’s context by mistake, through a closure or a global variable. An efect it installs there then leaks out of its own lifecycle, and a coefect it reads there escapes its dependency specification. Making the context implicit closes both.

Such a language can also make efects and coefects known to its compiler. (1) For efects, an efect iterator (Definition 51) allocates a closure at every step to hold the inverse together with the state it restores. With syntax for performing an efect, a compiler can emit a single state machine for the whole iteration and hold those inverses in its frame. (2) For coefects, the coefect specification can be admitted into the type system, with two benefits. First, a dependency cycle is reported at compile time instead of being left to the runtime (Section 6.5). Second, a dependency can be compared by the structure of its type rather than by key identity alone, as row types do [28], which is type-level support for the structural compatibility of Section 6.6.

Co-design with operating systems. Section 1.2.3 observes a coarse-grained substitute for dynamic composability, where the operating system supplies temporal composability at the granularity of a process, and the container orchestrator above it supplies spatial composability at the granularity of a service. An operating system co-designed with the paradigm would support fine-grained composition, by making the coefect specification a component declares the whole of what it can reach, and by providing its own resources as coefects.

Such an operating system can supply the sandbox that Section 6.3 defers to a mechanism outside the language. It does so by bounding a component to the dependencies it declares, supplying them when the component is loaded and leaving nothing else reachable from within it, as a WebAssembly module receives its imports from its embedder at instantiation [76]. It can also provide the coefect isolation and interception of Section 3.2.3 as abilities of its own, binding a key diferently for each component and mediating the accesses it supplies.

Such an operating system can also provide its own resources as coefects. A resource lying outside the boundary is made revertible where the runtime records each acquisition against the component that made it (Section 6.1), and every runtime keeps a record of its own. An operating system that provides the resource as a coefect keeps that record once, since it is the party that hands the resource out and can attribute it to the component that asked. Memory and file descriptors are the immediate candidates, and tracking them for the sake of recovery has been done at the kernel interface [77, 78]. Furthermore, an operating system can make revertible some of the operations Section 6.1 can only withhold or compensate for. A system that performs a write to persistent storage transactionally can roll it back [79], and one built on copy-on-write or immutable storage reaches an earlier state by moving a pointer [80, 81].

## 7. Related Work

Dynamic composability intersects several established research areas. We survey the most relevant lines of work and distinguish our contribution from each of them.

## 7.1. Efect and Coefect Systems

Section  2 reviewed efects and coefects as the theoretical pillars underlying our work. We first situate the monadic efect systems now common in industrial practice, then survey three research lines that extend efects and coefects in directions relevant to Cordis: recasting algebraic efects as capabilities, giving efects a reversible semantics, and unifying efects and coefects under a single graded discipline.

Monadic efect systems. One family of libraries encodes efects in the type systems of existing general-purpose languages, representing them as monadic values that a runtime executes. ZIO in Scala [82] models a computation as ZIO[R,E,A] and Efect-TS in TypeScript [83] as Effect<A,E,R>, a generic type whose parameters describe its result, its typed errors, and the services its context must supply; the fp-ts library [84] encodes the same error and requirement channels through Reader-based monad transformers. Two traits separate these systems from Cordis. First, the tracking is bought with a monadic embedding: a program obtains it only by being written inside the efect type, whereas Cordis tracks efects as an overlay over ordinary host code. Second, a requirement is discharged by interpretation, an installed service that supplies its operations, and when that service is withdrawn what its operations performed remains in place; Cordis instead pairs each efect with an inverse and re-resolves requirements as providers come and go (Section 3.1, Section 3.2).

Algebraic efects as capabilities. Algebraic efects (Section 2.1) make efect operations visible to the type system. The extension closest to our work is Brachthäuser et al.‘s Efekt language, which reinterprets efect types as capabilities [85, 86]: an efect type expresses what a computation requires from its context rather than what side efects it may produce. This perspective, like ours, treats the context as a mediator of capabilities. Cordis and Efekt difer in two respects. (1) In purpose, algebraic efects make efects visible to enable modular interpretation, giving one operation many handler semantics, whereas Cordis makes them visible to enable tracking and reversion, pairing every context transformation with an inverse. (2) In setting, Efekt disciplines efects statically at the type level, defaulting to scope-based reasoning in which capabilities are second-class and confined to their lexical scope, and recovering first-class use through boxing, which lifts that restriction by tracking captured capabilities in types; Cordis instead disciplines efects at runtime, aiming at complete resource recovery on component removal; Section 6.7 takes up what a language that made the context second class in this sense would ofer.

Reversible efect semantics. A parallel line gives efects a reversible semantics rather than an interpretive one. Heunen et al. [87] model side efects in a reversible setting by adapting Hughes’ arrows to dagger arrows and inverse arrows, capturing efects such as serialization and mutable store whose operations admit inverses. This is the formal account closest to our revertible efects: both pair each efect with the means to undo it rather than discharging it through a handler. The two difer in where reversibility resides, and in how much of it they demand. Heunen et al. work in a denotational, categorical setting where reversibility is a global property, guaranteed by construction since every computation is invertible, and the inverse is two-sided and recovered from the categorical structure. Cordis tracks inverses at runtime and requires less of them: not that the whole computation be reversible, but that each atomic efect admit a one-sided inverse, supplied by the caller at the point of application rather than derived, from which the inverse of any composite follows by composition (Section 3.1).

Graded types as unified efects and coefects. Orchard et al. [88] proposed graded modal types as an umbrella notion encompassing both efect reasoning (via graded monads) and coefect reasoning (via graded comonads), realized in the Granule language, demonstrating that a single type system can track both what a computation does and what it needs; more recent work extends coefects to imperative Java-like languages [89, 90] and to call-by-push-value [91]. All of these operate at the type level: efects and coefects are static annotations checked at compile time over lexically fixed scopes. Our contribution is orthogonal to this analysis: we lift the same two notions to runtime mechanisms, which lets Cordis handle dynamic composition. Temporal retraction and spatial dependency are re-resolved as the set of loaded components evolves, instead of being settled once over a fixed program text.

## 7.2. Programming Paradigms

Section 3.3.3 established the context paradigm as a discipline that mediates efects and coefects through an explicit context. Two established paradigms warrant explicit comparison: one shares our terminology, the other our treatment of crosscutting concerns.

Context-oriented programming. COP [92, 93] equips a language with layers—partial method and class definitions that are activated and deactivated at runtime according to the execution context, so that behavior adapts without the base code naming its context depen dencies [94]. COP and Cordis coincide in treating context as a first-class, runtime-mutable entity and in activating and deactivating behavior dynamically, but the resemblance is nominal. In COP, “context” denotes the ambient execution situation (e.g., location, user, mode), and activation changes method dispatch within a dynamically scoped extent; a layer neither tracks the side efects it induces nor reverts them, and activation is not governed by dependency satisfaction. In Cordis, the context is the Γ entity mediating efects and coefects: activation runs a component’s revertible efects and is driven by reactive coefect satisfaction (Section 3.2), and deactivation reverts them in full. COP varies what behavior runs; Cordis composes and reverts what efects and dependencies a component installs. Their diference is one of trade-of. COP folds activation into the host language’s method dispatch, gaining dynamically-scoped layer extents at the cost of language specificity, whereas Cordis, as a language-agnostic overlay, resolves activation reactively over a shared context. Cordis can thus express as a coefect only

COP’s global, value-driven fragment: context-dependent selection among implementations, but not dynamically-scoped activation.

Aspect-oriented programming. AOP [95, 96] modularizes a crosscutting concern into an aspect: a pointcut that quantifies over join points selected in the base program, and advice woven in at each. Cordis addresses the same problem of contextual behavior that would otherwise scatter across components, but its analogue of an aspect is a coefect: a shared point of media tion many components declare a dependence on, so that crosscutting behavior can be reshaped there without editing any of them. The two paradigms then difer on two axes. (1) Declaration versus obliviousness: an AOP pointcut is oblivious and quantified, matching arbitrary join points whose code is unaware it is advised, whereas Cordis confines crosscutting to the coefects each component declares, so its reach is exactly that declared surface. This yields determinacy and traceability: an application orchestrator can inspect and govern what cross-cuts a component at the configuration layer, without reading or analyzing its source, whereas an AOP concern is legible only through the aspects that quantify over it. (2) Lifecycle integration: a crosscutting change in Cordis is carried by a component’s efects, reverted when the component unloads and propagated reactively to its dependents, so it is one move within the dynamic composition model; dynamic-AOP systems [97, 98] can also weave and unweave at runtime, but as a stand alone operation, neither bound to a component’s lifecycle nor triggering re-resolution among the advised code.

## 7.3. Temporal Composability

Temporal composability concerns replacing or removing a component in a running program while recovering the efects it installed. Prior approaches divide by how they treat a departing component’s state and efects: carrying state forward to a successor version, recovering efects through developer-authored cleanup, reversing efects automatically within a scope fixed in advance, or reclaiming resources from a record the runtime accumulates by interposing on an interface.

Stateful forward migration. A broad family of systems replaces components in a running program without downtime by carrying their state forward across versions. All observe the same timing discipline: a component may be swapped only once it reaches a safe, interactionfree point. Kramer and Magee established this criterion as quiescence [51], which Vandewoude et al. later relaxed to the less disruptive tranquility [52]; our rolling-update pattern (Section 6.2) enforces it by draining in-flight requests before unloading a provider. Dynamic software updating (DSU) then migrates state forward through hand-written transformation functions: Hicks et al.‘s general-purpose DSU for C [99], Stoyle et al.’s type-safe update points via con-freeness analysis [100], and Hayden et al.‘s Kitsune [101] all map old-version data to newversion representations, inheriting heap objects, open files, and connections in place while re-initializing whatever is left unmigrated. The same discipline extends to persistent state: Overeem et al. [102] convert a running event store’s data between schema versions through hand-written upgrade operations while keeping the system available. Erlang/OTP [15] takes the same stance at the process level, migrating state through code\_change/3 and recovering from faults by restarting supervised processes rather than reverting their efects; JavaScript’s Hot Module Replacement (e.g., webpack [46], Vite [47]) does the same at the module level, handing state forward through the module.hot or import.meta.hot API across a reload. Compared with Cordis’s module replacement (Section 5.2), these approaches migrate in-memory state more gracefully: Cordis reverts the old component’s tracked efects and reapplies the new component’s from a clean slate, so a component’s own in-memory state does not survive a reload unless placed in a longer-lived dependency, and layering DSU-style forward migration atop revertible efects is future work. Cordis’s approach is nonetheless more general in two respects: it needs no hand-written migration functions of the kind DSU and HMR require, and it supports unloading a component entirely and recovering its resources, not merely updating one in place.

Developer-authored recovery. A second family recovers a component’s efects through cleanup or compensation logic that the developer writes by hand. Plugin lifecycle conventions (e.g., OSGi [50], Eclipse’s extension points, IntelliJ and VSCode) delegate cleanup to developerwritten unload callbacks; the Command pattern [103] encapsulates an operation together with an undo method for undo/redo stacks; the saga model [49] structures a long-lived transaction as steps each paired with a compensating action; algebraic efect handlers can attach finalizers that run on teardown [104]; and event sourcing [105] retracts state by appending compensating events rather than executing an inverse at all. In all of them the inverse is an unenforced duty, decoupled from the operation, so that a forgotten one leaks resources silently (as documented empirically in Section 1.2.1). React’s useEffect hook [106] comes closest to pairing an efect with its inverse structurally, returning a cleanup the runtime invokes before each re-execution and on unmount. Its shortfall is composability: a hook may be called only at the top level of a component or another hook, never inside a conditional, loop, or nested function, and its efect body accepts neither an async function nor an iterator. Efects thus cannot be assembled from other efects or interleaved with control flow, leaving nothing from which a composite inverse could be derived. Cordis efects carry no such restriction: they are ordinary operations that compose freely and may run asynchronously, and require a hand-written inverse only for each atomic efect, from which the inverse of any composite is derived by composition, so that assembling existing efects requires writing no inverses at all. This structural pairing of every efect with its inverse makes complete recovery an invariant of the system rather than a matter of developer discipline.

Statically scoped reversal. A third family reverses efects automatically, by construction, but confines reversal to a scope fixed in advance. Software transactional memory [107, 108], descended from hardware transactional memory [109], records a read/write log so that a group of memory operations either commits or aborts, rolling memory back to its pre-transaction state. Reversible computing, from Landauer and Bennett’s thermodynamic analyses [110, 111] to reversible languages such as Janus [112], goes further and makes every step of a whole computation globally invertible. Reversible process calculi build backtracking into the semantics itself: RCCS [113] carries a memory alongside each process and admits a step to be taken back when the past it leads to is causally equivalent, and Phillips and Ulidowski [114] derive reversible operators for CCS, ACP, and CSP uniformly while preserving their forward operational semantics. Their causal-consistency criterion is the concurrent counterpart of the order Cordis’s recovery follows, an accumulator applying a component’s own inverses in lastin-first-out order and the guard of Section  4.3.1 deferring a provider’s withdrawal until its consumers have deactivated (Theorem 63). The reach, however, is fixed by the semantics, every action performed remaining undoable, whereas a Cordis component supplies an inverse for each atomic efect and its accumulator brings the context back to where its composition began. Linear types [115], RAII [4], and Rust’s ownership system [61] tie a resource’s release to a lexical region. Each fixes the scope and reach of reversal statically; Cordis, by contrast, fixes no such scope in advance: it reverts arbitrary context operations over a component’s lifecycle, and treats lexical resource management as complementary, appropriate for local resources within a single component.

Interposed reclamation. A fourth family reclaims what a component acquired without the component itself supplying the inverses, by recording its acquisitions at an interface the runtime controls. Nooks [77] wraps every call crossing the boundary between the Linux kernel and its loadable extensions, so that the kernel objects an extension touches pass through an object tracker whose record tells the recovery manager what to release when the extension fails; shadow drivers [78] tap the same calls from the other side, recording the requests and configuration that determine a driver’s state so that a restarted instance can be restored to it. Akeso [116] obtains the record by compiler instrumentation instead, dividing kernel execution into nestable recovery domains that log their state changes and cross-thread dependencies, and rolling a faulting request back together with every domain that depends on it. Reclamation thus follows from a record the runtime maintains rather than from cleanup the developer remembers to write, which makes this family the closest systems-level precedent for revertible efects. It difers from Cordis in vocabulary and in reach. The platform fixes what can be recorded, whether as release code per kernel object type, one shadow per driver class, or an inverse per instrumented allocator, so a component may hold only resources the platform already knows how to release; a Cordis component instead introduces efects of its own and supplies an inverse for each atomic one (Section 3.1). Reclamation is likewise bounded by a request that commits or a restart of the same extension, whereas Cordis reverts over a component’s whole lifetime and propagates removal to its dependents, which release their own efects in turn (Section 3.2).

## 7.4. Spatial Composability

Spatial composability concerns how a component’s dependencies on others are declared and bound. Prior mechanisms divide by how binding responds to change: wiring dependencies once at initialization, reacting to the availability of whole components, or propagating change at the granularity of individual values.

Initialization-time dependency wiring. Two established mechanisms wire components together at initialization time. Dependency injection frameworks [38] (e.g., Spring [117], Guice, Angular, Inversify) inject dependencies into components at initialization, and UI framework context (e.g., Vue.js’s provide/inject and React’s Context API) passes them along a component tree. Some support dynamic scoping (e.g., Spring’s prototype/request scopes, Angular’s hierarchical injectors), but neither re-resolves reactively: when a provider is replaced or removed at runtime, existing dependents are neither deactivated nor re-initialized, and none ofers lifecycle management of the kind our component state machine provides. Cordis’s reactive coefects (Section 3.2) supply this: the notification mechanism triggers lifecycle transitions whenever the satisfaction predicate changes.

Availability-reactive component models. The closest precedent to our reactive coefects reacts to service availability. OSGi’s Declarative Services and iPOJO [118, 119] let components declare provided and required services, with the runtime automatically activating and deacti vating them as services appear and disappear; iPOJO’s Gravity project [119] explicitly targets autonomous runtime adaptation to changing service availability, and its provide/require model directly prefigures Cordis’s ctx.provide/ctx.get pattern. R-OSGi [53] extends the same abstraction transparently to distributed settings via RPC, mapping network failures to servicewithdrawal events, a pattern Section 6.2 discusses as an extension of the Cordis model. All these systems recover through a deactivation callback, which is limited in two ways. First, the callback is hand-written, so resource safety rests on developer discipline and a forgotten one leaks silently. Second, the callback is synchronous: should teardown require an asynchronous exchange with the departing dependency, the frameworks ofer no protocol to await it, forcing a blocking wait against a reference that may already be stale. Cordis’s reactive coefects close both gaps: deactivation reverts the dependents’ accumulated efects, and its inertial ?????????????????? state (Section 4.3.3) runs asynchronous teardown to completion before acting on further change.

Value-level reactivity. Functional reactive programming (FRP) [120] and its modern incarnations (e.g., signals [121, 122] in SolidJS, Vue’s reactivity system, Angular Signals) propagate change at a value-level granularity: when a signal changes, derived computations are re-evaluated synchronously or under a scheduler [123]. Cordis’s reactive coefects act at a componentlevel granularity, adding asynchronous lifecycle semantics that value-level propagation does not model. The same granularity diference runs the other way for consistency: propagating in a turn, in an order the dependency graph fixes, lets FRP require that no derived computation read a mixture of updated and stale inputs, which is glitch freedom [124], whereas Cordis has no counterpart of a turn, orchestration actions arriving one at a time, and guarantees only that no single transition straddles two resolutions of its coefects (Theorem 64). The two are complementary rather than competing: a Cordis coefect can itself carry reactive values, and a component updates on only the parts it actually consumes, refining component-level reactivity into finer-grained reactive coefects that span both levels.

## 8. Conclusion

We have presented a formal foundation for dynamic composability by lifting the classical concepts of efects and coefects to runtime mechanisms. Revertible efects address local temporal composability: every context transformation carries an inverse that the runtime tracks, and both tracking and recovery preserve composition, so the context is recovered upon component removal. Reactive coefects address local spatial composability: a component is notified against its coefect specification whenever the context changes, each change classified as activating, deactivating, or neutral, with coefect isolation varying what a declared key resolves to and coefect interception varying how the binding is used. We unify the efect context and the coefect context into a single context type, in which an observational equivalence on the coefects supplies the efects with independence, constituting a programming paradigm for spatiotemporal composability. Combining these mechanisms into the notion of a component then gives a calculus of dynamic composition, whose metatheory carries spatiotemporal composability from a single component to a whole system of interleaved components. We realize this paradigm as the Cordis meta-framework, with a core library providing efect tracking and coefect resolution, as well as a declarative component loader with configuration reconciliation and hot module replacement. The Koishi case study validates the design of Cordis in a production system with over 4000 community plugins.

Beyond human-curated plugin ecosystems, a compelling direction for future validation is self-evolving agent harnesses (Section  1.2.2), where an AI agent generates and replaces its own harness components continuously and with little human oversight. Applying Cordis in such a setting would validate the temporal guarantees of complete recovery under rapid component replacement, as well as the spatial guarantees of dependency coordination under frequent topological change. Such validation would demonstrate the paradigm’s applicability as a foundation for recoverable, coordinated, and continuous self-evolution in agent harnesses and other autonomous systems.

## References

[1] D. L. Parnas, “On the criteria to be used in decomposing systems into modules,” Communications of the ACM, vol. 15, no. 12, pp. 1053–1058, 1972, doi: 10.1145/361598.361623.

[2] D. Birsan, “On Plug-ins and Extensible Architectures,” ACM Queue, vol. 3, no. 2, pp. 40– 46, 2005, doi: 10.1145/1053331.1053345.

[3] B. Burns, B. Grant, D. Oppenheimer, E. Brewer, and J. Wilkes, “Borg, Omega, and Kubernetes,” Communications of the ACM, vol. 59, no. 5, pp. 50–57, 2016, doi: 10.1145/2890784.

[4] B. Stroustrup, The Design and Evolution of C++. Addison-Wesley, 1994.

[5] S. Marlow, S. Peyton Jones, A. Moran, and J. Reppy, “Asynchronous Exceptions in Haskell,” in Proceedings of the ACM SIGPLAN 2001 Conference on Programming Language Design and Implementation, in PLDI '01. New York, NY, USA: Association for Computing Machinery, 2001, pp. 274–285. doi: 10.1145/378795.378858.

[6] L. Cardelli, “Program Fragments, Linking, and Modularization,” in Proceedings of the 24th ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages (POPL 1997), ACM Press, 1997, pp. 266–277. doi: 10.1145/263699.263735.

[7] C. Szyperski, Component Software: Beyond Object-Oriented Programming, 2nd ed. Addison-Wesley, 2002.

[8] R. Lopopolo, “Harness Engineering: Leveraging Codex in an Agent-First World.” [Online]. Available: https://openai.com/index/harness-engineering/

[9] Anthropic, “Harness Design for Long-Running Application Development.” [Online]. Available: https://www.anthropic.com/engineering/harness-design-longrunning-apps

[10] L. Wang et al., “A Survey on Large Language Model Based Autonomous Agents,” Frontiers of Computer Science, vol. 18, no. 6, p. 186345, 2024, doi: 10.1007/s11704-024-40231-1.

[11] Y. Qin et al., “Tool Learning with Foundation Models,” ACM Computing Surveys, 2025, doi: 10.1145/3704435.

[12] C. Packer, V. Fang, S. G. Patil, K. Lin, S. Wooders, and J. E. Gonzalez, “MemGPT: Towards LLMs as Operating Systems,” CoRR, vol. abs/2310.08560, 2023.

[13] T. Guo et al., “Large Language Model Based Multi-Agents: A Survey of Progress and Challenges,” in Proceedings of the Thirty-Third International Joint Conference on Artificial Intelligence, in IJCAI 2024. 2024, pp. 8048–8057. doi: 10.24963/ijcai.2024/890.

[14] T. Cai, X. Wang, T. Ma, X. Chen, and D. Zhou, “Large Language Models as Tool Makers,” in Proceedings of the Twelfth International Conference on Learning Representations, in ICLR 2024. 2024. [Online]. Available: https://openreview.net/forum?id=qV83K9d5WB

[15] J. Armstrong, “Making Reliable Distributed Systems in the Presence of Software Errors,” Doctoral dissertation, 2003. [Online]. Available: https://erlang.org/download/ armstrong\_thesis\_2003.pdf

[16] E. Moggi, “Notions of computation and monads,” Information and Computation, vol. 93, no. 1, pp. 55–92, 1991, doi: 10.1016/0890-5401(91)90052-4.

[17] G. Plotkin and J. Power, “Adequacy for Algebraic Efects,” in Foundations of Software Science and Computation Structures, F. Honsell and M. Miculan, Eds., Berlin, Heidelberg: Springer Berlin Heidelberg, 2001, pp. 1–24.

[18] T. Petricek, D. Orchard, and A. Mycroft, “Coefects: unified static analysis of contextdependence,” in Proceedings of the 40th International Conference on Automata, Languages, and Programming - Volume Part II, in ICALP'13. Riga, Latvia: Springer-Verlag, 2013, pp. 385–397. doi: 10.1007/978-3-642-39212-2\_35.

[19] M. Gaboardi, S.-ya Katsumata, D. Orchard, F. Breuvart, and T. Uustalu, “Combining efects and coefects via grading,” in Proceedings of the 21st ACM SIGPLAN International Conference on Functional Programming, in ICFP 2016. Nara, Japan: Association for Computing Machinery, 2016, pp. 476–489. doi: 10.1145/2951913.2951939.

[20] A. Church, “A Formulation of the Simple Theory of Types,” The Journal of Symbolic Logic, vol. 5, no. 2, pp. 56–68, 1940, doi: 10.2307/2266170.

[21] B. C. Pierce, Types and Programming Languages. MIT Press, 2002.

[22] J. M. Lucassen and D. K. Giford, “Polymorphic Efect Systems,” in Proceedings of the 15th ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages, in POPL '88. San Diego, California, USA: Association for Computing Machinery, 1988, pp. 47–57. doi: 10.1145/73560.73564.

[23] P. Wadler, “Monads for functional programming,” in Program Design Calculi, M. Broy, Ed., Berlin, Heidelberg: Springer Berlin Heidelberg, 1993, pp. 233–264.

[24] G. Plotkin and J. Power, “Notions of Computation Determine Monads,” in Foundations of Software Science and Computation Structures, Berlin, Heidelberg: Springer Berlin Heidelberg, 2002, pp. 342–356. doi: 10.1007/3-540-45931-6\_24.

[25] G. Plotkin and M. Pretnar, “Handlers of Algebraic Efects,” in Programming Languages and Systems (ESOP), Berlin, Heidelberg: Springer Berlin Heidelberg, 2009, pp. 80–94. doi: 10.1007/978-3-642-00590-9\_7.

[26] M. Pretnar, “An Introduction to Algebraic Efects and Handlers. Invited tutorial paper,” Electron. Notes Theor. Comput. Sci., vol. 319, no. C, pp. 19–35, Dec. 2015, doi: 10.1016/ j.entcs.2015.12.003.

[27] D. Leijen, “Koka: Programming with Row Polymorphic Efect Types,” Electronic Proceedings in Theoretical Computer Science, vol. 153, pp. 100–126, Jun. 2014, doi: 10.4204/ eptcs.153.8.

[28] D. Leijen, “Type directed compilation of row-typed algebraic efects,” in Proceedings of the 44th ACM SIGPLAN Symposium on Principles of Programming Languages, in POPL '17. Paris, France: Association for Computing Machinery, 2017, pp. 486–499. doi: 10.1145/3009837.3009872.

[29] A. Bauer and M. Pretnar, “Programming with algebraic efects and handlers,” Journal of Logical and Algebraic Methods in Programming, vol. 84, no. 1, pp. 108–123, Jan. 2015, doi: 10.1016/j.jlamp.2014.02.001.

[30] K. Sivaramakrishnan et al., “Retrofitting parallelism onto OCaml,” Proc. ACM Program. Lang., vol. 4, no. ICFP, Aug. 2020, doi: 10.1145/3408995.

[31] T. Petricek, D. Orchard, and A. Mycroft, “Coefects: a calculus of context-dependent computation,” in Proceedings of the 19th ACM SIGPLAN International Conference on Functional Programming, in ICFP '14. Gothenburg, Sweden: Association for Computing Machinery, 2014, pp. 123–135. doi: 10.1145/2628136.2628160.

[32] T. Uustalu and V. Vene, “Comonadic Notions of Computation,” Electronic Notes in Theoretical Computer Science, vol. 203, no. 5, pp. 263–284, 2008, doi: 10.1016/j.entcs.2008.05.029.

[33] A. Brunel, M. Gaboardi, D. Mazza, and S. Zdancewic, “A Core Quantitative Coefect Calculus,” in Proceedings of the 23rd European Symposium on Programming Languages and Systems - Volume 8410, Berlin, Heidelberg: Springer-Verlag, 2014, pp. 351–370. doi: 10.1007/978-3-642-54833-8\_19.

[34] J. Reed and B. C. Pierce, “Distance makes the types grow stronger: a calculus for diferential privacy,” SIGPLAN Not., vol. 45, no. 9, pp. 157–168, Sep. 2010, doi: 10.1145/1932681.1863568.

[35] M. Abadi, A. Banerjee, N. Heintze, and J. G. Riecke, “A core calculus of dependency,” in Proceedings of the 26th ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages, in POPL '99. San Antonio, Texas, USA: Association for Computing Machinery, 1999, pp. 147–160. doi: 10.1145/292540.292555.

[36] D. E. Denning, “A lattice model of secure information flow,” Commun. ACM, vol. 19, no. 5, pp. 236–243, May 1976, doi: 10.1145/360051.360056.

[37] U. Dal Lago and F. Gavazzo, “A relational theory of efects and coefects,” Proc. ACM Program. Lang., vol. 6, no. POPL, Jan. 2022, doi: 10.1145/3498692.

[38] M. Fowler, “Inversion of Control Containers and the Dependency Injection pattern.” [Online]. Available: https://martinfowler.com/articles/injection.html

[39] A. M. Pitts and I. D. B. Stark, “Observable Properties of Higher Order Functions that Dynamically Create Local Names, or What's New?,” in Mathematical Foundations of Computer Science 1993 (MFCS 1993), in Lecture Notes in Computer Science, vol. 711. Springer, 1993, pp. 122–141. doi: 10.1007/3-540-57182-5\_8.

[40] G. D. Plotkin, “LCF Considered as a Programming Language,” Theoretical Computer Science, vol. 5, no. 3, pp. 223–255, 1977, doi: 10.1016/0304-3975(77)90044-5.

[41] D. R. Ghica, K. Muroya, and T. Waugh Ambridge, “A Robust Graph-Based Approach to Observational Equivalence,” Logical Methods in Computer Science, vol. 21, no. 2, p. 8:1– 8:95, 2025, doi: 10.46298/LMCS-21(2:8)2025.

[42] X. Leroy and S. Blazy, “Formal Verification of a C-like Memory Model and Its Uses for Verifying Program Transformations,” Journal of Automated Reasoning, vol. 41, no. 1, pp. 1–31, 2008, doi: 10.1007/s10817-008-9099-0.

[43] R. P. James and A. Sabry, “Yield: Mainstream Delimited Continuations,” in First International Workshop on the Theory and Practice of Delimited Continuations (TPDC 2011), 2011, pp. 20–32. [Online]. Available: https://homes.luddy.indiana.edu/sabry/files/yield.pdf

[44] A. W. Mazurkiewicz, “Trace Theory,” in Petri Nets: Central Models and Their Properties, Advances in Petri Nets 1986, Part II, in Lecture Notes in Computer Science, vol. 255. Springer, 1986, pp. 279–324. doi: 10.1007/3-540-17906-2\_30.

[45] U. A. Acar, G. E. Blelloch, and R. Harper, “Adaptive functional programming,” ACM Transactions on Programming Languages and Systems, vol. 28, no. 6, pp. 990–1034, 2006, doi: 10.1145/1186632.1186634.

[46] webpack, “Hot Module Replacement.” [Online]. Available: https://webpack.js.org/api/ hot-module-replacement/

[47] Vite, “HMR API.” [Online]. Available: https://vite.dev/guide/api-hmr

[48] E. N. (M. Elnozahy, L. Alvisi, Y.-M. Wang, and D. B. Johnson, “A Survey of Rollback-Recovery Protocols in Message-Passing Systems,” ACM Computing Surveys, vol. 34, no. 3, pp. 375–408, 2002, doi: 10.1145/568522.568525.

[49] H. Garcia-Molina and K. Salem, “Sagas,” in Proceedings of the 1987 ACM SIGMOD International Conference on Management of Data, in SIGMOD '87. 1987, pp. 249–259. doi: 10.1145/38713.38742.

[50] OSGi Alliance, OSGi Core Release 8. OSGi Alliance, 2020. [Online]. Available: https:// docs.osgi.org/specification/osgi.core/8.0.0/

[51] J. Kramer and J. Magee, “The Evolving Philosophers Problem: Dynamic Change Management,” IEEE Transactions on Software Engineering, vol. 16, no. 11, pp. 1293–1306, 1990, doi: 10.1109/32.60317.

[52] Y. Vandewoude, P. Ebraert, Y. Berbers, and T. D'Hondt, “Tranquility: A Low Disruptive Alternative to Quiescence for Ensuring Safe Dynamic Updates,” IEEE Transactions on Software Engineering, vol. 33, no. 12, pp. 856–868, 2007, doi: 10.1109/tse.2007.70733.

[53] J. S. Rellermeyer, G. Alonso, and T. Roscoe, “R-OSGi: Distributed Applications Through Software Modularization,” in Proceedings of the ACM/IFIP/USENIX 8th International Middleware Conference, in Middleware '07. 2007, pp. 1–20. doi: 10.1007/978-3-540-76778-7\_1.

[54] J. B. Dennis and E. C. Van Horn, “Programming Semantics for Multiprogrammed Computations,” Communications of the ACM, vol. 9, no. 3, pp. 143–155, 1966, doi: 10.1145/365230.365252.

[55] M. S. Miller, K.-P. Yee, and J. Shapiro, “Capability Myths Demolished,” technical report SRL2003–2, 2003. [Online]. Available: http://zesty.ca/capmyths/usenix.pdf

[56] R. N. M. Watson, J. Anderson, B. Laurie, and K. Kennaway, “Capsicum: Practical Capabilities for UNIX,” in Proceedings of the 19th USENIX Security Symposium, 2010, pp. 29–46. [Online]. Available: https://www.usenix.org/legacy/events/sec10/tech/full\_papers/ Watson.pdf

[57] R. Wahbe, S. Lucco, T. E. Anderson, and S. L. Graham, “Eficient Software-Based Fault Isolation,” in Proceedings of the 14th ACM Symposium on Operating Systems Principles, in SOSP '93. 1993, pp. 203–216. doi: 10.1145/168619.168635.

[58] A. Barth, A. P. Felt, P. Saxena, and A. Boodman, “Protecting Browsers from Extension Vulnerabilities,” in Proceedings of the 17th Annual Network and Distributed System Security Symposium, in NDSS '10. 2010. [Online]. Available: https://www.ndss-symposium.org/ ndss2010/protecting-browsers-extension-vulnerabilities/

[59] W. W. Ho and R. A. Olsson, “An Approach to Genuine Dynamic Linking,” Software: Practice and Experience, vol. 21, no. 4, pp. 375–390, 1991, doi: 10.1002/SPE.4380210404.

[60] P. Wadler and S. Blott, “How to Make Ad-hoc Polymorphism Less Ad Hoc,” in Proceedings of the 16th ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages, in POPL '89. 1989, pp. 60–76. doi: 10.1145/75277.75283.

[61] N. D. Matsakis and F. S. K. II, “The Rust Language and Type System,” in ACM SIGPLAN ML Family Workshop, Gothenburg, Sweden, Sep. 2014.

[62] D. Dreyer, R. Harper, M. M. T. Chakravarty, and G. Keller, “Modular Type Classes,” in Proceedings of the 34th ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages, in POPL '07. 2007, pp. 63–70. doi: 10.1145/1190216.1190229.

[63] Microsoft, “Declaration Merging.” [Online]. Available: https://www.typescriptlang. org/docs/handbook/declaration-merging.html

[64] T. Van Cutsem and M. S. Miller, “Proxies: Design Principles for Robust Object-oriented Intercession APIs,” in Proceedings of the 6th Symposium on Dynamic Languages, in DLS '10. 2010, pp. 59–72. doi: 10.1145/1869631.1869638.

[65] R. Hettinger, “Descriptor HowTo Guide.” [Online]. Available: https://docs.python.org/ 3/howto/descriptor.html

[66] P. Maes, “Concepts and Experiments in Computational Reflection,” in Conference on Object-Oriented Programming Systems, Languages, and Applications (OOPSLA), 1987, pp. 147–155. doi: 10.1145/38765.38821.

[67] G. Bracha and D. M. Ungar, “Mirrors: design principles for meta-level facilities of objectoriented programming languages,” in Proceedings of the 19th Annual ACM SIGPLAN Conference on Object-Oriented Programming, Systems, Languages, and Applications (OOP SLA), 2004, pp. 331–344. doi: 10.1145/1028976.1029004.

[68] R. Rouvoy and P. Merle, “Leveraging component-based software engineering with Fraclet,” Annals of Telecommunications, vol. 64, no. 1–2, pp. 65–79, 2009, doi: 10.1007/ s12243-008-0072-z.

[69] E. Burmako, “Scala Macros: Let Our Powers Combine!,” in Proceedings of the 4th Workshop on Scala, in SCALA@ECOOP '13. 2013, p. 3:1–3:10. doi: 10.1145/2489837.2489840.

[70] S. Raemaekers, A. van Deursen, and J. Visser, “Semantic Versioning and Impact of Breaking Changes in the Maven Repository,” Journal of Systems and Software, vol. 129, pp. 140–158, 2017, doi: 10.1016/j.jss.2016.04.008.

[71] P. Lam, J. Dietrich, and D. J. Pearce, “Putting the Semantics into Semantic Versioning,” in Proceedings of the 2020 ACM SIGPLAN International Symposium on New Ideas, New Paradigms, and Reflections on Programming and Software, in Onward! '20. 2020, pp. 157– 179. doi: 10.1145/3426428.3426922.

[72] P. Abate, R. Di Cosmo, R. Treinen, and S. Zacchiroli, “Dependency Solving: A Separate Concern in Component Evolution Management,” Journal of Systems and Software, vol. 85, no. 10, pp. 2228–2240, 2012, doi: 10.1016/j.jss.2012.02.018.

[73] L. Cardelli, “Structural Subtyping and the Notion of Power Type,” in Proceedings of the 15th ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages, in POPL '88. 1988, pp. 70–79. doi: 10.1145/73560.73566.

[74] B. Meyer, “Applying "Design by Contract",” Computer, vol. 25, no. 10, pp. 40–51, 1992, doi: 10.1109/2.161279.

[75] B. C. Pierce, “Bounded Quantification is Undecidable,” Information and Computation, vol. 112, no. 1, pp. 131–165, 1994, doi: 10.1006/inco.1994.1055.

[76] A. Haas et al., “Bringing the web up to speed with WebAssembly,” in Proceedings of the 38th ACM SIGPLAN Conference on Programming Language Design and Implementation (PLDI), ACM, 2017, pp. 185–200. doi: 10.1145/3062341.3062363.

[77] M. M. Swift, B. N. Bershad, and H. M. Levy, “Improving the reliability of commodity operating systems,” in Proceedings of the 19th ACM Symposium on Operating Systems Principles (SOSP), ACM, 2003, pp. 207–222. doi: 10.1145/945445.945466.

[78] M. M. Swift, M. Annamalai, B. N. Bershad, and H. M. Levy, “Recovering device drivers,” ACM Transactions on Computer Systems, vol. 24, no. 4, pp. 333–360, 2006, doi: 10.1145/1189256.1189257.

[79] D. E. Porter, O. S. Hofmann, C. J. Rossbach, A. Benn, and E. Witchel, “Operating System Transactions,” in Proceedings of the 22nd ACM Symposium on Operating Systems Principles (SOSP), ACM, 2009, pp. 161–176. doi: 10.1145/1629575.1629591.

[80] O. Kiselyov and C.-chieh Shan, “Delimited Continuations in Operating Systems,” in Modeling and Using Context (CONTEXT 2007), in Lecture Notes in Computer Science, vol. 4635. Springer, 2007, pp. 291–302. doi: 10.1007/978-3-540-74255-5\_22.

[81] E. Dolstra and A. Löh, “NixOS: a purely functional Linux distribution,” in Proceedings of the 13th ACM SIGPLAN International Conference on Functional Programming (ICFP), ACM, 2008, pp. 367–378. doi: 10.1145/1411204.1411255.

[82] ZIO, “ZIO: Type-safe, composable asynchronous and concurrent programming for Scala.” [Online]. Available: https://zio.dev/

[83] Efect, “Efect: A TypeScript library for building robust applications.” [Online]. Available: https://efect.website/

[84] G. Canti, “fp-ts: Functional programming in TypeScript.” [Online]. Available: https:// github.com/gcanti/fp-ts

[85] J. I. Brachthäuser, P. Schuster, and K. Ostermann, “Efects as capabilities: efect handlers and lightweight efect polymorphism,” Proc. ACM Program. Lang., vol. 4, no. OOPSLA, 2020, doi: 10.1145/3428194.

[86] J. I. Brachthäuser, P. Schuster, E. Lee, and A. Boruch-Gruszecki, “Efects, capabilities, and boxes: from scope-based reasoning to type-based reasoning and back,” Proc. ACM Program. Lang., vol. 6, no. OOPSLA1, 2022, doi: 10.1145/3527320.

[87] C. Heunen, R. Kaarsgaard, and M. Karvonen, “Reversible Efects as Inverse Arrows,” in Proceedings of the Thirty-Fourth Conference on the Mathematical Foundations of Programming Semantics (MFPS XXXIV), in Electronic Notes in Theoretical Computer Science, vol. 341. 2018, pp. 179–199. doi: 10.1016/j.entcs.2018.11.009.

[88] D. Orchard, V.-B. Liepelt, and H. Eades III, “Quantitative program reasoning with graded modal types,” Proc. ACM Program. Lang., vol. 3, no. ICFP, 2019, doi: 10.1145/3341714.

[89] R. Bianchini, F. Dagnino, P. Giannini, E. Zucca, and M. Servetto, “Coefects for sharing and mutation,” Proc. ACM Program. Lang., vol. 6, no. OOPSLA2, Oct. 2022, doi: 10.1145/3563319.

[90] R. Bianchini, F. Dagnino, P. Giannini, and E. Zucca, “A Java-like calculus with heterogeneous coefects,” Theoretical Computer Science, vol. 971, p. 114063, 2023, doi: https://doi. org/10.1016/j.tcs.2023.114063.

[91] C. Torczon, E. Suárez Acevedo, S. Agrawal, J. Velez-Ginorio, and S. Weirich, “Efects and Coefects in Call-by-Push-Value,” Proc. ACM Program. Lang., vol. 8, no. OOPSLA2, Oct. 2024, doi: 10.1145/3689750.

[92] R. Hirschfeld, P. Costanza, and O. Nierstrasz, “Context-oriented Programming,” Journal of Object Technology, vol. 7, no. 3, pp. 125–151, 2008, doi: 10.5381/jot.2008.7.3.a4.

[93] P. Costanza and R. Hirschfeld, “Language constructs for context-oriented programming: an overview of ContextL,” in Proceedings of the 2005 Symposium on Dynamic Languages (DLS '05), ACM, 2005, pp. 1–10. doi: 10.1145/1146841.1146842.

[94] G. Salvaneschi, C. Ghezzi, and M. Pradella, “Context-oriented programming: A software engineering perspective,” Journal of Systems and Software, vol. 85, no. 8, pp. 1801–1817, 2012, doi: 10.1016/j.jss.2012.03.024.

[95] G. Kiczales et al., “Aspect-Oriented Programming,” in ECOOP'97 — Object-Oriented Programming, 11th European Conference, in Lecture Notes in Computer Science, vol. 1241. Springer, 1997, pp. 220–242. doi: 10.1007/BFb0053381.

[96] G. Kiczales, E. Hilsdale, J. Hugunin, M. Kersten, J. Palm, and W. G. Griswold, “An Overview of AspectJ,” in ECOOP 2001 — Object-Oriented Programming, 15th European Conference, in Lecture Notes in Computer Science, vol. 2072. Springer, 2001, pp. 327–353. doi: 10.1007/3-540-45337-7\_18.

[97] A. Popovici, T. Gross, and G. Alonso, “Dynamic Weaving for Aspect-Oriented Programming,” in Proceedings of the 1st International Conference on Aspect-Oriented Software Development (AOSD 2002), ACM, 2002, pp. 141–147. doi: 10.1145/508386.508404.

[98] J. Bonér, “What Are the Key Issues for Commercial AOP Use: How Does AspectWerkz Address Them?,” in Proceedings of the 3rd International Conference on Aspect-Oriented Software Development (AOSD 2004), ACM, 2004, pp. 5–6. doi: 10.1145/976270.976273.

[99] M. Hicks, J. T. Moore, and S. Nettles, “Dynamic Software Updating,” in Proceedings of the ACM SIGPLAN 2001 Conference on Programming Language Design and Implementation, in PLDI '01. 2001, pp. 13–23. doi: 10.1145/378795.378798.

[100] G. Stoyle, M. Hicks, G. Bierman, P. Sewell, and I. Neamtiu, “Mutatis Mutandis: Safe and Predictable Dynamic Software Updating,” in Proceedings of the 32nd ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages, in POPL '05. 2005, pp. 183– 194. doi: 10.1145/1040305.1040321.

[101] C. M. Hayden, K. Saur, E. K. Smith, and M. Hicks, “Kitsune: Eficient, General-Purpose Dynamic Software Updating for C,” ACM Trans. Program. Lang. Syst., vol. 36, no. 4, 2014, doi: 10.1145/2629460.

[102] M. Overeem, M. Spoor, and S. Jansen, “The Dark Side of Event Sourcing: Managing Data Conversion,” in IEEE 24th International Conference on Software Analysis, Evolution and Reengineering, in SANER '17. 2017, pp. 193–204. doi: 10.1109/SANER.2017.7884621.

[103] E. Gamma, R. Helm, R. Johnson, and J. Vlissides, Design Patterns: Elements of Reusable Object-Oriented Software. Boston, MA: Addison-Wesley, 1994.

[104] D. Leijen, “Algebraic Efect Handlers with Resources and Deep Finalization,” technical report MSR-TR-2018-10, Apr. 2018. [Online]. Available: https://www.microsoft.com/ en-us/research/publication/algebraic-efect-handlers-resources-deep-finalization/

[105] M. Fowler, “Event Sourcing.” 2005.

[106] J. Lee, J. Ahn, and K. Yi, “React-tRace: A Semantics for Understanding React Hooks,” Proc. ACM Program. Lang., vol. 9, no. OOPSLA2, pp. 471–498, 2025, doi: 10.1145/3763067.

[107] N. Shavit and D. Touitou, “Software Transactional Memory,” in Proceedings of the Fourteenth Annual ACM Symposium on Principles of Distributed Computing, in PODC '95. 1995, pp. 204–213. doi: 10.1145/224964.224987.

[108] T. Harris, S. Marlow, S. Peyton Jones, and M. Herlihy, “Composable Memory Transactions,” in Proceedings of the Tenth ACM SIGPLAN Symposium on Principles and Practice of Parallel Programming, in PPoPP '05. 2005, pp. 48–60. doi: 10.1145/1065944.1065952.

[109] M. Herlihy and J. E. B. Moss, “Transactional Memory: Architectural Support for Lock-Free Data Structures,” in Proceedings of the 20th Annual International Symposium on Computer Architecture, in ISCA '93. 1993, pp. 289–300. doi: 10.1145/165123.165164.

[110] R. Landauer, “Irreversibility and Heat Generation in the Computing Process,” IBM Journal of Research and Development, vol. 5, no. 3, pp. 183–191, 1961, doi: 10.1147/rd.53.0183.

[111] C. H. Bennett, “Logical Reversibility of Computation,” IBM Journal of Research and Development, vol. 17, no. 6, pp. 525–532, 1973, doi: 10.1147/rd.176.0525.

[112] T. Yokoyama and R. Glück, “A Reversible Programming Language and its Invertible Self-Interpreter,” in Proceedings of the 2007 ACM SIGPLAN Workshop on Partial Evaluation and Semantics-Based Program Manipulation, in PEPM '07. 2007, pp. 144–153. doi: 10.1145/1244381.1244404.

[113] V. Danos and J. Krivine, “Reversible Communicating Systems,” in CONCUR 2004 — Concurrency Theory, 15th International Conference, in Lecture Notes in Computer Science, vol. 3170. Springer, 2004, pp. 292–307. doi: 10.1007/978-3-540-28644-8\_19.

[114] I. Phillips and I. Ulidowski, “Reversing Algebraic Process Calculi,” in Foundations of Software Science and Computation Structures, 9th International Conference (FOSSACS 2006), in Lecture Notes in Computer Science, vol. 3921. Springer, 2006, pp. 246–260. doi: 10.1007/11690634\_17.

[115] P. Wadler, “Linear Types Can Change the World!,” in Programming Concepts and Methods: Proceedings of the IFIP Working Group 2.2/2.3 Working Conference, North-Holland, 1990, pp. 561–581. [Online]. Available: https://homepages.inf.ed.ac.uk/wadler/papers/ linear/linear.ps

[116] A. Lenharth, V. S. Adve, and S. T. King, “Recovery domains: an organizing principle for recoverable operating systems,” in Proceedings of the 14th International Conference on Architectural Support for Programming Languages and Operating Systems (ASPLOS), ACM, 2009, pp. 49–60. doi: 10.1145/1508244.1508251.

[117] C. Walls, Spring in Action, 6th ed. Manning Publications, 2022. [Online]. Available: https://www.manning.com/books/spring-in-action-sixth-edition

[118] C. Escofier, R. S. Hall, and P. Lalanda, “iPOJO: an Extensible Service-Oriented Component Framework,” in IEEE International Conference on Services Computing, 2007, pp. 474– 481. doi: 10.1109/SCC.2007.74.

[119] H. Cervantes and R. S. Hall, “Autonomous Adaptation to Dynamic Availability Using a Service-Oriented Component Model,” in Proceedings of the 26th International Conference on Software Engineering, in ICSE '04. 2004, pp. 614–623. doi: 10.1109/ICSE.2004.1317483.

[120] C. Elliott and P. Hudak, “Functional Reactive Animation,” in Proceedings of the Second ACM SIGPLAN International Conference on Functional Programming, in ICFP '97. 1997, pp. 263–273. doi: 10.1145/258948.258973.

[121] G. H. Cooper and S. Krishnamurthi, “Embedding Dynamic Dataflow in a Call-by-Value Language,” in Programming Languages and Systems (ESOP 2006), in Lecture Notes in Computer Science, vol. 3924. Springer, 2006, pp. 294–308. doi: 10.1007/11693024\_20.

[122] I. Maier and M. Odersky, “Deprecating the Observer Pattern with Scala.React,” technical report EPFL-REPORT-176887, 2012. [Online]. Available: https://infoscience.epfl.ch/ record/176887

[123] E. Bainomugisha, A. L. Carreton, T. Van Cutsem, W. De Meuter, and others, “A Survey on Reactive Programming,” ACM Comput. Surv., vol. 45, no. 4, 2013, doi: 10.1145/2501654.2501666.

[124] A. Margara and G. Salvaneschi, “On the Semantics of Distributed Reactive Programming: The Cost of Consistency,” IEEE Trans. Software Eng., vol. 44, no. 7, pp. 689–711, 2018, doi: 10.1109/TSE.2018.2833109.