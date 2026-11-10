# THOX MeshStack Community Mesh: Opt-In User-Contributed Hardware for a Privacy-Centric Shared Computing and Capacity-Priced Distributed Inference Mesh

**Authors:** Craig Ross (Chief Executive Officer, THOX.ai LLC), Tommy Xaypanya (Chief Technology Officer and Co-Founder, THOX.ai LLC)

**Affiliation:** THOX.ai LLC

**Version:** Research Specification v0.1 (10 November 2026)

**Keywords:** MeshStack, distributed inference, privacy-preserving computing, capacity pricing, grant-gated KV cache, pipeline sharding, local-first AI, community mesh

## Abstract

The private household MeshStack specification (Ross and Xaypanya, 2026) enables a household to pool the memory of its own small devices through capacity-priced pipeline sharding, grant-gated parent-chained HMAC KV transfer, and lease-fenced device roles, with the coordinator remaining outside the payload path. That design is bounded by the aggregate capacity of devices under one administrative principal. This paper specifies an extension to a permissioned community mesh in which authenticated users opt in to contribute idle hardware. MeshStack subscribers then access the pooled capacity for models that exceed single-device or household limits, including private equivalents of cloud-scale inference. All mechanisms of the household design are preserved and scoped across principals: enrollment remains lease-fenced, admission fails closed under the two-domain capacity rule, KV and activation transfers remain grant-gated and principal-bound, and the coordinator receives only metadata. Plaintext never leaves devices the initiating principal owns or explicitly grants. The design differentiates from public collaborative systems such as Petals by remaining permissioned, authenticated, and fail-closed. No production community mesh is claimed; the contribution is a research specification and methodology that extends measured household mechanisms. External evidence is labeled as such. Evaluation reuses measured results from the household paper on host classes and proposes simulated and calculated protocols for community scale.

## 1. Introduction

Household MeshStack demonstrates that a small number of owner-controlled devices can be pooled without treating the home as a data center. The central limitation is scale: the largest model a household can place is bounded by its own aggregate usable memory and link capacity. Public cloud inference removes that bound at the cost of data residency, transport confidentiality, and execution confidentiality. A community of authenticated MeshStack subscribers and contributors can restore scale while retaining the household privacy invariants.

The contribution is a research specification for that extension. Users enroll compatible hardware (Thox devices or host computers carrying ThoxOS or a MeshStack runtime) under an authenticated principal. Capacity is advertised, lease-fenced, and priced. Subscribers route requests that cannot be satisfied locally or within their household mesh to the community pool. Pipeline stages are assembled from compatible contributor nodes under live grants. Whole-request routing remains the degenerate and preferred case when a single node holds a complete model. Optional private hosted routes require explicit consent and remain outside the private peer path.

The design is local-first. The coordinator is not in the payload path. Peers are authenticated before work is accepted. No cloud inference is required. These commitments, already public for the household product, are restated and extended to the multi-principal case.

## 2. Related Work

**Household MeshStack.** Ross and Xaypanya (2026) specify capacity-priced pipeline sharding with two-domain fail-closed admission, a parent-chained HMAC-keyed KV graph whose transfer is gated by both a cost model and a live authority path, and lease-fenced roles that preserve owner sovereignty under churn. Measured results on fleet host classes include lossless byte-split zstd compression of real GGUF KV at 1.17×–1.20× and parent-chained HMAC keying at 9.7 µs per 64-token chunk. A negative capacity result shows that a 27B-class model is unplaceable on three devices at the published 2/4/6 GB class floors under the stated placement rules. The coordinator is not in the payload path; the mesh is built on WireGuard-class transports. [Measured, household paper.]

**Public collaborative inference.** Petals (Borzunov et al., 2022, 2023) demonstrates that a public peer-to-peer swarm can host large models by assigning contiguous layer spans to volunteer servers and routing activations. External evidence reports interactive rates for BLOOM-176B on consumer GPUs. The public swarm exposes intermediate activations to peers, which the Petals documentation itself notes is unsuitable for confidential data; private swarms are recommended for sensitive workloads. SharedLLM and related coordinator-plus-mesh designs introduce trust registries and rate limiting but do not bind transfers to principal-scoped grants or crypto-shredding. IslandRun (2025) and DICOMPUTE (2026) address multi-objective orchestration and full-cost privacy models (residency, transport confidentiality, execution confidentiality, verifiable accounting) across personal, edge, and regional resources. These systems supply motivating evidence only; none is claimed as a THOX result.

