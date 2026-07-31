USENIX

THE ADVANCED COMPUTING SYSTEMS ASSOCIATION

# Spain: Succinct proofs for numerical computations

Zachary DeStefano, Noah Golub, Zile Huang, Julius Zhang, Sam Frank, and Michael Walfish, NYU

https://www.usenix.org/conference/osdi26/presentation/destefano

# This paper is included in the Proceedings of the 20th USENIX Symposium on Operating Systems Design and Implementation.

July 13–15, 2026 • Seattle, WA, USA

ISBN 978-1-939133-55-7

Open access to the Proceedings of the 20th USENIX Symposium on Operating Systems Design and Implementation is sponsored by

# Spain: Succinct proofs for numerical computations

Zachary DeStefano, Noah Golub, Zile Huang, Julius Zhang, Sam Frank, Michael Walfish

Courant Institute, NYU

Abstract. In a succinct proof protocol, a verifier gets assurance that an untrusted prover executed an agreed computation, without requiring the verifier to re-execute the computation itself. In little more than a decade, this area has undergone a remarkable transformation from theory to implemented systems. This activity is extremely exciting. But there is a catch. To apply succinct proofs, one needs to translate one’s computation to a set of equations, or constraints. The required translation has so far completely blocked systematic support for numerical computations, namely those for which the bulk of the computation uses approximations of real numbers. This paper fills that void with the design, implementation, and evaluation of a system called Spain. The starting insight of Spain is that since numerical computations inherently have approximation error, the constraint formalism should likewise allow for approximate satisfiability. Based on this insight, Spain introduces a new proof protocol and new ways to translate computations to constraints. Spain’s implementation improves over natural baselines by multiple orders of magnitude.

## 1 Introduction

A succinct proof protocol provides execution integrity: one party (the verifier) gets assurance that another party (the prover) executed an agreed computation, without requiring the verifier to redo the computation or trust the prover. A variant of this setup is zero-knowledge, which additionally hides sensitive inputs from the verifier. Note that execution integrity is orthogonal to program verification. Program verification is about ensuring that a given program meets a specification; here, the question is whether the alleged outputs of a program, verified or otherwise, truly came from running that program.

Succinct proofs have undergone a remarkable transformation. These constructs were known to theorists, based on foundational results in interactive proofs, zero-knowledge proofs, arguments, and probabilistically checkable proofs (PCPs) in the 1980s and 1990s [13, 14, 16, 17, 34, 65, 80, 89, 91, 120]. At the time, they were considered to be wildly impractical. However, over the past 15 years, these constructs have been refined and implemented (see [130, 140] for surveys). They have even been deployed [69, 126], mostly in cryptocurrency [54, 55, 72, 73, 84, 88, 103]. For example, in a traditional blockchain, every node re-executes all transactions to check the validity of state transitions; with succinct proofs, by contrast, a prover generates a proof once and records it on the blockchain, and other nodes need only verify the proof [133].

Despite all of the progress, there is an inescapable awk wardness in applying succinct proofs. One must arithmetize one’s computation, which means translating it to equations, or constraints; roughly speaking, a solution to the constraints corresponds to a valid program trace. Unfortunately, this process does not match how software developers write programs. Control flow, for example, is unnatural to represent as constraints. Making matters worse, the constraints are expressed over a finite field (such as the integers mod a given prime <sup>??</sup>), yet finite fields have no notion of negative numbers or even order relationships. Consequently, a simple program operation like conditionally branching based on a comparison between two numbers has a very verbose expression in constraints (§2).

Still, researchers and practitioners manage to get around the semantic gap for certain small-scale computations (like validating blockchain transactions). The verifier is truly fast, and the prover’s overhead is “only” 10<sup>6</sup>× relative to executing the computation natively (§7, §8).

However, the semantic gap becomes a yawning chasm for numerical computations: those for which the bulk of the computation uses fixed-point or floating-point approximations of real numbers. The core issue is that numerical computations don’t map naturally to equations over finite fields, not even with the kinds of gymnastics used for non-numerical computations. Not to mention, researchers have no hope of competing with the decades of investment in optimizing FPUs and GPUs.

Yet, numerical computations were one of the primary motivations for the invention of computers, and continue to be of intense interest. In the modern era, LLM training and inference, physics simulations, cyberphysical systems, and far more all compute over approximations of real numbers. Succinct proofs applied to numerical computations would thus allow such computations to run on untrusted infrastructure. For example, a user of an LLM could get a proof that the produced tokens truly came from running inference on a given model. Or someone could run a fluid simulation and then prove to others that the simulation ran as specified, without anyone having to redo the computation.

The purpose of this paper is to produce a system that applies succinct proofs to numerical computations, with three goals:

1. The system should be general-purpose. This means that the core proving machinery should not be specialized to the computation itself; in particular, if the computation changes, the core protocol should not have to change, nor should the pencil-and-paper mathematics that undergird the correctness of the succinct proof protocol.

2. The verifier should be less expensive computationally than native execution. Otherwise, the verifier could simply run the computation itself. Note that in zero-knowledge setups, this requirement does not arise, as the verifier

is not expected to be able to run the computation itself.   
However, zero-knowledge is a non-goal for us.

3. The prover’s overhead is no more than three orders of magnitude versus natively executing the computation. While in ordinary computing contexts, overhead of 1000× would be preposterous, in this research area, the state of the art, including in deployed systems, is 10<sup>5</sup>× or 10<sup>6</sup>×.

Prior works encoding numerical computations in proof systems do one of two things (§8). Some works give standalone encodings of specific numerical operations, embedded in general-purpose proof systems; these arguably meet goal 1 but at the cost of goal 3 [9, 50, 51, 59, 82, 115, 124]. Other works build end-to-end special-purpose protocols for specific numerical computations, sacrificing goal 1 – and in most cases goal 3, too [19, 63, 77, 78, 86, 127, 128, 151]. In fact, only one work that we are aware of has achieved goal 3 [105], but at severe compromise of goals 1 and 2.

This paper describes a system, Spain, that achieves all three goals in certain regimes. Spain makes several contributions:

A succinct proof framework for approximate rational arithmetic (§3). Spain’s idea here is to reflect existing numerical notions of accuracy by using constraints but having the proving machinery establish that each constraint holds approximately.

A new proving protocol (§4). To actually prove that the constraints hold approximately, Spain introduces a new proof protocol. It is built on and inspired by prior work, specifically Spartan [116], Zaratan [42], and DARK [40].

Highly compact arithmetizations (§5). Rather than paying a number of constraints proportional to the number of bits in numerical operations, Spain translates individual numerical operations to single constraints; for example, division and square root become one constraint each. This in turn enables highly eficient comparisons, range checks, and piecewise functions. Spain also uses division to create eficient translations of transcendental operations, such as <sup>??</sup> . These encodings could be of independent interest.

Rigorous proof (Apps. B, E, F). We prove correctness of Spain’s proof protocol and its arithmetizations.

Implementation of Spain (§6, Appx. G). We have implemented Spain. It includes several front-ends that translate numerical computations to constraints and a common backend that implements the Spain prover and verifier.

Experimental evaluation (§7). We evaluate Spain and baseline systems on various applications, including linear programming problems; machine learning primitives and an end-to-end application (GPT-2); fluid simulations; and geospatial calculations. We find that Spain has the fastest (general-purpose) numerical prover in the literature. Additionally, Spain’s verifier is the first that we are aware of to beat native execution for reasonably-sized numerical computations.

Like all succinct proof systems, Spain must pay high overheads. However, in exhibiting a new kind of arithmetization, Spain has substantially expanded what is possible.

## 2 Background

## 2.1 Numerical computations

People want to perform computations that involve realnumbered arithmetic. However, doing so exactly is often intractable. Instead, numerical programs are implemented with approximate arithmetic, which comes in two flavors: fixed-point and floating-point. Both have some rounding, or error. Numerical analysis studies how to ensure that the final result is meaningful.

Fixed-point arithmetic encodes a subset of the rational numbers (denoted <sup>Q</sup>), specifically those expressible as an integer divided by a fixed denominator (normally a power of two). Real numbers outside of fixed-point are mapped to nearby fixed-point numbers via rounding, prior to entering fixed-point operations. Operations obey absolute error bounds. For any two fixed-point numbers <sup>??</sup> and <sup>??</sup> and primitive operation op (for example, +, −, ×, or ÷), the fixed-point operation op<sub>??</sub> is defined (ignoring overflow) as:

![](images/4c81df621602bc0dd8ca3639f431c50b0ea43139f5b69d62faae2cdbbefcec74.jpg)

where |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup> for some fixed <sup>??</sup> that depends on the operation and the fixed-point format.

With floating-point representations and arithmetic, operations obey relative error bounds. Then with op as above, <sup>??,</sup> <sup>??</sup> as floating-point numbers, and op<sub>??</sub> now denoting the floating-point operation:

![](images/99c0ef793265aec7afcfd9afdf31430f70ec520680bb8ec321376063bec0e83f.jpg)

Where |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup>. Even simple operations introduce errors. For example, when using single-precision IEEE 754 [2] floating point, (2 ÷?? 5) ≈ 0<sup>.</sup>400000006 rather than exactly 0<sup>.</sup>4.

## 2.2 Succinct and probabilistic proofs

A succinct proof (or probabilistic proof ) is a cryptographic protocol between a prover and a verifier (typically thought of as probabilistic algorithms) about a statement that the prover wants to persuade the verifier of [64, 130]. We will in this work consider statements of the form: “(in<sup>,</sup> out) is a valid input-output pair for some procedure <sup>??</sup>.” That is, the succinct proof is aimed at establishing that the alleged out is truly the output when <sup>??</sup> is run on in.

Astonishingly, the data flowing from prover to verifier, and the work required by the verifier, is (at least in principle) much smaller than the work to execute <sup>??</sup>. Yet, a verifier is unlikely to be fooled by a false claim from the prover.

Succinct proof implementations typically have a frontend and a back-end. The front-end compiles <sup>??</sup> into a set of constraints. The back-end is the proving and verifying algorithms. We elaborate on both below.

Front-end: Arithmetization and R1CS. Various proof backends require statements to be compiled, by the front-end, to a rank-one constraint system (R1CS), which we often refer to as constraints. An R1CS structure is a system of <sup>??</sup> equations and <sup>??</sup> variables over a finite field (typically <sup>F</sup>??, the integers mod a prime <sup>??</sup>) with a subset of the variables designated as in and a subset designated as out [118]. These equations are represented by three matrices <sup>??</sup>, <sup>??</sup>, <sup>??</sup>, each of dimension <sup>??</sup> × <sup>??</sup>. An R1CS instance for a given structure is ( <sup>??,</sup> <sup>??,</sup> <sup>??,</sup> in<sup>,</sup> out); we say that an instance is satisfiable if there exists some witness <sup>??</sup> such that, for <sup>??</sup> := (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>), we have: ( <sup>??</sup> · <sup>??</sup>) ◦ (<sup>??</sup> · <sup>??</sup>) − (<sup>??</sup> · <sup>??</sup>) = 0<sup>®</sup>, with ◦ denoting entrywise multiplication. Unpacking the algebra, each constraint <sup>??</sup> ∈ {1<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>} restricts any assignment, that is any valuation of the variables <sup>??</sup> = (<sup>??</sup><sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>??), as follows: ( <sup>??</sup>??,<sub>1</sub><sup>??</sup><sub>1</sub> + · · · + ??<sub>??,??</sub>??<sub>??)</sub> <sub>·</sub> <sub>(</sub>??<sub>??,1</sub>??<sub>1 +</sub> <sub>·</sub> <sub>·</sub> <sub>·</sub> <sub>+</sub> ??<sub>??,??</sub>??<sub>??)</sub> <sub>−</sub> <sub>(</sub>??<sub>??,1</sub>??<sub>1 +</sub> <sub>·</sub> <sub>·</sub> <sub>·</sub> <sub>+</sub> ??<sub>??,??</sub>??<sub>??) = 0</sub>.

As a simple example, take the computation

function ??(??<sub>1</sub>, ??<sub>2</sub>, ??<sub>3</sub>)

![](images/c5c9804c220cb374b8a60d180cb4818441bad7e012fd2a238369be151cb580ab.jpg)

Here in is (<sup>??</sup><sub>1</sub><sup>,</sup> <sup>??</sup><sub>2</sub><sup>,</sup> <sup>??</sup><sub>3</sub>) and out is <sup>??</sup><sub>4</sub>. The first step in translation to R1CS is to unroll the computation so that each line of code is written as a product of linear combinations of variables, minus another linear combination of variables:

function ??(??<sub>1</sub>, ??<sub>2</sub>, ??<sub>3</sub>)

<sup>??</sup><sub>6</sub> ← <sup>??</sup><sub>1</sub> · <sup>??</sup><sub>1</sub> − 4 // <sup>??</sup><sub>6</sub> is a new var, part of the witness ??<sub>4</sub> ← ??<sub>6</sub> · (??<sub>2</sub> + 3??<sub>3</sub>) − 2

return <sup>??</sup><sub>4</sub>

Next, these lines are translated to constraints, each of which becomes a row in the <sup>??</sup>, <sup>??</sup>, <sup>??</sup> matrices. These constraints are:

![](images/e9ebdbdc96e2d320b5dd8e81c7d8c662ce53483178d0458c2129dfc7c642f7cd.jpg)

In matrix form, the constraints are:

![](images/35b686aa7bfd96e1549fe74d51c82cfc36abc2102e73d1f93199c3a44e035967.jpg)

Now, consider this valuation of the in variables: <sup>??</sup><sub>1</sub>=3, <sup>??</sup><sub>2</sub>=2, <sup>??</sup><sub>3</sub>=−1 (these quantities are in <sup>F</sup>??, so −1 is shorthand for <sup>??</sup> − 1), and the corresponding out valuation: <sup>??</sup><sub>4</sub> = −7 (shorthand for <sup>??</sup> − 7). In this case, the full assignment is <sup>??</sup> = [3<sup>,</sup> 2<sup>,</sup> −1<sup>,</sup> −7<sup>,</sup> 1<sup>,</sup> 5] . When subsequently giving example constraints, we drop the explicit “1·”, add the “<sup>??</sup> piece” to both sides, and use semantically appropriate variables to refer to elements of <sup>??</sup>.

One can translate an entire unrolled computation to a set of constraints, in the sense that some <sup>??</sup> satisfies the constraints only if <sup>??</sup> respects the original semantics of the computation. This translation is called arithmetization [7, 17, 18, 24, 35,

36, 49, 75, 81, 96, 97, 115, 118, 138, 146, 147]. It is typically accompanied by a witness generator, which either executes the computation and thereby obtains the assignment to <sup>??</sup> [15, 24, 26,76,81,102], or else solves the constraints using annotations provided by the translation process [35, 75, 96, 100, 114, 115].

Modern proof systems also translate computations into lookup tables [31, 33, 41, 57, 71, 119, 119], often in combination with constraints. However, lookup tables outperform constraints only when the table is small (for example, 2<sup>8</sup> elements) or has algebraic structure [119]. Numerical operations do not generally fit into either of these categories.

Back-end: Proving R1CS satisfiability. The job of the backend is, given an R1CS structure and instance ( <sup>??,</sup> <sup>??,</sup> <sup>??,</sup> in<sup>,</sup> out), to prove that a satisfying assignment exists. The back-end provides the following properties, which we state informally.

• Back-end soundness: If there does not exist a <sup>??</sup> such that <sup>??</sup> := (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>) makes ( <sup>??</sup> · <sup>??</sup>) ◦ (<sup>??</sup> · <sup>??</sup>) − (<sup>??</sup> · <sup>??</sup>) = 0, then the probability (over the verifier’s random choices) that the verifier accepts is negligible.

• Back-end completeness: If a prover has access to <sup>??</sup> such that <sup>??</sup> := (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>) makes ( <sup>??</sup> · <sup>??</sup>) ◦ (<sup>??</sup> · <sup>??</sup>) − (<sup>??</sup> · <sup>??</sup>) = 0, then the prover can make the verifier accept with probability 1, over the prover’s and verifier’s random choices.

For our work, the relevant strand of back-end protocols is based on the sum-check primitive [89]. We defer justifying this choice until we have established the necessary context (§4.1, §4.2.2). The sum-check primitive is an interactive proof [16, 65] by which the prover persuades the verifier that the sum of a given multi-variate polynomial’s evaluations over all Boolean combinations that its variables can take is a given value. (Appendix A reviews this primitive.) Succinct proofs that use the sum-check primitive typically do so multiple times within the same protocol; for example, GKR [66, 67] invokes the sum-check primitive once per layer in a layered circuit while Spartan [116] invokes the primitive twice (loosely speaking, one invocation is over the rows of the R1CS instance and one is over the columns). We call proofs built on the sum-check primitive sum-check protocols [30, 42, 44–46, 48, 60, 66–68, 116, 117, 119, 123, 129, 135–137, 139, 143, 147, 148].

Modern works in this strand [131] rely on polynomial commitment. The idea is that <sup>??</sup> is encoded as a polynomial by the prover; a small commitment (far smaller than <sup>??</sup>) is sent to the verifier; this commitment binds the prover to that polynomial; and one or more invocations of the sum-check primitive prove that an additional polynomial (formed from the prover’s committed polynomial, from in and out, and from the R1CS structure itself) has a certain property that is equivalent to <sup>??</sup> = (<sup>????,</sup> <sup>??????,</sup> 1<sup>,</sup> <sup>??</sup>) satisfying the instance.

The costs of the back-end are driven by the number of constraints, <sup>??</sup> and the number of witness elements, |<sup>??</sup>|. Specifically, the prover’s costs are roughly <sup>??</sup>(<sup>??</sup> + |<sup>??</sup>|). The verifier’s costs vary based on the protocol. Our work follows Spartan [92, 116] (without its SPARK module), where the verifier has an <sup>??</sup>(<sup>??</sup>) fixed cost that is specific to the structure (the constraints); this cost amortizes over synchronized instances, with each instance adding cost that is <sup>??</sup>(log(|<sup>??</sup>|)). There is also an <sup>??</sup> (log(|<sup>??</sup>|)) setup cost, reusable across all future invocations, including diferent R1CS structures. See elsewhere [38, 116, 117, 119] for techniques that asymptotically lower the verifier’s work at the prover’s expense.

To quantify, running the prover on a single machine is generally considered unreasonable when <sup>??</sup> and |<sup>??</sup>| are above 2<sup>29</sup> (unless one possesses terabytes of RAM and hundreds of cores) [108], owing to memory bottlenecks. There are techniques for scaling across a fleet [87, 108, 142, 144], and reducing memory requirements at the cost of increased prover time [20, 93, 99], but neither approach mitigates the sheer amount of work required to prove large computations.

Arithmetization poses a semantic challenge. A salient cost is translating from ordinary computations to R1CS; this appears in the values of <sup>??</sup> and |<sup>??</sup>|. Indeed, there is a massive semantic gap in this research area: ordinary computations do not map to equations over finite fields in a natural way. To highlight the challenge, consider the division of two positive <sup>??</sup>-bit integers. Checking this computation, <sup>??</sup> ← <sup>??</sup>/<sup>??</sup>, in R1CS involves two steps. First, the prover supplies the purported quotient <sup>??</sup> and remainder <sup>??</sup> and the following constraint is added: <sup>??</sup> · <sup>??</sup> = <sup>??</sup> − <sup>??</sup>, where <sup>??</sup> is a witness variable. Second, constraints are required to assert that <sup>??</sup> ≥ (<sup>??</sup>+1) and <sup>??</sup> ≥ (<sup>??</sup>+1).

But finite fields have no native notion of order, so a typical arithmetization of assert(<sup>??</sup> ≥ (<sup>??</sup> + 1)), where <sup>??</sup> and <sup>??</sup> are <sup>??</sup>-bit numbers, introduces witness variables <sup>??</sup><sub>0</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>??<sub>−1</sub> representing the bits of <sup>??</sup> − (<sup>??</sup> + 1). Then, for all <sup>??</sup>, constraints are added to enforce that each variable <sup>??</sup>?? is a bit: <sup>??</sup>?? · (1−<sup>??</sup>??) = 0. Finally, a constraint is added to enforce the relationship among <sup>??</sup>, <sup>??</sup>, satisfiable only if <sup>??</sup> − <sup>??</sup> − 1 is itself a <sup>??</sup>-bit number. This assert alone requires <sup>??</sup> additional variables and <sup>??</sup> + 1 constraints.

This blowup is not isolated to division. Researchers in succinct proofs often perform contortions to represent computations. While there are, for example, more succinct encodings of certain kinds of conditional operations [115], arbitrary low-level operations of the kind that would ordinarily be accelerated in hardware are not well-handled. In particular, representing a single numerical operation in R1CS typically involves explicitly expressing the digital logic of the operation. This results in a number of auxiliary variables and constraints that is a multiple of the number of bits of the numbers being represented in each operation [9, 50, 51, 82, 124] (§7, §8), rather than the number of machine instructions that would be required in an ordinary computing context.

## 3 Problem statement and overview of Spain

Problem statement. A prover and a verifier agree on a single numerical computation, <sup>??</sup>. The verifier sends input in, the prover executes <sup>??</sup> on that input, and claims that the output is out. The prover then wants to persuade the verifier that out indeed could have been produced by <sup>??</sup> (in), given the kinds of approximation that are inherent in fixed- or floating-point numerical computation. The verifier should spend fewer computational resources than if it ran <sup>??</sup> (in) itself; otherwise, the verifier could disregard out, and simply use the result of executing <sup>??</sup> on in. We will sometimes work in an amortized setting where multiple instances of <sup>??</sup> are outsourced on in<sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> in?? diferent inputs, getting diferent outputs out<sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> out?? .

The core conflict. On the one hand, existing proof machinery ensures that an execution proceeded exactly as it was supposed to. On the other hand, in the numerical context “supposed to” means “certain error”. To resolve this conflict between exactness and error, any protocol must reject truly wrong executions, namely those that include any operations with more than <sup>??</sup> error (§2.1). At the same time, the protocol must not be too much of a scold: if all operations do obey the <sup>??</sup> error bound, then the given execution should be accepted.

As noted in Section 2.2, some works handle this tension by representing the digital logic of the approximate computation in the arithmetization (the R1CS instance). A related approach is for the prover to embed in the R1CS instance variables that capture each operation’s error, thereby making the error incurred by each operation part of the statement to be validated [59]. Both approaches bring expense.

Overview of Spain. In contrast to existing work, Spain’s arithmetizations are agnostic to the error in each operation, yet the prover is forced to adhere to the bounds. Spain combines several new techniques, in the front-end and back-end. Figure 1 depicts Spain, contrasting it with the most natural baseline.

Front-end (§5): Spain introduces a new kind of arithmetization; it translates <sup>??</sup> to a set of constraints over the rational numbers <sup>Q</sup> (rather than a finite field <sup>F</sup>??) in way that satisfying all constraints up to some <sup>??</sup> corresponds to error up to <sup>??</sup> in each operation. Each constraint <sup>??</sup> ∈ {1<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>} enforces:  ????,<sub>1</sub>??<sub>1</sub> + · · · + ????,?????? ·  ????,<sub>1</sub>??<sub>1</sub> + · · · + ????,?????? −  <sup>??</sup>??,<sub>1</sub><sup>??</sup><sub>1</sub> + · · · + <sup>??</sup>??,??<sup>??</sup>??<sup></sup> ≤ <sup>?? .</sup> We call such constraints approximate constraints; compare to the constraints in §2.2 that enforce equality, which we call traditional constraints.

Approximate constraints are dramatically more concise than the alternative; in fact, each low-level operation in <sup>??</sup> generally corresponds to one or a small number of constraints. The intuition is that constraints in Spain are freed from operating on the bits of operands, being expressed over <sup>Q</sup>, and are freed from explicitly encoding approximation error, as “≤ <sup>??</sup>” encodes slackness directly. The trade-of is that a user of Spain must perform certain analyses not needed when working with traditional constraints. This requirement is a manifestation of the conflict stated earlier: the user must show that satisfying the constraints means the prover adhered to “≤ <sup>??</sup>” error, and also show that if the prover does execute the operation with bounded error, then it can satisfy the approximate constraints.

![](images/e335d4b5d39747060faea6ed145de79ee01d8d162d3b60aee9cf0dc766ce9018.jpg)  
Figure 1: High-level comparison between existing proof systems (left) and Spain (right). Given an initial claim, the protocol is divided into two phases: arithmetization and proving. Similar steps are vertically aligned to facilitate comparison.

Back-end (§4): Spain’s back-end enables a prover to establish that a given assignment (to a given set of constraints) meets the <sup>??</sup> bounds. We call such an assignment <sup>??</sup>-accurate.

Compared to prior work, Spain’s back-end has three interlocked aspects. First, Spain maps the constraints over <sup>Q</sup> to a finite field, which is the kind of domain typically used in sum-check protocols (§2.2). However, preserving the semantics of the constraints in the finite field requires care; a key mechanism is that the verifier chooses the finite field (via prime <sup>??</sup>) only after the prover commits to the assignment.

