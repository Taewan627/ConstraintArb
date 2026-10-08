import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "analysis"))

import runner
from prompt_builder import DECISION_FORMAT, NUDGE_TEXT, build_prompt
import stage3a_analysis


FIXTURE_HASH = "f85ec0c1cd631372123741a56186c1c8fdff80eaa2c1ddba1c58256dfce63e36"


def _sample_scenarios():
    by_template = {}
    for path in sorted((ROOT / "data/scenarios/v2").glob("*.json")):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        if scenario["condition"] == "A_HIGH" and scenario["name_set"] == 0:
            by_template.setdefault(scenario["template_id"], scenario)
    return [by_template[f"T{i:02d}"] for i in range(1, 6)]


def _old_prompt_fixture_hash():
    parts = []
    for scenario in _sample_scenarios():
        for info in ("explicit", "graph_only"):
            prompt = build_prompt(scenario, 0, info=info, task="decision")
            parts.append(f"{scenario['template_id']}|{info}|{prompt['system']}\n"
                         f"{prompt['user']}|{prompt['prompt_version']}")
    return hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()


def test_nudge_prompt_is_graph_only_plus_one_paragraph_and_preserves_old_prompts():
    scenarios = _sample_scenarios()
    assert _old_prompt_fixture_hash() == FIXTURE_HASH
    for scenario in scenarios:
        graph = build_prompt(scenario, 0, info="graph_only", task="decision")
        nudge = build_prompt(scenario, 0, info="graph_only_nudge", task="decision")
        expected_user = graph["user"].replace(
            "\n\n" + DECISION_FORMAT,
            "\n\n" + NUDGE_TEXT + "\n\n" + DECISION_FORMAT,
        )
        assert nudge["user"] == expected_user
        assert nudge["user"].count(NUDGE_TEXT) == 1
        assert graph["prompt_version"] == "prompt/1.0"
        assert build_prompt(scenario, 0, info="explicit", task="decision")["prompt_version"] == "prompt/1.0"
        assert nudge["prompt_version"] == "prompt/1.1-nudge"
    assert not any(word in NUDGE_TEXT.lower() for word in ("cost", "repairs", "manual", "engine", "minimisation"))


def test_stage3a_analysis_end_to_end_on_mock_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner, "ROOT", str(tmp_path))
    shutil.copytree(ROOT / "data/scenarios/v2", tmp_path / "data/scenarios/v2")
    config = ROOT / "configs/stage3a.yaml"
    models = ROOT / "configs/models.mock.yaml"
    for phase in ("S3A_G", "S3A_N", "S3A_REC"):
        assert runner.main([
            "--phase", phase, "--config", str(config), "--models-file", str(models),
            "--yes", "--run-id", f"test_{phase}",
        ]) == 0
    capsys.readouterr()

    parsed = tmp_path / "runs/mock/parsed"
    g_path = parsed / "test_S3A_G/decision_trials.csv"
    n_path = parsed / "test_S3A_N/decision_trials.csv"
    rec_path = parsed / "test_S3A_REC/recognition_trials.csv"
    out = tmp_path / "analysis/stage3a"
    stage3a_analysis.main([
        "--g", str(g_path), "--n", str(n_path), "--rec", str(rec_path),
        "--s2g", str(g_path), "--out", str(out), "--boot", "100",
        "--raw-dir", str(tmp_path / "runs/mock/raw"),
    ])
    captured = capsys.readouterr().out
    result = json.loads((out / "results.json").read_text(encoding="utf-8"))
    markdown = (out / "results.md").read_text(encoding="utf-8")
    assert result["model"] == "mock-noisy"
    assert result["bootstrap_replicates"] == 100
    assert result["n_trials"]["G"] > 0 and result["n_trials"]["N"] > 0
    assert result["n_trials"]["REC"] > 0
    assert result["recognition"]["parse_rate"] is not None
    assert "Auto-classification (prereg rule):" in markdown
    assert "Auto-classification (prereg rule):" in captured