**Differentiation.** The THOX community mesh is permissioned and account-bound. Enrollment produces an epoch-bearing lease. Transfers require a live, attenuable grant path. KV and activations remain principal-bound; mismatched model fingerprints or principals produce fail-closed rejection. The coordinator sees only metadata (capacity advertisements, block identifiers, token counts, load). Intermediate activations travel over authenticated, encrypted tunnels and are not recoverable by unauthorized peers. Capacity pricing and contribution credits replace pure volunteer economics. These properties are design requirements, not measured production claims.

## 3. System and Threat Model

A community mesh is the set of nodes enrolled under authenticated principals that have opted in to contribute or consume capacity. Nodes remain under the administrative control of their owners. Links may be LAN, tailnet, or wider-area, with the same variable, shared character as the household case. Churn is routine: an owner may drain, move, or power off a node at any time.

Threats include an honest-but-curious peer inside the community, a departed node that returns holding a stale lease, a stolen or compromised contributor device, a network observer, and a malicious subscriber attempting to reconstruct another principal’s state. The design assumes the coordinator is honest-but-curious for metadata only and is never placed in the payload path. No node is trusted with another principal’s plaintext unless an explicit, live grant authorizes it. Fail-closed is the default for admission, grant validation, and model-fingerprint mismatch.

## 4. Design

### 4.1 Enrollment and Lease-Fenced Roles

A contributor authenticates, advertises usable capacity (memory, thermal headroom, link class), and receives an epoch-bearing lease that grants an InferenceNode (or Anchor) role. The lease is scoped to the community pool and is revocable. Subscribers receive grant-issuance rights limited to their subscription tier. Roles and epochs are managed by the same secrets graph used in the household design, now with community scopes that isolate tenants.

### 4.2 Capacity Pricing and Two-Domain Admission

Admission remains the two-domain rule of the household specification: weights plus attention KV scaled by sequence length must fit usable memory, and workspace must fit the remaining budget. Partial admission fails closed. Capacity is priced. Contributors earn MeshCredits proportional to offered memory-time and completed work. Subscribers spend credits or subscription grants. Owner foreground work retains absolute priority (P0). Calculated capacity arithmetic from the household paper is reused; community-scale placement is simulated, not measured.

### 4.3 Pipeline Sharding and Whole-Request Routing

Contiguous layer ranges are assigned to stages. Activation tensors (one per token or micro-batch) cross stage boundaries over authenticated tunnels. Whole-request routing to a single node that already holds a complete model remains the preferred and degenerate case. Pipeline assembly occurs only when no single node can place the model under the admission rule. Stage servers already present in the private inference lineage supply the execution substrate. No tensor parallelism or expert parallelism is admitted for this generation.

### 4.4 Grant-Gated KV Graph and Secrets Graph

The KV cache remains a parent-chained, HMAC-keyed graph bound to an authenticated principal and an exact model fingerprint (weights, quant, tokenizer, RoPE, layout, engine). Cross-node transfer is gated by the PLACE cost model and by a live authority path in the grant DAG. Grants are attenuable and scoped. Consumption-time validation rejects stale epochs. Crypto-shredding deletes a principal’s descendants on revocation or lease expiry. Community scopes prevent cross-principal reuse. Measured HMAC and compression costs from the household paper apply to each chunk; they are not re-measured here.

### 4.5 Privacy Commitments and Coordinator Placement

Four commitments are restated and extended:

- Plaintext stays on devices the initiating principal owns or has explicitly granted.
- The coordinator is not in the payload path; it receives neither model weights nor private inference payloads.
- Peers are authenticated before work is accepted.
- No cloud inference is required. Optional private hosted routes are separate, disclosed, and consented.