Second, Spain establishes a statement that implies <sup>??</sup>-accuracy. Specifically, Spain modifies Spartan [116] to prove a statement about the sum of each constraint’s squared error, for a given assignment; this sum will be notated as ∥<sup>??</sup>X,?? ∥<sup>2</sup>. As we argue later, by proving that ∥<sup>??</sup>X,?? ∥<sup>2</sup> is small, the protocol guarantees that the assignment obeyed the required <sup>??</sup> bounds. Third, Spain uses a polynomial commitment protocol (§2.2) that is geared to integers, but makes several technical adjustments, as naive use of this primitive in our context would be prohibitive.

## 4 Spain’s approximation-friendly back-end

This section presents the core statement that Spain’s back-end proves (§4.1) and the techniques that it uses to do so (§4.2– §4.3). First, though, we must define what it means for a backend to be correct in Spain’s context. We do so by modifying the existing back-end notions of soundness and complete ness (§2.2). The modified properties are as follows, with respect to an R1CS instance <sup>X</sup> = ( <sup>??,</sup> <sup>??,</sup> <sup>??,</sup> in<sup>,</sup> out):

• Back-end <sup>??</sup>-soundness. If there does not exist a <sup>??</sup> such that <sup>??</sup> := (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>) is <sup>??</sup> -accurate for <sup>X</sup>, then the probability <sup>??</sup> (over the verifier’s random choices) that the verifier accepts is negligible. <sup>??</sup> is known as soundness error.

• Back-end <sup>??</sup>??-completeness. A prover with access to <sup>??</sup> such that <sup>??</sup> := (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>) is <sup>??</sup>??-accurate for <sup>X</sup> can make the verifier accept with probability 1, over the prover’s and verifier’s random choices in the protocol.

These definitions embed two diferent levels of <sup>??</sup>-accuracy; at the end of Section 4.1 below, we will see that <sup>??</sup>?? <sup><</sup> <sup>??</sup>. To preview the practical consequence, an honest prover will have to execute with greater precision (for completeness) than what the protocol guarantees to the verifier (via soundness).

## 4.1 What claim about error should be proved?

Spain’s back-end must establish the <sup>??</sup>-accuracy of an assignment <sup>??</sup>. Before highlighting the challenges, we give a compact notation for <sup>??</sup>-accuracy. Define the error vector <sup>??</sup>X,?? for an R1CS instance <sup>X</sup> = ( <sup>??,</sup> <sup>??,</sup> <sup>??,</sup> in<sup>,</sup> out) and an assignment <sup>??</sup> = (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>) as:

![](images/fb31cd68584b282e645f4f255a925e00a7e378b246ad4b2224a692f3793921eb.jpg)

This error vector has <sup>??</sup> components. Its <sup>??</sup>th component is ( <sup>??</sup>?? · <sup>??</sup>) · (<sup>??</sup>?? · <sup>??</sup>) − (<sup>??</sup>?? · <sup>??</sup>) <sup>,</sup> where <sup>??</sup>??, <sup>??</sup>??, and <sup>??</sup>?? are the <sup>??</sup>th rows of <sup>??</sup>, <sup>??</sup>, and <sup>??</sup>. Notice that if the component with maximum absolute value is upper-bounded by <sup>??</sup>, that is equivalent to saying that the assignment <sup>??</sup> for the instance <sup>X</sup> is <sup>??</sup>-accurate (§3). Meanwhile, the maximum absolute value over all components of <sup>??</sup>X,?? is, by definition, the <sup>ℓ∞</sup> norm of <sup>??</sup>X,??, denoted ∥<sup>??</sup>X,?? ∥<sub>∞</sub>. Thus, <sup>??</sup>-accuracy can be written:

![](images/edda2ecdec5c85c8c2340c0675e8929a7e05c0c6546873fffd1a36d72aa11edd.jpg)

One challenge is that we don’t know how to apply proving machinery to this inequality directly. Sum-check protocols (§2.2), for example, work over polynomial expressions. Although Spartan [116] shows how to cast R1CS satisfiability as suitable polynomial expressions, the <sup>ℓ</sup> norm cannot be turned into polynomial expressions, because of the absolute value and maximum operations.

Instead, our insight here is that the square of the <sup>ℓ2</sup> norm is compatible with sum-check protocols, and this quantity upperbounds the square of the <sup>ℓ∞</sup> norm. Specifically, for a vector <sup>??</sup>, the square of the <sup>ℓ2</sup> norm, ∥<sup>??</sup>∥<sup>2</sup>, is Í<sup>??</sup><sub>??=1</sub> <sup>??2</sup><sub>??</sub> . Also, the definitions of the norms imply that for any vector <sup>??</sup>, ∥<sup>??</sup>∥<sup>2</sup><sub>∞</sub> ≤ ∥<sup>??</sup>∥<sup>2.</sup> So, if the prover could persuade the verifier that

![](images/201f7de5c2bd3fecc683306c7c6325bda0238dae4956e549ef7d300f5ec40d98.jpg)

(1)

for some <sup>??</sup>, and if the verifier then checked that <sup>??</sup> ≤ <sup>??2</sup>, that would sufice to establish that ∥<sup>??</sup>X,?? ∥<sub>∞</sub> ≤ <sup>??</sup>.

However, there is another dificulty. While ∥<sup>??</sup>X,?? ∥<sup>2</sup> ≤ <sup>??2</sup> implies ∥<sup>??</sup>X,?? ∥<sub>∞</sub> ≤ <sup>??</sup>, the converse is not true. Consequently, an assignment <sup>??</sup> could well satisfy ∥<sup>??</sup>X,?? ∥<sub>∞</sub> ≤ <sup>??</sup>, but Equation (1) would not hold for any <sup>??</sup> ≤ <sup>??2</sup>. In a full protocol, an honest prover would then have no way to convince the verifier.

To address this, the execution by the prover has to be more accurate than <sup>??</sup>. Specifically, while Spain must meet Backend <sup>??</sup>-soundness, it must meet Back-end <sup>??</sup>??-completeness, where <sup>??</sup>?? = <sup>??</sup>/ <sup>??</sup>. (The gap between <sup>??</sup> and <sup>??</sup>?? can be narrowed; §D.3.) Under these conditions, there does exist <sup>??</sup> ≤ <sup>??2</sup> with ∥<sup>??</sup>X,?? ∥<sup>2</sup> = <sup>??</sup>. To see this, notice that the definitions of the norms imply that for any vector <sup>??</sup>, ∥<sup>??</sup>∥<sup>2</sup> ≤ <sup>??</sup> · ∥<sup>??</sup>∥<sup>2</sup><sub>∞</sub><sup>.</sup> Consequently, requiring that the prover produces an <sup>??</sup>??-accurate <sup>??</sup> yields ∥<sup>??</sup>X,?? ∥<sub>∞</sub> ≤ <sup>??</sup>?? = <sup>??</sup>/ <sup>??</sup> and thus:

![](images/e488b1d31489cb1ba488f0588ef3f63e2fc46ce4b0d08cd6a229f8d6b6ec93c7.jpg)

## 4.2 Main protocol

Spain’s back-end aims to establish Equation (1). Spain adapts three existing tools, specifically Spartan [116], which is a sum-check protocol (§2.2) that targets R1CS instances, and forms the core of Spain’s back-end; DARK [40], which is a polynomial commitment protocol (§2.2) with the ability to bind the prover to a polynomial over <sup>Q</sup>; and Zaratan [42], which is a framework for proving traditional R1CS satisfiability over the integers, as opposed to over a finite field.

One of the configurations explicitly considered by Zaratan is combining Spartan and DARK, and we will do likewise. Specifically, whereas Spartan assumes that an R1CS structure is defined over a finite field (typically <sup>F</sup>??; §2.2), Zaratan observes that <sup>??</sup> can be chosen at run-time by the verifier, after the prover commits to an encoded version of <sup>??</sup> via DARK.

Spain’s full protocol is given in Appendix B. Figure 2 provides an overview. This protocol embeds three major changes compared to prior work, as outlined below.

## 4.2.1 Proving statements over <sup>Q</sup>

Constraints in Spain are expressed over the rational numbers, <sup>Q</sup>. However, the sum-check primitive is typically applied over a finite field (§1, §2.2). Accordingly, Spain maps Equation (1) into a corresponding claim over a finite field, namely <sup>F</sup>??. But, this mapping is fraught; to highlight the challenge, we introduce some mathematical language.

Define <sup>Q(??)</sup> as {(<sup>??,</sup> <sup>??</sup>) ∈ <sup>Q</sup> | <sup>??</sup> <sup>∤</sup> <sup>??</sup>}. This set is the rational numbers without multiples of <sup>??</sup> in the denominator.<sup>1</sup> Spain

1. The prover runs an agreed-upon computation <sup>??</sup>, thereby producing <sup>??</sup>.

2. Using DARK, the prover encodes <sup>??</sup> as a polynomial, <sup>??</sup>; commits (§2.2) to that polynomial; and sends this commitment to the verifier, efectively binding itself to the value of <sup>??</sup>X,??.

3. The prover computes and sends <sup>??</sup> to the verifier; <sup>??</sup> is purportedly ∥<sup>??</sup>X,?? ∥<sup>2</sup>.

4. The verifier checks that <sup>??</sup> is less than <sup>??2</sup>.

5. The verifier sends a prime <sup>??</sup> to the prover randomly chosen from a set of large primes.

6. The prover and verifier map all rationals to elements of <sup>F</sup>?? and apply the sum-check protocol to the claim <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>) = <sup>??</sup>?? (<sup>??</sup>), reducing it to a claim about <sup>??</sup>.

7. The verifier checks consistency between the claim in Step 6 and the commitment to <sup>??</sup> in Step 2.

## Figure 2: Spain’s back-end protocol (simplified).

maps these numbers into a finite field, via:

![](images/64d81301b4659837d1c3e120179e2a2860a37b00126fbe973e879784a1844cb3.jpg)

and the Spain prover and verifier apply a sum-check protocol to the claim:

![](images/8b8ba7602d04110e279a41970375246e58c98a36db90318b8276e787d39d989a.jpg)

(2)

However, for this approach to make sense, there are two requirements. First, arithmetic must stay in <sup>Q( )</sup> , otherwise <sup>??</sup>?? is undefined. Second, unequal quantities in <sup>Q( )</sup> should stay unequal after the mapping. That is, if ∥<sup>??</sup>X,?? ∥<sup>2</sup> ≠ <sup>??</sup>, then <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>) = <sup>??</sup>?? (<sup>??</sup>) should not occur, except with negligible probability (over the verifier’s choice of <sup>??</sup>).

Spain achieves both requirements through a combination of convention, DARK, and the verifier’s checks. The starting convention is that all rational numbers in the <sup>??,</sup> <sup>??,</sup> <sup>??</sup> matrices that define an R1CS instance <sup>X</sup> are presumed to have a denominator <sup>??</sup> that is a power of two; thus <sup>??</sup> does not divide <sup>??</sup>. Furthermore, the assignment <sup>??</sup> is supposed to follow this convention as well. DARK partially preserves the convention, by ensuring that all committed rationals (Step 2) have the same denominator but not necessarily that it is exactly <sup>??</sup>. Surprisingly, this partial preservation does not give the prover room to cheat without detection (§B). For simplicity, our description below assumes that DARK preserves the convention fully.

One consequence is that arithmetic begins in <sup>Q(??)</sup>, and stays there. Thus, <sup>??</sup>?? is defined on all intermediate values and the result. To see this, notice that the convention ensures that the entries of <sup>??</sup> · <sup>??</sup>, <sup>??</sup> · <sup>??</sup>, and <sup>??</sup> · <sup>??</sup> have denominator <sup>??2</sup>; the entries of ( <sup>??</sup> · <sup>??</sup>) ◦ (<sup>??</sup> · <sup>??</sup>) have denominator <sup>??4</sup>, and the values of ( ( <sup>??</sup>?? · <sup>??</sup>) · (<sup>??</sup>?? · <sup>??</sup>) − (<sup>??</sup>?? · <sup>??</sup>))<sup>2</sup>, and hence ∥<sup>??</sup>X,?? ∥<sup>2</sup>, have denominator <sup>??8</sup>. The verifier completes the enforcement by requiring <sup>??</sup> to have denominator <sup>??8</sup>.

Another consequence is that this approach avoids collisions. If ∥<sup>??</sup>X,?? ∥<sup>2</sup> and <sup>??</sup> are not equal, then given that they have the same denominator, <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>) = <sup>??</sup>?? (<sup>??</sup>) only if the numerator <sup>??</sup> of ∥<sup>??</sup>X,?? ∥<sup>2</sup><sub>2</sub> − <sup>??</sup> is a multiple of <sup>??</sup>. Analysis shows that by limiting the numerators of the entries of <sup>??</sup>, <sup>??</sup>, <sup>??</sup>, and <sup>??</sup>, <sup>??</sup> can be kept small enough that the probability of a randomly chosen large prime, like <sup>??</sup>, dividing <sup>??</sup> is low (Appx. B.5).

Both Spain and Zaratan [42] map a claim from a larger domain (in their case <sup>Z</sup>, in Spain’s case <sup>Q</sup>) to some <sup>F</sup>??. However, the introduction of a denominator in Spain significantly complicates the analysis of collisions.

The bottom line is that Spain ensures that if the prover sends a <sup>??</sup> ≠ ∥<sup>??</sup>X,?? ∥<sup>2</sup> (Step 3, Figure 2), then with overwhelming probability over the choice of <sup>??</sup> in Step 5, <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>) ≠ <sup>??</sup>?? (<sup>??</sup>). Consequently, if the prover did lie in Step 3, it would be stuck trying to prove a false statement in Step 6.

## 4.2.2 Proving a new type of claim

To prove that <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>) = <sup>??</sup>?? (<sup>??</sup>), Spain observes that an adaptation of Spartan can directly prove statements about the squared <sup>ℓ2</sup> norm of the errors in an R1CS instance.

To explain how Spain both borrows and diverges from Spartan, we must present some further mathematical detail. One can view <sup>??,</sup> <sup>??,</sup> <sup>??</sup> ∈ <sup>F??×??</sup><sub>??</sub> , and <sup>??</sup> ∈ <sup>F??</sup><sub>??</sub> as functions. Specifically, letting <sup>??</sup> = ⌈log <sup>??</sup>⌉ and <sup>??</sup> = ⌈log <sup>??</sup>⌉, we view the matrices as functions {0<sup>,</sup> 1} × {0<sup>,</sup> 1} → <sup>F</sup>??. For example, <sup>??</sup>(<sup>??,</sup> <sup>??</sup>) is the entry of <sup>??</sup> at the row given by the binary representation of <sup>??</sup> and the column given by the binary representation of <sup>??</sup>. We do the same for <sup>??</sup>, viewing it as a function {0<sup>,</sup> 1} → <sup>F</sup>??.

An important concept is a polynomial extension of a discrete function. The polynomial extension of a function agrees with that function everywhere the function is defined, but the polynomial is defined over a larger domain. A polynomial extension can be thought of as an encoding of that function. As a simple example, imagine defining a function <sup>??</sup> at points 0 and 1, and drawing a line (a first-degree polynomial) through <sup>??</sup> (0) and <sup>??</sup> (1). The entire line – its description, or any two points on it – encodes the values of <sup>??</sup> (0) and <sup>??</sup> (1). We denote multilinear extensions with tildes. For example, for a function <sup>??</sup> (·) defined over <sup>??</sup> ∈ {0<sup>,</sup> 1} , the multilinear extension of <sup>??</sup> is <sup>˜??</sup> : <sup>F??</sup><sub>??</sub> → <sup>F</sup>??, which is a polynomial that equals <sup>??</sup> on {0<sup>,</sup> 1}<sup>??</sup>, with degree no more than 1 in each variable.

Now, let <sup>??</sup> stand in for <sup>??</sup>, <sup>??</sup>, or <sup>??</sup>, and let <sup>??</sup>?? (<sup>??</sup>) := Í?? , ?? <sup>??</sup> (<sup>??,</sup> <sup>??</sup>) · <sup>??</sup>(<sup>??</sup>)<sup>,</sup> where <sup>??</sup> and <sup>??</sup> are the multilinear extensions of <sup>??</sup> and <sup>??</sup>, respectively (when mapped to <sup>F</sup>??). Also, let Eq(·<sup>,</sup> ·) return 1 if its two arguments, viewed as <sup>??</sup>-bit strings, are the same and 0 otherwise; denote the multilinear extension of Eq as Eq.

In Spartan (and Zaratan), the prover aims to persuade the verifier of the following, where <sup>??</sup> is chosen randomly [116, §4]:

![](images/6a74344e5b5940bb4c890e0ca57a8812fe481027a80a6ff96bf3273c5d7cd641.jpg)

(3)

In Spain, by contrast, the prover aims to persuade the verifier (in Step 6) that the following holds:

![](images/fd3bb0deddaeeeb11a2a9235d002fc9c020486b65df71c65ab3e2ca8e9563583.jpg)

(4)

Notice from the definition of extension that the left-hand side above sums the squared error for each constraint, given assignment <sup>??</sup>, when the constraints and <sup>??</sup> are mapped to <sup>F</sup>??. That sum is <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>). Thus, the protocol is indeed establishing Equation (2). After this step, Spain follows Spartan.

## 4.2.3 Accelerating and adapting DARK

Spain makes two sets of modifications to DARK. First, whereas DARK normally works over a group of order unknown to both prover and verifier, Spain exploits interactivity to have the verifier generate a group for which it alone knows the order. Appendix C details this technique.

Second, DARK as originally proposed had an error: it provided only a weak binding property, namely it ensured only that the committed-to polynomial had rational coeficients [29]. This was problematic for Zaratan and other uses of DARK (for example, in combination with Spartan), as those uses require a polynomial with integer coeficients. Thus, Zaratan (and other protocols) layer techniques [29, 42] atop DARK, which have extra costs. However, in our context, the original (weaker) form of DARK sufices. Appendix B gives details.

## 4.3 Support for batching and “just in time” R1CS

Spain supports two variants of R1CS. The first is a SIMD-R1CS instance [134], which is a combination of <sup>??</sup> R1CS instances with the same structure (that is, multiple executions of the same program on diferent inputs). The second is an I-R1CS instance [97], where the prover and verifier interact to construct the full instance. Given a partial R1CS instance (one with some variables missing), the prover and verifier take turns filling it in. In round <sup>??</sup>, the prover commits to <sup>??</sup>??, and the verifier sends additional in??. The final R1CS instance has assignment <sup>??</sup> := (in<sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> in?? <sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup><sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup> ?? ).

Spain extends I-R1CS in a natural way: in Spain, the verifier may also supply constraints. Thus, the prover and verifier start with a partial structure, and as the prover commits to <sup>??</sup>?? in round <sup>??</sup>, the verifier submits in?? or new constraints. Further details of Spain’s support for R1CS variants are in Appendix D.

## 5 Encoding numerical operations in R1CS

This section describes how, by taking advantage of the backend claim of <sup>??</sup>-accuracy (§4), Spain produces dramatically more concise arithmetizations versus the traditional approach.

Using approximate constraints (§3) requires a new kind of correspondence between a numerical function <sup>??</sup> and an

R1CS structure that allegedly arithmetizes <sup>??</sup>. Roughly speaking, (a) any assignment that is <sup>??</sup>-accurate (§3) for the constraints should correspond to an execution of <sup>??</sup> with operations bounded by <sup>??</sup> (§2.1), and (b) for every execution of <sup>??</sup> with operations bounded by <sup>??</sup><sub>wg</sub> (where <sup>??</sup><sub>wg</sub> is a constant smaller than <sup>??</sup>) there should be an <sup>??</sup>??-accurate assignment. The need for separate <sup>??</sup> and <sup>??</sup><sub>wg</sub> reflects the same asymmetry that leads to <sup>??</sup>?? <sup><</sup> <sup>??</sup> (§4). Appendix E formalizes (a) and (b) as transla tion fidelity, and proves that the constraints described in this section meet these properties.

Note that translation fidelity concerns the error in each operation, not the accumulated error in the output of a computation. This is analogous to how the IEEE floating-point specification [2] bounds the error in each operation and relies on numerical analysis to derive bounds on the accumulated error.

Below we present arithmetizations using approximate constraints, notating them with ≈?? . For example, <sup>??</sup><sub>1</sub> · <sup>??</sup><sub>2</sub> ≈?? <sup>??</sup><sub>3</sub> enforces |<sup>??</sup><sub>1</sub> · <sup>??</sup><sub>2</sub> − <sup>??</sup><sub>3</sub>| ≤ <sup>??</sup>.

Division and square root. Recall that checking <sup>??</sup> ← <sup>??</sup>/<sup>??</sup> traditionally requires dozens of constraints (§2.2). Spain uses one constraint: <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>.

In traditional constraints, the square root operation (<sup>??</sup> ← <sup>??</sup>) is encoded as <sup>??</sup> · <sup>??</sup> = <sup>??</sup> − <sup>??</sup> plus dozens of constraints to bound <sup>??</sup> in terms of <sup>??</sup> and <sup>??</sup>. Spain again requires only one constraint: <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>. This takes advantage of the fact that all real square roots have arbitrarily close rational approximations. If one wants a specifically positive or negative root, one applies the square root operation again! For example, suppose we want <sup>??</sup> to be the negative square root of <sup>??</sup>. Then we use an additional constraint: <sup>??</sup> · <sup>??</sup> ≈?? −<sup>??</sup>, exploiting the fact that −<sup>??</sup> must be non-negative to have a real square root.

Note that this encoding of the square root operation can be satisfied when <sup>??</sup> is a small negative number, in contrast to usual numerical computations, where Not a Number (NaN) would arise. If this is problematic, the constraints and/or numerical analysis should ensure that the function’s input is strictly non-negative.

The power of approximate square roots. In traditional arithmetization, bottlenecks include range checks, branching, max, and min. As we show next, Spain arithmetizes approximate versions of these operations orders of magnitude more eficiently, using square roots.

assert (x ≥ y). Recall from Section 2.2 that this operation required <sup>??</sup> additional variables and <sup>??</sup> + 1 constraints. Spain requires only 1 constraint and 1 additional variable, regardless of bit width: <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup> − <sup>??</sup>, for some witness variable <sup>??</sup>. This is not a strict translation of assert but instead an approximate version that allows <sup>??</sup> to be <sup>??</sup> smaller than <sup>??</sup> but no smaller.

b ← (x ≥ y). Spain requires only 3 constraints and 2 auxiliary variables: <sup>??</sup> · (1 − <sup>??</sup>) ≈?? 0, (2<sup>??</sup> − 1) · (<sup>??</sup> − <sup>??</sup>) ≈?? <sup>??</sup>, and <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>. The first constraint ensures that <sup>??</sup> is Boolean. The second ensures that <sup>??</sup> is non-negative only when <sup>??</sup> correctly reflects the comparison. The third ensures that <sup>??</sup> is indeed non negative. As with square root and assert, this comparison is an approximate version; Appendix E.2 delves into the semantics.

max. Consider <sup>??</sup> ← max(<sup>??</sup>) for an array <sup>??</sup> = [<sup>??</sup><sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>??]. Spain’s approach here is inspired by Distiller [76], which encodes a checker for min, rather than embedding logic to identify the minimum. However, Distiller requires <sup>??</sup> · (<sup>??</sup> +3) +1 constraints and <sup>??</sup> · (<sup>??</sup> + 2) witness variables, where <sup>??</sup> is the bit-widths of the elements in the array. Spain’s are far more concise because it pays so little for comparison operations:

<sub>•</sub> <sub>for</sub> <sub>all</sub> ?? <sub>∈</sub> <sub>{1</sub>, . . . , ?? <sub>}:</sub> ??<sub>?? ·</sub> ??<sub>?? ≈??</sub> ?? <sub>−</sub> ??<sub>??</sub>

• for all <sup>??</sup> ∈ {1<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup> }: <sup>??</sup>?? · (1 − <sup>??</sup>?? ) ≈?? 0

• for all <sup>??</sup> ∈ {1<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup> }: <sup>??</sup>?? · (<sup>??</sup> − <sup>??</sup>?? ) ≈?? 0

![](images/6de94ce69af1b69b2b4f78bfcd42a7cf61fa995d067b9ab11072215e8a6c4d56.jpg)

The first set ensures that <sup>??</sup> is greater than or equal to all elements in the array. The next two sets ensure that <sup>??</sup>?? is Boolean and that <sup>??</sup>?? can be 1 only if <sup>??</sup>?? = <sup>??</sup> (to support multiple equal maxima, <sup>??</sup>?? is allowed to be 0 even when <sup>??</sup>?? = <sup>??</sup>). The last ensures that exactly one of the <sup>??</sup>?? is 1. This requires 3 · <sup>??</sup> + 1 constraints and 2 · <sup>??</sup> auxiliary variables.

Piecewise functions, sorting, and beyond. The encoding of comparisons naturally leads to eficient translations of piecewise functions; ReLU will demonstrate this below. Similarly, the previous best solutions for sorting or for string manipulation paid relative to the number of bits in their inputs due to comparisons, while Spain’s approach more closely matches the number of instructions in a typical CPU execution.

ReLU is a primitive in machine learning contexts. The operation is <sup>??</sup> ← max(0<sup>,</sup> <sup>??</sup>). This function can be represented in constraints as <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup> − <sup>??</sup>, <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>, and (<sup>??</sup> − <sup>??</sup>) · <sup>??</sup> ≈?? 0. The first two ensure that <sup>??</sup> ≥ max(0<sup>,</sup> <sup>??</sup>). The last one ensures that <sup>??</sup> = 0 or <sup>??</sup> = <sup>??</sup>.

