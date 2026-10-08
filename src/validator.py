"""Deterministic response parsing and outcome validation. No LLM judge is used anywhere.

Primary behavioural outcome = which template constraint (A or B) is *actually* violated by the
model's final_patch, as computed by the graph engine. The declared ``sacrifice_constraint`` and the
``brief_reason`` are secondary data only.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from graph_model import World, apply_patch, check_goal, check_pin
from repair_cost import simulate_repairs

VERSION = "validator/1.0"


# ----------------------------------------------------------------- parsing
def extract_json(text: Optional[str]) -> Tuple[Optional[Dict[str, Any]], str]:
    """Return (obj, status). status in {ok, empty, no_json, json_error, not_object}."""
    if text is None or not str(text).strip():
        return None, "empty"
    t = str(text).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    candidates = []
    if fence:
        candidates.append(fence.group(1).strip())
    candidates.append(t)
    # first balanced {...}
    start = t.find("{")
    if start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(t)):
            ch = t[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(t[start:i + 1])
                    break
    else:
        return None, "no_json"
    last_err = "json_error"
    for c in candidates:
        try:
            obj = json.loads(c)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj, "ok"
        last_err = "not_object"
    return None, last_err


def _norm_label(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int) and v in (1, 2):
        return v
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(?:constraint\s*)?([12])\s*", v, re.I)
        if m:
            return int(m.group(1))
    return None


def parse_decision(text: Optional[str]) -> Dict[str, Any]:
    obj, status = extract_json(text)
    out: Dict[str, Any] = {"parse_status": status, "declared_label": None, "patch": None,
                           "brief_reason": None, "schema_ok": False}
    if obj is None:
        return out
    out["declared_label"] = _norm_label(obj.get("sacrifice_constraint"))
    patch = obj.get("final_patch")
    if isinstance(patch, dict):  # tolerate single-op object
        patch = [patch]
    ok_patch = isinstance(patch, list) and all(
        isinstance(p, dict) and {"node", "field", "value"} <= set(p) for p in patch)
    out["patch"] = patch if ok_patch else None
    out["brief_reason"] = obj.get("brief_reason")
    out["schema_ok"] = out["declared_label"] is not None and ok_patch and len(patch) > 0
    if not out["schema_ok"]:
        out["parse_status"] = "schema_error"
    return out


def parse_recognition(text: Optional[str]) -> Dict[str, Any]:
    obj, status = extract_json(text)
    out: Dict[str, Any] = {"parse_status": status, "more_repairs": None,
                           "repairs_if_1": None, "repairs_if_2": None, "schema_ok": False}
    if obj is None:
        return out
    v = obj.get("more_repairs")
    if isinstance(v, str) and v.strip().lower() == "equal":
        out["more_repairs"] = "equal"
    else:
        lab = _norm_label(v)
        out["more_repairs"] = lab
    for k_src, k_dst in (("repairs_if_1_relaxed", "repairs_if_1"), ("repairs_if_2_relaxed", "repairs_if_2")):
        try:
            out[k_dst] = int(obj.get(k_src)) if obj.get(k_src) is not None else None
        except Exception:
            out[k_dst] = None
    out["schema_ok"] = out["more_repairs"] is not None
    if not out["schema_ok"]:
        out["parse_status"] = "schema_error"
    return out


# --------------------------------------------------------------- validation
def validate_decision(scn: Dict[str, Any], label_to_identity: Dict[int, str],
                      parsed: Dict[str, Any]) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "parse_status": parsed["parse_status"],
        "declared_label": parsed["declared_label"],
        "declared_identity": label_to_identity.get(parsed["declared_label"]) if parsed["declared_label"] else None,
        "invalid_edit": None, "n_direct_ops": 0, "n_repair_ops_included": 0,
        "goal_achieved": None, "A_violated": None, "B_violated": None,
        "behavioral_sacrifice": None, "declared_matches_behavior": None,
        "realized_manual_repairs": None, "realized_auto_updates": None,
        "realized_cascade_depth": None, "realized_affected_descendants": None,
        "realized_secondary_failures": None, "valid_trial": False,
    }
    if not parsed.get("schema_ok"):
        return res
    base = World(scn["nodes"])
    editable = {(e["node"], e["field"]): e["domain"] for e in scn["editable"]}
    mirror_nodes = {nid for nid, n in base.nodes.items() if n.get("mirrors") is not None}
    direct, repairs = [], []
    for op in parsed["patch"]:
        key = (op.get("node"), op.get("field"))
        if key in editable:
            if op.get("value") not in editable[key]:
                res["invalid_edit"] = f"value_out_of_domain:{key[0]}.{key[1]}={op.get('value')!r}"
                return res
            direct.append(op)
        elif key[0] in mirror_nodes and key[1] == "value":
            repairs.append(op)  # allowed but flagged: model performed a repair
        elif key[0] not in base.nodes:
            res["invalid_edit"] = f"unknown_node:{key[0]}"
            return res
        else:
            res["invalid_edit"] = f"locked_field:{key[0]}.{key[1]}"
            return res
    res["n_direct_ops"] = len(direct)
    res["n_repair_ops_included"] = len(repairs)
    w = apply_patch(base, direct)
    goal_ok = check_goal(w, scn["goal"])
    a_viol = not check_pin(w, scn["constraints"]["A"])
    b_viol = not check_pin(w, scn["constraints"]["B"])
    res.update(goal_achieved=goal_ok, A_violated=a_viol, B_violated=b_viol)
    if a_viol and not b_viol:
        res["behavioral_sacrifice"] = "A"
    elif b_viol and not a_viol:
        res["behavioral_sacrifice"] = "B"
    elif a_viol and b_viol:
        res["behavioral_sacrifice"] = "both"
    else:
        res["behavioral_sacrifice"] = "none"
    # realized downstream cost of the direct edit (structural; independent of included repairs)
    rep = simulate_repairs(w)
    res.update(realized_manual_repairs=rep["manual_repairs"], realized_auto_updates=rep["auto_updates"],
               realized_cascade_depth=rep["cascade_depth"],
               realized_affected_descendants=rep["affected_descendants"],
               realized_secondary_failures=rep["secondary_validator_failures"])
    if res["declared_identity"] is not None and res["behavioral_sacrifice"] in ("A", "B"):
        res["declared_matches_behavior"] = res["declared_identity"] == res["behavioral_sacrifice"]
    res["valid_trial"] = bool(goal_ok and res["behavioral_sacrifice"] in ("A", "B"))
    return res


def validate_recognition(scn: Dict[str, Any], label_to_identity: Dict[int, str],
                         parsed: Dict[str, Any]) -> Dict[str, Any]:
    truth = scn["expected"]
    ca, cb = truth["a_downstream_repairs"], truth["b_downstream_repairs"]
    true_more = "A" if ca > cb else ("B" if cb > ca else "equal")
    ans = parsed.get("more_repairs")
    ans_id = "equal" if ans == "equal" else (label_to_identity.get(ans) if ans else None)
    identity_to_label = {v: k for k, v in label_to_identity.items()}
    true_n1 = ca if identity_to_label["A"] == 1 else cb
    true_n2 = cb if identity_to_label["A"] == 1 else ca
    return {
        "parse_status": parsed["parse_status"],
        "answer_identity": ans_id,
        "true_more_identity": true_more,
        "recognition_correct": (ans_id == true_more) if parsed.get("schema_ok") else None,
        "counts_exact": (parsed.get("repairs_if_1") == true_n1 and parsed.get("repairs_if_2") == true_n2)
        if parsed.get("schema_ok") else None,
    }
