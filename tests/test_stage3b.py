import hashlib
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "analysis"))

import runner
from prompt_builder import CONTROL_TEXT, DECISION_FORMAT, NUDGE_TEXT, build_prompt
import stage3b_analysis


FIXTURE_HASHES = {
    "explicit": "ab7a87600c39e7150ad3be1f815fad274e4d092807078f24f2d76b8ef2c3d1c0",
    "graph_only": "784b8419d051626d99b4be9147436437e29373e9a970bb5edd0d34bf97600318",
    "graph_only_nudge": "5f8b186220d2daf410557f9e9fd691591ad7711160f2a09757b9226296e8bfa2",
}


def _sample_scenarios():
    by_template = {}
    for path in sorted((ROOT / "data/scenarios/v2").glob("*.json")):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        if scenario["condition"] == "A_HIGH" and scenario["name_set"] == 0:
            by_template.setdefault(scenario["template_id"], scenario)
    return [by_template[f"T{i:02d}"] for i in range(1, 6)]


def _prompt_hash(info):
    parts = []
    for scenario in _sample_scenarios():
        prompt = build_prompt(scenario, 0, info=info, task="decision")
        parts.append(f"{scenario['template_id']}|{info}|{prompt['system']}\n"
                     f"{prompt['user']}|{prompt['prompt_version']}")
    return hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()


def test_control_prompt_is_graph_only_plus_one_neutral_paragraph():
    assert {info: _prompt_hash(info) for info in FIXTURE_HASHES} == FIXTURE_HASHES
    for scenario in _sample_scenarios():
        graph = build_prompt(scenario, 0, info="graph_only", task="decision")
        ctrl = build_prompt(scenario, 0, info="graph_only_ctrl", task="decision")
        expected = graph["user"].replace(
            "\n\n" + DECISION_FORMAT,
            "\n\n" + CONTROL_TEXT + "\n\n" + DECISION_FORMAT,
        )
        assert ctrl["user"] == expected
        assert ctrl["user"].count(CONTROL_TEXT) == 1
        assert ctrl["prompt_version"] == "prompt/1.2-ctrl"
    banned = ("cost", "repair", "manual", "engine", "minim", "depend", "downstream", "consequence", "affect")
    assert not any(word in CONTROL_TEXT.lower() for word in banned)
    assert NUDGE_TEXT in build_prompt(_sample_scenarios()[0], 0, "graph_only_nudge")["user"]


def test_stage3b_config_matches_preregistered_cell_counts():
    cfg = yaml.safe_load((ROOT / "configs/stage3b.yaml").read_text(encoding="utf-8"))
    assert cfg["base_seed"] == 20261008
    assert cfg["max_cost_usd_without_confirm"] == 30
    expected = {"S3B_SMOKE": 72, "S3B_G": 480, "S3B_X": 320, "S3B_REC": 320, "S3B_CTRL": 120}
    for phase, trials in expected.items():
        ph = cfg["phases"][phase]
        models = ph["models"]
        assert len(runner.build_trials(phase, cfg, models)) == trials


def test_stage3b_analysis_end_to_end_on_mock_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner, "ROOT", str(tmp_path))
    shutil.copytree(ROOT / "data/scenarios/v2", tmp_path / "data/scenarios/v2")
    mock_models = ROOT / "configs/models.mock.yaml"
    stage3b_cfg = ROOT / "configs/stage3b.yaml"
    stage3a_cfg = ROOT / "configs/stage3a.yaml"
    phases = (
        ("S3B_G", stage3b_cfg), ("S3B_X", stage3b_cfg), ("S3B_REC", stage3b_cfg),
        ("S3B_CTRL", stage3b_cfg), ("S3A_G", stage3a_cfg), ("S3A_N", stage3a_cfg),
    )
    for phase, config in phases:
        assert runner.main([
            "--phase", phase, "--config", str(config), "--models-file", str(mock_models),
            "--models", "nonoa", "--yes", "--run-id", f"mock_{phase}",
        ]) == 0
    capsys.readouterr()

    parsed = tmp_path / "runs/mock/parsed"
    out = tmp_path / "analysis/stage3b"
    stage3b_analysis.main([
        "--g", str(parsed / "mock_S3B_G/decision_trials.csv"),
        "--x", str(parsed / "mock_S3B_X/decision_trials.csv"),
        "--rec", str(parsed / "mock_S3B_REC/recognition_trials.csv"),
        "--ctrl", str(parsed / "mock_S3B_CTRL/decision_trials.csv"),
        "--g3a", str(parsed / "mock_S3A_G/decision_trials.csv"),
        "--n3a", str(parsed / "mock_S3A_N/decision_trials.csv"),
        "--out", str(out), "--boot", "100", "--raw-dir", str(tmp_path / "runs/mock/raw"),
    ])
    captured = capsys.readouterr().out
    result = json.loads((out / "results.json").read_text(encoding="utf-8"))
    markdown = (out / "results.md").read_text(encoding="utf-8")
    assert result["bootstrap_replicates"] == 100
    assert "mock-noisy" in result["new_models"]
    assert result["new_models"]["mock-noisy"]["n_trials"]["G"] > 0
    assert result["deepseek_v4_pro"]["n_trials"]["CTRL"] > 0
    assert "Auto-classification (prereg rule):" in markdown
    assert "Auto-classification (prereg rule):" in captured