Transcendental functions. Arithmetizing transcendental functions, such as <sup>????</sup> or tanh(<sup>??</sup>), over some interval traditionally uses polynomial approximation [50, 51, 78, 82, 105, 124, 128,151]. Specifically, for a function <sup>??</sup> (<sup>??</sup>) to be approximated, one identifies a polynomial <sup>??</sup>(<sup>??</sup>) such that |<sup>??</sup>(<sup>??</sup>) − <sup>??</sup> (<sup>??</sup>)| ≤ <sup>??</sup> for <sup>??</sup> in the given interval. The motivation is that add and multiply, which are the operations that polynomials require, are the easiest to represent in traditional constraints.

However, there is an additional issue (besides the overhead from traditional enforcement of numerical operations in constraints): polynomials require many terms to converge. Drawing on its support for division, Spain uses rational approximations: a ratio of polynomials <sup>??</sup>(<sup>??</sup>)/<sup>??</sup>(<sup>??</sup>) such that |<sup>??</sup>(<sup>??</sup>)/<sup>??</sup> (<sup>??</sup>) − <sup>??</sup> (<sup>??</sup>) | ≤ <sup>??</sup> for <sup>??</sup> in the interval. In Spain, rational approximations cost nearly nothing extra over polynomial approximations, but rational approximations converge faster. To illustrate, compare the degree-4 Taylor series for <sup>??</sup> :

![](images/39a71e36df1523f53b0d303ec394aa72536159c34ab7f534ce3e9282e2d28426.jpg)

to the degree-[4/4] Padé approximant [98]:

![](images/8e47d9bd5c636efc0b6d34a990b3225f6037355377a8e84021704bcb6c1849cd.jpg)

Note that the number of constraints for the two approaches is the same (for translating <sup>ℎ</sup>(<sup>??</sup>), Spain memoizes the powers of <sup>??</sup>). One can compare accuracy (using a computer algebra system or a large piece of paper), and consider the size of the intervals for which |<sup>??</sup>(<sup>??</sup>) − <sup>??</sup> | ≤ <sup>??</sup> and |<sup>ℎ</sup>(<sup>??</sup>) − <sup>??</sup> | ≤ <sup>??</sup> respectively. In this example, take <sup>??</sup> = 0<sup>.</sup>01. The Taylor Series (<sup>??</sup>) has error at most 0<sup>.</sup>01 over the interval [−1<sup>.</sup>07<sup>,</sup> 1<sup>.</sup>00] and larger errors outside this interval. The Padé approximant (<sup>ℎ</sup>) has error at most 0<sup>.</sup>01 over [−8<sup>.</sup>11<sup>,</sup> 2<sup>.</sup>84]. In fact, the degree [2/2] Padé approximant has error at most 0<sup>.</sup>01 over [−2<sup>.</sup>18<sup>,</sup> 1<sup>.</sup>16]: better than the degree-4 Taylor series.

Better approximations (more accuracy, wider interval) for the same number of terms also translates to fewer variables and hence fewer constraints to achieve the same accuracy. Going beyond exponentials, the technique of rational approximation works for a large class of functions.

Concurrent work [124] makes a similar observation; they find that for highly precise approximations, arithmetizations (of high-degree polynomials) can be even more expensive than traditional arithmetizations of division. These authors then incorporate Padé approximations to existing proof pipelines, obtaining a small speedup. Their paper contains many intriguing examples of approximation using this technique. All of these examples can be used in Spain directly, only with lower cost, because division is so inexpensive in Spain.

## 6 Implementation of Spain

## 6.1 Back-end implementation

Spain’s back-end implements the protocol described in Section 4.2. It also supports SIMD-R1CS and I-R1CS (§4.3).

Spain implements fixed-size large integer arithmetic with inline limb storage; this avoids the performance cost of existing large integer libraries’ [3–5] heap allocation of limb arrays. This functionality is used to compute and check <sup>??</sup> (Steps 3 and 4 in Fig. 2). Spain also implements 64- and 128-bit finite field arithmetic, with support for fast type conversion from large integers (Step 6); Spain does not use existing finite field libraries [11] because they optimize at compile time for a specific field, whereas in Spain, the finite field is determined only at run time. Finally, Spain implements fixed-size RSA group arithmetic, to do fast modular arithmetic for moduli not known at compile time (Steps 2 and 7).

Spain’s back-end is implemented in 12,135 lines of Rust, including the new libraries.

## 6.2 Front-end implementation

We implemented three front-ends for Spain.

Gadget front-end. This front-end provides a library of gadgets [113,150] (pairs of functions where the first generates constraints and the second generates witness values satisfying them), including the primitives in Section 5. The framework is modular and extensible.

ONNX front-end. ONNX [95, 132] is a specification for machine learning models. In ordinary use, one describes a model in ONNX’s format (a collection of nodes), and then a highly optimized run-time executes the model on the available hardware. Spain’s ONNX front-end translates from the ONNX format to approximate constraints. For the accompanying witness generator (§2.2), we had hoped to reuse ONNXcompatible run-times and tools; however, existing run-times neither produce satisfying assignments to auxiliary variables of the kind that arise in arithmetization (§5) nor run with the high-precision floating-point types that Spain uses (§6.3).

Spain solves this challenge with two sub-components. The first is a model translator that converts an ONNX model to a verbose version of the model, whose nodes produce output that includes the auxiliary information. In the process, the model translator rewrites transcendental functions to use rational approximations (§5), using the textbook implementation of the Remez algorithm [104]. The translator also modifies the operations in the model to specify higher-precision data types (for example, double- or quadruple-precision floating point instead of single-precision floating point). The second subcomponent is a from-scratch ONNX executor that supports these high-precision data types. This executor implements each ONNX operator that appears in Spain’s benchmarks (§7).

Linear programming front-end. This front-end is specialized to linear programming problems for comparison with prior work (§7), specifically Otti [9].

Spain’s front-ends are implemented in, respectively, 2898 lines of Rust; 4747 lines of Python and 2025 lines of Rust; and 1524 lines of Rust.

## 6.3 Numerical considerations

A user of Spain begins with a particular computation <sup>??</sup> and desired error <sup>??</sup>. Note that the choice of <sup>??</sup> is exogenous to Spain, and should be driven by numerical considerations (§2.1). The user must then determine: (a) <sup>??</sup>, to inform the verifier’s check of <sup>??</sup> (§4), (b) <sup>??</sup><sub>wg</sub>, the precision at which the prover must run <sup>??</sup> (§5, Appx. E), and (c) <sup>??</sup>, the denominator used in the arithmetization of <sup>??</sup> (§4.2.1, Appx. B). The general recipe for doing so is as follows. First, translate <sup>??</sup> to R1CS. Next, perform numerical analysis on each operation in the translation and compose the analyses to obtain an upper bound on <sup>??</sup> in terms of <sup>??</sup> (Appx. E.2). This <sup>??</sup>, along with the number of constraints, <sup>??</sup>, upper-bounds <sup>??</sup>?? (§4). Finally, returning to the numerical analysis, <sup>??</sup>?? enforces an upper bound on <sup>??</sup><sub>wg</sub> and on 1/<sup>??</sup>, and thus a lower bound on <sup>??</sup> (Appx. E.2).

One could perform this last step analytically; essentially one would determine the maximum magnitude of values in the computation over all possible inputs, and then choose smallenough <sup>??</sup> and 1/<sup>??</sup> to ensure each constraint has error upperbounded by <sup>??</sup>??. For convenience, we instead guess (by running the witness generator at an estimated high precision) and check (by observing that it produces a witness for which ∥<sup>??</sup>X,?? ∥<sup>2</sup> ≤ <sup>??</sup>). This approach is not dangerous: choosing <sup>??</sup><sub>wg</sub> and 1/<sup>??</sup> too large – meaning underestimating the required precision – cannot afect soundness (which holds regardless of the prover’s behavior). Furthermore, if there were such an underestimate, the prover could recalibrate and run witness generation at higher precision for all subsequent proof generations; witness generation is not the primary bottleneck for the prover (§7.2). For the same reason, accidentally overestimating precision does not unduly increase costs.

In Section 7, we provide values of <sup>??</sup>, <sup>??</sup>, <sup>??</sup>??, and <sup>??</sup> for the benchmarks in our experiments. Here, we work through their derivation for one example, a fluid simulation with <sup>??</sup> = 2<sup>−32</sup>.

By analyzing the translation to R1CS (Appx. E), we get that <sup>??</sup> = <sup>??</sup>/4 sufices: an <sup>??</sup>-accurate assignment to the constraints ensures absolute error of <sup>??</sup> = 2<sup>−32</sup>. Supposing that <sup>??</sup> ≤ 2<sup>26</sup>, the prover needs a witness with error <sup>??</sup>?? ≤ <sup>??</sup>/ 2<sup>26</sup> = 2<sup>−47</sup> (§4.1). For witness generation, this example uses doubleprecision floating-point arithmetic, which has relative error about 2<sup>−53</sup>. In this application, the magnitude of intermediate values is suficiently small that this relative error keeps the absolute error of each operation (<sup>??</sup><sub>wg</sub>) below 2<sup>−47</sup>. Note that the next choice up, quadruple-precision floating-point arithmetic, has relative error 2<sup>−112</sup>, and would sufice if the intermediate values were larger.

Furthermore, most constraints are satisfied with error far smaller than <sup>??</sup>??, so the “closeness” of <sup>??</sup><sub>wg</sub> and the floatingpoint relative error is not a concern in practice, and one can even run witness generation in a way where some constraints violate <sup>??</sup>?? provided their totality satisfies ∥<sup>??</sup>X,?? ∥<sup>2</sup> ≤ <sup>??</sup>. To counterbalance <sup>??</sup><sub>wg</sub> being close to <sup>??</sup>??, this example chooses 1/<sup>??</sup> to be significantly smaller than <sup>??</sup>??: 2<sup>−70</sup>.

Spain’s back-end scales these floating-point values and converts them to large fixed-width integers to commit via DARK and to compute <sup>??</sup> exactly (Steps 2 and 3, Figure 2). For these steps, Spain combines 256-, 512-, and 786-bit integer arithmetic. Spain then maps these integers to field elements to execute the sum-check protocol steps (Step 6, Figure 2).

## 7 Experimental evaluation

We aim to answer the following questions experimentally:

1. How does Spain perform compared to the best proof systems for numerical computations?

2. What are the contributions to Spain’s costs?

3. In what regimes does Spain meet the performance goals stated in Section 1?

Baselines. We compare Spain to five baselines, listed below. Two are end-to-end general-purpose systems, two are synthetic general-purpose systems with back-ends very similar to

Spain’s (for isolating the efect of Spain’s front-end), and one is a special-purpose system.

Otti [9]: This is a general-purpose proof system in which fixed-point numerical computations are translated to finite field operations (§2.2). Otti aims at linear programming and semidefinite programming. Otti’s back-end is a non-interactive and zero-knowledge variant of Spartan [116] so Otti ofers qualitative properties that Spain does not (§7.4). Our experiments run Otti’s released code [10].

ZKLP [51]: This general-purpose proof system encodes IEEE 754 floating-point logic in I-R1CS (§4.3, §D.2). ZKLP’s back-end is the gnark [32] implementation of Groth16 [70], which (like Otti’s back-end) is non-interactive and zeroknowledge. Our experiments run ZKLP’s released code [52].

Otti-FE: This baseline uses Otti’s front-end, meaning the same constraints as in Otti, and couples it with Spain’s backend implementation (including DARK), adjusted to prove a statement in the form of Equation (3) (§4.2.2). This setup results in a small fraction of Otti’s constraints not being satisfied, because they rely on inverses over Otti’s original finite field, rather than the one that Spain uses for sum-check, which is smaller. To be pessimistic to Spain, we filter out these constraints in our measurements.

ZKLP-FE: This baseline uses the same back-end as Otti-FE. For the front-end, we adopt a synthetic approach because ZKLP’s front-end is not compatible with Spain’s back-end, and making it so would have been a significant engineering efort. To apply this baseline to a benchmark, we count the operation types in the benchmark; for each operation type, we borrow constraint counts from ZKLP, and use the total number of constraints to construct an R1CS structure. Although this structure is semantically meaningless, its size (which is what drives performance) reflects the expected number of constraints that would be produced by using ZKLP’s arithmetization of single-precision floating-point computations.

zkGPT [105]: This baseline is a special-purpose proof system for GPT-2 inference (described below). We choose it because it is, to our knowledge, the fastest applicationspecific prover for any numerical computation in the literature; however, the proof system itself mirrors the structure of GPT-2 inference, so it cannot be adapted to other computations.

Benchmarks. Our benchmarks are in four families:

Linear Programming. This family includes several linear programming instances from the Netlib library [61] that are used by Otti [9] (specifically, adlittle, afiro, sc105, scagr7, and scsd8).

Machine Learning. This family includes common machine learning primitives (Softmax, LayerNorm, and GELU) as well as the inference phase of GPT-2 [106].

<sub>Softmax</sub> <sub>maps</sub> ?? <sub>=</sub> <sub>[</sub>??<sub>1</sub>, . . . , ??<sub>?? ]</sub> <sub>to</sub> ?? <sub>=</sub> <sub>[</sub>??<sub>1</sub>, . . . , ??<sub>??]</sub> <sub>as</sub> follows: <sup>??</sup>?? ← <sup>??????</sup> /(Í<sup>??</sup><sub>??=1</sub> <sup>??????</sup> ), for <sup>??</sup> ∈ {1<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>}. Spain arithmetizes this computation with Remez approximations of <sup>????</sup>1 <sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??????</sup> (§5). This microbenchmark runs on each row of a 32 × 32 tensor.

![](images/3f8cc89fc0c9184f4ae2d1ef2f5e2c4e184b38f3a158a7f60b75989ed4871395.jpg)  
Figure 3: Numerical parameters for benchmark families. <sup>??</sup>?? varies within a family as it depends on the number of constraints <sup>??</sup> (§4.1) and batch size <sup>??</sup> (§4.3, §D.1) for the particular instance(s). We report the minimum <sup>??</sup>?? across the family. <sup>??</sup><sub>wg</sub> is omitted because all witness generation is performed using double- or quadruple precision floating point, which has relative rather than absolute error guarantees (§6.3). Specifically, the Linear Programming, Fluid Simulation, and Geolocation families use double-precision, and the Machine Learning family uses quadruple-precision.

LayerNorm involves computing the mean and variance of a vector and then normalizing the vector. Specifically, <sup>??</sup> = [<sup>??</sup><sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>??] is transformed to <sup>??</sup> = [<sup>??</sup><sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>?? ] via ??<sub>?? ←</sub> <sup>??−</sup>√<sub>??+??</sub> , where <sup>??</sup> and <sup>??</sup> are the mean and variance of the inputs <sup>??</sup>, and <sup>??</sup> provides numerical stability. Spain arithmetizes this benchmark with square root, division, and multiplication operations. We run this microbenchmark on a 32 × 768 tensor.

GELU is a popular activation function used in GPTs, defined as <sup>??</sup> · Φ(<sup>??</sup>), where Φ(<sup>??</sup>) is the Gaussian CDF. Spain arithmetizes this with a piecewise linear approximation (§5). We run this microbenchmark on a 32 × 3072 tensor.

GPT-2 [106] is an open source LLM that uses several machine learning primitives, including Softmax, LayerNorm, GELU, and matrix multiplication (MatMul). For MatMul, Spain includes an optimization not described earlier: Spain translates to a checker that uses the Freivalds algorithm [56]. This requires an approximate version of Freivalds [74] together with Spain’s extension to I-R1CS (§4.3, Appx. D.2). This benchmark runs the inference phase of GPT-2, and is parameterized by a length of input tokens (seq), and a number of iterations, passes.

Fluid Simulation. This family is a Stable-Fluids-style [125] incompressible fluid simulation that approximately solves the 2D Navier-Stokes equations over square grids. Spain arithmetizes this benchmark with multiplication, max, and min operations. We benchmark 8 × 8 and 16 × 16 grids, each simulated for 10 timesteps, denoted small and large respectively. Even at such small sizes, these benchmarks are computationally intensive; simulations of this form often run on GPUs in practice.

Geolocation. This family includes the geospatial computation in ZKLP [51], which checks consistency between spherical coordinates (latitude, longitude) and coordinates in a hierarchical Discrete Global Grid System [110] called Uber H3 [37]. This benchmark required simulating modular arithmetic, by arithmetizing the ⌊·⌋ operation.

Figure 3 gives the numerical parameters for each family.

Metrics, measurement, and method. We report the proving time, verification time, constraint counts (<sup>??</sup>, from §2.2), and proof size of Spain and baseline systems on the benchmarks above. We also report the cost of native execution. In addition, we measure the memory usage of Spain’s prover, and fixed and setup costs for the Spain verifier.

We run all experiments in single-threaded configurations, on CPUs. We measure time based on the wall clock, with a harness that runs and times all phases of Spain. The exception is witness generation. That is timed diferently depending on the benchmark. For the Linear Programming benchmarks, we time a custom Rust program that solves the linear program and uses the solution to generate the witness values. For ONNX benchmarks, we time the execution of the transformed ONNX model on Spain’s high-precision ONNX executor (§6.2). For Fluid Simulation, similar to the Linear Programming benchmarks, we time a custom Rust program that generates witness values.

We report the average of at least 5 runs for each experiment. The standard deviations are within 11% of the means.

Testbed. For all experiments, we run the verifier on a 2.1 GHz 64-Core AMD Opteron 6272 with 256 GB RAM, running Red Hat Enterprise Linux 9.8. To reflect the motivation for succinct proofs, we run the prover on a more powerful machine: a 64- Core Intel Xeon Platnium 8592+ with 3 TB RAM, running Red Hat Enterprise Linux 9.6. When running Otti and ZKLP on our hardware, we use the artifacts provided by the authors.

## 7.1 Spain versus baselines

To compare Spain to the baselines, we run the aforementioned benchmarks. For ZKLP-FE run on GPT-2, the constraint counts are too large to run the back-end. Instead, we estimate prover and verifier time, as well as proof size, by executing ZKLP-FE on synthetic instances of various sizes and extrapolating times linearly (<sup>??2</sup> <sup>></sup> 0<sup>.</sup>99 for both).

Figure 4 depicts the results. Spain shows dramatic improvement in number of constraints (<sup>??</sup>). This owes to the techniques in Section 5; for example, with the Linear Programming bench marks, the baseline needs verbose constraints to represent comparisons (≥<sup>,</sup> ≤<sup>,</sup> and so on) whereas Spain does not.

The lowered <sup>??</sup> for Spain yields prover speedups of 8–2700×, bringing the prover’s overhead down in some cases to our goal of 3 orders of magnitude (§1). In fact, notice that Spain’s back-end is worse than the baselines on a per-constraint basis; for example, Otti outperforms Otti-FE (which has a Spain-like backend) when running with substantially the same constraints. Yet, the reduction in <sup>??</sup> is more than enough to compensate. Indeed, the only baseline that Spain’s prover does not exceed is zkGPT. But zkGPT does not apply beyond that one benchmark, and it has qualitative disadvantages, described later (§7.3).

Similarly, Spain’s verifier improves on all baselines except zkGPT (see above) and ZKLP. ZKLP’s back-end is specifically aimed at verifier performance, but it has high setup cost (§7.3, §7.4). Spain’s improvement over all other baselines stems from substantial reduction in the number of auxiliary variables in the arithmetizations, making the witness <sup>??</sup> correspondingly smaller. Meanwhile, recall that one contribution to the verifier’s costs is a component logarithmic in |<sup>??</sup>| (§2.2).

![](images/2d181205225ec52ff2bca06f6718052af1a5ed48766f9d49255a200f4b30b333.jpg)  
Figure 4: Constraint counts, native execution time, prover time, verifier time, proof sizes, and overhead of proving (ratio of prover:native) for baselines and benchmarks. “Native time” refers to the verifier’s hardware while the Spain/native ratio is measured on the prover’s hardware. Times, proof sizes, and ratios are displayed with two significant figures. Constraints are displayed with three significant figures. The italicized numbers for ZKLP-FE mean that the times and proof sizes are extrapolated (see text); the back-end could not run at that scale. zkGPT does not support a batched configuration, so we scale zkGPT’s measurements by passes where appropriate. Spain improves over baselines in constraint counts (from 32× to 4 orders of magnitude). With two exceptions, Spain improves over baselines in prover and verifier time, by at least an order of magnitude. The first exception is zkGPT, which outperforms Spain on all metrics, except for verifier time when passes = 16, where Spain’ verifier is slightly better. The second exception is ZKLP, whose verifier outperforms Spain’s verifier by 4–5×.

## 7.2 Costs of Spain

We examine the relative costs of the protocol phases, for the prover and verifier. Figures 5 and 6 depict the results. For most benchmarks, DARK is the dominant cost. For GPT-2, witness generation (compute <sup>??</sup>) has a larger share of prover time, due almost entirely to the diference in complexity between executing matrix multiplication (which must happen to generate the witness) and checking matrix multiplication with the Freivalds algorithm (which is what the constraints enforce, as described in the GPT-2 benchmark earlier).

The prover’s primary resource bottleneck is memory. For example, with GPT-2, our largest benchmark, the prover requires ≈41 GB for seq=32, passes=1, and ≈267 GB for seq=32, passes=16. The verifier’s bottleneck for small computations (small <sup>??</sup>) is DARK evaluation. The bottleneck for larger computations is evaluating <sup>??</sup>, <sup>??</sup>, and <sup>??</sup> at a random point.

## 7.3 Breaking even and batching

Recall that to justify outsourcing on performance grounds, the verifier must be cheaper than native execution (§1). For the largest linear program, scsd8, Figure 4 shows that Spain’s verifier does meet this condition. However, for most of the other benchmarks, this condition is not met.

In these cases, Spain must amortize fixed costs (§2.2) via batching. This is the SIMD-R1CS model (§4.3, Appx. D.1): the same computation repeated on diferent input/output pairs. This structure is natural for many numerical computations. For example, when running an LLM, people don’t just want one token; they want a whole paragraph (or more...).

Spain’s verifier indeed benefits from batching; notice that for the rows in Figure 4 featuring GPT-2 with various passes, the verifier’s work grows less than linearly in batch size. Indeed, Figure 6 shows that the fixed costs – namely fixed work in DARK (§4.2.3, Appx. C) and evaluating <sup>??,</sup> <sup>??,</sup> <sup>??</sup> at a random point (Step 6, Figure 2) – are the dominant contribution when verifying single instances, and thus amortization is beneficial. These results agree with the theory. Specifically, Spain’s fixedcost is <sup>??</sup> (<sup>??</sup>) for the entire batch (§2.2). Meanwhile, Spain’s variable costs comprise a component logarithmic in the total witness size across all instances in the batch and a component linear in the number of variables in in and out across all instances. Given this cost profile, there is usually a batch size for which, in principle, Spain’s verifier breaks even once the batch size crosses a threshold. We say usually because, for very small computations with very large in and/or out, the variable costs alone may exceed the cost of native execution.

![](images/889f8dcb64303b7beeebd44c3fab3756b689c3f372980884ef5ee5402e321c5c.jpg)  
Step 1 (Compute <sup>??</sup>) Step 2 (Commit to <sup>??</sup> via DARK) Step 3 (Compute <sup>??</sup>) Step 6 (Sum-check) Step 7 (Open commitment to <sup>??</sup>)

Figure 5: Prover phase breakdown for Spain. Steps refer to those in Figure 2. Steps 4 and 5 are omitted as they incur no cost for the prover.  
![](images/d41309320ef7a9b408c8be039636339fb5d17a9e2b663d94560ddc75cd2f77ac.jpg)  
Steps 4-6 Step 7 (Evaluate <sup>??</sup>, <sup>??</sup>, and <sup>??</sup>) Step 7 (Open commitment to <sup>??</sup>) Step 7 (Test <sup>??</sup> consistency with Step 6’s claim)  
Figure 6: Verifier phase breakdown for Spain. Steps refer to those in Figure 2. Steps 1-3 are omitted as they incur no cost for the verifier. The majority of the verifier’s time is spent in Step 7, which decomposes into three sub-steps: evaluating <sup>??,</sup> <sup>??,</sup> <sup>??</sup>; opening the commitment to <sup>??</sup>; and checking consistency between the claim in Step 6 about <sup>??</sup> and the opening of <sup>??</sup>, using in and out.

In contrast to Spain, zkGPT does not amortize with passes; as shown in Figure 4 (the GPT-2 rows), zkGPT’s verifier is more expensive than Spain’s verifier at seq=32<sup>,</sup> passes=16. For ZKLP, the comparison is equivocal. On the one hand, ZKLP’s fixed costs (which are not included in Figure 4) amortize over all future uses of an R1CS structure, not merely a synchronized batch as in Spain; on the other hand, ZKLP’s fixed costs are dramatically higher (over 50 thousand times larger than the verifier’s work on a single instance [112]).

A loose end is setup costs, as distinct from fixed costs (§2.2); these are not depicted. However, on our benchmarks, Spain’s setup costs range from negligible to 5× the verifier’s work to check a single instance, so this cost quickly amortizes.

