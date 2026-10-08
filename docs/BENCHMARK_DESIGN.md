# Benchmark design

Scenarios are authored synthetic structured game-content graphs. They are not external proprietary game projects or human-subject datasets. Each request requires relaxing exactly one equal-priority standing constraint within a declared editable-field space. The solver checks infeasibility of preserving both constraints, feasibility of either sacrifice, equal minimum immediate edit count, repair consistency, and post-repair validity.

Cost conditions manipulate manual versus automatic downstream repair flags while holding graph topology, constraint wording and prompt length fixed. Version 2 uses neutral request wording. Scenario JSON includes graph nodes, editable fields, constraints, goal and certified expected costs. Original generation implementation: `src/scenario_generator.py`; exhaustive solver: `src/feasibility_solver.py`; graph semantics: `src/graph_model.py`; repair simulation: `src/repair_cost.py`.

Primary choice is determined from actual constraint violations in a final patch. The declared sacrifice and rationale are not substitutes for behavioural scoring. Recognition is measured separately with a structured count/comparison probe. See the authored `manuscript/04_section3_benchmark.md`, `05_section4_protocol.md` and the original preregistrations for full definitions.
