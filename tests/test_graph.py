import pytest
from conftest import handbuilt
from graph_model import World, GraphError, apply_patch, check_goal, check_pin
from repair_cost import simulate_repairs


def test_availability_semantics():
    s = handbuilt()["H01"]
    w = World(s["nodes"])
    assert w.avail("loc_frost_cave") == 2
    assert w.avail("item_toll_token") == 2          # via location
    assert w.avail("npc_old_maren") == 2            # via unlocked_by encounter
    assert w.avail("quest_bridge_toll") == 2        # min over requires_any
    assert not check_goal(w, s["goal"])


def test_requires_any_takes_min_and_requires_all_takes_max():
    w = World([{"id": "a", "type": "x", "act": 1}, {"id": "b", "type": "x", "act": 3},
               {"id": "t", "type": "q", "requires_any": ["a", "b"]},
               {"id": "u", "type": "q", "requires_all": ["a", "b"]}])
    assert w.avail("t") == 1 and w.avail("u") == 3


def test_cycle_detected():
    w = World([{"id": "a", "type": "x", "location": "b"}, {"id": "b", "type": "x", "location": "a"}])
    with pytest.raises(GraphError):
        w.avail("a")


def test_duplicate_ids_rejected():
    with pytest.raises(GraphError):
        World([{"id": "a", "type": "x"}, {"id": "a", "type": "y"}])


def test_sacrifice_edit_achieves_goal_and_violates_only_that_constraint():
    s = handbuilt()["H02"]
    w = apply_patch(World(s["nodes"]), [{"node": "item_toll_token", "field": "location", "value": "loc_millbrook"}])
    assert check_goal(w, s["goal"])
    assert not check_pin(w, s["constraints"]["A"]) and check_pin(w, s["constraints"]["B"])


def test_repair_cost_manual_vs_engine():
    hb = handbuilt()
    edit_a = [{"node": "item_toll_token", "field": "location", "value": "loc_millbrook"}]
    r_eq = simulate_repairs(apply_patch(World(hb["H01"]["nodes"]), edit_a))
    r_hi = simulate_repairs(apply_patch(World(hb["H02"]["nodes"]), edit_a))
    assert r_eq["manual_repairs"] == 1 and r_eq["auto_updates"] == 2
    assert r_hi["manual_repairs"] == 3 and r_hi["auto_updates"] == 0
    # structure identical: same number of affected descendants regardless of cost condition
    assert r_eq["affected_descendants"] == r_hi["affected_descendants"] == 3
    assert r_eq["final_valid"] and r_hi["final_valid"]


def test_cascade_depth_tree():
    s = handbuilt()["H04"]
    w = apply_patch(World(s["nodes"]), [{"node": "item_storm_lens", "field": "act", "value": 1}])
    r = simulate_repairs(w)
    assert r["manual_repairs"] == 4 and r["cascade_depth"] == 2 and r["secondary_validator_failures"] == 2