## 7.4 Summary and discussion

We believe that Spain meets the goal of being generalpurpose (§1): it easily handled an array of natural benchmarks, and we did not have to discard any benchmarks because Spain lacked suficient expressiveness.

At its core, Spain bakes approximation into the constraints themselves, eliminating the need to enforce numerical semantics explicitly, which in turn improves on the number of constraints (<sup>??</sup>) in an arithmetization, by 32× to 17,000× (§7.1).

This reduction lowers the prover overhead versus natural baselines by 1–3 orders of magnitude, down to 3–5 orders of magnitude versus native execution (§7.1). Spain’s prover isn’t the fastest in the literature; that honor belongs to zkGPT [105], but as we have noted, zkGPT is specialized to a specific machine learning model architecture, and its verifier neither breaks even nor benefits from amortization (§7.3).

Spain’s verifier beats native execution for some reasonablysized numerical problems (§7.3), and is the only system we experimented with to do so. Given their cost profiles (§7.2), Spain’s verifier and prover would directly benefit from improvements in integer polynomial commitment protocols or rational ones [6, 121]. There are additional avenues for improving the verifier’s costs. Most saliently, the verifier could shift some work to the prover using SPARK [116] or one of its descendants [38, 117, 119].

A structural disadvantage of Spain is that, for the time being, its new arithmetizations require its back-end. Traditional constraints are more portable; they can be combined with back-ends that provide diferent properties. Otti’s back-end, for example, provides zero-knowledge and non-interactivity. ZKLP’s back-end does too, and it inherits from Groth16 [70] an extremely fast verifier (albeit with high fixed costs; §7.3). If Spain’s arithmetizations could be ported to alternative back-ends (§9), Spain could derive end-to-end speedups and enhanced properties.

## 8 Other related work

We have described Spain’s intellectual antecedents throughout. Here we focus on the intersection of proof systems and numerical computations; we divide the work into two strands.

General-purpose (§1) proof systems. The first attempt to represent numerical operations in succinct proofs was Ginger [115], which supported fixed-point and primitive floatingpoint operations, by mapping them to operations in a finite field <sup>F</sup>??. Ginger used static analysis, bit-wise decompositions of values, and a large field (large <sup>??</sup>) to ensure a unique representation of each rational encountered during execution.

Subsequent works applied variations on this encoding to specific numerical problems, for example Otti [9] to linear programs, zkQMC [50] to Monte Carlo simulations, and KL24 [82] to transcendental functions. All of these works target general-purpose back-ends [8, 21–24, 46, 47, 49, 58, 62, 70, 85, 90, 100, 116, 117] and express computations as traditional constraints over a finite field.

A few recent works have explored alternative approaches, focusing on arithmetizing floating-point arithmetic. The works in this vein range between strict IEEE 754 compliance with support for all rounding modes and exceptions [51] (see §7) and more relaxed semantics [59]. All such works translate numerical operations using more constraints than Spain; however, they ofer relative error guarantees that Spain does not.

Recently, interest has renewed in a class of proof systems known as zkVMs [15, 25, 26, 53, 83, 145]. These proof systems allow for proving the correct execution of any programs written in a given instruction set, typically RISC-V [107]. Although RISC-V includes numerical operations via floatingpoint instructions in an extension, we do not know of any zkVMs that currently support this extension.

Like Spain, some works have back-ends that work over domains other than finite fields. Chen et al. [45] arithmetize numerical computations as arithmetic circuits (addition and multiplication gates) over Galois rings, by encoding a rounding operation as a sequence of additions and multiplications within the ring. They then run GKR [66, 67] (§2.2) over the Galois ring. Bitan et al. [27] observe that some sum-check protocols can be modified so that the protocol messages themselves become approximate. Although we have yet to do a detailed analysis, we estimate that the costs of these approaches would be in between Spain’s and the approaches derived from Ginger.

Finally, concurrent with this work, others have refined Zaratan [42] (discussed in §4.2), which is geared to integer computations. These works design polynomial commitment protocols over rational numbers that are significantly faster than DARK [6, 121].<sup>2</sup> While these works apply their faster polynomial commitments to general-purpose proof systems for exact integer and rational arithmetic, rather than approximate computations, we observe that the polynomial commitments themselves are compatible with Spain. We anticipate that replacing DARK with the fastest of them will improve the most expensive components of Spain by at least an order of magnitude (§7.2).

Special-purpose proof systems. Here we consider systems designed around specific applications. These systems rely on the observation that checkers for some numerical computations can be directly represented as sum-check protocols (§2.2).

The first in this line of work is Thaler’s protocol for proving matrix multiplication [129]. Some works use Thaler’s protocol as a primitive in proof systems for machine learning [19, 63, 77, 78, 86, 105, 127, 128, 151] (see the survey of Peng et. al [101] for a taxonomy). These protocols typically quantize numerical values, and alternate between checking exact operations (such as matrix multiplications, convolutions, and activation functions) and rounding to return to a quantized domain. From our testing, the most eficient of these systems is zkGPT [105], which was discussed and evaluated (§7).

## 9 Conclusion

Spain meets the goal of proving numerical computations in a general-purpose way, while in some regimes meeting the goals (§1) of a prover with 3 orders of magnitude overhead and a verifier less expensive than native (§7.4).

Spain also introduces a new form of arithmetization, approximate constraints (§5). We believe this is of independent interest, as eficient arithmetizations are an object of intense study among those interested in succinct proofs. In principle, approximate constraints are usable in conjunction with the two dominant forms of arithmetization: traditional constraints and lookup tables (§E.4, §2.2).

A natural area for future work is adapting other proof backends (both those based on sum-check protocols and those not based on sum-check protocols) to handle approximate constraints. Other future work includes reducing the cost of polynomial commitment in Spain, slashing the cost of Spain’s verifier by shifting work to the prover (§7.4), making Spain zero-knowledge and non-interactive, supporting relative error in constraints, and adding numerical support to zkVMs (§8) [15, 53, 83, 145]. Many of these are separate research eforts, which we hope our work here has motivated.

## Acknowledgments

We are grateful to our shepherd, Andi Quinn, who went above and beyond with close readings that fundamentally improved the presentation of this work. In a similar vein, this paper was substantially improved by the thoughtful suggestions of the anonymous OSDI reviewers. Andrew Blumberg gave useful comments. All errors and problems are the fault of the authors. This project used computing resources at the Courant Institute and NYU’s HPC organization, and was partially supported by gifts from Google and Stellar.

## References

[1] Carmichael function. https://en<sup>.</sup>wikipedia<sup>.</sup>org/ wiki/Carmichael\_function. Wikipedia, Wikimedia foundation.

[2] IEEE standard for floating-point arithmetic. IEEE Std 754-2019 (Revision of IEEE 754-2008), pages 1–84, 2019.

[3] FLINT: Fast Library for Number Theory. http:// flintlib<sup>.</sup>org, 2025.

[4] GNU MP: The GNU Multiple Precision Arithmetic Library. https://gmplib<sup>.</sup>org, 2025.

[5] MPFR: The GNU Multiple Precision Floating-Point Reliably Library. https://www<sup>.</sup>mpfr<sup>.</sup>org, 2025.

[6] Alexander Abdugafarov, Albert Garreta, Amit Kumar, Michał Osadnik, Psi Vesely, Ilia Vlasov, and Kai Zhe Zheng. Zinc+: SNARKs for polynomial rings. Cryptology ePrint Archive, Paper 2026/855, 2026.

[7] Miguel Ambrona, Anne-Laure Schmitt, Raphael R. Toledo, and Danny Willems. New optimization techniques for PlonK’s arithmetization. Cryptology ePrint Archive, Paper 2022/462, 2022.

[8] Scott Ames, Carmit Hazay, Yuval Ishai, and Muthuramakrishnan Venkitasubramaniam. Ligero: Lightweight sublinear arguments without a trusted setup. In ACM Conference on Computer and Communications Security (CCS), 2017.

[9] Sebastian Angel, Andrew J. Blumberg, Eleftherios Ioannidis, and Jess Woods. Eficient representation of numerical optimization problems for SNARKs. In SECURITY, 2022.

[10] Sebastian Angel, Andrew J. Blumberg, Eleftherios Ioannidis, and Jess Woods. Otti: A zkSNARK compiler, solver, prover and verifier for optimization problems. https://github<sup>.</sup>com/eniac/otti, 2022.

[11] arkworks contributors. arkworks zkSNARK ecosystem. https://arkworks<sup>.</sup>rs, 2022.

[12] Sanjeev Arora and Boaz Barak. Computational Complexity: A modern approach. Cambridge University Press, 2009.

[13] Sanjeev Arora, Carsten Lund, Rajeev Motwani, Madhu Sudan, and Mario Szegedy. Proof verification and the hardness of approximation problems. Journal of the ACM, 45(3):501–555, May 1998.

[14] Sanjeev Arora and Shmuel Safra. Probabilistic checking of proofs: a new characterization of NP. Journal of the ACM, 45(1):70–122, January 1998.

[15] Arasu Arun, Srinath Setty, and Justin Thaler. Jolt: SNARKs for virtual machines via lookups. In Annual International Conference on the Theory and Applications of Cryptographic Techniques (EUROCRYPT), 2024.

[16] László Babai. Trading group theory for randomness. In ACM Symposium on the Theory of Computing (STOC),

May 1985.

[17] László Babai, Lance Fortnow, Leonid A Levin, and Mario Szegedy. Checking Computations in Polylogarithmic Time. In ACM STOC, 1991.

[18] László Babai, Lance Fortnow, and Carsten Lund. Nondeterministic exponential time has two-prover interactive protocols. computational complexity, 1(1):3–40, Mar 1991.

[19] David Balbás, Dario Fiore, Maria Vasco, Damien Robissout, and Claudio Soriente. Modular sumcheck proofs with applications to machine learning and image processing. In ACM Conference on Computer and Communications Security (CCS), 2023.

[20] Anubhav Baweja, Pratyush Mishra, Tushar Mopuri, Karan Newatia, and Steve Wang. Scribe: Low-memory SNARKs via read-write streaming. Cryptology ePrint Archive, Paper 2024/1970, 2024.

[21] E. Ben-Sasson, A. Chiesa, E. Tromer, and M. Virza. Scalable zero knowledge via cycles of elliptic curves. In IACR International Cryptology Conference (CRYPTO), August 2014.

[22] Eli Ben-Sasson, Iddo Bentov, Yinon Horesh, and Michael Riabzev. Fast Reed-Solomon Interactive Oracle Proofs of Proximity. In ICALP, 2018.

[23] Eli Ben-Sasson, Iddo Bentov, Yinon Horesh, and Michael Riabzev. Scalable, transparent, and postquantum secure computational integrity. Cryptology ePrint Archive, Report 2018/046, 2018.

[24] Eli Ben-Sasson, Alessandro Chiesa, Daniel Genkin, Eran Tromer, and Madars Virza. SNARKs for C: Verifying program executions succinctly and in zero knowledge. In IACR International Cryptology Conference (CRYPTO), August 2013.

[25] Eli Ben-Sasson, Alessandro Chiesa, Daniel Genkin, Eran Tromer, and Madars Virza. TinyRAM architecture specification, v0.991, 2013.

[26] Eli Ben-Sasson, Alessandro Chiesa, Eran Tromer, and Madars Virza. Succinct non-interactive zero knowledge for a von Neumann architecture. In USENIX Security, 2014.

[27] Dor Bitan, Zachary DeStefano, Shafi Goldwasser, Yuval Ishai, Yael Tauman Kalai, and Justin Thaler. Sum-check protocol for approximate computations. In Annual International Conference on the Theory and Applications of Cryptographic Techniques (EUROCRYPT), 2026.

[28] Alexander R. Block, Zhiyong Fang, Jonathan Katz, Justin Thaler, Hendrik Waldner, and Yupeng Zhang. Field-Agnostic SNARKs from Expand-Accumulate Codes. In IACR International Cryptology Conference (CRYPTO), 2024.

[29] Alexander R. Block, Justin Holmgren, Alon Rosen, Ron D. Rothblum, and Pratik Soni. Time- and Space-Eficient Arguments from Groups of Unknown Order. In IACR International Cryptology Conference

(CRYPTO), 2021.

[30] Andrew J. Blumberg, Justin Thaler, Victor Vu, and Michael Walfish. Verifiable computation using multiple provers. Cryptology ePrint Archive, Paper 2014/846, 2014.

[31] Jonathan Bootle, Andrea Cerulli, Jens Groth, Sune Jakobsen, and Mary Maller. Arya: Nearly Linear-Time Zero-Knowledge Proofs for Correct Program Execution. In ASIACRYPT, 2018.

[32] Gautam Botrel, Thomas Piellard, Youssef El Housni, Ivo Kubjas, and Arya Tabaie. Consensys/gnark: v0.11.0, September 2024.

[33] Sean Bowe, Jack Grigg, and Daira Hopwood. Recursive proof composition without a trusted setup. Cryptology ePrint Archive, Paper 2019/1021, 2019.

[34] G. Brassard, D. Chaum, and C. Crépeau. Minimum disclosure proofs of knowledge. Journal of Computer and System Sciences, 37(2):156–189, October 1988.

[35] B. Braun, A. J. Feldman, Z. Ren, S. Setty, A. J. Blumberg, and M. Walfish. Verifying computations with state. In ACM Symposium on Operating Systems Principles (SOSP), November 2013.

[36] Benjamin Braun. Compiling computations to constraints for verified computation. UT Austin Honors thesis HR-12-10, December 2012.

[37] Isaac Brodsky. H3: Uber’s hexagonal hierarchical spatial index. Uber Blog, June 2018.

[38] Benedikt Bünz, Jessica Chen, Zachary DeStefano, and Binyi Chen. Almost linear-time permutation check. Cryptology ePrint Archive, Paper 2025/1850, 2025.

[39] Benedikt Bünz and Ben Fisch. Multilinear Schwartz-Zippel mod N and lattice-based succinct arguments. In Theory of Cryptography Conference (TCC), 2023.

[40] Benedikt Bünz, Ben Fisch, and Alan Szepieniec. Transparent SNARKs from DARK compilers. In Annual International Conference on the Theory and Applications of Cryptographic Techniques (EUROCRYPT), 2020.

[41] Matteo Campanelli, Dario Fiore, and Rosario Gennaro. Natively compatible super-eficient lookup arguments and how to apply them: Natively compatible super eficient lookup arguments. J. Cryptol., 38(1), January 2025.

[42] Matteo Campanelli and Mathias Hall-Andersen. Fully succinct arguments over the integers from first principles. Cryptology ePrint Archive, Paper 2024/1548, 2024.

[43] R. D. Carmichael. Note on a new number theory function. Bulletin of the American Mathematical Society, 16(5):232–238, 1910.

[44] Binyi Chen, Benedikt Bünz, Dan Boneh, and Zhenfei Zhang. HyperPlonk: Plonk with Linear-Time Prover and High-Degree Custom Gates. In Annual International Conference on the Theory and Applications of

Cryptographic Techniques (EUROCRYPT), 2023.

[45] Shuo Chen, Jung Hee Cheon, Dongwoo Kim, and Daejun Park. Interactive proofs for rounding arithmetic. IEEE Access, 10, 2022.

[46] Alessandro Chiesa,Yuncong Hu,Mary Maller,Pratyush Mishra, Noah Vesely, and Nicholas Ward. Marlin: Preprocessing zkSNARKs with universal and updatable SRS. In IACR International Cryptology Conference (CRYPTO), 2020.

[47] Alessandro Chiesa, Dev Ojha, and Nicholas Spooner. Fractal: Post-quantum and transparent recursive proofs from holography. In IACR International Cryptology Conference (CRYPTO), 2020.

[48] Graham Cormode, Michael Mitzenmacher, and Justin Thaler. Practical verified computation with streaming interactive proofs. In Innovations in Theoretical Computer Science (ITCS), pages 90–112, January 2012.

[49] Craig Costello, Cédric Fournet, Jon Howell, Markulf Kohlweiss, Benjamin Kreuter, Michael Naehrig, Bryan Parno, and Samee Zahur. Geppetto: Versatile verifiable computation. In IEEE Symposium on Security and Privacy, May 2015.

[50] Zachary DeStefano, Dani Barrack, and Michael Dixon. zkQMC: Zero-knowledge proofs for (some) probabilistic computations using quasi-randomness. Cryptology ePrint Archive, Paper 2022/1007, 2022.

[51] Jens Ernstberger, Chengru Zhang, Luca Ciprian, Philipp Jovanovic, and Sebastian Steinhorst. Zero-knowledge location privacy via accurate floating-point SNARKs. In IEEE Symposium on Security and Privacy, 2025.

[52] Jens Ernstberger, Chengru Zhang, Luca Ciprian, Philipp Jovanovic, and Sebastian Steinhorst. Zeroknowledge location privacy via accurate floating-point SNARKs. https://github<sup>.</sup>com/tumberger/zk-Location, 2025.

[53] Ethereum Foundation. Ethereum foundation zkVM list. https://ethproofs<sup>.</sup>org/zkvms, 2025.

[54] Filecoin Foundation. Filecoin: A decentralized, eficient, and robust foundation for humanity’s information. https://filecoin<sup>.</sup>io.

[55] Mina Foundation. Mina protocol. https:// minaprotocol<sup>.</sup>com, 2026.

[56] R. Freivalds. Probabilistic machines can use less running time. In Proceedings of the IFIP Congress, pages 839–842, 1977.

[57] Ariel Gabizon and Zachary J. Williamson. plookup: A simplified polynomial protocol for lookup tables. Cryptology ePrint Archive, Report 2020/315, 2020.

[58] Ariel Gabizon, Zachary J. Williamson, and Oana Ciobotaru. PLONK: Permutations over Lagrange-bases for Oecumenical Noninteractive arguments of Knowledge. Cryptology ePrint Archive, Report 2019/953, 2019.

[59] Sanjam Garg, Abhishek Jain, Zhengzhong Jin, and Yinuo Zhang. Succinct zero knowledge for floating

point computations. In ACM Conference on Computer and Communications Security (CCS), 2022.

[60] Albert Garreta, Hendrik Waldner, Katerina Hristova, and Luca Dall’Ava. Zinc: Succinct arguments with small arithmetization overheads from IOPs of proximity to the integers. Cryptology ePrint Archive, Paper 2025/316, 2025.

[61] David Gay. netlib. https://portal<sup>.</sup>ampl<sup>.</sup>com/ \~dmg/netlib/lp/data/, 2013.

[62] Rosario Gennaro, Craig Gentry, Bryan Parno, and Mariana Raykova. Quadratic span programs and succinct NIZKs without PCPs. In Annual International Conference on the Theory and Applications of Cryptographic Techniques (EUROCRYPT), May 2013.

[63] Zahra Ghodsi, Tianyu Gu, and Siddharth Garg. SafetyNets: verifiable execution of deep neural networks on an untrusted cloud. International Conference on Neural Information Processing Systems (NIPS), 2017.

[64] Oded Goldreich. Probabilistic proof systems – a primer. Foundations and Trends in Theoretical Computer Science, 3(1), 2008.

[65] S. Goldwasser, S. Micali, and C. Rackof. The knowledge complexity of interactive proof systems. SIAM Journal on Computing, 18(1):186–208, 1989.

[66] Shafi Goldwasser, Yael Tauman Kalai, and Guy N. Rothblum. Delegating computation: Interactive proofs for muggles. In ACM Symposium on the Theory of Computing (STOC), May 2008.

[67] Shafi Goldwasser, Yael Tauman Kalai, and Guy N Rothblum. Delegating computation: interactive proofs for muggles. J. ACM, 62(4), 2015.

[68] Alexander Golovnev, Jonathan Lee, Srinath Setty, Justin Thaler, and Riad S. Wahby. Brakedown: Linear-time and field-agnostic SNARKs for R1CS. In CRYPTO, 2023.

[69] Google. Longfellow ZK. https://github<sup>.</sup>com/ google/longfellow-zk.

[70] Jens Groth. On the size of pairing-based non-interactive arguments. In Annual International Conference on the Theory and Applications of Cryptographic Techniques (EUROCRYPT), 2016.

[71] Ulrich Habock. Multivariate lookups based on logarithmic derivatives. Cryptology ePrint Archive, Paper 2022/1530, 2022.

[72] Daira-Emma Hopwood, Sean Bowe, Taylor Hornby, and Nathan Wilcox. Zcash protocol specification. https: //zips<sup>.</sup>z<sup>.</sup>cash/protocol/protocol<sup>.</sup>pdf, 2025.

[73] StarkWare Industries. Starkware. https:// starkware<sup>.</sup>co.

[74] Hao Ji, Michael Mascagni, and Yaohang Li. Gaussian variant of freivalds’ algorithm for eficient and reliable matrix product verification. CoRR, abs/1705.10449, 2017.

[75] Kunming Jiang, Fraser Brown, and Riad S. Wahby.

CoBBL: Dynamic Constraint Generation for SNARKs. In IEEE Symposium on Security and Privacy, 2025.

[76] Kunming Jiang, Devora Chait-Roth, Zachary DeStefano, Michael Walfish, and Thomas Wies. Less is more: refinement proofs for probabilistic proofs. In IEEE Symposium on Security and Privacy, 2023.

[77] Chanyang Ju, Hyeonbum Lee, Heewon Chung, Jae Hong Seo, and Sungwook Kim. Eficient sumcheck protocol for convolution. IEEE Access, 9:164047– 164059, 2021.

[78] Daniel Kang, Tri Dao, and Matei Zaharia. ZKML: An optimizing system for ML inference in zero-knowledge proofs. Proceedings of the ACM SIGMOD Conference, 2024.

[79] Aniket Kate, Gregory M. Zaverucha, and Ian Goldberg. Constant-size commitments to polynomials and their applications. In ASIACRYPT, 2010.

[80] J. Kilian. A note on eficient zero-knowledge proofs and arguments (extended abstract). In ACM Symposium on the Theory of Computing (STOC), pages 723–732, May 1992.

[81] Ahmed Kosba, Charalampos Papamanthou, and Elaine Shi. xJsnark: a framework for eficient verifiable computation. In IEEE Symposium on Security and Privacy, 2018.

[82] Kaarel August Kurik and Peeter Laud. Novel approximations of elementary functions in zero-knowledge proofs. Cryptology ePrint Archive, Paper 2024/859, 2024.

[83] Succinct Labs. SP1 zkVM. https://github<sup>.</sup>com/ succinctlabs/sp1, 2025.

[84] Ryan Lavin, Xuekai Liu, Hardhik Mohanty, Logan Norman, Giovanni Zaarour, and Bhaskar Krishnamachari. A survey on the applications of zero-knowledge proofs, 2026.

[85] Jonathan Lee. Dory: Eficient, transparent arguments for generalised inner products and polynomial commitments. In IACR Theory of Cryptography Conference (TCC), 2021.

[86] Seunghwa Lee, Hankyung Ko, Jihye Kim, and Hyunok Oh. vCNN: Verifiable convolutional neural network based on zk-SNARKs. IEEE Transactions on Depend able and Secure Computing, 21(4):4254–4270, 2024.

[87] Tianyi Liu, Tiancheng Xie, Jiaheng Zhang, Dawn Song, and Yupeng Zhang. Pianist: Scalable zkRollups via fully distributed zero-knowledge proofs. In IEEE Symposium on Security and Privacy, pages 1777–1793, Los Alamitos, CA, USA, May 2024. IEEE Computer Society.

[88] Loopring Foundation. Loopring: Ethereum’s First zkRollup Layer 2. https://loopring<sup>.</sup>org.

[89] Carsten Lund, Lance Fortnow, Howard J. Karlof, and Noam Nisan. Algebraic methods for interactive proof systems. Journal of the ACM, 39(4):859–868, 1992.

[90] Mary Maller,Sean Bowe,Markulf Kohlweiss, and Sarah Meiklejohn. Sonic: Zero-knowledge SNARKs from linear-size universal and updatable structured reference strings. In ACM Conference on Computer and Communications Security (CCS), 2019.

[91] Silvio Micali. Computationally sound proofs. SIAM Journal on Computing, 30(4):1253–1298, 2000.

[92] Microsoft. Spartan: High-speed zero-knowledge SNARKs without trusted setup. https:// github<sup>.</sup>com/microsoft/Spartan, 2025.

[93] Vineet Nair, Justin Thaler, and Michael Zhu. Proving CPU executions in small space. Cryptology ePrint Archive, Paper 2025/611, 2025.

[94] Ihyun Nam. A survey of multivariate polynomial commitment schemes. arXiv:2306.11383, 2023.

[95] ONNX Contributors. Open Neural Network Exchange Intermediate Representation (ONNX IR) Specification. https://github<sup>.</sup>com/onnx/onnx/blob/ main/docs/IR<sup>.</sup>md, 2026.

[96] Alex Ozdemir, Fraser Brown, and Riad Wahby. CirC: Compiler infrastructure for proof systems, software verification, and more. In IEEE Symposium on Security and Privacy, 2022.

[97] Alex Ozdemir, Evan Laufer, and Dan Boneh. Volatile and persistent memory for zksnarks via algebraic interactive proofs. In IEEE Symposium on Security and Privacy, 2025.

