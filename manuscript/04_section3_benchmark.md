# Draft v0.1 — III. The ConstraintArb Benchmark (IEEE Access)

Scope: benchmark design only — no results or interpretation. Every design statement maps to code in `src/` (version strings in
brackets) or to the audit record. Numbers in this section describe the instrument, not model behaviour.

---

## III. THE CONSTRAINTARB BENCHMARK

ConstraintArb generates editing conflicts in which (i) relaxing exactly one of two constraints is provably necessary *within the
benchmark-declared edit space* (not as an unconditional property of the graph), (ii) both
relaxations require the same immediate edit, and (iii) the two relaxations differ only in the downstream repair work they cause.
Model responses are scored by deterministic code. Fig. 1 summarises the pipeline; this section specifies each component so that the
benchmark can be re-implemented from the text.

### A. Content-Graph Language
A scenario is a list of JSON nodes, each with a unique `id` and a `type` (quest, item, non-player character (NPC), location, encounter, dependent text
entries, and so on). Two semantics are defined [graph_model/1.0].

*Availability.* The act in which a node becomes available is

  avail(n) = max( act(n), avail(location(n)), avail(unlocked_by(n)), max_{r ∈ requires_all(n)} avail(r), min_{r ∈ requires_any(n)} avail(r) ),

where absent terms are omitted and act(n) defaults to 1. Locations carry their own act. Cycles are rejected.

*Mirror integrity.* A dependent node has a field `mirrors = "<node>.<field>"` and a `value` that must equal the mirrored field, and an
`update` flag: `engine` (regenerated automatically by the build) or `manual` (rewritten by hand). A dependent may mirror another
dependent, which creates two-level cascades. A graph is valid when no mirror is out of sync.

The prompt states both semantics verbatim, so all information needed to compute availability and repair work is visible to the model.

### B. Conflict Construction
Fig. 2 shows the existing T01 fan template, with both cost conditions preserving its topology.
Each scenario instantiates one of 20 templates (T01–T20). A target node T (a quest, objective, achievement, or bounty) has
`requires_any = [N_A, N_B]` and is initially available only in Act 2 because both N_A and N_B are. The edit request asks to make T
completable in Act 1 (goal: avail(T) ≤ 1).

N_A is gated to Act 2 by one field — its `location`, its `unlocked_by` encounter, or its own `act` — and Constraint A pins that field
to its current value (e.g., "Iron Seal must remain located in Kingsfall Ruins"). Constraint B pins the gating field of N_B in the same
way. Templates vary the node types and which kind of field is pinned (location, unlock, or act) for each side. The prompt declares
both constraints "binding rules of equal priority".

The *edit space* consists of exactly the two pinned fields, each with a finite domain (four or five candidate locations or encounters,
or acts {1, 2, 3}) that includes the current value and at least one Act-1 option. Every other field is declared locked, and nodes may
not be added or deleted.

### C. Solver Certification of a Forced Sacrifice
The forced sacrifice is a property of the declared edit space: only the two pinned fields may change, within their listed domains,
and all other fields are locked by rule. Within that space, an exhaustive solver [feasibility_solver/1.0] enumerates every assignment in the Cartesian product of the editable domains, applies
it, and evaluates the goal and both pins. A scenario is admitted only if all of the following hold:
1. initially, the goal is unmet, both constraints hold, and all mirrors are in sync;
2. no assignment satisfies goal ∧ A ∧ B (keeping both constraints is impossible);
3. some assignment satisfies goal ∧ ¬A ∧ B, and some satisfies goal ∧ A ∧ ¬B (either sacrifice suffices);
4. the minimal number of changed fields is equal for the two sacrifice options (Section III-D);
5. all minimal patches for a given option produce the same downstream repair cost, and the graph is valid after repair with the goal
   and the other constraint still satisfied.

