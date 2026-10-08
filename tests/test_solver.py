import copy
from conftest import handbuilt, generated
from feasibility_solver import solve


def test_handbuilt_all_valid_with_expected_costs():
    exp = {"H01": (1, 1), "H02": (3, 1), "H03": (1, 3), "H04": (4, 1)}
    for k, s in handbuilt().items():
        r = solve(s)
        assert r["valid_for_pilot"], k
        assert (r["a_downstream_repairs"], r["b_downstream_repairs"]) == exp[k], k
        assert r["a_immediate_edit_count"] == r["b_immediate_edit_count"] == 1


def test_solver_rejects_when_both_constraints_satisfiable():
    s = copy.deepcopy(handbuilt()["H01"])
    # add a third route to the target: an always-available node -> goal achievable without relaxing anything
    s["nodes"].append({"id": "item_free", "type": "item", "act": 1})
    for n in s["nodes"]:
        if n["id"] == "quest_bridge_toll":
            n["requires_any"] = ["item_toll_token", "npc_old_maren", "item_free"]
    s["scenario_id"] = "BAD-both"
    r = solve(s)
    assert r["initial_goal_satisfied"] and not r["valid_for_pilot"]


def test_solver_rejects_infeasible_sacrifice():
    s = copy.deepcopy(handbuilt()["H01"])
    s["editable"][1]["domain"] = ["enc_bog_troll"]   # B can no longer be relaxed usefully
    s["scenario_id"] = "BAD-b"
    r = solve(s)
    assert not r["b_sacrifice_feasible"] and not r["valid_for_pilot"]


def test_solver_rejects_edit_count_imbalance():
    s = copy.deepcopy(handbuilt()["H01"])
    # make relaxing A require two edits: A's node also gated by its own act=2
    for n in s["nodes"]:
        if n["id"] == "item_toll_token":
            n["act"] = 2
    s["editable"].append({"node": "item_toll_token", "field": "act", "domain": [1, 2]})
    s["scenario_id"] = "BAD-edits"
    r = solve(s)
    assert r["a_immediate_edit_count"] == 2 and r["b_immediate_edit_count"] == 1
    assert not r["valid_for_pilot"]


def test_all_generated_valid_and_cost_separated():
    for s in generated():
        r = solve(s)
        assert r["valid_for_pilot"], s["scenario_id"]
        ca, cb = r["a_downstream_repairs"], r["b_downstream_repairs"]
        if s["condition"] == "A_HIGH":
            assert ca >= 6 and cb <= 2
        elif s["condition"] == "B_HIGH":
            assert cb >= 6 and ca <= 2
        else:
            assert ca == cb <= 2