[98] H. Padé. Sur la représentation approchée d’une fonction par des fractions rationnelles. Annales scientifiques de l’École Normale Supérieure, 3e série, 9:3–93, 1892.

[99] Christodoulos Pappas and Dimitrios Papadopoulos. HOBBIT: space-eficient zkSNARK with optimal prover time. In USENIX Security, 2025.

[100] Bryan Parno, Craig Gentry, Jon Howell, and Mariana Raykova. Pinocchio: Nearly practical verifiable computation. In IEEE Symposium on Security and Privacy, May 2013.

[101] Zhizhi Peng, Chonghe Zhao, Taotao Wang, Guofu Liao, Zibin Lin, Yifeng Liu, Bin Cao, Long Shi, Qing Yang, and Shengli Zhang. A survey of zero-knowledge proof based verifiable machine learning. Artificial Intelligence Review, Apr 2026.

[102] Pepper Project. Pequin: An end-to-end toolchain for verifiable computation, SNARKs, and probabilistic proofs. https://github<sup>.</sup>com/pepper-project/ pequin, 2018.

[103] Polygon Labs UI. Polygon. https:// polygon<sup>.</sup>technology.

[104] William H. Press, Brian P. Flannery, Saul A. Teukolsky, and William T. Vetterling. Numerical Recipes in C: The Art of Scientific Computing. Cambridge University Press, 2 edition, October 1992.

[105] Wenjie Qu, Yĳun Sun, Xuanming Liu, Tao Lu, Yanpei Guo, Kai Chen, and Jiaheng Zhang. zkGPT: an eficient

non-interactive zero-knowledge proof framework for LLM inference. In USENIX Security, 2025.

[106] Alec Radford, Jef Wu, Rewon Child, David Luan, Dario Amodei, and Ilya Sutskever. Language models are unsupervised multitask learners. https://cdn<sup>.</sup>openai<sup>.</sup>com/better-languagemodels/language\_models\_are\_unsupervised\_ multitask\_learners<sup>.</sup>pdf, 2019.

[107] RISC-V International. RISC-V: Ratified Specification. https://riscv<sup>.</sup>org/specifications/ ratified/, 2025.

[108] Michael Rosenberg, Tushar Mopuri, Hossein Hafezi, Ian Miers, and Pratyush Mishra. Hekaton: Horizontallyscalable zkSNARKs via proof aggregation. In ACM Conference on Computer and Communications Security (CCS), 2024.

[109] J. Barkley Rosser and Lowell Schoenfeld. Approximate formulas for some functions of prime numbers. Illinois Journal of Mathematics, 6:64–94, 1962.

[110] Kevin Sahr, Denis White, and Jon A. Kimerling. Geodesic discrete global grid systems. Cartography and Geographic Information Science, 30:121–134, 2003.

[111] J. T. Schwartz. Fast probabilistic algorithms for verification of polynomial identities. J. ACM, 27(4):701–717, October 1980.

[112] SCIPR Lab. libsnark ppzkSNARK empirical performance README. https://github<sup>.</sup>com/ scipr-lab/libsnark/blob/master/libsnark/ zk\_proof\_systems/ppzksnark/README<sup>.</sup>md, 2017. GitHub repository documentation.

[113] SCIPR Lab and contributors. libsnark: a C++ library for zksnark proofs. https://github<sup>.</sup>com/scipr-lab/ libsnark, 2026.

[114] S. Setty, B. Braun, V. Vu, A. J. Blumberg, B. Parno, and M. Walfish. Resolving the conflict between generality and plausibility in verified computation. In European Conference on Computer Systems (EuroSys), pages 71–84, April 2013.

[115] S. Setty, V. Vu, N. Panpalia, B. Braun, A. J. Blumberg, and M. Walfish. Taking proof-based verified computation a few steps closer to practicality. In USENIX Security, August 2012.

[116] Srinath Setty. Spartan: Eficient and general-purpose zkSNARKs without trusted setup. In CRYPTO, 2020.

[117] Srinath Setty and Jonathan Lee. Quarks: Quadrupleeficient transparent zkSNARKs. Cryptology ePrint Archive, Paper 2020/1275, 2020.

[118] Srinath Setty, Justin Thaler, and Riad Wahby. Customizable constraint systems for succinct arguments. Cryptology ePrint Archive, Paper 2023/552, 2023.

[119] Srinath Setty, Justin Thaler, and Riad Wahby. Unlocking the Lookup Singularity with Lasso. In Annual Interna tional Conference on the Theory and Applications of

Cryptographic Techniques (EUROCRYPT), 2024.

[120] Adi Shamir. IP = PSPACE. Journal of the ACM, 39(4):869–877, October 1992.

[121] Alireza Shirzad, Sriram Sridhar, Dimitrios Papadopoulos, and Charalampos Papamanthou. Relaxed modular PCS from arbitrary PCS and applications to SNARKs for integers. Cryptology ePrint Archive, Paper 2026/347, 2026.

[122] Michael Sipser. Introduction to the Theory of Computation. Cengage Learning, 3 edition, 2013.

[123] Eduardo Soria-Vazquez. Doubly eficient interactive proofs over infinite and non-commutative rings. In IACR Theory of Cryptography Conference (TCC), 2022.

[124] Sriram Sridhar, Shravan Srinivasan, Dimitrios Papadopoulos, and Charalampos Papamanthou. Eficiently provable approximations for non-polynomial functions. In USENIX Security, 2026.

[125] Jos Stam. Stable fluids. In SIGGRAPH, 1999.

[126] Alan Stapelberg. Opening up ‘Zero-Knowledge Proof technology to promote privacy in age assurance. https://blog<sup>.</sup>google/technology/safetysecurity/opening-up-zero-knowledgeproof-technology-to-promote-privacyin-age-assurance/, July 2025.

[127] Haochen Sun, Tonghe Bai, Jason Li, and Hongyang Zhang. zkDL: Eficient zero-knowledge proofs of deep learning training. IEEE Transactions on Information Forensics and Security, 2024.

[128] Haochen Sun, Jason Li, and Hongyang Zhang. zkLLM: Zero knowledge proofs for large language models. In ACM Conference on Computer and Communications Security (CCS), 2024.

[129] Justin Thaler. Time-optimal interactive proofs for circuit evaluation. In IACR International Cryptology Conference (CRYPTO), August 2013.

[130] Justin Thaler. Proofs, Arguments, and Zero-Knowledge. http://people<sup>.</sup>cs<sup>.</sup>georgetown<sup>.</sup>edu/ jthaler/ProofsArgsAndZK<sup>.</sup>html, 2023.

[131] Justin Thaler. Sum-check is all you need: An opinionated survey on fast provers in SNARK design. Cryptology ePrint Archive, Paper 2025/2041, 2025.

[132] The Linux Foundation. ONNX: Open Neural Network Exchange. https://onnx<sup>.</sup>ai, 2019.

[133] Louis Tremblay Thibault, Tom Sarry, and Abdelhakim Senhaji Hafid. Blockchain scaling using rollups: A comprehensive survey. IEEE Access, 10:93039– 93054, 2022.

[134] Ioanna Tzialla, Abhiram Kothapalli, Bryan Parno, and Srinath Setty. Transparency dictionaries with succinct proofs of correct operation. In Network and Distributed System Security Symposium (NDSS), 2022. https: //eprint<sup>.</sup>iacr<sup>.</sup>org/2021/1263.

[135] V. Vu, S. Setty, A. J. Blumberg, and M. Walfish. A hybrid architecture for interactive verifiable computa-

tion. In IEEE Symposium on Security and Privacy, May 2013.

[136] Riad S. Wahby, Max Howald, Siddharth Garg, abhi shelat, and Michael Walfish. Verifiable ASICs. In IEEE Symposium on Security and Privacy, 2016.

[137] Riad S. Wahby, Ye Ji, Andrew J. Blumberg, abhi shelat, Justin Thaler, Michael Walfish, and Thomas Wies. Full accounting for verifiable outsourcing. In ACM Conference on Computer and Communications Security (CCS), 2017.

[138] Riad S. Wahby, Srinath Setty, Max Howald, Zuocheng Ren, Andrew J. Blumberg, and Michael Walfish. Eficient RAM and control flow in verifiable outsourced computation. In Network and Distributed System Security Symposium (NDSS), 2015.

[139] Riad S. Wahby, Ioanna Tzialla,abhi shelat, Justin Thaler, and Michael Walfish. Doubly-eficient zkSNARKs without trusted setup. In IEEE Symposium on Security and Privacy, 2018.

[140] Michael Walfish and Andrew J. Blumberg. Verifying computations without reexecuting them: from theoretical possibility to near practicality. Communications of the ACM (CACM), 58(2), 2015.

[141] Wikimedia Foundation Wikipedia. Localization (commutative algebra). https://en<sup>.</sup>wikipedia<sup>.</sup>org/ wiki/Localization\_(commutative\_algebra).

[142] Howard Wu, Wenting Zheng, Alessandro Chiesa, Raluca Ada Popa, and Ion Stoica. DIZK: a distributed zero knowledge proof system. In USENIX Security, 2018.

[143] Tiacheng Xie, Jiaheng Zhang, Yupeng Zhang, Charalampos Papamanthou, and Dawn Song. Libra: Succinct Zero-Knowledge Proofs with Optimal Prover Computation. In IACR International Cryptology Conference (CRYPTO), 2019.

[144] Tiancheng Xie, Jiaheng Zhang,Zerui Cheng,Fan Zhang, Yupeng Zhang, Yongzheng Jia, Dan Boneh, and Dawn Song. zkBridge: Trustless cross-chain bridges made practical. In ACM Conference on Computer and Communications Security (CCS), 2022.

[145] RISC Zero. RISC0 zkVM. https://github<sup>.</sup>com/ risc0/risc0, 2025.

[146] Collin Zhang, Zachary DeStefano, Arasu Arun, Joseph Bonneau, Paul Grubbs, and Michael Walfish. Zombie: Middleboxes that don’t snoop. In Symposium on Networked Systems Design and Implementation (NSDI), 2024.

[147] Yupeng Zhang, Daniel Genkin, Jonathan Katz, Dimitrios Papadopoulos, and Charalampos Papamanthou. vSQL: Verifying arbitrary SQL queries over dynamic outsourced databases. In IEEE Symposium on Security and Privacy, 2017.

[148] Yupeng Zhang, Daniel Genkin, Jonathan Katz, Dimitrios Papadopoulos, and Charalampos Papamanthou.

A zero-knowledge version of vSQL. Cryptology ePrint Archive, Paper 2017/1146, 2017.

[149] Richard Zippel. Probabilistic algorithms for sparse polynomials. In Edward W. Ng, editor, Symbolic and Algebraic Computation, pages 216–226. Springer Berlin Heidelberg, 1979.

[150] zkcrypto. bellman: zk-SNARK library, 2026.

[151] Zkonduit. Easy Zero-Knowledge Inference. https: //github<sup>.</sup>com/zkonduit/ezkl, 2024.

## A Sum-check primitive

Given a prover, P, and a verifier, V, the sum-check primitive of Lund et al. [89] is an interactive protocol for proving that a claimed value <sup>??</sup> is equal to the sum of evaluations of a <sup>??</sup>-variate polynomial <sup>??</sup> over the Boolean hypercube: {0<sup>,</sup> 1} . This primitive is depicted in Figure 7.

Spain relies on the following lemma concerning the soundness and completeness of this primitive [122, Chapter 10.4] [12, Chapter 8.5] [130, Chapter 4.1].

Lemma 1. The primitive in Figure 7 is an interactive proof (the term is defined in the references above) for the claim that <sup>??</sup> = Í??<sub>∈</sub> <sub>{0</sub>,<sub>1}</sub>?? <sup>??</sup> (<sup>??</sup>). If the initial claim is false, V rejects with probability at least 1 − <sup>????</sup>/<sup>??</sup>. If the initial claim is true, P can make V accept with probability 1.

## B Spain’s full back-end protocol and analysis

Here we provide background on polynomial commitment schemes and define the properties required by Spain (§B.1); provide Spain’s full back-end protocol (§B.2) and its correctness proofs (§B.3); quantify the guarantees based on the specific parameters in our implementation and evaluation (§B.4); and finally prove some supporting lemmas (§B.5).

For clarity in exposition, when we mention a polynomial commitment scheme, we are referring to a polynomial commitment scheme for multilinear polynomials. Additionally, when we use the term “coeficients” for a <sup>??</sup>-variate multilinear polynomial, these refer to the coeficients in the multilinear Lagrange basis [130, §3.5] with the interpolating set being the <sup>??</sup>-variate Boolean hypercube: {0<sup>,</sup> 1} . These are exactly the evaluations of the polynomial over the Boolean hypercube.

B.1 Spain-compatible polynomial commitment schemes A multilinear polynomial commitment scheme [79, 94] PC is a tuple of protocols (Setup<sup>,</sup> Commit<sup>,</sup> Open<sup>,</sup> Verify), defined as follows.

• Setup: Given security parameter <sup>??</sup> and a bound on the number of variables in polynomials to be committed to, produce public parameters pp.

• Commit: Given public parameters pp and a multilinear polynomial <sup>˜??</sup> , produce a commitment com <sub>˜??</sub> .

Setup: P and V agree on a field <sup>F</sup>?? and a degree <sup>??</sup> multi-variate   
polynomial <sup>??</sup> over <sup>F</sup>?? with <sup>??</sup> variables.   
Online phase: If at any point V’s check fails, it rejects.   
1. P sends V a value <sup>??</sup>, claimed to equal   
∑︁ ??<sub>(</sub>??<sub>)</sub>   
<sup>??</sup>∈ {0<sup>,</sup>1}<sup>??</sup>   
and a univariate polynomial <sup>??</sup><sub>1</sub>(<sup>??</sup>), claimed to equal   
∑︁ ?? <sub>(</sub>??, ?? , . . . , ??<sub>?? )</sub> .   
<sub>(</sub>??<sub>2</sub>,...,??<sub>?? )</sub> <sub>∈</sub> <sub>{0</sub>,<sub>1}</sub><sup>??</sup>−1   
2. V checks that <sup>??</sup> = <sup>??</sup><sub>1</sub>(0) + <sup>??</sup><sub>1</sub>(1).   
3. V sends P a random <sup>??</sup><sub>1</sub> ∈ <sup>F</sup>??.   
<sub>4.</sub> <sub>For</sub> ?? <sub>=</sub> <sub>2</sub>, . . . , ??<sub>:</sub>   
(a) P sends V a univariate polynomial <sup>??</sup>?? (<sup>??</sup>), claimed to   
equal   
∑︁ ?? <sub>(</sub>??<sub>1</sub>, . . . , ?? <sub>?? −1</sub>, ??, ?? <sub>??+1</sub>, . . . , ??<sub>?? )</sub>.   
<sub>(</sub>??<sub>??+1</sub>,...,??<sub>?? )</sub> <sub>∈</sub> <sub>{0</sub>,<sub>1}</sub><sup>??</sup>−<sup>??</sup>   
(b) V checks that <sup>??</sup>??<sub>−1</sub> (<sup>??</sup>??<sub>−1</sub>) = <sup>??</sup>?? (0) + <sup>??</sup>?? (1).   
(c) V sends P a random <sup>??</sup>?? ∈ <sup>F</sup>??.   
5. Finally, V checks that <sup>??</sup>?? (<sup>??</sup>??) = <sup>??</sup> (<sup>??</sup><sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>??).   
If all checks pass, V accepts.

Figure 7: The sum-check primitive of Lund et al. [89].

• Open: Given public parameters pp, a multilinear polynomial <sup>˜??</sup> , and a point <sup>??</sup>, produce a result <sup>??</sup> and a proof <sup>??</sup>?? that <sup>??</sup> = <sup>˜??</sup> (<sup>??</sup>). Together, the result and proof are called an opening of com <sub>˜??</sub> at <sup>??</sup>.

• Verify: Given public parameters pp, a commitment com <sub>˜??</sub> , a point <sup>??</sup>, and an alleged opening (<sup>??,</sup> <sup>??</sup>??), output “accept” if <sup>??</sup>?? is a valid proof that <sup>??</sup> = <sup>˜??</sup> (<sup>??</sup>) and “reject” otherwise.

A polynomial commitment scheme is binding if it is intractable for a prover to produce two distinct openings (<sup>??,</sup> <sup>??</sup>??) and (<sup>??′,</sup> <sup>??</sup>??′ ) for the same commitment com <sub>˜??</sub> such that the verifier accepts both openings. For Spain, intractable means that a polynomial-time adversary cannot succeed with probability greater than <sup>??</sup><sub>PC</sub>.

Spain requires, as a building block, a binding polynomial commitment scheme, PC, that satisfies an additional property, which we call Weak Integer Binding. Weak Integer Binding is parameterized by 2 constants, <sup>??</sup><sub>max</sub> and <sup>??</sup><sub>max</sub>. Weak Integer Binding has two sub-properties, given below. To state the subproperties we define Integer-limited: a <sup>??</sup>-variate multilinear polynomial <sup>˜??</sup> is called Integer-limited if all of its coeficients are integers with magnitude at most <sup>??</sup><sub>max</sub>.

• Weak Integer Binding, sub-property 1. It is impossible for a prover to produce a commitment com <sub>˜??</sub> unless for some positive integer <sup>??′</sup> and multilinear polynomial <sup>??</sup>˜, <sup>˜??</sup> = <sup>??</sup>˜/<sup>??′</sup>, where <sup>??′</sup> ≤ <sup>??</sup><sub>max</sub> and <sup>??</sup>˜ is Integer-limited. (Here <sup>??</sup>˜/<sup>??′</sup> means a polynomial with the same coeficients as <sup>??</sup>˜ but with an extra <sup>??′</sup> factor in each coeficient’s denominator.)

• Weak Integer Binding, sub-property 2. Given an honest (polynomial-time) prover, for any Integer-limited polynomial <sup>˜??</sup> , invoking Commit causes the prover to produce a valid commitment, and for any point <sup>??</sup>, invoking Open causes the prover to produce a corresponding opening that causes Verify to accept

Weak Integer Binding is similar to, but weaker than, the notion of a Relaxed Mod-PCS introduced by Zinc [60]. A Relaxed Mod-PCS imposes an additional requirement, extractability (essentially, that the prover must “know” <sup>˜??</sup> of the right form in order to produce com <sub>˜??</sub> ).

Also, note that Weak Integer Binding is an idealized property in that sub-property 1 states that it is impossible, rather than computationally intractable, for a prover to produce a commitment com <sub>˜??</sub> that does not satisfy the stated condition. When instantiating a multilinear commitment primitive (§B.4), we will handle probabilistic deviation from the ideal.

## B.2 Spain’s back-end protocol

Spain’s full protocol is in Figure 8. This protocol is parameterized by a constant <sup>??</sup>; an R1CS instance, <sup>X</sup>, containing rationals with unreduced denominator <sup>??</sup> and unreduced numerators with magnitude at most <sup>??</sup><sub>max</sub>; a polynomial commitment scheme PC satisfying Weak Integer Binding with parameters <sup>??</sup><sub>max</sub> and <sup>??</sup><sub>max</sub> (§B.1); and a large set of primes, <sup>??</sup>. The R1CS structure underlying <sup>X</sup> has <sup>??</sup> constraints and <sup>??</sup> variables. Recall from Section 4.2.2 that <sup>??</sup> and <sup>??</sup> are defined to be ⌈log <sup>??</sup>⌉ and ⌈log <sup>??</sup>⌉ respectively.

Note that Weak Integer Binding means an honest prover commits to a polynomial <sup>˜??</sup> with integer coeficients, yet Spain has been described (Fig. 2, §4) as committing to a polynomial <sup>??</sup> with rational coeficients. In fact, in Step 1 (Fig. 8), Spain’s prover obtains <sup>˜??</sup> by multiplying <sup>??</sup> by <sup>??</sup>. Meanwhile the elements of <sup>??</sup> are expected to have unreduced denominator <sup>??</sup> (§4.2.1) and hence the same holds for the coeficients of <sup>??</sup>. Thus, <sup>˜??</sup> indeed has integer coeficients.

## B.3 Correctness of Spain’s back-end protocol

In this section, we prove the correctness, meaning completeness and soundness (§4), of Spain’s back-end, specifically the protocol in Figure 8. The figure depicts, and the proof is about, an idealized version of Spain in which the polynomial commitment scheme meets the properties in Appendix B.1. In addition to quantifying parameters, Appendix B.4 instantiates the polynomial commitment scheme with a concrete protocol, namely DARK [40], and handles the deviation from the ideal.

En route to the proof, we define <sup>??</sup>??,??,??<sub>max</sub>,??,??<sub>max</sub> (written as <sup>??</sup> for brevity) to be

![](images/c211e7e2d1e7444bf691443500374d7c1bfa70528fd93bf450cdfd99b42445d2.jpg)

Additionally, we use min <sup>??</sup> to denote the smallest prime in <sup>??</sup>, and |<sup>??</sup>| to denote the number of primes in <sup>??</sup>.

The definitions of completeness and soundness (§4) reference <sup>??</sup>-accuracy, which was described informally in Section 3. Below, we state <sup>??</sup>-accuracy more formally. Let <sup>??</sup>?? denote row <sup>??</sup> of matrix <sup>??</sup>.

Definition (<sup>??</sup>-accuracy). An assignment <sup>??</sup> for an R1CS structure <sup>S</sup> = ( <sup>??,</sup> <sup>??,</sup> <sup>??</sup>) is <sup>??</sup>-accurate if

![](images/abe107d66fe09d34302169d01406e874cd7df701d3b3a7af34f50031fdc84734.jpg)

We are now ready to state the central correctness theorem for Spain.

Theorem 1. The protocol in Figure 8 satisfies Back-end (<sup>??</sup>/ <sup>??</sup>)-completeness. The protocol also satisfies Back-end <sup>??</sup>-soundness, with soundness error <sup>??</sup> upper-bounded by

![](images/a4ff9b369a3b43319ceee2bee230d71aed996600eec4f4dd0cdf0b7b92585d88.jpg)

Proof. We use two facts about <sup>??</sup>??, both proved in Appendix B.5.

Lemma 2 (<sup>??</sup>?? ill-defined). Let <sup>X</sup>, <sup>??</sup>, and <sup>??</sup> be as in Figure 8, and let <sup>??</sup> be sampled uniformly from <sup>??</sup>. Then

![](images/d9a462e9deb8fde5032a5ed99489bc434ccd6d937ea394302a3d26b2746fe0fd.jpg)

Lemma 3 (<sup>??</sup>?? collision). Let <sup>X</sup>, <sup>??</sup>, <sup>??</sup>, and <sup>??</sup> be as in Figure 8 with <sup>??</sup> ≠ ∥<sup>??</sup>X,?? ∥<sup>2</sup>, and let <sup>??</sup> be sampled uniformly from <sup>??</sup>. Conditioned on <sup>??</sup>?? being defined for ∥<sup>??</sup>X,?? ∥<sup>2</sup>, we have

![](images/61ec76912a0c5629a163912dab2f02e727908f04ddb2559d7a74fc6ab22fcd52.jpg)

Back-end (<sup>??</sup>/ <sup>??</sup>)-completeness. If P has an assignment <sup>??</sup> that is (<sup>??</sup>/ <sup>??</sup>)-accurate for the instance <sup>X</sup>, by the argument of Section 4.1, ∥<sup>??</sup>X,?? ∥<sup>2</sup> ≤ <sup>??2</sup>. Thus if P sends messages prescribed by the protocol, every check by V passes, and V accepts with probability 1.

Back-end <sup>??</sup>-soundness. Suppose that there does not exist an <sup>??</sup>-accurate assignment for <sup>X</sup>. We bound the probability that V accepts.

First, an adversarial prover need not use Commit in Step 1 to produce com <sub>˜??</sub> nor use Open in Step 8 to produce an alleged opening (<sup>??,</sup> <sup>??</sup>??) of com <sub>˜??</sub> at <sup>??ˆ</sup>. To handle all adversarial prover behavior involving the polynomial commitment, we define E<sub>bind</sub> to capture the event that V accepts the opening in Step 8 but this opening is inconsistent with the commitment provided in Step 1. By inconsistent, we mean that <sup>??</sup> ≠ <sup>˜??</sup> (<sup>??ˆ</sup>). By the binding property of the polynomial commitment scheme,

![](images/fb66d06be132d63090720d5b83804046065a396d26cac366a2fe956b7e5e5ffe.jpg)

We now consider the case where E<sub>bind</sub> does not occur, so the binding property of the polynomial commitment scheme fixes a unique <sup>˜??</sup> and thus a unique <sup>??</sup> (and unique <sup>??</sup>).

