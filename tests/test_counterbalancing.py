import collections
import re
from conftest import generated
from prompt_builder import build_prompt, label_map


def _strip_numbers(text):
    return re.sub(r"\"update\": \"(manual|engine)\"", "\"update\": \"X\"", re.sub(r"= \d+", "= N", text))


def test_three_conditions_per_template_nameset():
    c = collections.Counter((s["template_id"], s["name_set"]) for s in generated())
    assert len(c) == 40 and set(c.values()) == {3}


def test_conditions_differ_only_in_update_flags_and_report_numbers():
    groups = collections.defaultdict(dict)
    for s in generated():
        groups[(s["template_id"], s["name_set"])][s["condition"]] = s
    for key, g in groups.items():
        for order in (0, 1):
            texts = {c: build_prompt(g[c], order)["user"] for c in g}
            assert len({len(t) for t in texts.values()}) == 1, key            # identical length
            assert len({_strip_numbers(t) for t in texts.values()}) == 1, key  # identical modulo cost cues


def test_constraint_wording_identical_across_conditions():
    groups = collections.defaultdict(set)
    for s in generated():
        groups[(s["template_id"], s["name_set"])].add((s["constraints"]["A"]["text"], s["constraints"]["B"]["text"]))
    assert all(len(v) == 1 for v in groups.values())


def test_graph_structure_identical_across_conditions():
    groups = collections.defaultdict(set)
    for s in generated():
        struct = tuple(sorted((n["id"], n.get("mirrors")) for n in s["nodes"]))
        groups[(s["template_id"], s["name_set"])].add(struct)
    assert all(len(v) == 1 for v in groups.values())


def test_order_swaps_labels_and_listing():
    s = generated()[0]
    p0, p1 = build_prompt(s, 0), build_prompt(s, 1)
    assert label_map(0) == {1: "A", 2: "B"} and label_map(1) == {1: "B", 2: "A"}
    a_txt, b_txt = s["constraints"]["A"]["text"], s["constraints"]["B"]["text"]
    assert f"Constraint 1: {a_txt}" in p0["user"] and f"Constraint 1: {b_txt}" in p1["user"]
    assert p0["user"].index(s["constraints"]["A"]["node"] + "\"") < p0["user"].index(s["constraints"]["B"]["node"] + "\"")


def test_name_sets_differ_in_names_and_polarity():
    by = collections.defaultdict(dict)
    for s in generated():
        if s["condition"] == "EQUAL":
            by[s["template_id"]][s["name_set"]] = s
    for t, d in by.items():
        assert d[0]["entity_names"]["A"] != d[1]["entity_names"]["A"] or d[0]["entity_names"]["B"] != d[1]["entity_names"]["B"]
        assert d[0]["polarity"] == "pos" and d[1]["polarity"] == "neg"


def test_high_cost_side_balanced():
    c = collections.Counter(s["condition"] for s in generated())
    assert c["A_HIGH"] == c["B_HIGH"] == c["EQUAL"] == 40


def test_recognition_prompt_does_not_ask_for_decision():
    s = generated()[0]
    p = build_prompt(s, 0, task="recognition")["user"]
    assert "sacrifice_constraint" not in p and "more_repairs" in p


def test_graph_only_omits_report():
    s = generated()[0]
    assert "Dependency report" not in build_prompt(s, 0, info="graph_only")["user"]
    assert "Dependency report" in build_prompt(s, 0, info="explicit")["user"]
