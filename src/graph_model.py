"""Minimal deterministic game-content graph DSL.

A scenario state is a list of nodes (dicts). Every node has an ``id`` and ``type``.

Availability semantics (used by the local goal):
    avail(n) = max( n.act (default 1),
                    avail(n.location)      if n has "location",
                    avail(n.unlocked_by)   if n has "unlocked_by",
                    max(avail(r) for r in n.requires_all),
                    min(avail(r) for r in n.requires_any) )
Location nodes carry their own ``act`` (the act in which they become reachable).

Mirror integrity (used for downstream repair cost):
    A node with ``mirrors = "<node_id>.<field>"`` must satisfy  node.value == resolve(mirrors).
    ``update`` is "engine" (regenerated automatically, cost 0) or "manual" (hand repair, cost 1).
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional, Tuple

GATE_REF_FIELDS = ("location", "unlocked_by")
VERSION = "graph_model/1.0"


class GraphError(Exception):
    pass


class World:
    def __init__(self, nodes: Iterable[Dict[str, Any]]):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        for n in nodes:
            if "id" not in n:
                raise GraphError("node without id")
            if n["id"] in self.nodes:
                raise GraphError(f"duplicate node id {n['id']}")
            self.nodes[n["id"]] = copy.deepcopy(n)

    # ------------------------------------------------------------------ basics
    def copy(self) -> "World":
        return World(self.nodes.values())

    def get(self, node_id: str, field: str) -> Any:
        if node_id not in self.nodes:
            raise GraphError(f"unknown node {node_id}")
        return self.nodes[node_id].get(field)

    def set(self, node_id: str, field: str, value: Any) -> None:
        if node_id not in self.nodes:
            raise GraphError(f"unknown node {node_id}")
        self.nodes[node_id][field] = value

    def resolve(self, ref: str) -> Any:
        node_id, field = ref.split(".", 1)
        return self.get(node_id, field)

    def to_list(self) -> List[Dict[str, Any]]:
        return [copy.deepcopy(n) for n in self.nodes.values()]

    # ------------------------------------------------------------ availability
    def avail(self, node_id: str, _stack: Optional[Tuple[str, ...]] = None) -> int:
        stack = _stack or ()
        if node_id in stack:
            raise GraphError(f"availability cycle through {node_id}")
        stack = stack + (node_id,)
        n = self.nodes.get(node_id)
        if n is None:
            raise GraphError(f"unknown node {node_id}")
        a = int(n.get("act", 1))
        for f in GATE_REF_FIELDS:
            ref = n.get(f)
            if ref:
                a = max(a, self.avail(ref, stack))
        req_all = n.get("requires_all") or []
        for r in req_all:
            a = max(a, self.avail(r, stack))
        req_any = n.get("requires_any") or []
        if req_any:
            a = max(a, min(self.avail(r, stack) for r in req_any))
        return a

    def avail_read_set(self, node_id: str) -> set:
        """All (node, field) pairs that can influence avail(node_id) (static over-approximation)."""
        out: set = set()
        seen: set = set()

        def visit(nid: str) -> None:
            if nid in seen:
                return
            seen.add(nid)
            n = self.nodes[nid]
            out.add((nid, "act"))
            for f in GATE_REF_FIELDS:
                out.add((nid, f))
                if n.get(f):
                    visit(n[f])
            for f in ("requires_all", "requires_any"):
                out.add((nid, f))
                for r in n.get(f) or []:
                    visit(r)

        visit(node_id)
        return out

    # --------------------------------------------------------------- integrity
    def mirror_violations(self) -> List[str]:
        """Node ids whose mirrored value is out of sync."""
        bad = []
        for nid, n in self.nodes.items():
            ref = n.get("mirrors")
            if ref is not None and n.get("value") != self.resolve(ref):
                bad.append(nid)
        return bad

    def dependents_of(self, ref: str) -> List[str]:
        return [nid for nid, n in self.nodes.items() if n.get("mirrors") == ref]

    def mirror_depth(self, node_id: str) -> int:
        """Depth of a mirror node below the first non-mirror source (1 = direct dependent)."""
        d = 0
        cur = node_id
        guard = 0
        while self.nodes[cur].get("mirrors") is not None:
            src = self.nodes[cur]["mirrors"].split(".", 1)[0]
            d += 1
            cur = src
            guard += 1
            if guard > 100:
                raise GraphError("mirror cycle")
        return d


# --------------------------------------------------------------- constraints
def check_pin(world: World, pin: Dict[str, Any]) -> bool:
    """A persistent constraint: (node, field, op, value)."""
    v = world.get(pin["node"], pin["field"])
    op = pin.get("op", "eq")
    if op == "eq":
        return v == pin["value"]
    if op == "ne":
        return v != pin["value"]
    if op == "le":
        return v is not None and v <= pin["value"]
    if op == "ge":
        return v is not None and v >= pin["value"]
    raise GraphError(f"unknown op {op}")


def check_goal(world: World, goal: Dict[str, Any]) -> bool:
    return world.avail(goal["target"]) <= int(goal["max_act"])


def apply_patch(world: World, patch: List[Dict[str, Any]]) -> World:
    w = world.copy()
    for op in patch:
        w.set(op["node"], op["field"], op["value"])
    return w