Setup: Prover P and Verifier V agree on the parameters of the protocol, which are as follows:   
• a small constant <sup>??</sup> ≪ 1   
• an instance, <sup>X</sup> = ( <sup>??,</sup> <sup>??,</sup> <sup>??,</sup> in<sup>,</sup> out), consisting of rationals with unreduced denominator <sup>??</sup> (a power of 2).   
• a polynomial commitment scheme PC satisfying Weak Integer Binding with parameters <sup>??</sup><sub>max</sub> and <sup>??</sup><sub>max</sub>.   
• a large set of primes, <sup>??</sup>, from which V will sample in the protocol.   
Preprocessing: P and V performs the setup required by PC.   
Online phase: If at any point V’s check fails, it rejects.   
1. Using PC, P commits to a multilinear polynomial <sup>˜??</sup> whose coeficients are purportedly integers. P sends this commitment to V.   
• Define <sup>??</sup> := <sup>˜??</sup> /<sup>??</sup>. Define <sup>??</sup> as the coeficients of <sup>??</sup>, and define <sup>??</sup> := (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>). If P is honest, then <sup>??</sup> is chosen to make <sup>??</sup> an   
<sup>??</sup>-accurate assignment to <sup>X</sup>.   
2. P computes ∥<sup>??</sup>X,?? ∥<sup>2</sup> (over <sup>Q</sup>), and sends <sup>??</sup> := ∥<sup>??</sup>X,?? ∥<sup>2</sup> · <sup>??8</sup> to V.   
3. V checks that <sup>??</sup> is an integer, computes <sup>??</sup> := <sup>??</sup>/<sup>??8</sup>, and checks that 0 ≤ <sup>??</sup> ≤ <sup>??2</sup>.   
4. V samples a random prime <sup>??</sup> ∼ <sup>??</sup>, sends it to P, and P and V map all quantities in <sup>Q</sup> into <sup>F</sup>?? via <sup>??</sup>??.   
5. V and P run a degree-4 sum-check primitive on   
??<sub>?? (</sub>??<sub>) =</sub> ∑︁ <sub>(</sub>??<sub>??(</sub>??<sub>)</sub> <sub>·</sub> ??<sub>??(</sub>??<sub>)</sub> <sub>−</sub> ??<sub>?? (</sub>??<sub>))</sub>2,   
<sup>??</sup> ∈ {0<sup>,</sup>1}<sup>??</sup>   
where <sup>??</sup>??, <sup>??</sup>??, and <sup>??</sup>?? are defined as in Section 4.2.2.   
The result of this primitive is three purported claims over <sup>F</sup>??:   
??<sub>?? =</sub> ??<sub>??(</sub>??<sub>)</sub>, ??<sub>?? =</sub> ??<sub>??(</sub>??<sub>)</sub>, <sub>and</sub> ??<sub>?? =</sub> ??<sub>?? (</sub>??<sub>)</sub>   
for a random <sup>??</sup> ∈ <sup>F</sup>??.   
6. V samples a random <sup>??</sup> ∈ <sup>F</sup>??, sends <sup>??</sup> to P, and computes   
?? <sub>←</sub> ??<sub>?? +</sub> ??<sub>?? ·</sub> ?? <sub>+</sub> ??<sub>?? ·</sub> ??2.   
7. P and V run a degree-2 sum-check primitive on   
?? <sub>=</sub> ∑︁ <sub>(</sub> ??<sub>(</sub>??, ??<sub>)</sub> <sub>+</sub> ??<sub>(</sub>??, ??<sub>)</sub> <sub>·</sub> ?? <sub>+</sub> ?? <sub>(</sub>??, ??<sub>)</sub> <sub>·</sub> ??2<sub>)</sub> <sub>·</sub> ??<sub>(</sub>??<sub>)</sub>.   
<sup>??</sup>∈ {0<sup>,</sup>1}<sup>??</sup>   
This results in the following four purported claims over <sup>F</sup>??:   
??<sub>?? =</sub> ??<sub>(</sub>??, ??<sub>)</sub>, ??<sub>?? =</sub> ??<sub>(</sub>??, ??<sub>)</sub>, ??<sub>?? =</sub> ??<sub>(</sub>??, ??<sub>)</sub>, <sub>and</sub> ??<sub>?? =</sub> ??<sub>(</sub>??<sub>)</sub>   
for a random <sup>??</sup> ∈ <sup>F??</sup>??. q   
8. P maps the point <sup>??</sup> into <sup>Z</sup> as <sup>??ˆ</sup>, opens the commitment to <sup>˜??</sup> at <sup>??ˆ</sup>, and sends the result <sup>??</sup> (and accompanying proof <sup>??</sup>??) to V.   
9. V uses <sup>??</sup>?? to check that the result <sup>??</sup> is a valid opening; if it is, <sup>??</sup> = <sup>˜??</sup> (<sup>??ˆ</sup>) over the rationals. V computes in(<sup>??</sup>) and out  (<sup>??</sup>) (over <sup>F</sup>??),   
and combines them with <sup>??</sup>/<sup>??</sup> = <sup>˜??</sup> (<sup>??ˆ</sup>)/<sup>??</sup> = <sup>??</sup>(<sup>??ˆ</sup>) (mapped to <sup>F</sup>?? via <sup>??</sup>??) to produce <sup>??</sup>˜(<sup>??</sup>). V then checks the purported claims from   
the end of Step 7.   
If all checks pass, V accepts.

## Figure 8: Spain’s back-end protocol for proving that an R1CS instance has an <sup>??</sup>-accurate assignment.

Because <sup>X</sup> has no <sup>??</sup>-accurate assignment, ∥<sup>??</sup>X,?? ∥<sub>∞</sub> <sup>></sup> <sup>??</sup> and thus ∥<sup>??</sup>X,?? ∥<sup>2 ></sup> <sup>??2</sup>. However, in Step 3, V accepts only if <sup>??</sup> ≤ <sup>??2</sup>. Consequently, <sup>??</sup> ≠ ∥<sup>??</sup>X,?? ∥<sup>2</sup>.

is undefined on ∥<sup>??</sup>X,?? ∥<sup>2</sup> or <sup>??</sup>?? (<sup>??</sup>) = <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>).

For V to accept the final check in Step 9, it must be the case that, in some step of the protocol, a false claim is transformed into a true claim. We define one bad event per step that captures this transformation.

• E<sub>sc1</sub>: the event that, in Step 5, <sup>??</sup>?? (<sup>??</sup>) ≠ <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>), but after the first sum-check primitive, the claims <sup>??</sup>?? = <sup>??</sup>??(<sup>??</sup>), <sup>??</sup>?? = <sup>??</sup>??(<sup>??</sup>), and <sup>??</sup>?? = <sup>??</sup>?? (<sup>??</sup>) are all true.

• E??<sub>??</sub> : the event that, in Step 4, <sup>??</sup> ≠ ∥<sup>??</sup>X,?? ∥<sup>2</sup><sub>2</sub>, but either <sup>??</sup>?? • E<sub>agg</sub>: the event that, in Step 6, <sup>??</sup>?? ≠ <sup>??</sup>??(<sup>??</sup>), <sup>??</sup>?? ≠ <sup>??</sup>?? (<sup>??</sup>), or <sup>??</sup>?? ≠ <sup>??</sup>?? (<sup>??</sup>), but the aggregated claim <sup>??</sup> = <sup>??</sup>?? + <sup>??</sup>?? · <sup>??</sup> + <sup>??</sup>?? · <sup>??2</sup> is true.

• E<sub>sc2</sub>: the event that, in Step 7,

![](images/b4a8fa84826af0cd34ed3c4d1657484dc9a84b05a5571dd3f42ccb8ecbf15e24.jpg)

but after the second sum-check primitive, the claims <sup>??</sup>?? = ??<sub>(</sub>??, ??<sub>),</sub> ??<sub>?? =</sub> ??<sub>(</sub>??, ??<sub>),</sub> ??<sub>?? =</sub> ?? <sub>(</sub>??, ??<sub>),</sub> <sub>and</sub> ??<sub>?? =</sub> ??<sub>(</sub>??<sub>)</sub> <sub>are</sub> all true.

If none of these occur, then <sup>??</sup>?? is defined on ∥<sup>??</sup>X,?? ∥<sup>2</sup>, <sup>??</sup>?? (<sup>??</sup>) ≠ <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>), and each step of the protocol transforms a false claim into a false claim. As a result, in the final step, at least one of the following must be false:

![](images/458d19cc1ca5b712bc056da970a84f0f58e2b4f2254b178cd051d246329857f9.jpg)

Either the verifier’s explicit evaluation of <sup>??</sup>, <sup>??</sup>, or <sup>??</sup> at (<sup>??,</sup> <sup>??</sup>) will expose a false claim, or the opening of the commitment to <sup>??</sup> will expose a false claim about <sup>??</sup>(<sup>??</sup>). Hence V rejects if none of the bad events occur.

By a union bound, the probability that V accepts is at most the sum of the probabilities of these bad events, plus Pr[E<sub>bind</sub>]. We now bound the probability of each bad event.

For E??<sub>q</sub>, by Lemma 2, the probability that <sup>??</sup>?? is undefined on ∥<sup>??</sup>X,?? ∥<sup>2</sup><sub>2</sub> is at most

![](images/43af1fc1a6cab1c006d88c073e374a29d1d712e8e78d9ee13a1ae32867c3b7fe.jpg)

By Lemma 3, the probability that <sup>??</sup>?? (<sup>??</sup>) = <sup>??</sup>?? (∥<sup>??</sup>X,?? ∥<sup>2</sup>), conditioned on <sup>??</sup> ≠ ∥<sup>??</sup>X,?? ∥<sup>2</sup> and <sup>??</sup>?? being defined on ∥<sup>??</sup>X,?? ∥<sup>2</sup>, is at most

![](images/a485a5105337812bfa74622c527ac4b8e044a3bd0a87bf0862fe3534e0bfb0e2.jpg)

Thus, by a union bound,

![](images/933c4d663e71a22810c867beda580cc0afa9db6146fe798388006a8e94b8375d.jpg)

For E<sub>sc1</sub>, this event involves an invocation of the sum-check primitive on a degree-4 polynomial with <sup>??</sup> variables where the claimed sum is false but the final polynomial evaluation claims are all true. By Lemma 1 and min <sup>??</sup> ≤ <sup>??</sup>,

![](images/062327964bf30754e3975d5a5673485945f54fffdcb7681eda86fbdb4a72f500.jpg)

For E<sub>agg</sub>, this event treats three claims as a degree 2 polynomial and evaluates this polynomial at a random point <sup>??</sup>. If at least one constituent claim is false, the resulting polynomial is non-zero, and thus, by the Factor Theorem (a univariate case of the Schwartz-Zippel lemma [111, 149]) and min <sup>??</sup> ≤ <sup>??</sup>,

![](images/63ca340f07a8d03ebded7eeb0e5eb62fa09edb5cc4963bfa6821681bc5f071ca.jpg)

For E , this event involves an invocation of the sum-check primitive on a degree-2 polynomial with <sup>??</sup> variables where the claimed sum is false but the final polynomial evaluation claims are all true. By Lemma 1 and min <sup>??</sup> ≤ <sup>??</sup>,

![](images/50de87f43f149efd5f31976063059fa119590c94f421908150c2f52c671a3611.jpg)

By a union bound over all bad events, we get Back-end <sup>??</sup>-soundness holds with error at most

![](images/bcb20ea542fe0341c458db0ef9997d874278993484bc426cac4c8df03eda5a90.jpg)

□

## B.4 Quantifying the guarantees of Spain’s back-end

The implementation described in Sections 6 and 7 uses specific parameters. The following corollary characterizes the soundness and completeness guarantees of Spain’s back-end when instantiated with DARK as the polynomial commitment scheme, and in a regime that covers the aforementioned parameters.

Corollary 1. When Figure 8 is instantiated with the following parameters:

• <sup>??</sup> ≤ 2<sup>32</sup>, <sup>??</sup> ≤ 2<sup>32</sup>;

• <sup>??</sup> ≤ 2<sup>96</sup>;

• PC is the DARK multilinear polynomial commitment scheme [40] with <sup>??</sup><sub>max</sub> ≤ 2<sup>96</sup>; and

• <sup>??</sup> is the set of 128-bit primes,

the resulting protocol has Back-end (<sup>??</sup>/ <sup>??</sup>)-completeness and Back-end <sup>??</sup>-soundness, with soundness error <sup>??</sup> ≤ 2<sup>−40</sup>.

Proof. Back-end (<sup>??</sup>/ <sup>??</sup>)-completeness. DARK satisfies subproperty 2 of Weak Integer Binding, so the completeness result of Theorem 1 applies directly to this corollary.

Back-end <sup>??</sup>-soundness. For soundness, DARK only satisfies sub-property 1 of Weak Integer Binding with high probability (explicitly bounded further below), so we have to modify the soundness analysis of Theorem 1.

Suppose that there does not exist an <sup>??</sup>-accurate assignment for <sup>X</sup>. We bound the probability that V accepts. Define the event E<sub>weak</sub> to be the event that, over randomness internal to DARK’s Verify function, V accepts an alleged opening of a commitment com <sub>˜??</sub> at <sup>??ˆ</sup> where <sup>˜??</sup> does not satisfy the conditions detailed in sub-property 1 of Weak Integer Binding.

Conditioned on E<sub>weak</sub> not occurring, the verifier’s acceptance probability is upper-bounded by the soundness error stated in Theorem 1. Thus, the overall probability that V accepts is at most

![](images/3b1d169eba5849905134d0cee13a7c5007ee417b1829415897b77bc185046a1a.jpg)

It remains to fill in the parameters and bound Pr[E<sub>weak</sub>].

First, we quantify DARK-related parameters. We explicitly set <sup>??</sup><sub>max</sub> ≤ 2<sup>96</sup> and derive <sup>??</sup><sub>PC</sub>, <sup>??</sup><sub>max</sub>, and Pr[E<sub>weak</sub>] using a combination of the analysis in the corrected DARK paper [40] and a subsequent work [39]. In the corrected DARK paper [40], it is proved that <sup>??</sup><sub>PC</sub> for the DARK polynomial commitment scheme is at most (3 log |<sup>??</sup>|)/2 , where <sup>??</sup> is a parameter internal to DARK that introduces a tradeof between <sup>??</sup><sub>PC</sub> and <sup>??</sup><sub>max</sub>. By choosing <sup>??</sup> = 50, we get that <sup>??</sup><sub>PC</sub> ≤ (3 log |<sup>??</sup>|)/2 = 3 · 32/2<sup>50</sup> <sup><</sup> 2<sup>−43</sup>. From the analysis and scripts provided in the subsequent work [39], we get that for <sup>??</sup><sub>max</sub> ≤ 2<sup>1422</sup>, Pr[E<sub>weak</sub>] ≤ <sup>??</sup><sub>PC</sub>. Note that the analysis below is not very sensitive to the magnitude of <sup>??</sup><sub>max</sub> or <sup>??</sup><sub>max</sub>; however, it is very sensitive to <sup>??</sup> , and <sup>??</sup> is chosen with that in mind.

Next, we need to determine the size of <sup>??</sup>, the set of 128-bit primes. The number of 128-bit primes is exactly <sup>??</sup>(2<sup>128</sup>) − <sup>??</sup>(2<sup>127</sup>), where <sup>??</sup>(<sup>??</sup>) is the prime counting function. By the following standard bound [109]:

![](images/92ee1ed0d2cf4ba2a4b4d1ef016e47e0c2f88197ac90b3dba14be8e178a55a8e.jpg)

we have that

![](images/e337f0b5fd40e00eb0d2c86f652c5afc452eaf60cb4a3f6ecec762736ba07ea0.jpg)

Additionally, min <sup>??</sup> <sup>></sup> 2<sup>127</sup> by definition.

The remainder of the proof proceeds by computing

![](images/69aa7384f37d91b7427b24f0224364c62997a03ddc942498fc308c961f87897a.jpg)

using the parameters above. This calculation is tedious but mechanical. By definition:

![](images/d94151b696f41d29852f7c6834acb6f6c252ecd9a4486dc84e02709188b9c70e.jpg)

It follows that

![](images/4f3b656dd873a7bc52caa74045bcd74f54a8196accab0350e39967a3417bd28e.jpg)

Additionally, we have the following bound on the second term:

![](images/c4023d457f45524dd9bc764518c5c09cd8c3f152e951651fdad1e77e145f54d1.jpg)

By summing these two terms, <sup>??</sup><sub>PC</sub> <sup><</sup> 2<sup>−43</sup>, and Pr[E<sub>weak</sub>] ≤ <sup>??</sup><sub>PC</sub>, we get that the probability that the verifier accepts a non-<sup>??</sup>-accurate assignment is less than 2<sup>−40</sup>, as claimed. □

## B.5 Deferred proofs

Here we prove Lemma 2 and Lemma 3. We start with two counting lemmas that they use.

Lemma 4. Given an integer <sup>??</sup> of magnitude at most <sup>??</sup> and a set <sup>??</sup> of primes,

![](images/0c9655041d439bff8ebc5bd68216bf5acb26f3c0cb6e91585ac8be10290a649f.jpg)

Proof. For <sup>??</sup> to be divisible by a prime <sup>??</sup>, <sup>??</sup> must be one of the prime factors of <sup>??</sup>. Suppose by contradiction that <sup>??</sup> had more than ⌊log <sub>??</sub> <sup>??</sup>⌋ prime factors from <sup>??</sup> (counting multiplicity). Then <sup>??</sup> would have magnitude at least (min <sup>??</sup>)<sup>⌊log</sup>min <sup>??</sup> <sup>??⌋+1</sup> <sup>></sup> <sup>??</sup>, a contradiction. Thus, <sup>??</sup> has at most ⌊log<sub>min ??</sub> <sup>??</sup>⌋ prime factors from <sup>??</sup>, and the probability that a random prime from <sup>??</sup> divides <sup>??</sup> is at most ⌊log <sub>??</sub> <sup>??</sup>⌋/|<sup>??</sup>|. □

Lemma 5. Consider instance <sup>X</sup>, multilinear polynomial <sup>˜??</sup> , and vector <sup>??</sup>, as defined in the protocol in Figure 8. Let <sup>??′</sup> be the unreduced denominator shared by the coeficients of <sup>˜??</sup> . Then, the denominator of ∥<sup>??</sup>X,?? ∥<sup>2</sup> is exactly <sup>??8</sup> · <sup>??′4</sup>. The numerator of <sup>??</sup> − ∥<sup>??</sup>X,?? ∥<sup>2</sup> is at most <sup>??</sup>, where <sup>??</sup> is as defined in Section B.3, and the denominator of this diference has the same denominator as ∥<sup>??</sup>X,?? ∥<sup>2</sup>.

Proof. The proof proceeds by bookkeeping: tracking exact denominators and an upper bound on the magnitude of intermediate numerators. The accounting pessimistically assumes that no reduction occurs when performing arithmetic operations. For example, when adding two rationals (<sup>??</sup><sub>1</sub><sup>,</sup> <sup>??</sup><sub>1</sub>) and (<sup>??</sup><sub>2</sub><sup>,</sup> <sup>??</sup><sub>2</sub>) where gcd(<sup>??</sup><sub>1</sub><sup>,</sup> <sup>??</sup><sub>2</sub>) = 1, the numerator of the result is at most |<sup>??</sup><sub>1</sub>| · <sup>??</sup><sub>2</sub> + |<sup>??</sup><sub>2</sub>| · <sup>??</sup><sub>1</sub> in magnitude and the denominator is exactly <sup>??</sup><sub>1</sub> · <sup>??</sup><sub>2</sub>.

By definition (§4.1),

![](images/22c7b9c663169686fbbba95f2d48abbc79ce673549b44b6e2b3e7614f6e9584a.jpg)

Note that these summations are over <sup>??</sup> and <sup>??</sup> summands respectively as opposed to 2<sup>??</sup> and 2<sup>??</sup> summands as described in Section 4.2.2. This is because we are working with <sup>??</sup>, <sup>??</sup>, <sup>??</sup> as matrices, rather than their multilinear extensions.

Now, recall that the entries of <sup>??</sup>, <sup>??</sup>, <sup>??</sup>, in, and out all have unreduced denominator <sup>??</sup>; recall also that the numerators of the entries of <sup>??</sup>, <sup>??</sup>, <sup>??</sup>, in, and out have magnitude at most <sup>??</sup><sub>max</sub> (§B.2).

<sup>??</sup> is a concatenation of in, out, and <sup>??</sup> (the definition of <sup>??</sup> is in Figure 8). To bound the components of <sup>??</sup>, Weak Integer Binding’s sub-property 1 (§B.1) implies that, for the coeficients of <sup>˜??</sup> , their unreduced denominator, <sup>??′</sup>, satisfies <sup>??′</sup> ≤ <sup>??</sup><sub>max</sub> and their numerators have magnitude at most <sup>??</sup><sub>max</sub>. By definition of <sup>??</sup>, its coeficients – that is, the components of <sup>??</sup> – share an unreduced denominator of <sup>??</sup> · <sup>??′</sup>, and each has an unreduced numerator of magnitude at most <sup>??</sup><sub>max</sub>. From this, it follows that <sup>??</sup>, when written with a common unreduced denominator of <sup>??</sup> · <sup>??′</sup>, has numerators of magnitude at most ??<sub>max ·</sub> ??′<sub>.</sub>

For any matrix <sup>??</sup>, <sup>??</sup>??,??<sup>??</sup>?? is a rational with an unreduced numerator of magnitude at most <sup>??2</sup><sub>max</sub> · <sup>??′</sup> and an unreduced denominator exactly <sup>??2</sup> · <sup>??′</sup>.

Thus, Í<sup>??</sup><sub>??=1</sub> <sup>??</sup>??,?? <sup>??</sup>?? is a rational with a numerator of magexactly <sup>??2</sup> · <sup>??′</sup>.

It follows that Í<sup>??</sup><sub>??=1</sub> <sup>??</sup>??,?? <sup>??</sup>?? · Í<sup>??</sup><sub>??=1</sub> <sup>??</sup>??,?? <sup>??</sup>?? is a rational with a denominator of magnitude exactly (<sup>??2</sup> · <sup>??′</sup>)<sup>2</sup> = <sup>??4</sup> · <sup>??′2</sup>.

When subtracting Í<sup>??</sup><sub>??=</sub> <sup>??</sup>??,?? <sup>??</sup>??, a rational of the form (<sup>??</sup><sub>1</sub><sup>,</sup> <sup>??2</sup> · <sup>??′</sup>), from Í<sup>??</sup><sub>??=1</sub> <sup>??</sup>??,?? <sup>??</sup>?? ·Í<sup>??</sup><sub>??=1</sub> <sup>??</sup>??,?? <sup>??</sup>??, a rational of the form (<sup>??</sup><sub>2</sub><sup>,</sup> <sup>??4</sup> · <sup>??′2</sup>), one needs to multiply the numerator and denominator of the first rational by <sup>??2</sup> · <sup>??′</sup> to get a common denominator (in the worst case). Thus, after performing the scaling and subtraction, the resulting rational has a numerator of magnitude at most

![](images/b5a3550dd820ef4af74efe87f3c514e9eff7deb9322caab4aaf40b9763367960.jpg)

and an unreduced denominator of magnitude exactly <sup>??4</sup> · <sup>??′2</sup>.

Squaring this rational to get the contribution of row <sup>??</sup> to ∥<sup>??</sup>X,?? ∥<sup>2</sup> results in a rational with a numerator of magnitude at most

![](images/c2dbba28da1430c3cc15c13823ade702277b521aa45b1850b768cdebea4af664.jpg)

and an unreduced denominator of magnitude exactly <sup>??8</sup> · <sup>??′4</sup>.

Summing over <sup>??</sup> rows to get ∥<sup>??</sup>X,?? ∥<sup>2</sup> does not change the denominator so results in a rational with denominator <sup>??8</sup> · <sup>??′4</sup> (as claimed) and a numerator of magnitude at most

![](images/70a944a223d29cab01c6026db9596c29b507dbb742350a12239c2cc8e1771403.jpg)

which simplifies to

![](images/211786cd8aa7ab3441c0d46009789f969dff24e0a4b53992ca70744f23de1cb8.jpg)

To bound the numerator and denominator of <sup>??</sup> − ∥<sup>??</sup>X,?? ∥<sup>2</sup>, we first need to characterize the numerator and denominator of <sup>??</sup>. To do this, we consider V’s checks in Step 3. To pass these checks, <sup>??</sup> must be a rational of the form (<sup>??,</sup> <sup>??8</sup>) where <sup>??</sup> is a positive integer bounded above by <sup>??8</sup> (since 0 ≤ <sup>??</sup> ≤ <sup>??2</sup> ≤ 1). To perform the subtraction <sup>??</sup> − ∥<sup>??</sup>X,?? ∥<sup>2</sup>, one needs to multiply the numerator and denominator of <sup>??</sup> by <sup>??′4</sup> to get a common denominator (in the worst case). The resulting rational <sup>??</sup> − ∥<sup>??</sup>X,?? ∥<sup>2</sup> has a numerator of magnitude at most

![](images/253f0ab627bb6febba5ada482a3ebc587efb4895fdbf91e3149e41aca94d3a77.jpg)

and an unreduced denominator of magnitude exactly <sup>??8</sup> · <sup>??′4</sup>, as claimed.

Given that <sup>??′</sup> ≤ <sup>??</sup><sub>max</sub> and <sup>??</sup> ≤ <sup>??8</sup>, the numerator is upper-bounded by

![](images/4042244aa71035ee7de90eb863c730adab596db7f8fff7d41d48411235ca02de.jpg)

This is exactly <sup>??</sup>, as claimed.

With the prime-divisibility bound (Lemma 4) and the numerator bound (Lemma 5) in hand, the two <sup>??</sup>?? facts quickly follow.

