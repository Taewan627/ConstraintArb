"""Deterministic downstream repair-cost simulation.

After the model's direct edit, mirror integrity may be broken. The repair procedure repeatedly
re-synchronises out-of-sync mirror nodes (breadth-first, deterministic id order):
  * update == "engine" -> regenerated automatically (counted, cost 0)
  * update == "manual" -> one manual repair operation (cost 1)
until the artifact is globally valid again. Primary metric: ``manual_repairs``.
"""
from __future__ import annotations

from typing import Any, Dict

from graph_model import World

VERSION = "repair_cost/1.0"


def simulate_repairs(world_after_edit: World, max_rounds: int = 100) -> Dict[str, Any]:
    w = world_after_edit.copy()
    initial_violations = w.mirror_violations()
    manual = 0
    auto = 0
    touched = set()
    max_depth = 0
    rounds = 0
    while True:
        bad = sorted(w.mirror_violations())
        if not bad:
            break
        rounds += 1
        if rounds > max_rounds:
            raise RuntimeError("repair did not converge")
        for nid in bad:
            n = w.nodes[nid]
            n["value"] = w.resolve(n["mirrors"])
            touched.add(nid)
            if n.get("update") == "engine":
                auto += 1
            else:
                manual += 1
            max_depth = max(max_depth, w.mirror_depth(nid))
    return {
        "manual_repairs": manual,
        "auto_updates": auto,
        "affected_descendants": len(touched),
        "secondary_validator_failures": len(initial_violations),
        "cascade_depth": max_depth,
        "nodes_touched": len(touched),
        "repair_rounds": rounds,
        "final_valid": len(w.mirror_violations()) == 0,
        "repaired_world": w,
    }