Data residency, transport confidentiality, and execution confidentiality are maintained by the combination of principal-bound keying, grant attenuation, and encrypted tunnels. Verifiable accounting is limited to the metadata the coordinator already holds and to local audit logs under owner control.

## 5. Implementation Notes

The specification builds on the household reference (Python lineage) and the private inference lineage (stage servers, pipeline planner). WireGuard-class transports supply the authenticated tunnels. No new production code is claimed. Clean-room adoption of external patterns (pipeline stage assignment, DHT-style discovery) is required; no external code is copied.

## 6. Evaluation Methodology

No community-mesh measurements exist. The following protocol is proposed:

- Reuse measured household results (KV compression 1.17×–1.20×, HMAC 9.7 µs/chunk, cross-host transfer overhead 0.196 s, two-host split at n=1) as the base cost model. Label these MEASURED (household, host class).
- Simulate placement and admission for community pools (example: 10–50 mixed 4–16 GB nodes) using the existing planner arithmetic. Label SIMULATED.
- Calculate capacity gains for models that the household paper showed unplaceable (e.g., 27B at class floors, 70B-class). Label CALCULATED.
- Privacy drills: grant revocation, lease expiry, and crypto-shredding on a multi-principal test harness. Label the drill results when obtained.
- No device-specific TTFT, hit-rate, quality, or energy numbers are claimed until measured on the stated host or device class under the cold/warm protocol.

## 7. Discussion and Limitations

The design inherits the household limitations: engine evidence is thin, codec scope is baseline, security side-channels remain unexamined, and control-plane ownership under wide-area churn is undecided. Community-specific limitations include free-riding, WAN latency and bandwidth, contributor churn at larger scale, and the absence of attested execution or differential privacy on intermediate activations. These are deferred until quality data, side-channel review, and freedom-to-operate analysis exist. KV remains a cache, not semantic memory. Public claims stay limited to what has been measured on host classes.

The negative capacity result of the household paper is the strongest argument for the extension: when household floors cannot place a useful model, a permissioned community pool is the remaining local-first path.

## 8. Conclusion

The household MeshStack specification pools devices under one principal. The community extension pools devices under many authenticated principals while preserving the same privacy invariants, fail-closed admission, grant-gated transfers, and lease fencing. The result is a research specification for private, capacity-priced distributed inference that lets MeshStack subscribers reach models larger than any single household can hold, without placing the coordinator in the payload path and without requiring traditional cloud inference. Implementation and measurement remain future work.

## References

Borzunov, A., et al. (2022). Petals: Collaborative Inference and Fine-tuning of Large Models. arXiv:2209.01188.

Borzunov, A., et al. (2023). Distributed inference and fine-tuning of large language models over the Internet. NeurIPS.

IslandRun (2025). Privacy-Aware Multi-Objective Orchestration for Distributed AI Inference. arXiv:2512.00595.

DICOMPUTE (2026). An Economic and Privacy-Aware Framework for Distributed Artificial Intelligence Inference. arXiv:2611.10804.

Ross, C., & Xaypanya, T. (2026). THOX MeshStack: Capacity-Priced Pipeline Sharding, Grant-Gated KV Transfer and Lease-Fenced Device Roles for a Private Household Mesh. THOX.ai Research technical report v1.1.0. DOI: 10.5281/zenodo.23969070.

## Reproducibility Statement

Measured numbers cited from the household paper are taken from that report and labeled with host class. Simulated and calculated results in this specification use the published planner arithmetic and admission rules. No new code or data are released with this research specification. A future implementation will publish the planner, grant-validation harness, and measurement scripts.

## Generative AI Assistance Disclosure

Synthetic agents assisted with literature search, outline synthesis, and drafting under the direction of the human authors. All technical claims, evidence labels, and design decisions were reviewed and remain the responsibility of Craig Ross and Tommy Xaypanya.

---

*End of research specification v0.1. Next actions: architecture diagram (household vs community), grant-DAG figure, capacity-placement table, LaTeX packaging for Zenodo/arXiv, HF Papers indexing under Thox-ai after DOI.*
# Capacity-Placement Table (Calculated from Household Planner Arithmetic)