Proof of Lemma 2 (<sup>??</sup>?? ill-defined). <sup>??</sup>?? is undefined on ∥<sup>??</sup>X,?? ∥<sup>2</sup><sub>2</sub> exactly when <sup>??</sup> divides the denominator of ∥<sup>??</sup>X,?? ∥<sup>2</sup><sub>2</sub>. By Lemma 5, the denominator is a product of powers of <sup>??</sup> and <sup>??′</sup> (where <sup>??′</sup> ≤ <sup>??</sup><sub>max</sub>). By construction, <sup>??</sup> does not divide <sup>??</sup>; thus <sup>??</sup> divides the denominator of ∥<sup>??</sup>X,?? ∥<sup>2</sup> if and only if <sup>??</sup> divides <sup>??′</sup>. Applying Lemma 4 with <sup>??</sup> = <sup>??</sup><sub>max</sub> gives the bound. □

Proof of Lemma 3 (<sup>??</sup>?? collision). <sup>??</sup>?? (<sup>??</sup>) = <sup>??</sup>?? (∥<sup>??</sup>??,?? ∥<sup>2</sup>) if and only if <sup>??</sup> divides the numerator of <sup>??</sup> − ∥<sup>??</sup>??,?? ∥<sup>2</sup>, which, by Lemma 5, has magnitude at most <sup>??</sup>. Applying Lemma 4 with <sup>??</sup> = <sup>??</sup> gives the desired bound. □

## C DARK with verifier-known group order

This appendix details the technique mentioned in Section 4.2.3. We consider an RSA group <sup>G</sup> with generator <sup>??</sup> and modulus <sup>??</sup> = <sup>??</sup><sub>1</sub> · <sup>??</sup><sub>2</sub>. The verifier knows <sup>??</sup><sub>1</sub> and <sup>??</sup><sub>2</sub>, while the prover only knows <sup>??</sup> and <sup>??</sup> but not its factorization.

DARK requires, as a primitive, a way for the prover to convince the verifier that <sup>??</sup> = <sup>??</sup> · <sup>?? ·</sup> given <sup>??</sup> , <sup>??</sup> , and <sup>??</sup> and a constant <sup>??</sup> known to both parties. The problem is computing (<sup>??</sup> ) ; the verifier cannot eficiently compute an exponentiation this large, because it requires ⌈log <sup>??</sup>⌉ multiplications, which is potentially on the order of a million or a billion (the combined bit-length of all witness elements). DARK solves this with a proof of exponentiation protocol that is burdensome for the prover. In Spain, the verifier borrows an optimization from RSA signing algorithms when the signer knows the factorization of <sup>??</sup>.

The key observation is that knowledge of the factorization of <sup>??</sup> allows the verifier to compute <sup>??</sup>(<sup>??</sup>), where <sup>??</sup> is Carmichael’s function [1, 43]. Then the verifier can compute <sup>??′</sup> = <sup>??</sup> mod <sup>??</sup>(<sup>??</sup>), a value on the order of <sup>??</sup> rather than <sup>??</sup> itself, and compute (<sup>????</sup>)<sup>??</sup> instead of (<sup>????</sup>)<sup>??</sup>.

The correctness of this substitution is as follows. <sup>??</sup> is a group element and thus is relatively prime to <sup>??</sup>, so by the definition of Carmichael’s function, we have (<sup>??</sup> ) <sup>( )</sup> ≡ 1 (mod <sup>??</sup>)<sup>,</sup> and thus (<sup>????</sup>)<sup>??</sup> ≡ (<sup>????</sup>)<sup>??</sup> (mod <sup>??</sup>)<sup>.</sup>

This substitution is eficient because log <sup>??′</sup> ≈ log <sup>??</sup>, which is at worst a few thousand rather than a few billion.

At a high level, replacing the proof of exponentiation in DARK with an explicit exponentiation, independent of how the verifier computes, does not change the security of DARK.

Block et al. [29, Lemma 6.4] formally prove this in the context of a verifier that does not know the factorization of <sup>??</sup> and opts to compute (<sup>??</sup> ) directly. Their proof applies to our setting as well, as the verifier’s computation of (<sup>????</sup>)<sup>??</sup> is functionally equivalent to computing (<sup>??</sup> ) directly.

## D Protocol extensions

Spain can be adapted and extended in various ways.

## D.1 SIMD-R1CS

Per Section 4.3, Spain can be adapted to support common variations on R1CS, namely SIMD-R1CS and I-R1CS.

In SIMD-R1CS (§4.3), the prover has <sup>??</sup> instances, each with its own public input and witness, but sharing the same R1CS structure ( <sup>??,</sup> <sup>??,</sup> <sup>??</sup>). That is, there are vectors <sup>??</sup><sub>0</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>??<sub>−1</sub>, corresponding to instances <sup>X</sup><sub>0</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>, X</sup>??<sub>−1</sub>, where all instances are the same R1CS structure. To support SIMD-R1CS, define <sup>??</sup>(<sup>??,</sup> <sup>??</sup>) similarly to <sup>??</sup>(<sup>??</sup>). Here <sup>??</sup> selects the particular instance and <sup>??</sup> selects the variable within that instance (similar to how <sup>??</sup> functioned earlier). Given the multilinear extension <sup>??</sup>(<sup>??</sup><sub>1</sub><sup>,</sup> <sup>??</sup><sub>2</sub>), define

![](images/2b7bfc0c7216e00bccc3264f07870ad7990ac0e8147415be50b5c4cbe1e6799b.jpg)

Then there are two options for proving correctness across all <sup>??</sup> instances.

The first option is for the prover to make a single claim <sup>??</sup> about the sum of squared errors across all <sup>??</sup> instances. Then, the verifier can confirm that <sup>??</sup> ≤ <sup>??2</sup> and the two parties can apply the sum-check protocol to prove that

![](images/b4df6ea82beee2efbb4f5076ce7766664cab38770b44d71dd26f8ffc8c342fdc.jpg)

where <sup>ℓ</sup> = ⌈log <sup>??</sup>⌉. This provides Back-end <sup>??</sup>-soundness and Back-end (<sup>??</sup>/ <sup>??</sup> · <sup>??</sup>)-completeness. Notice that completeness degrades with <sup>??</sup> here.

The second option is to have the prover make <sup>??</sup> − 1 separate claims, where for <sup>??</sup> = {0<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup> − 1}, each claim <sup>??</sup> ?? is about ∥<sup>??</sup>X<sub>??</sub> ,??<sub>??</sub> ∥<sup>2</sup> for the respective instance <sup>X</sup> ?? . The verifier then checks that each <sup>??</sup> ?? is at most <sup>??2</sup>. Then, the prover and verifier interpret <sup>??</sup>?? (<sup>??</sup>) = [<sup>??</sup>?? (<sup>??</sup><sub>0</sub>)<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>?? (<sup>??</sup>??<sub>−1</sub>)] as a function (from index bits to value) to get its multilinear extension: <sup>??</sup> (<sup>??</sup>). Finally, and uses polynomial identity testing (similar to Spartan [116]) to prove that <sup>??</sup> (<sup>??</sup>) is equal to

![](images/9b599c5df14cdb81dd137fde41332871d0a4543ccd074ad6b0eeb94f881188f9.jpg)

This provides Back-end <sup>??</sup>-soundness and Back-end (<sup>??</sup>/ <sup>??</sup>)- completeness. Compared to the first option, completeness does

not degrade with <sup>??</sup> here; however, the expression is degree 5 in <sup>??</sup> rather than degree 4, which mildly increases prover and verifier time.

## D.2 I-R1CS

For I-R1CS (§4.3), the modification to Spain is simply: at the end of the protocol, rather than opening a single commitment, the prover opens all commitments <sup>??</sup><sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>, ??</sup>??.

Recall that Spain introduces an additional optimization: Spain allows for the prover and verifier to collaboratively introduce not only new values for the assignment but also new constraints on the witness in each round. This allows the verifier to encode random challenges in constraints, or to partially specify constraints that are “filled-in” by the prover. These techniques reduce the cost of performing dot products between the witness and random vectors, which is the core operation in checkers for matrix multiplication [56, 74]

## D.3 Diferent norms for error measurement

Spain can be generalized to have a smaller gap between soundness and completeness versus the one presented in the paper, namely <sup>??</sup>?? = <sup>??</sup>/ <sup>??</sup>. Doing so lowers the precision required of the prover’s witness generation (see §6.3 for the interplay between “precision of witness generation” and <sup>??</sup>??) but makes the underlying back-end protocol more costly.

Specifically, by using the <sup>ℓ2??</sup> norm rather than the <sup>ℓ2</sup> norm of <sup>??</sup>X,??, for integer <sup>??</sup> <sup>></sup> 1, Spain will continue to have Backend <sup>??</sup>-soundness but now it will have Back-end (<sup>??</sup>/<sup>??1/(2??)</sup> )- completeness. That is because the following chain of inequalities holds:

![](images/4c81478542dd6623655c820d2f5e1335d2ef5ed222739b8bf93fbfac173bda72.jpg)

for any integer <sup>??</sup> <sup>></sup> 1. To adapt Spain to use the <sup>ℓ2</sup> norm, the prover and verifier start with the following equation in place of Equation (4) in Section 4.2.2 (Step 5 in Figure 8):

![](images/81458f1b337ce259b7f569ecc10853361a0fef464b517358a48ed1aaeadc78a7.jpg)

This is a degree-(4<sup>??</sup>) polynomial in <sup>??</sup>, so as <sup>??</sup> increases, so does prover time, verifier time, and communication.

## E Translation fidelity

This appendix defines translation fidelity and covers some technical details of this concept. The bulk of the appendix analyzes the translation fidelity of the arithmetizations presented in Section 5.

## E.1 Preliminaries

Definitions. Given an R1CS structure <sup>S</sup> = ( <sup>??,</sup> <sup>??,</sup> <sup>??</sup>), recall that all entries in <sup>??,</sup> <sup>??,</sup> <sup>??</sup> are presumed to have a given denominator <sup>??</sup>, and likewise with the assignment <sup>??</sup> (§4.2.1, Appx. B). We call such numbers <sup>??</sup>-multiples, where <sup>??</sup> = 1/<sup>??</sup>.

Let <sup>??</sup>?? (<sup>??</sup>) denote the possible outputs of function <sup>??</sup> on input <sup>??</sup> when its individual operations have error bounded by ??<sub>.</sub>

Recall the distinction between <sup>??</sup> and <sup>??</sup><sub>wg</sub> (§3). <sup>??</sup> is part of the underlying protocol’s soundness guarantee: if any operation in an execution has error greater than <sup>??</sup>, the verifier is supposed to reject with high probability. On the other hand, <sup>??</sup><sub>wg</sub> connects to the protocol’s completeness guarantee: we want to arrange the design and implementation so that if the prover limits the per-operation error to <sup>??</sup><sub>wg</sub>, then it can satisfy all constraints with suitable error, and thereby cause the verifier to accept.

The reason for the asymmetry is technical. It relates to the definitions of soundness and completeness in the front-end (given in the next paragraph), and to the fact that <sup>??</sup> and <sup>??</sup>?? are diferent, which itself stems from the fact that ∥<sup>??</sup>X,?? ∥<sub>∞</sub> ≤ <sup>??</sup> does not imply ∥<sup>??</sup>X,?? ∥<sup>2</sup> ≤ <sup>??2</sup> (§4.1).

Now, consider a purported translation of <sup>??</sup> to an R1CS structure <sup>S</sup> = ( <sup>??,</sup> <sup>??,</sup> <sup>??</sup>). Translation fidelity is two properties:

• The translation is <sup>??</sup>-tf-sound if: for all <sup>??</sup>-accurate assignments (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>) to <sup>S</sup>, out ∈ <sup>??</sup>?? (in).

• The translation is <sup>??</sup>?? -tf-complete if: for all (in<sup>,</sup> out) such that out ∈ <sup>??</sup>??<sub>wg</sub> (in) and (in<sup>,</sup> out) contains only <sup>??</sup>-multiples, there exists an accompanying <sup>??</sup> such that (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>) is an <sup>??</sup>??-accurate assignment to <sup>S</sup>.

It is helpful to keep the following ordering in mind:

<sup>??</sup> ≥ <sup>??</sup> (will be established in the examples below)

<sub>≥</sub> ??<sub>wg</sub> (will be established in the examples below)

Per-operation vs per-function translation fidelity. The definitions of tf-soundness and tf-completeness cover translation of an entire function. However, the arithmetizations that we present in the next section will be at the level of individual operations. For these lower-level translations to be relevant, Spain needs a way to combine the translations of individual operations. The needed concept is composition (of operations or functions), and specifically how translations combine under composition. The description below delves into detail; the high-level point is that focusing on the translations of individual operations is justified.

Given two functions <sup>??</sup> and <sup>??</sup>, with corresponding R1CS instances <sup>X</sup>?? = (<sup>??</sup>??<sup>,</sup> <sup>??</sup>??<sup>,</sup> <sup>??</sup>??<sup>,</sup> in??<sup>,</sup> out??) and <sup>X</sup>?? = ( <sup>??</sup>??<sup>,</sup> <sup>??</sup>??<sup>,</sup> <sup>??</sup>??<sup>,</sup> in??<sup>,</sup> out??), the corresponding instance for <sup>??</sup> ◦ <sup>??</sup>, <sup>X</sup>??<sub>◦</sub>?? , is ( <sup>??,</sup> <sup>??,</sup> <sup>??,</sup> in<sup>,</sup> out) where in = in?? , out = out??, and <sup>??,</sup> <sup>??,</sup> <sup>??</sup> contain the constraints of <sup>??</sup>??<sup>,</sup> <sup>??</sup>??<sup>,</sup> <sup>??</sup>?? and <sup>??</sup>??<sup>,</sup> <sup>??</sup>??<sup>,</sup> <sup>??</sup>??, relabeled so that the output variables of <sup>X</sup>?? and the input variables of <sup>X</sup>?? refer to the same set of variables, which we call med; the variables in med are not part of either in or out. The lemma below states that translation fidelity is preserved by the composition of functions.

Lemma 6. If <sup>??</sup> and <sup>X</sup>?? satisfy <sup>??</sup>-tf-soundness and <sup>??</sup>?? -tfcompleteness, and if <sup>??</sup> and <sup>X</sup>?? satisfy <sup>??′</sup>-tf-soundness and <sup>??′</sup><sub>??</sub> -tf-completeness, then <sup>??</sup> ◦ <sup>??</sup> and <sup>X</sup>??<sub>◦</sub>?? satisfy min{<sup>??,</sup> <sup>??′</sup>}- tf-soundness and max{<sup>??</sup>??<sup>,</sup> <sup>??′</sup> }-tf-completeness.

Proof. We first establish min{<sup>??,</sup> <sup>??′</sup>}-tf-soundness, where <sup>??∗</sup> := min{<sup>??,</sup> <sup>??</sup> }. The constraints of <sup>X</sup>??<sub>◦</sub>?? are those of <sup>X</sup>?? together with those of <sup>X</sup>??, sharing only the variables med. An <sup>??∗</sup>- accurate assignment to the composite therefore restricts to an <sup>??∗</sup>-accurate assignment to each part; as <sup>??∗</sup> ≤ <sup>??</sup> and <sup>??∗</sup> ≤ <sup>??′</sup>, these are in particular <sup>??</sup>- and <sup>??′</sup>-accurate. Then <sup>??</sup>-tf-soundness of <sup>??</sup> gives med ∈ <sup>??</sup>?? (in), and <sup>??′</sup>-tf-soundness of <sup>??</sup> gives out ∈ <sup>??</sup> ?? (med), so out ∈ (<sup>??</sup> ◦ <sup>??</sup>)?? (in).

For tf-completeness, set <sup>??∗</sup> := max{<sup>??</sup>?? <sup>,</sup> <sup>??′</sup><sub>??</sub> }. Consider (in<sup>,</sup> out) where in and out contain <sup>??</sup>-multiples and out ∈ (<sup>??</sup> ◦ <sup>??</sup>) ?? (in). By definition of the composite, there must be med, consisting of <sup>??</sup>-multiples, with med ∈ <sup>??</sup>?? (in) and out ∈ <sup>??</sup> ?? (med). Applying <sup>??</sup>??-tf-completeness of <sup>??</sup>, there exists <sup>??</sup>??, where (in<sup>,</sup> med<sup>,</sup> 1<sup>,</sup> <sup>??</sup>??) is an <sup>??</sup>??-accurate assignment to ( <sup>??</sup>??<sup>,</sup> <sup>??</sup>??<sup>,</sup> <sup>??</sup>??). Likewise, there exists <sup>??</sup>??, where (med<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>??) is an <sup>??′</sup> -accurate assignment to (<sup>??</sup>??<sup>,</sup> <sup>??</sup>??<sup>,</sup> <sup>??</sup>??). Combining <sup>??</sup>??, <sup>??</sup>??, and med into <sup>??</sup>, the assignment (in<sup>,</sup> out<sup>,</sup> 1<sup>,</sup> <sup>??</sup>) satisfies each constraint of <sup>X</sup>??<sub>◦</sub>?? with error upper-bounded by <sup>??</sup>?? or <sup>??</sup><sub>??</sub>, hence upper-bounded by <sup>??∗</sup>. □

## E.2 Analysis of arithmetizations

The <sup>??</sup> and <sup>??</sup>?? described for the translations below depend on the magnitudes of the inputs to these subfunctions. This is not problematic because Spain enforces a strict bound on the magnitude of rationals in the proof protocol (§B). By considering this maximum magnitude, one derives absolute bounds on <sup>??</sup> and <sup>??</sup>??.

z ← x/y. Division is a special case where the error bound is inversely proportional to the magnitude of <sup>??</sup>, and thus one must place restrictions on the domain of <sup>??</sup> or perform static analysis to ensure <sup>??</sup> is not too close to 0 when using this operation. Here we will assume that |<sup>??</sup>| ≥ <sup>??</sup> for some known ?? > <sub>0.</sub>

First, we establish <sup>??</sup>-tf-soundness. Suppose we have an <sup>??</sup>-accurate assignment to <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>. That means |<sup>??</sup> · <sup>??</sup> − <sup>??</sup>| ≤ <sup>??</sup>. Rearranging, we have that |<sup>??</sup> − (<sup>??</sup>/<sup>??</sup>)| ≤ <sup>??</sup>/|<sup>??</sup>|. This implies that <sup>??</sup> is within <sup>??</sup>/|<sup>??</sup>| of <sup>??</sup>/<sup>??</sup>, and thus |<sup>??</sup> − (<sup>??</sup>/<sup>??</sup>)| ≤ <sup>??</sup>/<sup>??</sup> (using the assumed lower bound on |<sup>??</sup>|). Letting <sup>??</sup> = <sup>??</sup>/<sup>??</sup> completes the proof of <sup>??</sup>-tf-soundness.

Second, for <sup>??</sup>?? -tf-completeness, consider all (<sup>??,</sup> <sup>??,</sup> <sup>??</sup>), restricted to <sup>??</sup>-multiples, such that <sup>??</sup> = (<sup>??</sup>/<sup>??</sup>) + <sup>??</sup><sub>±</sub> where |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup><sub>wg</sub>. The constraint has error at most

![](images/186a942a196861e75561881e2bce93faabb59305309179e5ca17517861757bdd.jpg)

This establishes <sup>??</sup>??-tf-completeness provided that <sup>??</sup>?? ≥ <sup>??</sup><sub>wg</sub>|<sup>??</sup>| for all inputs <sup>??</sup>.

y ← x. First, we establish <sup>??</sup>-tf-soundness. Suppose we have an <sup>??</sup>-accurate assignment to <sup>??</sup>·<sup>??</sup> ≈?? <sup>??</sup>. That means |<sup>??2</sup>−<sup>??</sup>| ≤ <sup>??</sup>. This can be rewritten as |<sup>??</sup> − <sup>??</sup>| · |<sup>??</sup> + <sup>??</sup>| ≤ <sup>??</sup>, where <sup>??</sup> is a true square root of <sup>??</sup>, and assume WLOG that <sup>??</sup> is the positive root. This implies that either |<sup>??</sup> − <sup>??</sup> | or |<sup>??</sup> + <sup>??</sup> | is less than or equal to <sup>??</sup>. This, in turn, implies that <sup>??</sup> is within <sup>??</sup> of a true square root of <sup>??</sup>. Letting <sup>??</sup> = <sup>??</sup> finishes the proof for <sup>??</sup>-tf-soundness.

Second, for <sup>??</sup>?? -tf-completeness, consider all (<sup>??,</sup> <sup>??</sup>), restricted to <sup>??</sup>-multiples, such that <sup>??</sup> = <sup>??</sup> + <sup>??</sup><sub>±</sub> where <sup>??</sup><sub>±</sub> is a real number with |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup><sub>wg</sub>. The constraint <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup> is satisfied with error at most

![](images/0178d37dee3c60b317e6471b9285f1e901db429c3c3ccbb8da60f5355c7fca89.jpg)

This establishes <sup>??</sup>?? -tf-completeness provided that <sup>??</sup>?? ≥ 2<sup>??</sup><sub>wg</sub>| <sup>??</sup>| + <sup>??2</sup><sub>wg</sub> for all inputs <sup>??</sup>.

assert (x ≥ y). Recall that this is an assert of the form “greaterthan-or-approximately equal” where <sup>??</sup> and <sup>??</sup> are allowed (but not required) to be “approximately-equal” when they are within <sup>??</sup> of each other.

First, we establish <sup>??</sup>-tf-soundness. Suppose we have an <sup>??</sup>- accurate assignment to <sup>??</sup> ·<sup>??</sup> ≈?? <sup>??</sup>−<sup>??</sup>. That means |<sup>??2</sup>− (<sup>??</sup>−<sup>??</sup>)| ≤ <sup>??</sup>. By definition, <sup>??2</sup> ≥ 0. This implies that <sup>??</sup> − <sup>??</sup> ≥ −<sup>??</sup>. Letting <sup>??</sup> = <sup>??</sup> finishes the proof for <sup>??</sup>-tf-soundness.

Second, for <sup>??</sup>?? -tf-completeness, consider all <sup>??,</sup> <sup>??</sup>, restricted to <sup>??</sup>-multiples, such that <sup>??</sup> ≥ <sup>??</sup>. Let <sup>??</sup> be the nearest <sup>??</sup>-multiple to <sup>??</sup> − <sup>??</sup>. Thus, <sup>??</sup> = <sup>??</sup> − <sup>??</sup> + <sup>??</sup><sub>±</sub> where |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup>/2. Then the constraint <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup> − <sup>??</sup> is satisfied with error at most

![](images/f2fb5b244e1f4185f1ebb86a5bdfbe2ec8b47392f6030c29090ac0ff5720f58a.jpg)

This establishes <sup>??</sup>?? -tf-completeness provided that <sup>??</sup>?? ≥ ?? ?? <sub>−</sub> ?? <sub>+</sub> ??2<sub>/4.</sub>

b ← (x ≥ y). First, we establish <sup>??</sup>-tf-soundness for <sup>??</sup> <sup><</sup> 1/8. Suppose we have an <sup>??</sup>-accurate assignment to the constraints: <sup>??</sup> · (1 − <sup>??</sup>) ≈?? 0, (2<sup>??</sup> − 1) · (<sup>??</sup> − <sup>??</sup>) ≈?? <sup>??</sup>, and <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>. Using the same reasoning as in proving <sup>??</sup>-tf-soundness for the assert statement, the third constraint implies <sup>??</sup> ≥ −<sup>??</sup>.

The first constraint implies |<sup>??</sup> · (1 − <sup>??</sup>)| ≤ <sup>??</sup>. By our bound on <sup>??</sup> and the quadratic formula applied to −<sup>??</sup> ≤ <sup>??</sup> · (1 − <sup>??</sup>) ≤ <sup>??</sup>, we have

![](images/e442688a7bd7fe532ba49adc9e6c79f7bfd13001749f4be36291c6b22f67554c.jpg)

or

![](images/24073c9bf7d7d9d1e685d6a0623b81ac02b1c96c4f043d92109a16b28b17594e.jpg)

Given that 1 − 4<sup>??</sup> ≥ 1−4<sup>??</sup> for <sup>??</sup> <sup><</sup> 1/4, and 1 + 4<sup>??</sup> ≤ 1+4<sup>??</sup> for <sup>??</sup> <sup><</sup> 1/4, this implies that <sup>??</sup> ∈ [−2<sup>??,</sup> 2<sup>??</sup>] ∪ [1 − 2<sup>??,</sup> 1 + 2<sup>??</sup>], namely that <sup>??</sup> is within 2<sup>??</sup> of either 0 or 1.

The second constraint requires the most involved analysis. An <sup>??</sup>-accurate assignment implies | (2<sup>??</sup> − 1) · (<sup>??</sup> − <sup>??</sup>) − <sup>??</sup>| ≤ <sup>??</sup>.

Given that <sup>??</sup> ≥ −<sup>??</sup>, this implies (2<sup>??</sup> − 1) · (<sup>??</sup> − <sup>??</sup>) ≥ −2<sup>??</sup>. Let <sup>??′</sup> := 2<sup>??</sup> − 1. From the bounds on <sup>??</sup> from before

![](images/0c5e64f88379c5fbad7307b2607fe08aef568903eedbc252b7b946cb20bbdf01.jpg)

