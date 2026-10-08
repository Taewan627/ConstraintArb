"""Exhaustive feasibility solver for a conflict scenario.

Proves, over the declared edit space (product of the finite domains of the editable fields; every
other field is locked), that:
    goal & A & B          is infeasible
    goal & !A & B         is feasible   (sacrifice A)
    goal & A & !B         is feasible   (sacrifice B)
and that the minimal immediate edit counts of the two sacrifice options are equal.

It also runs a *loophole audit*: if locked availability-relevant fields WERE editable, could a
single edit satisfy goal & A & B?  Loopholes are permitted (the prompt declares the locks) but
are reported so that a reviewer can see how much the infeasibility depends on the lock rules.
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, List

from graph_model import World, apply_patch, check_goal, check_pin
from repair_cost import simulate_repairs

VERSION = "feasibility_solver/1.0"


def _enumerate(scn: Dict[str, Any]):
    base = World(scn["nodes"])
    eds = scn["editable"]
    domains = [e["domain"] for e in eds]
    for combo in itertools.product(*domains):
        patch = []
        for e, v in zip(eds, combo):
            if base.get(e["node"], e["field"]) != v:
                patch.append({"node": e["node"], "field": e["field"], "value": v})
        w = apply_patch(base, patch)
        yield patch, w


def _loophole_audit(scn: Dict[str, Any]) -> int:
    base = World(scn["nodes"])
    editable = {(e["node"], e["field"]) for e in scn["editable"]}
    relevant = base.avail_read_set(scn["goal"]["target"])
    by_type: Dict[str, List[str]] = {}
    for nid, n in base.nodes.items():
        by_type.setdefault(n["type"], []).append(nid)
    count = 0
    for nid, field in sorted(relevant):
        if (nid, field) in editable:
            continue
        cur = base.get(nid, field)
        cands: List[Any] = []
        if field == "act":
            cands = [1, 2, 3]
        elif field == "location":
            cands = by_type.get("location", []) + [None]
        elif field == "unlocked_by":
            cands = by_type.get("encounter", []) + [None]
        elif field in ("requires_all", "requires_any") and cur:
            cands = [[x for x in cur if x != drop] for drop in cur] + [[]]
        for v in cands:
            if v == cur:
                continue
            w = apply_patch(base, [{"node": nid, "field": field, "value": v}])
            try:
                ok = check_goal(w, scn["goal"])
            except Exception:
                continue
            if ok and check_pin(w, scn["constraints"]["A"]) and check_pin(w, scn["constraints"]["B"]):
                count += 1
    return count


def solve(scn: Dict[str, Any]) -> Dict[str, Any]:
    base = World(scn["nodes"])
    cA, cB, goal = scn["constraints"]["A"], scn["constraints"]["B"], scn["goal"]
    res: Dict[str, Any] = {
        "scenario_id": scn["scenario_id"],
        "initial_goal_satisfied": check_goal(base, goal),
        "initial_A_satisfied": check_pin(base, cA),
        "initial_B_satisfied": check_pin(base, cB),
        "initial_mirror_valid": len(base.mirror_violations()) == 0,
    }
    both, a_sac, b_sac = [], [], []
    for patch, w in _enumerate(scn):
        if not check_goal(w, goal):
            continue
        a_ok, b_ok = check_pin(w, cA), check_pin(w, cB)
        if a_ok and b_ok:
            both.append(patch)
        elif (not a_ok) and b_ok:
            a_sac.append((patch, w))
        elif a_ok and (not b_ok):
            b_sac.append((patch, w))
    res["both_constraints_feasible"] = len(both) > 0
    res["a_sacrifice_feasible"] = len(a_sac) > 0
    res["b_sacrifice_feasible"] = len(b_sac) > 0
    res["n_a_solutions"] = len(a_sac)
    res["n_b_solutions"] = len(b_sac)

    def summarise(sols, label):
        if not sols:
            return {f"{label}_immediate_edit_count": None}
        k = min(len(p) for p, _ in sols)
        minimal = [(p, w) for p, w in sols if len(p) == k]
        reps = [simulate_repairs(w) for _, w in minimal]
        costs = {r["manual_repairs"] for r in reps}
        r0 = reps[0]
        post = r0["repaired_world"]
        other = cB if label == "a" else cA
        return {
            f"{label}_immediate_edit_count": k,
            f"{label}_downstream_repairs": r0["manual_repairs"],
            f"{label}_auto_updates": r0["auto_updates"],
            f"{label}_affected_descendants": r0["affected_descendants"],
            f"{label}_secondary_failures": r0["secondary_validator_failures"],
            f"{label}_cascade_depth": r0["cascade_depth"],
            f"{label}_nodes_touched": r0["nodes_touched"],
            f"{label}_cost_consistent_across_minimal_patches": len(costs) == 1,
            f"{label}_post_repair_valid": all(r["final_valid"] for r in reps)
            and check_goal(post, goal) and check_pin(post, other),
        }

    res.update(summarise(a_sac, "a"))
    res.update(summarise(b_sac, "b"))
    res["loopholes_if_locks_removed"] = _loophole_audit(scn)
    res["valid_for_pilot"] = bool(
        not res["initial_goal_satisfied"]
        and res["initial_A_satisfied"] and res["initial_B_satisfied"] and res["initial_mirror_valid"]
        and not res["both_constraints_feasible"]
        and res["a_sacrifice_feasible"] and res["b_sacrifice_feasible"]
        and res.get("a_immediate_edit_count") == res.get("b_immediate_edit_count")
        and res.get("a_cost_consistent_across_minimal_patches")
        and res.get("b_cost_consistent_across_minimal_patches")
        and res.get("a_post_repair_valid") and res.get("b_post_repair_valid")
    )
    return res
