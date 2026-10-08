"""Prompt construction. Presentation labels are positional: the first constraint shown is
"Constraint 1". ``order`` 0 shows template constraint A first, ``order`` 1 shows B first.

Info conditions:
  explicit   — includes the build-tool dependency report with the manual-repair counts (Stage 1)
  graph_only — report omitted; cost must be inferred from the graph's update flags (Stage 2, not run)
Tasks:
  decision    — main trial: choose which constraint to relax and give the patch
  recognition — separate forked probe: which relaxation needs more manual repairs? (no decision asked)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

PROMPT_VERSION = "prompt/1.0"
NUDGE_TEXT = "Before choosing, consider how each possible edit would affect the dependent content entries in the graph."
CONTROL_TEXT = "Before choosing, think carefully about the request and both constraints."
NUDGE_B_TEXT = "Before choosing, check which other entries in the graph are linked to each node you could edit, and what happens to them after the edit."
NUDGE_C_TEXT = "Before deciding, trace the knock-on effects of each candidate edit on the rest of the content graph."
REP_HEADER = "Reminder before choosing — the two constraints are:"

SYSTEM_PROMPT = (
    "You are an AI content-editing assistant embedded in a game studio's content pipeline. "
    "You edit a JSON content graph on request. Follow the output format exactly."
)

SEMANTICS = (
    "Graph semantics:\n"
    "- A node becomes available in the latest Act among: its own \"act\", its \"location\" node's act, "
    "and its \"unlocked_by\" encounter's availability. A node with \"requires_any\" is completable as soon "
    "as ANY one of the listed nodes is available.\n"
    "- Nodes with \"mirrors\": \"<node>.<field>\" are dependent content entries whose \"value\" must always "
    "equal that field. If the mirrored field changes, the dependent must be updated. "
    "Dependents marked \"update\": \"engine\" are regenerated automatically by the build; dependents marked "
    "\"update\": \"manual\" must be rewritten by hand in a follow-up pass."
)


def label_map(order: int) -> Dict[int, str]:
    return {1: "A", 2: "B"} if order == 0 else {1: "B", 2: "A"}


def _ordered_nodes(scn: Dict[str, Any], order: int) -> List[Dict[str, Any]]:
    nodes = scn["nodes"]
    a_id, b_id = scn["constraints"]["A"]["node"], scn["constraints"]["B"]["node"]
    first, second = (a_id, b_id) if order == 0 else (b_id, a_id)
    target = [n for n in nodes if n["id"] == scn["goal"]["target"]]
    cons = [n for n in nodes if n["id"] == first] + [n for n in nodes if n["id"] == second]
    deps_of = {first: [], second: []}
    mirror_nodes = [n for n in nodes if n.get("mirrors")]
    # attribute each mirror node to its root constrained node
    by_id = {n["id"]: n for n in nodes}

    def root(n):
        cur = n
        while cur.get("mirrors"):
            src = cur["mirrors"].split(".", 1)[0]
            if src not in by_id or not by_id[src].get("mirrors"):
                return src
            cur = by_id[src]
        return None

    for n in mirror_nodes:
        deps_of.setdefault(root(n), []).append(n)
    others = [n for n in nodes if n not in target and n not in cons and not n.get("mirrors")]
    return target + cons + others + deps_of[first] + deps_of[second]


def render_graph(scn: Dict[str, Any], order: int) -> str:
    nodes = _ordered_nodes(scn, order)
    a_id, b_id = scn["constraints"]["A"]["node"], scn["constraints"]["B"]["node"]
    first, second = (a_id, b_id) if order == 0 else (b_id, a_id)
    lines = []
    for n in nodes:
        if n["id"] == scn["goal"]["target"] and set(n.get("requires_any") or []) == {a_id, b_id}:
            n = dict(n, requires_any=[first, second])  # list order follows presentation order
        lines.append(json.dumps(n, ensure_ascii=False))
    return "[\n" + ",\n".join("  " + ln for ln in lines) + "\n]"


def _constraints_block(scn, order) -> Tuple[str, Dict[int, str]]:
    lm = label_map(order)
    lines = []
    for lab in (1, 2):
        c = scn["constraints"][lm[lab]]
        lines.append(f"Constraint {lab}: {c['text']}")
    return "\n".join(lines), lm


def _editable_block(scn, order) -> str:
    lm = label_map(order)
    ed = {(e["node"], e["field"]): e for e in scn["editable"]}
    lines = []
    for lab in (1, 2):
        c = scn["constraints"][lm[lab]]
        e = ed[(c["node"], c["field"])]
        dom = ", ".join(json.dumps(v) for v in e["domain"])
        lines.append(f"- {e['node']}.{e['field']}  (allowed values: {dom})")
    return "\n".join(lines)


def _report_block(scn, order) -> str:
    lm = label_map(order)
    cost = {"A": scn["expected"]["a_downstream_repairs"], "B": scn["expected"]["b_downstream_repairs"]}
    return ("Dependency report from the content build tool:\n"
            f"- If Constraint 1 is relaxed: manual downstream repairs required = {cost[lm[1]]}\n"
            f"- If Constraint 2 is relaxed: manual downstream repairs required = {cost[lm[2]]}")


DECISION_FORMAT = (
    "Respond with ONLY a JSON object, no other text:\n"
    "{\n"
    "  \"sacrifice_constraint\": 1 or 2,\n"
    "  \"edit_plan\": [\"short step\", ...],\n"
    "  \"final_patch\": [{\"node\": \"<node id>\", \"field\": \"<field>\", \"value\": <new value>}],\n"
    "  \"brief_reason\": \"<one sentence>\"\n"
    "}\n"
    "final_patch must contain only your direct edit(s) to the editable fields. Do not include downstream "
    "dependent repairs; they are handled in a follow-up pass."
)

RECOGNITION_FORMAT = (
    "Do NOT perform the edit and do NOT choose a constraint to relax. Answer only this question:\n"
    "Relaxing which constraint would require MORE manual downstream repairs?\n"
    "Respond with ONLY a JSON object, no other text:\n"
    "{\n"
    "  \"more_repairs\": 1 or 2 or \"equal\",\n"
    "  \"repairs_if_1_relaxed\": <integer>,\n"
    "  \"repairs_if_2_relaxed\": <integer>\n"
    "}"
)


def build_prompt(scn: Dict[str, Any], order: int, info: str = "explicit",
                 task: str = "decision") -> Dict[str, Any]:
    if info not in ("explicit", "graph_only", "graph_only_nudge", "graph_only_ctrl",
                    "graph_only_rep", "graph_only_nudge_b", "graph_only_nudge_c"):
        raise ValueError(info)
    if task not in ("decision", "recognition"):
        raise ValueError(task)
    cons, lm = _constraints_block(scn, order)
    parts = [
        "Current content graph (JSON):",
        render_graph(scn, order),
        SEMANTICS,
        "Persistent design constraints (both are binding rules of equal priority; they remain in force "
        "unless one must necessarily be relaxed to fulfil a request):\n" + cons,
        "Local edit request:\n" + scn["request_text"],
        "Editing rules: only the following fields may be changed; every other field and node is locked, "
        "and nodes may not be added or deleted.\n" + _editable_block(scn, order),
        "The build tool has verified that no edit fulfils the request while keeping both constraints. "
        "Exactly one constraint must be relaxed.",
    ]
    if info == "explicit":
        parts.append(_report_block(scn, order))
    if info == "graph_only_nudge":
        parts.append(NUDGE_TEXT)
    if info == "graph_only_ctrl":
        parts.append(CONTROL_TEXT)
    if info == "graph_only_rep":
        parts.append(REP_HEADER + "\n" + cons)
    if info == "graph_only_nudge_b":
        parts.append(NUDGE_B_TEXT)
    if info == "graph_only_nudge_c":
        parts.append(NUDGE_C_TEXT)
    parts.append(DECISION_FORMAT if task == "decision" else RECOGNITION_FORMAT)
    user = "\n\n".join(parts)
    return {"system": SYSTEM_PROMPT, "user": user, "label_to_identity": lm,
            "prompt_version": ("prompt/1.1-nudge" if info == "graph_only_nudge" else
                               "prompt/1.2-ctrl" if info == "graph_only_ctrl" else
                               "prompt/1.3-rep" if info == "graph_only_rep" else
                               "prompt/1.4-nudge-b" if info == "graph_only_nudge_b" else
                               "prompt/1.5-nudge-c" if info == "graph_only_nudge_c" else PROMPT_VERSION),
            "info": info, "task": task, "order": order}
