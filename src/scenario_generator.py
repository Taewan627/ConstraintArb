"""Generate matched conflict scenarios from 20 base templates.

Design (per template x name_set):
  * Target node T (locked) with requires_any [NA, NB]; T is available in Act 2; the local request
    asks for T to become completable in Act 1.
  * NA is pinned by Constraint A, NB by Constraint B. Changing the pinned field is the ONLY way to
    bring NA (resp. NB) into Act 1, so exactly one constraint must be relaxed (proved by the solver).
  * NA and NB each have exactly 8 mirror dependents, in identical shape ("fan": 8 direct;
    "tree": 4 direct each with 1 child). Dependency structure, node count and wording are IDENTICAL
    across cost conditions. Only the per-dependent ``update`` flag differs:
        "manual" -> hand repair (cost 1), "engine" -> regenerated automatically (cost 0)
  * Conditions:   EQUAL  : A low, B low
                  A_HIGH : A high (8 manual), B low
                  B_HIGH : A low,  B high (8 manual)
    Low = 1 manual dependent (fan) or 1 manual branch = 2 (tree).
Counterbalancing:
  * name_set 0/1 -> different entity names AND constraint wording polarity (0 positive, 1 negative)
  * presentation order (which constraint is shown as "Constraint 1") is handled in prompt_builder.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(__file__))
from feasibility_solver import solve  # noqa: E402

VERSION = "scenario_generator/1.0"
GEN_SEED = 20261005
CONDITIONS = ("EQUAL", "A_HIGH", "B_HIGH")
N_DEPENDENTS = 8
NEUTRAL_REQUEST = 'Playtest feedback: Act 1 ends too early. Make "{T}" completable in Act 1.'

# ------------------------------------------------------------------ name pools
POOLS: Dict[str, List[str]] = {
    "quest": ["The Lost Lantern", "Ashes of the Mill", "A Debt to the Tide", "The Silent Bellfry",
              "Roots Beneath Varn", "The Glass Pilgrim", "Smoke over Hollin", "The Warden's Oath",
              "Salt and Iron", "The Ninth Lock", "Embers in the Well", "The Crooked Ledger",
              "Wolves at Dunmere", "The Brass Choir", "Under the Weeping Arch", "The Ferryman's Coin"],
    "achievement": ["Pathfinder of the Vale", "Keeper of Small Fires", "Friend of the Marsh",
                    "Long Road Home", "First Light", "Unbroken Chain", "Tidecaller", "Mapmaker"],
    "objective": ["Signal the Watchtower", "Restore the Old Pump", "Escort the Courier",
                  "Light the Beacon Line", "Open the Granary", "Repair the Rope Bridge",
                  "Calm the Stampede", "Reach the Hermit's Hut"],
    "bounty": ["Bounty: The Gray Poacher", "Bounty: Rustfang", "Bounty: The Mire Witch",
               "Bounty: Captain Sorrel", "Bounty: The Ash Hound", "Bounty: Twin Jackals",
               "Bounty: The Lamplighter", "Bounty: Old Bitterroot"],
    "item": ["Ember Lantern", "Tide Compass", "Bone Whistle", "Iron Seal", "Moonwell Flask",
             "Rusted Key of Varn", "Glass Feather", "Pilgrim's Map", "Storm Lens", "Copper Bell",
             "Saltwood Charm", "Hollow Crown", "Ledger of Debts", "Ash Sigil", "Weaver's Spindle",
             "Frostglass Shard"],
    "npc": ["Old Maren", "Brother Tolve", "Captain Ysolde", "Wren the Tinker", "Hask the Ferryman",
            "Sister Calla", "Dorran Vey", "Mother Ilse", "Pell the Scout", "Quill the Archivist",
            "Garrow Stone", "Lady Seraphine", "Fenn Marsh", "Ottilie Crane", "Bram Holloway",
            "Nessa of the Reeds"],
    "route": ["Smugglers' Tunnel", "Cliffside Path", "Sunken Causeway", "Old Mine Shaft",
              "Rope Ferry Crossing", "Northern Pass", "Aqueduct Walk", "Root Bridge",
              "Lantern Road", "Tidal Steps", "Collapsed Viaduct", "Reedway Channel"],
    "vendor": ["Tinker's Stall", "Bone Market", "Salt Trader", "Herbalist's Cart", "Relic Broker",
               "Wandering Smith", "Lamp-Oil Seller", "Map Merchant", "Fishwife's Stand", "Rope Maker"],
    "companion": ["Ash the Hound", "Kestrel", "Brother Odo", "Mira Swift", "The Iron Golem",
                  "Tamsin Reed", "Old Gruff", "Lio the Squire", "Saffi", "Captain Rook"],
    "waypoint": ["Shrine of First Light", "Ferry Post", "Beacon Hill", "Wayshrine of Ash",
                 "Old Signal Stone", "Pilgrim's Rest", "Hermit's Bell", "Harbor Gate Stone"],
    "mount": ["Dun Marsh Pony", "Ironback Strider", "Reed Skiff", "Ash Stag", "Cliff Goat",
              "Saltwind Glider", "Bog Ox", "Lantern Moth"],
    "trainer": ["Swordmaster Hale", "Archery Coach Vin", "Alchemist Rennet", "Climbing Guide Oda",
                "Fishing Teacher Pim", "Lockpick Mentor Sly", "Rune Scribe Ada", "Rider Bess"],
    "recipe": ["Recipe: Ember Tonic", "Recipe: Saltbread", "Recipe: Frost Salve", "Recipe: Lamp Oil",
               "Recipe: Rope Glue", "Recipe: Iron Polish", "Recipe: Marsh Tea", "Recipe: Ash Ink"],
    "location": ["Millbrook Village", "Gull's Rest", "Ferrow Fields", "Tanner's Crossing",
                 "Briar Hollow", "Saltmere Docks", "Owl Ridge", "Cinder Quarry", "Frost Cave",
                 "Drowned Abbey", "Glasswood", "Bitter Marsh", "Ashen Spire", "Kingsfall Ruins",
                 "Thornwatch Keep", "Mirelight Bog", "Stonewake Hills", "Copper Coast", "Dunmere",
                 "Varn Hollow"],
    "encounter": ["Bandit Ambush", "Rat Swarm", "Bog Troll", "Bandit Chief Corvo",
                  "The Ash Wyrm", "Drowned Knight", "Frost Matron", "Iron Sentinel", "Marsh Hydra",
                  "Cinder Golem", "Warden of Thorns", "Tide Serpent", "Ghoul Packmaster", "The Hollow King"],
    "speaker": ["Innkeeper Bel", "Guard Tomas", "Child Pia", "Old Fisher Gil", "Priestess Anwen",
                "Merchant Royce", "Scout Ilka", "Blacksmith Doran", "Bard Lisel", "Hermit Oswin",
                "Stablehand Fay", "Archivist Jory"],
}

DEP_KINDS = [
    ("npc_dialogue", "{speaker}'s dialogue line about {E}"),
    ("quest_log", "Quest-log entry describing {E}"),
    ("map_marker", "World-map marker for {E}"),
    ("codex_entry", "Codex page on {E}"),
    ("loading_tip", "Loading-screen tip mentioning {E}"),
    ("tutorial_popup", "Tutorial pop-up about {E}"),
    ("achievement_text", "Achievement description referencing {E}"),
    ("vendor_line", "{speaker}'s shop line about {E}"),
    ("companion_bark", "Companion remark about {E}"),
    ("cutscene_cue", "Cutscene cue referencing {E}"),
]
CHILD_KINDS = [
    ("localization", "Localized text (DE) of: {P}"),
    ("voice_script", "Voice-over script for: {P}"),
    ("subtitle", "Subtitle track for: {P}"),
    ("localization", "Localized text (JA) of: {P}"),
]

CONSTRAINT_TEXT = {
    "location": ("{N} must remain located in {V}.", "Do not move {N} out of {V}."),
    "unlocked_by": ("{N} must remain locked until {V} has been defeated.",
                    "Do not make {N} available before {V} has been defeated."),
    "act": ("{N} must remain an Act {V} element.", "Do not move {N} out of Act {V}."),
}

# ------------------------------------------------------------------- templates
# (tid, target_type, a_type, a_kind, b_type, b_kind, shape, target_desc, request)
TEMPLATES = [
    ("T01", "quest", "item", "location", "npc", "unlocked_by", "fan",
     "Completed by recovering the {A} or by persuading {B} to open the flooded gate.",
     "Playtest feedback: Act 1 runs out of content too early. Make the quest \"{T}\" completable in Act 1."),
    ("T02", "quest", "npc", "location", "item", "act", "tree",
     "Completed by talking to {A} or by presenting the {B} at the chapel.",
     "The Act 1 story beat feels unresolved. Make the quest \"{T}\" completable in Act 1."),
    ("T03", "achievement", "route", "unlocked_by", "mount", "location", "fan",
     "Earned by travelling via the {A} or by riding the {B} across the valley.",
     "Early players never see this achievement. Make \"{T}\" earnable in Act 1."),
    ("T04", "objective", "vendor", "location", "trainer", "act", "tree",
     "Done by buying supplies from the {A} or by training with {B}.",
     "The Act 1 tutorial chain stalls here. Make the objective \"{T}\" completable in Act 1."),
    ("T05", "bounty", "companion", "unlocked_by", "item", "location", "fan",
     "Claimable with help from {A} or by using the {B} to track the target.",
     "Bounties feel absent early. Make \"{T}\" claimable in Act 1."),
    ("T06", "quest", "waypoint", "act", "npc", "location", "tree",
     "Completed by activating the {A} or by meeting {B}.",
     "Act 1 needs a stronger hook. Make the quest \"{T}\" completable in Act 1."),
    ("T07", "quest", "recipe", "act", "vendor", "unlocked_by", "fan",
     "Completed by crafting with the {A} or by trading at the {B}.",
     "The crafting tutorial should finish in Act 1. Make the quest \"{T}\" completable in Act 1."),
    ("T08", "objective", "route", "unlocked_by", "waypoint", "unlocked_by", "tree",
     "Done by crossing the {A} or by lighting the {B}.",
     "Players get stuck in Act 1 with no progress. Make the objective \"{T}\" completable in Act 1."),
    ("T09", "achievement", "item", "location", "item", "location", "fan",
     "Earned by collecting the {A} or the {B}.",
     "This achievement should introduce collecting in Act 1. Make \"{T}\" earnable in Act 1."),
    ("T10", "quest", "npc", "act", "companion", "act", "tree",
     "Completed by recruiting {A} or by travelling with {B}.",
     "The party system should appear in Act 1. Make the quest \"{T}\" completable in Act 1."),
    ("T11", "bounty", "trainer", "location", "route", "unlocked_by", "fan",
     "Claimable after training with {A} or by ambushing the target on the {B}.",
     "The combat loop needs an early reward. Make \"{T}\" claimable in Act 1."),
    ("T12", "quest", "mount", "unlocked_by", "recipe", "act", "tree",
     "Completed by taming the {A} or by brewing with the {B}.",
     "Act 1 pacing review asks for this quest earlier. Make \"{T}\" completable in Act 1."),
    ("T13", "objective", "npc", "unlocked_by", "item", "act", "fan",
     "Done by getting directions from {A} or by reading the {B}.",
     "The Act 1 map is confusing without this objective. Make \"{T}\" completable in Act 1."),
    ("T14", "achievement", "vendor", "unlocked_by", "companion", "location", "tree",
     "Earned by completing a trade at the {A} or by befriending {B}.",
     "Social systems should be visible in Act 1. Make \"{T}\" earnable in Act 1."),
    ("T15", "quest", "item", "act", "waypoint", "location", "fan",
     "Completed by attuning the {A} or by praying at the {B}.",
     "Narrative review: the Act 1 ending needs this payoff. Make the quest \"{T}\" completable in Act 1."),
    ("T16", "bounty", "npc", "location", "npc", "unlocked_by", "tree",
     "Claimable with intel from {A} or from {B}.",
     "Early-game bounty board is empty. Make \"{T}\" claimable in Act 1."),
    ("T17", "quest", "route", "act", "trainer", "unlocked_by", "fan",
     "Completed by scouting the {A} or by learning from {B}.",
     "Speedrun-safe pacing requires this quest in Act 1. Make \"{T}\" completable in Act 1."),
    ("T18", "objective", "companion", "location", "mount", "act", "tree",
     "Done with {A}'s help or by riding the {B}.",
     "Traversal should be introduced in Act 1. Make the objective \"{T}\" completable in Act 1."),
    ("T19", "achievement", "recipe", "unlocked_by", "npc", "act", "fan",
     "Earned by mastering the {A} or by earning {B}'s trust.",
     "Retention data shows players quit before this. Make \"{T}\" earnable in Act 1."),
    ("T20", "quest", "waypoint", "unlocked_by", "item", "location", "tree",
     "Completed by restoring the {A} or by returning the {B}.",
     "The Act 1 climax needs a clear resolution. Make the quest \"{T}\" completable in Act 1."),
]


def slug(s: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in s)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


class NameDraw:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.used: set = set()

    def draw(self, pool: str) -> str:
        cands = [n for n in POOLS[pool] if n not in self.used]
        n = self.rng.choice(cands)
        self.used.add(n)
        return n


def _low_manual_pattern(shape: str, rng: random.Random) -> List[bool]:
    """Return manual flags for the 8 dependents in the LOW condition."""
    flags = [False] * N_DEPENDENTS
    if shape == "fan":
        flags[rng.randrange(N_DEPENDENTS)] = True
    else:  # tree: dependents ordered [d0,c0,d1,c1,...]; one branch manual -> 2 repairs
        b = rng.randrange(N_DEPENDENTS // 2)
        flags[2 * b] = True
        flags[2 * b + 1] = True
    return flags


def build_scenario(tpl, name_set: int, condition: str, version: int = 1) -> Dict[str, Any]:
    tid, t_type, a_type, a_kind, b_type, b_kind, shape, t_desc, request = tpl
    rng = random.Random(f"{GEN_SEED}-{tid}-names-{name_set}")
    nd = NameDraw(rng)
    names = {
        "T": nd.draw(t_type), "A": nd.draw(a_type), "B": nd.draw(b_type),
        "L1a": nd.draw("location"), "L1b": nd.draw("location"), "L2a": nd.draw("location"),
        "L2b": nd.draw("location"), "L3": nd.draw("location"),
        "E1": nd.draw("encounter"), "E2a": nd.draw("encounter"), "E2b": nd.draw("encounter"),
        "E3": nd.draw("encounter"), "D1": nd.draw("quest"), "D2": nd.draw("quest"),
    }
    ids = {k: f"{('loc' if k.startswith('L') else 'enc' if k.startswith('E') else 'quest' if k.startswith('D') else {'T': t_type, 'A': a_type, 'B': b_type}[k])}_{slug(v)}"
           for k, v in names.items()}
    nodes: List[Dict[str, Any]] = []
    # context: locations & encounters
    for key, act in (("L1a", 1), ("L1b", 1), ("L2a", 2), ("L2b", 2), ("L3", 3)):
        nodes.append({"id": ids[key], "type": "location", "name": names[key], "act": act})
    for key, act, loc in (("E1", 1, "L1a"), ("E2a", 2, "L2a"), ("E2b", 2, "L2b"), ("E3", 3, "L3")):
        nodes.append({"id": ids[key], "type": "encounter", "name": names[key], "act": act,
                      "location": ids[loc]})
    nodes.append({"id": ids["D1"], "type": "quest", "name": names["D1"], "act": 2,
                  "location": ids["L2b"], "requires_all": [ids["E2b"]]})
    nodes.append({"id": ids["D2"], "type": "quest", "name": names["D2"], "act": 3,
                  "location": ids["L3"], "unlocked_by": ids["E3"]})

    def constrained_node(side: str, ntype: str, kind: str, home_loc: str, gate_enc: str):
        n = {"id": ids[side], "type": ntype, "name": names[side]}
        if kind == "location":
            n.update(act=1, location=ids["L2a"] if side == "A" else ids["L2b"])
            pin_val = n["location"]
            domain = [ids[k] for k in ("L1a", "L1b", "L2a", "L2b", "L3")]
            shown = names["L2a"] if side == "A" else names["L2b"]
        elif kind == "unlocked_by":
            n.update(act=1, location=ids[home_loc], unlocked_by=ids[gate_enc])
            pin_val = n["unlocked_by"]
            domain = [ids[k] for k in ("E1", "E2a", "E2b", "E3")]
            shown = names[gate_enc]
        elif kind == "act":
            n.update(act=2, location=ids[home_loc])
            pin_val = 2
            domain = [1, 2, 3]
            shown = "2"
        else:
            raise ValueError(kind)
        return n, pin_val, domain, shown

    nA, pinA, domA, shownA = constrained_node("A", a_type, a_kind, "L1a", "E2a")
    nB, pinB, domB, shownB = constrained_node("B", b_type, b_kind, "L1b", "E2b")
    target = {"id": ids["T"], "type": t_type, "name": names["T"], "act": 1, "location": ids["L1a"],
              "requires_any": [ids["A"], ids["B"]],
              "description": t_desc.format(A=names["A"], B=names["B"])}
    nodes = [target, nA, nB] + nodes

    # dependents ------------------------------------------------------------
    pattern_rng = random.Random(f"{GEN_SEED}-{tid}-pattern")
    low_flags = {"A": _low_manual_pattern(shape, pattern_rng), "B": _low_manual_pattern(shape, pattern_rng)}
    high_side = {"EQUAL": None, "A_HIGH": "A", "B_HIGH": "B"}[condition]
    dep_rng = random.Random(f"{GEN_SEED}-{tid}-deps-{name_set}")
    speakers = list(POOLS["speaker"])
    dep_rng.shuffle(speakers)
    for side, kind, pin_val in (("A", a_kind, pinA), ("B", b_kind, pinB)):
        flags = [True] * N_DEPENDENTS if high_side == side else low_flags[side]
        src = f"{ids[side]}.{kind}"
        kinds = list(DEP_KINDS)
        dep_rng.shuffle(kinds)
        ent = names[side]
        spk_i = 0 if side == "A" else 6
        if shape == "fan":
            for i in range(N_DEPENDENTS):
                k, fmt = kinds[i]
                nodes.append({"id": f"dep_{slug(ent)}_{i + 1}", "type": k,
                              "name": fmt.format(speaker=speakers[(spk_i := spk_i + 1) % len(speakers)], E=ent),
                              "mirrors": src, "value": pin_val,
                              "update": "manual" if flags[i] else "engine"})
        else:
            for b in range(N_DEPENDENTS // 2):
                k, fmt = kinds[b]
                pid = f"dep_{slug(ent)}_{b + 1}"
                pname = fmt.format(speaker=speakers[(spk_i := spk_i + 1) % len(speakers)], E=ent)
                nodes.append({"id": pid, "type": k, "name": pname, "mirrors": src, "value": pin_val,
                              "update": "manual" if flags[2 * b] else "engine"})
                ck, cfmt = CHILD_KINDS[b]
                nodes.append({"id": f"{pid}_{ck[:3]}", "type": ck, "name": cfmt.format(P=pname),
                              "mirrors": f"{pid}.value", "value": pin_val,
                              "update": "manual" if flags[2 * b + 1] else "engine"})

    pol = name_set % 2  # 0 positive, 1 negative wording
    cA = {"node": ids["A"], "field": a_kind, "op": "eq", "value": pinA, "kind": a_kind,
          "text": CONSTRAINT_TEXT[a_kind][pol].format(N=names["A"], V=shownA)}
    cB = {"node": ids["B"], "field": b_kind, "op": "eq", "value": pinB, "kind": b_kind,
          "text": CONSTRAINT_TEXT[b_kind][pol].format(N=names["B"], V=shownB)}
    scn = {
        "scenario_id": (f"S2-{tid}-{condition}-n{name_set}" if version == 2
                        else f"{tid}-{condition}-n{name_set}"),
        "template_id": tid, "condition": condition, "name_set": name_set, "polarity": "pos" if pol == 0 else "neg",
        "shape": shape, "a_kind": a_kind, "b_kind": b_kind, "a_type": a_type, "b_type": b_type,
        "generator_version": VERSION,
        "nodes": nodes,
        "goal": {"target": ids["T"], "max_act": 1},
        "constraints": {"A": cA, "B": cB},
        "editable": [{"node": ids["A"], "field": a_kind, "domain": domA},
                     {"node": ids["B"], "field": b_kind, "domain": domB}],
        "request_text": (NEUTRAL_REQUEST if version == 2 else request).format(T=names["T"]),
        "entity_names": names,
    }
    if version == 2:
        scn["scenario_version"] = 2
    return scn


def scenario_hash(scn: Dict[str, Any]) -> str:
    s = json.dumps({k: v for k, v in scn.items() if k != "expected"}, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


AUDIT_COLS = ["scenario_id", "template_id", "condition", "name_set", "shape", "a_kind", "b_kind",
              "both_constraints_feasible", "a_sacrifice_feasible", "b_sacrifice_feasible",
              "a_immediate_edit_count", "b_immediate_edit_count",
              "a_downstream_repairs", "b_downstream_repairs",
              "a_auto_updates", "b_auto_updates", "a_affected_descendants", "b_affected_descendants",
              "a_secondary_failures", "b_secondary_failures", "a_cascade_depth", "b_cascade_depth",
              "a_nodes_touched", "b_nodes_touched", "n_a_solutions", "n_b_solutions",
              "loopholes_if_locks_removed", "cost_design_ok", "valid_for_pilot", "scenario_hash"]


def cost_design_ok(scn, res) -> bool:
    ca, cb = res.get("a_downstream_repairs"), res.get("b_downstream_repairs")
    if ca is None or cb is None:
        return False
    low = (1, 2)
    c = scn["condition"]
    if c == "EQUAL":
        return ca in low and cb in low and ca == cb
    if c == "A_HIGH":
        return 6 <= ca <= 10 and cb in low
    if c == "B_HIGH":
        return 6 <= cb <= 10 and ca in low
    return False


def generate(out_dir: str, audit_csv: str, pairs_csv: str, version: int = 1) -> List[Dict[str, Any]]:
    os.makedirs(out_dir, exist_ok=True)
    rows, scns, pairs = [], [], []
    for tpl in TEMPLATES:
        for ns in (0, 1):
            ids = {}
            for cond in CONDITIONS:
                scn = build_scenario(tpl, ns, cond, version=version)
                res = solve(scn)
                ok = cost_design_ok(scn, res)
                res["cost_design_ok"] = ok
                res["valid_for_pilot"] = bool(res["valid_for_pilot"] and ok)
                scn["expected"] = {k: res.get(k) for k in (
                    "a_downstream_repairs", "b_downstream_repairs", "a_immediate_edit_count",
                    "b_immediate_edit_count", "a_cascade_depth", "b_cascade_depth", "valid_for_pilot")}
                scn["scenario_hash"] = scenario_hash(scn)
                res["scenario_hash"] = scn["scenario_hash"]
                for k in ("template_id", "condition", "name_set", "shape", "a_kind", "b_kind"):
                    res[k] = scn[k]
                rows.append(res)
                scns.append(scn)
                ids[cond] = scn["scenario_id"]
                with open(os.path.join(out_dir, scn["scenario_id"] + ".json"), "w", encoding="utf-8", newline="\n") as f:
                    json.dump(scn, f, indent=1, ensure_ascii=False)
            pairs.append({"template_id": tpl[0], "name_set": ns, **{f"sid_{c}": ids[c] for c in CONDITIONS}})
    with open(audit_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_COLS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # a matched pair is valid only if all three of its conditions are valid
    valid = {r["scenario_id"]: r["valid_for_pilot"] for r in rows}
    with open(pairs_csv, "w", newline="", encoding="utf-8") as f:
        fields = ["template_id", "name_set"] + [f"sid_{c}" for c in CONDITIONS] + ["all_valid"]
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for p in pairs:
            p["all_valid"] = all(valid[p[f"sid_{c}"]] for c in CONDITIONS)
            w.writerow(p)
    return scns


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--version", type=int, choices=(1, 2), default=1)
    ap.add_argument("--out", default=None)
    ap.add_argument("--audit", default=None)
    ap.add_argument("--pairs", default=None)
    a = ap.parse_args()
    if a.version == 1:
        out = a.out or os.path.join(root, "data", "scenarios", "generated")
        audit = a.audit or os.path.join(root, "analysis", "feasibility_audit.csv")
        pairs = a.pairs or os.path.join(root, "data", "matched_pairs", "matched_pairs.csv")
    else:
        out = a.out or os.path.join(root, "data", "scenarios", "v2")
        audit = a.audit or os.path.join(root, "analysis", "feasibility_audit_v2.csv")
        pairs = a.pairs or os.path.join(root, "data", "matched_pairs", "matched_pairs_v2.csv")
    s = generate(out, audit, pairs, version=a.version)
    print(f"generated {len(s)} scenarios")