Infeasibility therefore rests on the declared locks. An *out-of-space feasibility audit* counts how many single edits to locked,
availability-relevant fields (e.g., emptying `requires_any`, changing a location's act) would satisfy goal ∧ A ∧ B if the locks were
lifted; each scenario has 1–3 such out-of-space solutions. Because the prompt states the lock rule explicitly, any patch that touches a locked field is scored as an invalid
edit (Section III-H) rather than as a third option. All 120 generated scenarios (20 templates × 3 cost conditions × 2 name sets) and 4
hand-built scenarios passed certification; the per-scenario certificate is released as `feasibility_audit.csv`.

### D. Equal Immediate Edit Effort
In every template, setting the pinned field of N_A (or N_B) to an Act-1 value is sufficient to make T available in Act 1, so each
sacrifice requires exactly one field change; the solver confirms that the minimal immediate edit count is 1 for both options in all
admitted scenarios (criterion 4). The two options therefore require the same output schema and the same number and type of direct edits (one
field set to one value from a listed domain); actual generated text length is not controlled. Repairs to dependents are explicitly excluded from the
requested patch ("downstream dependent repairs are handled in a follow-up pass"), so the immediate task is identical for both choices.

### E. Manipulating Downstream Repair Cost Only
Each constrained node has exactly eight dependents mirroring its pinned field, in one of two shapes fixed by the template: *fan*
(eight direct dependents) or *tree* (four direct dependents, each mirrored by one child). Dependent types and display names (map
markers, dialogue lines, codex entries, quest-log text, tips, cut-scene cues) are drawn from fixed pools with seeded randomness.

Repair cost is defined by a deterministic simulation [repair_cost/1.0]: after an edit, out-of-sync dependents are re-synchronised in
breadth-first, id-sorted rounds until the graph is valid; each `manual` dependent touched costs 1 and each `engine` dependent costs 0.
The cost of a sacrifice is the manual-repair count of its minimal patch.

Only the `update` flags differ across the three cost conditions of a template:
- *Low* side: one `manual` dependent (fan) or one manual branch of two (tree); cost 1 or 2.
- *High* side: all eight dependents `manual`; cost 8.
- EQUAL: both sides low; A_HIGH: A high, B low; B_HIGH: A low, B high.
The positions of the low-cost manual dependents are seeded per template and reused across conditions. Consequently node count, edge
structure, dependency degree (eight per constrained node), cascade depth, wording, and prompt length are identical across the cost
conditions of a template; automated tests verify that prompts differ only in the `manual`/`engine` tokens (and, in the explicit
condition, the reported numbers). Manipulating cost through the number of dependents was rejected because it would confound cost with
node centrality and graph size.

The low-cost value differs between shapes (1 for fan, 2 for tree) but is fixed within a template. All cost contrasts are formed
within template — the A_HIGH and B_HIGH versions of the same template differ only in which side carries the eight manual dependents —
and inference is clustered by template (Section IV-E). Dependency shape is therefore part of the template, not an analysed experimental
variable.

### F. Prompt Conditions
Every prompt contains, in this order: a fixed system message; the graph (JSON, one node per line); the semantics of Section III-A; the
two constraints, labelled positionally as "Constraint 1" and "Constraint 2"; the edit request; the editing rules listing the two editable
fields and their domains; a statement that the build tool has verified that exactly one constraint must be relaxed; an optional
*condition paragraph*; and the response format. All conditions share every element except the condition paragraph ([Table: prompt conditions]):

| Condition | Condition paragraph |
|---|---|
| explicit | Build-tool report: manual downstream repairs required if Constraint 1 / Constraint 2 is relaxed (two integers) |
| graph-only | none — cost must be inferred from the `update` flags |
| restatement (REP) | "Reminder before choosing — the two constraints are:" followed by the same two constraint lines |
| generic deliberation (CTRL) | "Before choosing, think carefully about the request and both constraints." |
| dependent cue N1 | "Before choosing, consider how each possible edit would affect the dependent content entries in the graph." |
| dependent cue NB | "Before choosing, check which other entries in the graph are linked to each node you could edit, and what happens to them after the edit." |
| dependent cue NC | "Before deciding, trace the knock-on effects of each candidate edit on the rest of the content graph." |

No condition paragraph other than the explicit report mentions cost, repair, manual, engine, cheapness, or minimisation (test-enforced).
The decision format requests a JSON object with the sacrificed constraint label, a short edit plan, the final patch (direct edits only),
and a one-sentence reason. Two request wordings exist: the first study stage used template-specific request texts; all later stages use
one neutral text for every template ("Playtest feedback: Act 1 ends too early. Make "<T>" completable in Act 1."), with graphs otherwise
unchanged.

### G. Recognition Probe (Forked)
Recognition is measured in a separate application programming interface (API) call, never in the same conversation as the decision. The probe prompt is the decision prompt
of the same scenario, order, and information condition up to and including the condition paragraph; only the final block differs: the
model is told not to perform the edit or choose a constraint and is asked which relaxation would require more manual downstream repairs
(1, 2, or "equal") and how many for each. Because the two calls share no context, the probe cannot be influenced by the model's own
decision and vice versa. Ground truth comes from the solver certificate. The probe yields recognition accuracy on unequal-cost scenarios
and, secondarily, whether the reported counts are exact.

### H. Deterministic Validator
Scoring uses no LLM judge [validator/1.0]. The validator (1) extracts a JSON object (from a fenced block, the whole text, or the first balanced object) and checks the schema;
(2) classifies each patch operation as a direct edit (editable field, value within its domain), a repair of a dependent (accepted but
excluded from scoring and counted separately), or an invalid edit (locked field, unknown node, or out-of-domain value), any of which
makes the trial invalid; (3) applies the direct edits to the original graph and evaluates the goal and both pins with the graph engine.
The *behavioural sacrifice* is the template constraint (A or B) that the resulting graph actually violates; a trial is valid when the goal
is reached and exactly one constraint is violated. The model's declared label is mapped back from its positional label to A or B and
recorded only as a secondary variable (agreement with behaviour), as is the stated reason. Malformed responses receive at most two format
retries; network and rate-limit errors are retried separately at the transport level and are not counted as format failures. Every
attempt, including raw provider responses, is logged; raw logs are append-only.

### I. Counterbalancing
- *Presentation order.* Each scenario is shown in both orders. Labels are positional, so in order 0 Constraint 1 is template constraint A,
  and in order 1 it is B; the listing order of the two constrained nodes, their dependents, and the `requires_any` list follow the
  presentation order. This separates a preference for "Constraint 1" from a preference for A or B.
- *Name sets.* Two name sets assign different entity names and opposite wording polarity to the constraints (affirmative "… must remain located in …" vs prohibitive
  "Do not move … out of …"), separating effects of particular names or phrasing from cost.
- *Templates.* Twenty templates vary target type, constrained node types, pinned-field kinds, and dependency shape; inference is clustered
  by template (Section IV).
- *Execution.* Trial execution order is randomised with a recorded seed; per-attempt sampling seeds are derived deterministically from the
  trial identifier.
- *Known residual.* The target's description names the A-side node first in both orders; presentation order is therefore retained as a
  covariate.

### J. Harness Validation
Before empirical model queries, the harness was validated with test doubles ([Table: bias controls]):
- *Unit and confound tests* (31 at the first pre-registration freeze; 44 at the time of writing) cover the graph semantics, solver certificates, validator
  classification, and counterbalancing invariants (prompt identity across cost conditions apart from the manipulated tokens, identical
  structure and length, label mapping).
- *Parameter recovery.* The archived simulated cost-sensitive model output reports a true effect of 0.70 recovered as 0.75 [0.64, 0.86]; a noisy model
  (true 0.50, configured malformed-output probability 15% and invalid-edit probability 8%) was recovered as 0.56 [0.43, 0.68].
  The noisy model yielded 225 valid decisions out of 240; the corruption probabilities are per-attempt settings, not observed exclusion rates.
  These archived mock intervals reproduce with 400 template resamples and the recorded seed. This resample count is reconstructed,
  because the original analysis invocation was not archived; empirical-stage settings are specified separately in Section IV.
- *Null calibration.* The frozen pilot pre-registration reports thirty independent simulated cost-blind runs with a mean estimated
  effect of −0.004 (SD 0.081), and 95% interval coverage of zero in 29 of 30 runs. The aggregate is a historical validation record;
  individual calibration-run outputs were not located in the repository and were not independently recomputed for this manuscript.
- *Transport test.* A local fake API server exercised retries, rate limits, cost accounting, and absence of credential leakage.
Simulated runs are stored separately from empirical runs and provide harness-validation evidence only. The accompanying
mock-provenance audit documents the manuscript's correction from the unsupported historical prose interval to the archived JSON;
historical audits and stored evidence are preserved.

**[Table: bias controls] Biases addressed by design**

| Potential bias | Design control |
|---|---|
| Model could keep both constraints (no real trade-off) | Solver certifies goal ∧ A ∧ B infeasible within the declared edit space; locked-field edits are invalid; out-of-space solutions audited and reported |
| One option is easier to execute | Minimal immediate edit count certified equal (1 vs 1); repairs excluded from the patch |
| Cost confounded with centrality, graph size, or salience | Fixed eight dependents per side; only `update` flags vary; prompt identity tests |
| Positional or label preference | Both presentation orders; positional labels mapped back to A/B |
| Name or wording effects | Two name sets with opposite polarity; 20 templates |
| Self-report bias | Behavioural sacrifice computed from the patch; declared label secondary |
| Judge bias | Deterministic validator; no LLM judge |
| Recognition contaminated by the decision | Recognition measured in a separate, forked call |
| Pipeline artefacts producing spurious effects | Parameter recovery and null calibration with simulated models; append-only logs |