Two-domain admission rule (fail-closed): weights \(W\) + attention KV \(\times\) sequence length \(T\) must fit usable memory \(R\); workspace must fit remaining budget. Values below are illustrative calculations based on published class floors and the 27B negative result from Ross and Xaypanya (2026). Label: CALCULATED. No device measurements claimed.

| Model Class | Approx. Weight Footprint (Q4) | Single-Node Min RAM | Household (3× devices @ 2/4/6 GB) | Community Pool Example (mixed 8–32 GB nodes) | Placement Mode |
|-------------|-------------------------------|---------------------|-----------------------------------|-----------------------------------------------|----------------|
| 4B dense | ~2.5 GB | 4 GB | Fits single P4/P6 | Fits any single node | Whole-request |
| 8B dense | ~5 GB | 8 GB | Fits single P6 or host | Fits single 8+ GB node | Whole-request |
| 27B dense | ~16–18 GB | 24 GB | Unplaceable (negative result) | 2 stages (e.g., 16 GB + 16 GB) | Pipeline |
| 32B dense | ~18–20 GB | 28 GB | Unplaceable | 2–3 stages | Pipeline |
| 70B dense | ~40 GB | 48–56 GB | Unplaceable | 3–4 stages (e.g., 16+16+16 GB) | Pipeline |
| 70B MoE (A3B) | ~20–24 GB active | 32 GB | Marginal / unplaceable | 2 stages | Pipeline or whole-request |

**Notes**
- Sequence length \(T = 4096\) assumed for KV estimate. Actual KV is measured at 65,536 B/token attention + fixed recurrent state for the 27B reference (household paper).
- Usable memory is less than advertised RAM (OS, runtime, headroom).
- Pipeline stage count is the minimum number of nodes whose contiguous layer ranges satisfy the two-domain rule.
- Owner foreground work retains absolute priority (P0) on any node.
- Credits: contributors earn MeshCredits proportional to memory-time offered; subscribers spend credits or subscription grants.

All numbers are CALCULATED from the published admission geometry and class floors. They are not measured community-mesh results.

## Figures

### Figure 1. Household Mesh vs Community Mesh Extension

![Architecture](fig1_architecture.png)

*Caption: Household Mesh (left) versus Community Mesh Extension (right). Solid green arrows are authenticated, grant-gated payload paths. Dashed arrows are control and metadata only. The coordinator remains outside the payload path in both cases. Subscriber (blue) and contributor (orange) nodes appear only in the community extension. Research specification.*

### Figure 2. Pipeline Sharding Across Community Nodes

![Pipeline](fig2_pipeline.png)

*Caption: Pipeline sharding places contiguous layer ranges on contributor stages. One activation tensor per token crosses each boundary. Whole-request routing remains the preferred degenerate case. CALCULATED from household admission geometry.*

### Figure 3. Grant DAG (Secrets Graph)



### TikZ Source Code (for LaTeX packaging)

The following TikZ code reproduces the three figures above. Brand green is defined as `#05A451`. It compiles with `pdflatex` (requires `tikz`, `positioning`, `arrows.meta`).

```latex
% Define colors in preamble
\definecolor{thoxgreen}{HTML}{05A451}
\definecolor{coordfill}{HTML}{E8F5E9}
\definecolor{subfill}{HTML}{E3F2FD}
\definecolor{contribfill}{HTML}{FFF3E0}
\definecolor{stagefill}{HTML}{FFF8E1}
\definecolor{attenfill}{HTML}{F3E5F5}

% Figure 1
\begin{figure}[htbp]
\centering
\begin{tikzpicture}[
  node distance=1.2cm and 1.5cm,
  every node/.style={font=\small},
  box/.style={draw, rounded corners=3pt, minimum height=1.1cm, minimum width=2.2cm, align=center, inner sep=3pt},
  coord/.style={box, fill=coordfill, draw=thoxgreen, line width=1.2pt},
  device/.style={box, fill=gray!10, draw=black!70},
  sub/.style={box, fill=subfill, draw=blue!70!black},
  contrib/.style={box, fill=contribfill, draw=orange!80!black},
  payload/.style={->, thoxgreen, line width=1.5pt, >=Stealth},
  control/.style={->, gray, dashed, line width=0.7pt, >=Stealth},
  scale=0.85
]
% (full content abbreviated in this note; see tikz_diagrams.tex for complete source)
\end{tikzpicture}
\caption{Household Mesh (left) versus Community Mesh Extension (right). ...}
\label{fig:architecture}
\end{figure}

% Figure 2 and Figure 3 similarly available in tikz_diagrams.tex
```

