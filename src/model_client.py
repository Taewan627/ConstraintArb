"""Provider-agnostic chat client (stdlib only).

Providers:
  openai_compat — any OpenAI-compatible /chat/completions endpoint (OpenAI, OpenRouter, DeepSeek, ...)
  anthropic     — Anthropic Messages API
  mock          — deterministic test doubles (never used for scientific results)

Secrets are read from environment variables (optionally loaded from a .env file); they are never
logged or written to run records.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

CLIENT_VERSION = "model_client/1.0"


def load_dotenv(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


class TransportError(Exception):
    pass


def _post(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise TransportError(f"HTTP {e.code}: {body}") from None
    except Exception as e:  # network / timeout
        raise TransportError(f"{type(e).__name__}: {e}") from None


class ModelClient:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.name = cfg["name"]
        self.provider = cfg["provider"]
        self.model = cfg.get("model")
        self.temperature = cfg.get("temperature")
        self.max_tokens = int(cfg.get("max_tokens", 2048))
        self.timeout = int(cfg.get("timeout", 180))
        self.transport_retries = int(cfg.get("transport_retries", 4))
        if self.provider in ("openai_compat", "anthropic"):
            key_env = cfg.get("api_key_env")
            if not key_env or not os.environ.get(key_env):
                raise RuntimeError(f"model {self.name}: missing API key env var {key_env!r}")
            self._key = os.environ[key_env]

    def available(self) -> bool:
        return True

    # ------------------------------------------------------------------ call
    def chat(self, system: str, user: str, seed: Optional[int] = None,
             meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return {text, usage:{input_tokens, output_tokens}, raw, transport_attempts, latency_s}."""
        t0 = time.time()
        if self.provider == "mock":
            out = _mock_response(self.cfg, user, seed, meta or {})
            out.update(transport_attempts=1, latency_s=0.0)
            return out
        last = None
        for attempt in range(1, self.transport_retries + 2):
            try:
                if self.provider == "openai_compat":
                    out = self._openai(system, user, seed)
                elif self.provider == "anthropic":
                    out = self._anthropic(system, user)
                else:
                    raise RuntimeError(f"unknown provider {self.provider}")
                out.update(transport_attempts=attempt, latency_s=round(time.time() - t0, 3))
                return out
            except TransportError as e:
                last = str(e)
                retryable = any(s in last for s in ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503",
                                                    "HTTP 504", "HTTP 529", "Timeout", "URLError",
                                                    "RemoteDisconnected", "ConnectionReset", "SSLError",
                                                    "SSL:", "ConnectionResetError", "IncompleteRead"))
                if not retryable or attempt > self.transport_retries:
                    break
                time.sleep(min(60, 2 ** attempt + random.random()))
        return {"text": None, "usage": {}, "raw": None, "transport_error": last,
                "transport_attempts": attempt, "latency_s": round(time.time() - t0, 3)}

    def _openai(self, system, user, seed):
        base = self.cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
        payload: Dict[str, Any] = {"model": self.model,
                                   "messages": [{"role": "system", "content": system},
                                                {"role": "user", "content": user}]}
        tok_field = self.cfg.get("max_tokens_field", "max_tokens")
        payload[tok_field] = self.max_tokens
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if seed is not None and self.cfg.get("send_seed", True):
            payload["seed"] = seed
        for k, v in (self.cfg.get("extra_body") or {}).items():
            payload[k] = v
        headers = {"Authorization": f"Bearer {self._key}"}
        headers.update(self.cfg.get("extra_headers") or {})
        r = _post(base + "/chat/completions", headers, payload, self.timeout)
        if "error" in r:
            raise TransportError(f"API error: {str(r['error'])[:300]}")
        ch = (r.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        text = msg.get("content")
        if isinstance(text, list):
            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
        u = r.get("usage") or {}
        return {"text": text, "raw": r, "finish_reason": ch.get("finish_reason"),
                "served_model": r.get("model"),
                "usage": {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                          "provider_cost_usd": u.get("cost")}}

    def _anthropic(self, system, user):
        base = self.cfg.get("base_url", "https://api.anthropic.com/v1").rstrip("/")
        payload: Dict[str, Any] = {"model": self.model, "system": system, "max_tokens": self.max_tokens,
                                   "messages": [{"role": "user", "content": user}]}
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        for k, v in (self.cfg.get("extra_body") or {}).items():
            payload[k] = v
        headers = {"x-api-key": self._key, "anthropic-version": "2023-06-01"}
        r = _post(base + "/messages", headers, payload, self.timeout)
        if r.get("type") == "error":
            raise TransportError(f"API error: {str(r.get('error'))[:300]}")
        text = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        u = r.get("usage") or {}
        return {"text": text, "raw": r, "finish_reason": r.get("stop_reason"), "served_model": r.get("model"),
                "usage": {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens")}}


# ------------------------------------------------------------------ mocks
def _mock_response(cfg: Dict[str, Any], user: str, seed: Optional[int], meta: Dict[str, Any]) -> Dict[str, Any]:
    """Test doubles. behaviour:
       cost_sensitive : picks the lower-cost constraint with prob p_follow (reads the report)
       cost_blind     : ignores cost; picks label 1 with prob p_label1
       noisy          : cost_sensitive + malformed JSON / invalid edits at configured rates
    """
    rng = random.Random(f"{cfg['name']}-{seed}-{meta.get('trial_id')}-{meta.get('attempt')}")
    beh = cfg.get("behaviour", "cost_blind")
    scn, lm, task = meta.get("scenario"), meta.get("label_to_identity"), meta.get("task", "decision")
    m = re.findall(r"If Constraint ([12]) is relaxed: manual downstream repairs required = (\d+)", user)
    costs = {int(a): int(b) for a, b in m}
    usage = {"input_tokens": len(user) // 4, "output_tokens": 60}
    if task == "recognition":
        if costs:
            c1, c2 = costs[1], costs[2]
        else:  # graph-only: crude count of manual dependents would go here; mock guesses
            c1, c2 = rng.randint(1, 8), rng.randint(1, 8)
        if rng.random() < float(cfg.get("p_recog_error", 0.0)):
            c1, c2 = c2, c1
        more = 1 if c1 > c2 else (2 if c2 > c1 else "equal")
        return {"text": json.dumps({"more_repairs": more, "repairs_if_1_relaxed": c1,
                                    "repairs_if_2_relaxed": c2}), "usage": usage, "raw": None}
    if beh in ("cost_sensitive", "noisy") and costs and costs[1] != costs[2]:
        low = 1 if costs[1] < costs[2] else 2
        lab = low if rng.random() < float(cfg.get("p_follow", 0.85)) else 3 - low
    else:
        lab = 1 if rng.random() < float(cfg.get("p_label1", 0.5)) else 2
    ident = lm[lab]
    c = scn["constraints"][ident]
    ed = next(e for e in scn["editable"] if e["node"] == c["node"] and e["field"] == c["field"])
    # choose a goal-achieving value for the sacrificed field
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from graph_model import World, apply_patch, check_goal
    base = World(scn["nodes"])
    vals = [v for v in ed["domain"] if v != c["value"] and
            check_goal(apply_patch(base, [{"node": c["node"], "field": c["field"], "value": v}]), scn["goal"])]
    val = rng.choice(vals)
    patch = [{"node": c["node"], "field": c["field"], "value": val}]
    if beh == "noisy" and rng.random() < float(cfg.get("p_invalid_edit", 0.1)):
        patch = [{"node": scn["goal"]["target"], "field": "requires_any", "value": []}]
    body = {"sacrifice_constraint": lab, "edit_plan": ["relax the cheaper constraint"],
            "final_patch": patch, "brief_reason": "mock"}
    text = json.dumps(body)
    if beh == "noisy" and rng.random() < float(cfg.get("p_malformed", 0.15)):
        text = "Sure! Here is my answer: {sacrifice_constraint: " + str(lab)
    return {"text": text, "usage": usage, "raw": None}
