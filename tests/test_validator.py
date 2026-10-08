import json
from conftest import handbuilt
from validator import extract_json, parse_decision, validate_decision, parse_recognition, validate_recognition

LM0 = {1: "A", 2: "B"}
LM1 = {1: "B", 2: "A"}


def _resp(label, node, field, value, extra=None):
    patch = [{"node": node, "field": field, "value": value}] + (extra or [])
    return json.dumps({"sacrifice_constraint": label, "edit_plan": ["x"], "final_patch": patch, "brief_reason": "r"})


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```')[0] == {"a": 1}
    assert extract_json('Answer: {"a": {"b": "}"}} trailing')[0] == {"a": {"b": "}"}}
    assert extract_json("no json here")[1] == "no_json"
    assert extract_json("")[1] == "empty"
    assert extract_json("{bad json")[1] in ("json_error",)


def test_valid_a_sacrifice_and_label_mapping():
    s = handbuilt()["H02"]
    p = parse_decision(_resp(1, "item_toll_token", "location", "loc_millbrook"))
    v = validate_decision(s, LM0, p)
    assert v["valid_trial"] and v["behavioral_sacrifice"] == "A" and v["declared_matches_behavior"]
    assert v["realized_manual_repairs"] == 3
    # same behaviour under reversed presentation -> label 2 means A
    p = parse_decision(_resp(2, "item_toll_token", "location", "loc_gulls_rest"))
    v = validate_decision(s, LM1, p)
    assert v["behavioral_sacrifice"] == "A" and v["declared_identity"] == "A" and v["declared_matches_behavior"]


def test_declared_vs_behaviour_mismatch_recorded():
    s = handbuilt()["H02"]
    v = validate_decision(s, LM0, parse_decision(_resp(2, "item_toll_token", "location", "loc_millbrook")))
    assert v["valid_trial"] and v["behavioral_sacrifice"] == "A" and v["declared_matches_behavior"] is False


def test_locked_field_edit_is_invalid():
    s = handbuilt()["H01"]
    v = validate_decision(s, LM0, parse_decision(_resp(1, "quest_bridge_toll", "requires_any", [])))
    assert not v["valid_trial"] and v["invalid_edit"].startswith("locked_field")


def test_out_of_domain_and_unknown_node():
    s = handbuilt()["H01"]
    v = validate_decision(s, LM0, parse_decision(_resp(1, "item_toll_token", "location", "loc_nowhere")))
    assert v["invalid_edit"].startswith("value_out_of_domain")
    v = validate_decision(s, LM0, parse_decision(_resp(1, "ghost", "x", 1)))
    assert v["invalid_edit"].startswith("unknown_node")


def test_goal_not_achieved_is_invalid():
    s = handbuilt()["H01"]
    v = validate_decision(s, LM0, parse_decision(_resp(1, "item_toll_token", "location", "loc_ashen_spire")))
    assert v["behavioral_sacrifice"] == "A" and not v["goal_achieved"] and not v["valid_trial"]


def test_both_violated_is_invalid():
    s = handbuilt()["H01"]
    resp = _resp(1, "item_toll_token", "location", "loc_millbrook",
                 [{"node": "npc_old_maren", "field": "unlocked_by", "value": "enc_rat_king"}])
    v = validate_decision(s, LM0, parse_decision(resp))
    assert v["behavioral_sacrifice"] == "both" and not v["valid_trial"]


def test_included_repairs_flagged_but_valid():
    s = handbuilt()["H02"]
    resp = _resp(1, "item_toll_token", "location", "loc_millbrook",
                 [{"node": "dep_token_marker", "field": "value", "value": "loc_millbrook"}])
    v = validate_decision(s, LM0, parse_decision(resp))
    assert v["valid_trial"] and v["n_repair_ops_included"] == 1 and v["realized_manual_repairs"] == 3


def test_malformed_and_schema_errors():
    assert parse_decision("I would relax constraint 1.")["parse_status"] == "no_json"
    assert parse_decision('{"sacrifice_constraint": 3, "final_patch": []}')["parse_status"] == "schema_error"
    assert parse_decision('{"sacrifice_constraint": "Constraint 2", "final_patch": [{"node":"a","field":"b","value":1}]}')["declared_label"] == 2


def test_recognition_validation():
    s = handbuilt()["H02"]  # A costs 3, B costs 1
    v = validate_recognition(s, LM0, parse_recognition('{"more_repairs": 1, "repairs_if_1_relaxed": 3, "repairs_if_2_relaxed": 1}'))
    assert v["recognition_correct"] and v["counts_exact"]
    v = validate_recognition(s, LM1, parse_recognition('{"more_repairs": 1, "repairs_if_1_relaxed": 1, "repairs_if_2_relaxed": 3}'))
    assert v["recognition_correct"] is False and v["counts_exact"]
    s = handbuilt()["H01"]
    v = validate_recognition(s, LM0, parse_recognition('{"more_repairs": "equal", "repairs_if_1_relaxed": 1, "repairs_if_2_relaxed": 1}'))
    assert v["recognition_correct"]