Full compilable source is in `tikz_diagrams.tex` (includes PDF build). All community elements are research specification only.


![Grant DAG](fig3_grant_dag.png)

*Caption: Grant DAG: principal-bound, attenuable grants with consumption-time validation and crypto-shredding on revocation. No cross-principal reuse. Model fingerprint must match exactly.*



## TikZ Source Code

The following TikZ code generates the three figures. It is verified to compile with pdflatex. Brand green is defined as #05A451.

```latex
% Requires:
% \usepackage{tikz}
% \usetikzlibrary{positioning,arrows.meta}
% \definecolor{thoxgreen}{HTML}{05A451}
% \definecolor{coordfill}{HTML}{E8F5E9}
% \definecolor{subfill}{HTML}{E3F2FD}
% \definecolor{contribfill}{HTML}{FFF3E0}
% \definecolor{grantfill}{HTML}{F3E5F5}
% \definecolor{consume}{HTML}{FFEBEE}

% Figure 1: Household vs Community Architecture
\begin{tikzpicture}[
  node distance=8mm,
  box/.style={draw, rounded corners=2pt, minimum height=12mm, minimum width=28mm, align=center, font=\small},
  coord/.style={box, fill=coordfill, draw=thoxgreen, thick},
  device/.style={box, fill=gray!10, draw=black},
  sub/.style={box, fill=subfill, draw=blue!70!black},
  contrib/.style={box, fill=contribfill, draw=orange!80!black},
  payload/.style={-{Stealth[length=3mm]}, draw=thoxgreen, thick},
  meta/.style={-{Stealth[length=2mm]}, draw=gray, dashed, thin},
  label/.style={font=\scriptsize, color=gray!80!black}
]
% Household scope and Community scope as in tikz_diagrams.tex
% (full source in companion file)
\end{tikzpicture}

% Figure 2: Pipeline Sharding
\begin{tikzpicture}[
  stage/.style={draw, rounded corners=2pt, fill=contribfill, draw=orange!80!black, 
                minimum height=22mm, minimum width=32mm, align=center, font=\small},
  act/.style={-{Stealth[length=3mm]}, draw=thoxgreen, thick}
]
\node[stage] (s1) {Stage 1\\Layers 0--12\\Contributor A};
\node[stage, right=of s1] (s2) {Stage 2\\Layers 13--24\\Contributor B};
\node[stage, right=of s2] (s3) {Stage 3\\Layers 25--36\\Contributor C};
\node[stage, right=of s3] (s4) {Stage 4\\Layers 37--48\\Contributor D};
\draw[act] (s1) -- (s2);
\draw[act] (s2) -- (s3);
\draw[act] (s3) -- (s4);
\end{tikzpicture}

% Figure 3: Grant DAG
\begin{tikzpicture}[
  box/.style={draw, rounded corners=2pt, minimum height=14mm, minimum width=32mm, align=center, font=\small},
  principal/.style={box, fill=subfill, draw=blue!70!black},
  root/.style={box, fill=coordfill, draw=thoxgreen},
  scope/.style={box, fill=contribfill, draw=orange!80!black},
  atten/.style={box, fill=grantfill, draw=purple!70!black},
  consume/.style={box, fill=consume, draw=red!70!black},
  arr/.style={-{Stealth[length=2.5mm]}, draw=black!80}
]
\node[principal] (p) {Principal\\(Subscriber)};
\node[root, right=of p] (r) {Root Grant\\(Lease Epoch)};
\node[scope, right=of r] (s) {Community\\Scope};
% ... remaining nodes and arrows as in tikz_diagrams.tex
\end{tikzpicture}
```

Full compilable source is in `tikz_diagrams.tex`. The PDF preview is `tikz_diagrams.pdf`.