We also have <sup>??′</sup> · (<sup>??</sup> − <sup>??</sup>) ≥ −2<sup>??</sup>. We consider two cases, depending on which interval <sup>??′</sup> falls into.

Case 1: <sup>??′</sup> ∈ [−1 − 4<sup>??,</sup> −1 + 4<sup>??</sup>]. In this case, we have

![](images/f861c5e36d9c8dd136b9b4e02bf75b6153d131924fdc64d78ebf87d2e98429da.jpg)

Given that <sup>??</sup> ≤ 1/8, we have

![](images/a37b065b3ee4966e20c3a0bd2d0806220e3bdbf8f5db3f9baa5b5f9373f6b684.jpg)

Case 2: <sup>??′</sup> ∈ [1 − 4<sup>??,</sup> 1 + 4<sup>??</sup>]. In this case, we have

![](images/6f817a03d5a3b06d3802a8b0139d27dfa2973eb5eee2f2cdd01ca2b68ee4f6ec.jpg)

Given that <sup>??</sup> ≤ 1/8, we have

![](images/f47515d505dfe0948a2574504e56f8a94d05b19b013e0caf3e7089fbd005deaa.jpg)

Summarizing the two cases: <sup>??</sup> ∈ [−2<sup>??,</sup> 2<sup>??</sup>] (which is case 1) implies <sup>??</sup> − <sup>??</sup> ≤ 4<sup>??</sup>, while <sup>??</sup> ∈ [1 − 2<sup>??,</sup> 1 + 2<sup>??</sup>] (which is case 2) implies <sup>??</sup> − <sup>??</sup> ≥ −4<sup>??</sup>, or <sup>??</sup> − <sup>??</sup> ≤ 4<sup>??</sup>.

Taking the contrapositive of both

![](images/55be6991f33676da0e8800be7a670736329cb6f7ed44b6354d35345875732df0.jpg)

Finally, if |<sup>??</sup> − <sup>??</sup>| ≤ 4<sup>??</sup>, no further conclusion can be drawn about <sup>??</sup>, except that it must remain in the intervals derived above. This means it must be within 2<sup>??</sup> of either 0 or 1.

By taking <sup>??</sup> = 4<sup>??</sup>, the relationships among <sup>??</sup>, <sup>??</sup>, and <sup>??</sup> obey the intended semantics of the operation, and thus <sup>??</sup>-tfsoundness holds.

Second, we establish <sup>??</sup>??-tf-completeness, provided that <sup>??</sup><sub>wg</sub> ≤ 1/2. Consider all (<sup>??,</sup> <sup>??,</sup> <sup>??</sup>), restricted to <sup>??</sup>-multiples, such that <sup>??</sup> = 1 + <sup>??</sup><sub>±</sub> if <sup>??</sup> ≥ <sup>??</sup> and <sup>??</sup> = <sup>??</sup><sub>±</sub> otherwise, where <sup>??</sup><sub>±</sub> is a real number with |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup><sub>wg</sub>.

For the first constraint there are two cases to consider.

Case 1: suppose <sup>??</sup> ≥ <sup>??</sup> and thus <sup>??</sup> = 1 + <sup>??</sup><sub>±</sub>. The constraint is satisfied with error at most

![](images/434c5a8d406a7507e50dd956037398925515e67af3228c0d505a78055ab4c9b7.jpg)

Case 2: suppose <sup>??</sup> <sup><</sup> <sup>??</sup> and thus <sup>??</sup> = <sup>??</sup><sub>±</sub>. The upper bound on error is the same:

![](images/d632575846b3a2e6f3d6c1a02f68e0189a91200175557f679991dc7ec304825b.jpg)

For the second constraint, take <sup>??</sup> = (2<sup>??</sup> − 1) · (<sup>??</sup> − <sup>??</sup>). The constraint is then satisfied with zero error.

For the third constraint, take <sup>??</sup> to be the nearest <sup>??</sup>-multiple to <sup>??</sup>. Thus, <sup>??</sup> = <sup>??</sup> + <sup>??</sup><sub>±</sub> where |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup>/2. Such a square root exists because <sup>??</sup> ≥ 0. This follows because (2<sup>??</sup> − 1) and (<sup>??</sup> − <sup>??</sup>) have the same sign, as long as <sup>??</sup><sub>wg</sub> ≤ 1/2. Now, we show <sup>??</sup> ≤ 2 · |<sup>??</sup> − <sup>??</sup>|, as follows. If <sup>??</sup> ≥ <sup>??</sup>, then <sup>??</sup> = 1 + <sup>??</sup><sub>±</sub> and thus

![](images/35c0f10f951f278f0ac723d49a8612fe1fbaa572848c1df93a1fc52766c9812c.jpg)

If <sup>??</sup> <sup><</sup> <sup>??</sup>, then <sup>??</sup> = <sup>??</sup><sub>±</sub> and thus

![](images/a351bdbfa5c5ca9e486aed6ba7791860bb961d29274ece6f044efbf7fa4933fc.jpg)

Given this, the third constraint is satisfied with error at most

![](images/939633c52aff31b485ca2c466152798ef8ad8ff21b4b93fe381a7059481c2dcd.jpg)

This establishes <sup>??</sup>?? -tf-completeness provided that <sup>??</sup>?? ≥ max{??<sub>wg</sub> + ??<sup>2</sup><sub>wg</sub>, ??√︁2 · |?? − ??| + ??<sup>2</sup>/4}.

z ← max{v <sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> v }. Recall the constraints from Section 5:

<sub>•</sub> <sub>for</sub> <sub>all</sub> ?? <sub>∈</sub> <sub>{1</sub>, . . . , ?? <sub>}:</sub> ??<sub>?? ·</sub> ??<sub>?? ≈??</sub> ?? <sub>−</sub> ??<sub>??</sub>

• for all <sup>??</sup> ∈ {1<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup> }: <sup>??</sup>?? · (1 − <sup>??</sup>?? ) ≈?? 0

• for all <sup>??</sup> ∈ {1<sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup> }: <sup>??</sup>?? · (<sup>??</sup> − <sup>??</sup>?? ) ≈?? 0

• Í<sup>??</sup><sub>??=1</sub> <sup>??</sup>?? ≈?? 1

First, we establish <sup>??</sup>-tf-soundness, for all <sup>??</sup> ≤ 1/4 when <sup>??</sup> · (2<sup>??</sup> + 1) <sup><</sup> 1. Suppose we have an <sup>??</sup>-accurate assignment to the constraints. For the first set of constraints, we can reuse the results from the assert operation to establish that <sup>??</sup> ≥ <sup>??</sup>?? − <sup>??</sup> for all <sup>??</sup>. From the second set of constraints, we can use the same reasoning as in <sup>??</sup> ← (<sup>??</sup> ≥ <sup>??</sup>) to establish that each <sup>??</sup>?? is within 2<sup>??</sup> of either 0 or 1. Given that <sup>??</sup> · (2<sup>??</sup> + 1) <sup><</sup> 1, the last constraint and the second set together imply that there exists some index <sup>??</sup> such that <sup>??</sup> ?? is within 2<sup>??</sup> of 1. This follows by contradiction, suppose this was not the case, then each <sup>??</sup>?? would be within 2<sup>??</sup> of 0, and thus Í<sup>??</sup><sub>??</sub> <sup>??</sup>?? ≤ 2<sup>??</sup> · <sup>??</sup> <sup><</sup> 1 − <sup>??</sup>, leaving the final constraint unsatisfied by more than <sup>??</sup>.

This leaves the third set of constraints to analyze. Let <sup>??</sup> be the index for which <sup>??</sup> ?? ≥ 1 − 2<sup>??</sup>. Since the assignment is <sup>??</sup>-accurate, |<sup>??</sup> ?? · (<sup>??</sup> − <sup>??</sup> ?? )| ≤ <sup>??</sup>. Thus:

![](images/efca6c50a0f20ca9d9969a8158a1911af0550d588969e6b17216e16a829e70ef.jpg)

In particular:

![](images/2fb047b353bd1b5445d8d3105c7ad553a4c45e2def93b4b0683b6b89267b46ef.jpg)

We already have <sup>??</sup> ≥ <sup>??</sup>?? − <sup>??</sup> for all <sup>??</sup>, which implies

![](images/489f0633c7047bdf52bc7097e14365bfa7459dee98f9c78fef9a87534b91ef4c.jpg)

and since <sup>??</sup> <sup><</sup> <sub>1−2??</sub> € also

![](images/fa86fd1e8d83aea524f6873945341a673b509e85542519db31e75e00b4731b23.jpg)

Thus, |<sup>??</sup> − max?? <sup>??</sup>?? | ≤ <sup>??</sup><sub>1−2??</sub> . Given that <sup>??</sup> ≤ 1/4, <sup>??</sup><sub>1−2??</sub> ≤ <sup>??</sup>1/2 = 2<sup>??</sup>. Setting <sup>??</sup> = 2<sup>??</sup> completes the proof of <sup>??</sup>-tf-soundness.

Second, we establish <sup>??</sup>??-tf-completeness. Consider all (<sup>??</sup><sub>1</sub><sup>,</sup> <sup>.</sup> <sup>.</sup> <sup>.</sup> <sup>,</sup> <sup>??</sup>??<sup>,</sup> <sup>??</sup>), restricted to <sup>??</sup>-multiples, such that <sup>??</sup> = max?? <sup>??</sup>?? + <sup>??</sup><sub>±</sub> for some <sup>??</sup><sub>±</sub> where |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup><sub>wg</sub>.

Take <sup>??</sup> ?? = 1 for the index <sup>??</sup> corresponding to the maximum value, and set all other <sup>??</sup>?? to 0.

For the first set of constraints, we use that <sup>??</sup> − <sup>??</sup>?? ≥ −<sup>??</sup><sub>wg</sub>. This follows from the fact that <sup>??</sup> = max?? <sup>??</sup>?? + <sup>??</sup><sub>±</sub> and thus <sup>??</sup> − <sup>??</sup>?? = max?? (<sup>??</sup>??) + <sup>??</sup><sub>±</sub> − <sup>??</sup>?? ≥ <sup>??</sup><sub>±</sub> ≥ −<sup>??</sup><sub>wg</sub>. Now there are two cases to consider.

Case 1: suppose <sup>??</sup> − <sup>??</sup>?? ≥ 0. In this case, set <sup>??</sup>?? to be the nearest <sup>??</sup>-multiple to <sup>??</sup> − <sup>??</sup>??. Thus, <sup>??</sup>?? = <sup>??</sup> − <sup>??</sup>?? + <sup>??</sup><sub>±??</sub>, where |<sup>??</sup><sub>±??</sub> | ≤ <sup>??</sup>/2. These constraints are satisfied with error at most

![](images/45e5c2f0d89eb69890b4e53a6962db1bb85994b1456c232a4923b250223ec4ab.jpg)

Case 2: suppose <sup>??</sup> − <sup>??</sup>?? <sup><</sup> 0. In this case, take <sup>??</sup>?? = 0. These constraints are satisfied with error at most

![](images/54a0a43320c80f153887bc8145f2233c530482a9a7316c5608f3ea71e009312a.jpg)

The second and fourth set of constraints are satisfied with zero error, by the choice of <sup>??</sup>?? above.

The third set of constraints breaks into two cases. When <sup>??</sup>?? = 0, the <sup>??</sup>th constraint in the set is satisfied with zero error. When <sup>??</sup>?? = 1 (that is, when <sup>??</sup> = <sup>??</sup> ), constraint <sup>??</sup> in the set is satisfied with error at most <sup>??</sup><sub>wg</sub>, as <sup>??</sup> ?? · (<sup>??</sup> − <sup>??</sup> ?? ) = <sup>??</sup> − <sup>??</sup> ?? = ??<sub>± ≤</sub> ??<sub>wg.</sub>

This establishes <sup>??</sup>?? -tf-completeness provided that

![](images/1b1d065cbc3f984a25570d04ec10cb2f3186a203aef765c8a1a71c6edb4c75a1.jpg)

ReLU. First, we establish <sup>??</sup>-tf-soundness for <sup>??</sup> ≤ 1. Suppose we have an <sup>??</sup>-accurate assignment to the constraints: <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup> − <sup>??</sup>, <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>, and (<sup>??</sup> − <sup>??</sup>) · <sup>??</sup> ≈?? 0 From the first and second constraints, we have that <sup>??</sup> ≥ −<sup>??</sup> + max(0<sup>,</sup> <sup>??</sup>). The third constraint is where things diverge from prior analyses. An <sup>??</sup>-accurate assignment implies | (<sup>??</sup> − <sup>??</sup>) · <sup>??</sup>| ≤ <sup>??</sup>. This can be decomposed as |<sup>??</sup> − <sup>??</sup>| · |<sup>??</sup>| ≤ <sup>??</sup>. For the product on the left to be at most <sup>??</sup>, then at least one of the two factors must be at most <sup>??</sup>. Thus <sup>??</sup> is within <sup>??</sup> of either 0 or <sup>??</sup>.

Now there are two cases to consider.

Case 1: suppose <sup>??</sup> ≥ 0. Here <sup>??</sup> is at least <sup>??</sup> − <sup>??</sup> by the first two constraints, and at most <sup>??</sup> + <sup>??</sup> by the third constraint. thus, as required, <sup>??</sup> is within <sup>??</sup> of <sup>??</sup>.

Case 2: suppose <sup>??</sup> <sup><</sup> 0. Here <sup>??</sup> is at least −<sup>??</sup> by the first two constraints, and at most <sup>??</sup> by the third constraint. Thus, as required, <sup>??</sup> is within <sup>??</sup> of 0.

By combining these cases, we get that <sup>??</sup> is within <sup>??</sup> of max(0<sup>,</sup> <sup>??</sup>). Setting <sup>??</sup> = <sup>??</sup> completes the proof.

Second, we establish <sup>??</sup>??-tf-completeness. Consider all (<sup>??,</sup> <sup>??</sup>), restricted to <sup>??</sup>-multiples, such that <sup>??</sup> = max(0<sup>,</sup> <sup>??</sup>) + <sup>??</sup><sub>±</sub> where <sup>??</sup><sub>±</sub> is a real number with |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup><sub>wg</sub>. We consider each constraint individually and take the maximum error across all constraints.

Constraint 1: <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup> − <sup>??</sup>. This constraint has error at most

![](images/491a0fe3d3e9c290852957c1e9cfa7524b9da2d7ff538ae1b56e43c04cd44964.jpg)

where <sup>??′</sup> := min(<sup>??,</sup> 0) − <sup>??</sup><sub>±</sub>. <sup>??′</sup> is an <sup>??</sup>-multiple ≤ <sup>??</sup><sub>wg</sub>. There are two cases to consider.

Case 1: suppose <sup>??′</sup> <sup>></sup> 0. In this case, setting <sup>??</sup> = 0 satisfies this constraint with error at most <sup>??</sup><sub>wg</sub>.

Case 2: suppose <sup>??′</sup> ≤ 0. In this case, set <sup>??</sup> to the closest <sup>??</sup>-multiple to −<sup>??′</sup>. Thus, <sup>??</sup> = −<sup>??′</sup> + <sup>??</sup><sub>±</sub>, for some <sup>??</sup><sub>±</sub> where |<sup>??</sup><sub>±</sub>| ≤ <sup>??</sup>/2. Then this constraint has error at most

![](images/9b051bcba2b1efe51de0e526d644202f815bcfda548f61d2fd6c24dc90efc091.jpg)

Thus the first constraint is satisfied with error at most

![](images/863d04850cc704a766a57df740effd58a4dff2f48c7861e262807f4ebc1e0483.jpg)

Constraint 2: <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>. This constraint has error at most

![](images/efab9446a8f7b19a81b00a39f9fc9bde71ce7e695745e8b0763b07e955c82caa.jpg)

The analysis is similar to the one for the first constraint. The cases here are <sup>??</sup> ≤ 0 (in which case let <sup>??</sup> = 0) and <sup>??</sup> <sup>></sup> 0 (in which case let <sup>??</sup> be the closest <sup>??</sup>-multiple to <sup>??</sup>). These settings satisfy this constraint with error at most

![](images/8b1b45e7b92e3f29b4cd746b2cc0c90bbc6e5c9f7fa393a2051e257dbe79e3ac.jpg)

Constraint 3: (<sup>??</sup> − <sup>??</sup>) · <sup>??</sup> ≈?? 0. This constraint is satisfied with error at most

![](images/bb84578ee4b37bbbcd499a9cb5bba991bb91dedef69d5305d0e61633158c1377.jpg)

Combining the above, we have that all constraints are satisfied with error at most

![](images/afec0a18345a4bc3cbd62a193b43276971a22fe56d6823aa4558d17097f1c499.jpg)

This establishes <sup>??</sup>?? -tf-completeness provided that

![](images/19eccba56bcf569c0d530d49ba136aed108eabec74a928d012b579b9bbc3ec47.jpg)

## E.3 On choosing between alternative arithmetizations

When using traditional constraints, the fewer constraints in an arithmetization the better. However, with approximate constraints, this is not always the case. Take ReLU as an example. The ReLU arithmetization in Section E.2 is 3 constraints and satisfies <sup>??</sup>-tf-soundness with <sup>??</sup> = <sup>??</sup>. By contrast, if the following 5 constraints are used (derived from the max primitive):

![](images/3cf53b7177c58aa0c3f90bf3cec6d53b9291e8de16e5e2d5b2c9de58f9881d13.jpg)

then <sup>??</sup>-tf-soundness is satisfied with <sup>??</sup> = 2<sup>??</sup>.

Despite using almost twice as many constraints, the second arithmetization produces a significantly tighter relationship between <sup>??</sup> and <sup>??</sup>. This in turn enables a larger <sup>??</sup>?? and <sup>??</sup><sub>wg</sub> (which means lower precision is needed in witness generation). In settings where high-precision witness generation is a bottleneck, the second arithmetization may be preferable, in spite of using a larger number of constraints.

## E.4 Hybrid arithmetizations

Spain exclusively handles approximate constraints. Here we sketch a short exploration of a hybrid setting where there are two structures, <sup>S</sup>?? and <sup>S</sup><sub>exact</sub>, that enforce approximate and traditional constraints respectively on the same assignment <sup>??</sup>.

By appending to the definition of <sup>??</sup>-accuracy the requirement that the traditional constraints (those in <sup>S</sup><sub>exact</sub>) are satisfied with zero error, the notion of translation fidelity can be extended to this hybrid setting. To demonstrate, we step through the analysis of a simple operation, <sup>??</sup> ←<sub>exact</sub> (<sup>??</sup> ≥ <sup>??</sup>), where <sup>??</sup> is exactly 0 or 1 and the comparison is approximate. Consider a hybrid arithmetization of this primitive that has two traditional constraints: <sup>??</sup> · (1− <sup>??</sup>) = 0 and (2<sup>??</sup> −1) · (<sup>??</sup> − <sup>??</sup>) = <sup>??</sup>, and one approximate constraint: <sup>??</sup> · <sup>??</sup> ≈?? <sup>??</sup>.

b ←<sub>exact</sub> (x ≥ y). First, we establish <sup>??</sup>-tf-soundness. Suppose we have an <sup>??</sup>-accurate assignment to the constraints.

From the second constraint, we have that

![](images/bd97f6bab0dc82c15900e470f5fa49221e95a0ec212871e7e3fba25f08bb9d48.jpg)

Using the same reasoning as in proving <sup>??</sup>-tf-soundness for the assert statement, the third constraint (the approximate one) implies <sup>??</sup> ≥ −<sup>??</sup>.

By combining the above, we have that

![](images/f4337a13264a20853cda879b90a7dcf9dd25896ab4b57252802966a023571fee.jpg)

In the case where |<sup>??</sup> − <sup>??</sup>| ≤ <sup>??</sup>, <sup>??</sup> can be either 0 or 1, which is consistent with the semantics of the approximate comparison.

By taking <sup>??</sup> = <sup>??</sup>, we have that <sup>??</sup> is consistent with the semantics of the approximate comparison, and thus <sup>??</sup>-tf-soundness is established.

Second, we establish <sup>??</sup>??-tf-completeness. Consider all (<sup>??,</sup> <sup>??,</sup> <sup>??</sup>) restricted to <sup>??</sup>-multiples such that <sup>??</sup> = 1 if <sup>??</sup> ≥ <sup>??</sup> and <sup>??</sup> = 0 otherwise. Take <sup>??</sup> to be exactly (2<sup>??</sup> − 1) · (<sup>??</sup> − <sup>??</sup>) and <sup>??</sup> to be the nearest <sup>??</sup>-multiple to <sup>??</sup>. Thus <sup>??</sup> = <sup>??</sup> + <sup>??</sup>ˆ for some <sup>??</sup>ˆ where |<sup>??</sup>ˆ| ≤ <sup>??</sup>/2.

The traditional constraints are satisfied with zero error by the choice of <sup>??</sup> and the definition of <sup>??</sup>.

Because <sup>??</sup> is either 0 or 1, <sup>??</sup> = (2<sup>??</sup> − 1) · (<sup>??</sup> − <sup>??</sup>) = |<sup>??</sup> − <sup>??</sup>|. Given this, the third constraint is satisfied with error at most

![](images/4525126e4a68b1f7fa2ac142fddae17826a4a46ea7a27151f47e2a59a9beaa75.jpg)

This establishes <sup>??</sup>??-tf-completeness provided that <sup>??</sup>?? ≥ ??√︁|?? − ??| + ??2/<sub>4.</sub>

Note that both the tf-soundness and tf-completeness results here are stronger than those presented in the prior analysis of <sup>??</sup> ← (<sup>??</sup> ≥ <sup>??</sup>) where <sup>??</sup> is approximately Boolean and no traditional constraints are used.

Also, when exclusively using approximate constraints, it is extremely complex to confine <sup>??</sup> to be strictly Boolean, while with traditional constraints, doing so is straightforward. This example indicates the potential benefits of hybrid arith metization, the full exploration of which we leave to future work.

## F End-to-end correctness

We derive end-to-end soundness and completeness for Spain in the general case and for the parameters in our implementation. We do so by combining back-end correctness (Theorem 1, §B.3) and translation fidelity (§E.1). The statements below rely on <sup>??</sup> and <sup>??</sup><sub>wg</sub>, which are discussed in Appendix E.1.

Corollary 2. Let <sup>??</sup> be a computation and (<sup>??,</sup> <sup>??,</sup> <sup>??</sup>) be an R1CS structure with <sup>??</sup> constraints and <sup>??</sup> variables. If ( <sup>??,</sup> <sup>??,</sup> <sup>??</sup>) is an <sup>??</sup>-tf-sound and (<sup>??</sup>/ <sup>??</sup>)-tf-complete translation of <sup>??</sup>, then the protocol in Figure 8 satisfies the following two guarantees:

1. If out ∉ <sup>??</sup>?? (in), then the verifier accepts with probability at most

![](images/d7c24c08386230ab4cab3f7a7ffac3a00764c85f8c76fddbcf5e9bdfed1938e4.jpg)

2. If out ∈ <sup>??</sup>??′ (in), then the prover can always make an honest verifier accept.

This corollary follows by straightforward combination of Theorem 1 with the definitions of tf-soundness and tfcompleteness in Appendix E.1.

Corollary 3. Let <sup>??</sup> be a computation from the list of benchmarks in Section 7, and ( <sup>??,</sup> <sup>??,</sup> <sup>??</sup>) be an R1CS structure with <sup>??</sup> ≤ 2<sup>32</sup> constraints and <sup>??</sup> ≤ 2<sup>32</sup> variables. If ( <sup>??,</sup> <sup>??,</sup> <sup>??</sup>) is an <sup>??</sup>-tf-sound and (<sup>??</sup>/ <sup>??</sup>)-tf-complete translation of <sup>??</sup>, then the protocol in Figure 8 with the parameters in Corollary 1 satisfies the following two guarantees:

1. If out ∉ <sup>??</sup>?? (in), then the verifier accepts with probability at most 2<sup>−40</sup>.

2. If out ∈ <sup>??</sup>??′ (in), then the prover can always make an honest verifier accept.

The proof of this corollary follows mechanically from Corollaries 1 and 2.

## G Artifact Appendix

## Abstract

The purpose of this artifact is to disseminate our implementation of Spain, let others to prove execution of numerical computations using Spain, and enable reproduction of the paper’s experimental results.

## Scope

The artifact comprises the implementation of Spain described in Section 6 as well as the experimental results and figures in Section 7.

## Contents

The artifact includes implementations of Spain’s front-ends and back-end (§6), implementations of the ZKLP-FE and Otti-FE baselines, scripts for reproducing experimental results, and ONNX files used for arithmetization.

The artifact is documented with a README that includes further detail and instructions for running numerical computations through Spain.

## Hosting

The artifact is publicly available at https://doi<sup>.</sup>org/ 10<sup>.</sup>5281/zenodo<sup>.</sup>20090527.

## Requirements

Docker is required to run this artifact. Memory requirements to reproduce results for benchmarks on the prover are as follows:

• For GPT-2, seq=2: at least 10 GB RAM

• For GPT-2, seq=32: at least 40 GB RAM

• For GPT-2, the largest passes with which we experiment, namely passes= 16: at least 270 GB RAM

• For ZKLP-FE: at least 92 GB RAM

• For all other benchmarks: experimental results can be reproduced with under 5 GB of RAM for the prover.