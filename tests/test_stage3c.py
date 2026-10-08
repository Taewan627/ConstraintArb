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
from prompt_builder import (
    CONTROL_TEXT, DECISION_FORMAT, NUDGE_B_TEXT, NUDGE_C_TEXT, NUDGE_TEXT, REP_HEADER,
    _constraints_block, build_prompt,
)
import stage3c_analysis


OLD_PROMPT_FIXTURE_HASHES = {
    "explicit": "ab7a87600c39e7150ad3be1f815fad274e4d092807078f24f2d76b8ef2c3d1c0",
    "graph_only": "784b8419d051626d99b4be9147436437e29373e9a970bb5edd0d34bf97600318",
    "graph_only_nudge": "5f8b186220d2daf410557f9e9fd691591ad7711160f2a09757b9226296e8bfa2",
    "graph_only_ctrl": "5c54a1e0acd62c1baf4225f966971834c5066f9bd7e671f2934104589f30fecd",
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


def test_stage3c_prompts_preserve_old_fixtures_and_add_exact_paragraphs():
    assert {info: _prompt_hash(info) for info in OLD_PROMPT_FIXTURE_HASHES} == OLD_PROMPT_FIXTURE_HASHES
    banned = ("cost", "repair", "manual", "engine", "cheap", "expensive", "minim")
    expected_versions = {
        "graph_only_rep": "prompt/1.3-rep",
        "graph_only_nudge_b": "prompt/1.4-nudge-b",
        "graph_only_nudge_c": "prompt/1.5-nudge-c",
    }
    for scenario in _sample_scenarios():
        for order in (0, 1):
            graph = build_prompt(scenario, order, info="graph_only", task="decision")
            constraints, _ = _constraints_block(scenario, order)
            paragraphs = {
                "graph_only_rep": REP_HEADER + "\n" + constraints,
                "graph_only_nudge_b": NUDGE_B_TEXT,
                "graph_only_nudge_c": NUDGE_C_TEXT,
            }
            for info, paragraph in paragraphs.items():
                prompt = build_prompt(scenario, order, info=info, task="decision")
                expected = graph["user"].replace(
                    "\n\n" + DECISION_FORMAT,
                    "\n\n" + paragraph + "\n\n" + DECISION_FORMAT,
                )
                assert prompt["user"] == expected
                assert prompt["prompt_version"] == expected_versions[info]
                assert sum(prompt["user"].count(text) for text in (REP_HEADER, NUDGE_B_TEXT, NUDGE_C_TEXT)) == 1
                assert not any(word in paragraph.lower() for word in banned)
    assert NUDGE_TEXT and CONTROL_TEXT


def test_stage3c_config_and_model_copy_match_preregistered_counts():
    cfg = yaml.safe_load((ROOT / "configs/stage3c.yaml").read_text(encoding="utf-8"))
    assert cfg["base_seed"] == 20261009
    assert cfg["max_cost_usd_without_confirm"] == 20
    assert (ROOT / "configs/models_stage3c.yaml").read_bytes() == (ROOT / "configs/models_stage3b.yaml").read_bytes()
    expected = {"S3C_SMOKE_REP": 24, "S3C_SMOKE_NB": 24, "S3C_SMOKE_NC": 24,
                "S3C_G": 160, "S3C_REP": 160, "S3C_N1": 160, "S3C_NB": 160, "S3C_NC": 160}
    for phase, count in expected.items():
        assert len(runner.build_trials(phase, cfg, cfg["phases"][phase]["models"])) == count


def _classification_fixture():
    per_model = {}
    for model in ("deepseek-v4-pro", "deepseek-v4.1-flash"):
        arms = {}
        for arm in stage3c_analysis.ARMS:
            arms[arm] = {
                "valid_rate": 1.0,
                "delta": {"estimate": 0.75 if arm in ("N1", "NB", "NC") else (0.30 if arm == "G" else 0.40),
                          "ci95": [0.60, 0.90]},
                "effect": {"estimate": 0.45 if arm != "G" else 0.0,
                           "ci95": [0.35, 0.55] if arm != "G" else [0.0, 0.0]},
            }
        per_model[model] = {
            "gap_present": True, "arms": arms,
            "rep_specific": {"estimate": 0.35, "ci95": [0.25, 0.45]},
        }
    return {"per_model": per_model}


def test_classify_stage3c_g2_pass_partial_fail():
    result = _classification_fixture()
    assert stage3c_analysis.classify_stage3c(result)["G2"]["label"] == "PASS"

    partial = _classification_fixture()
    partial["per_model"]["deepseek-v4-pro"]["arms"]["REP"]["delta"]["estimate"] = 0.60
    assert stage3c_analysis.classify_stage3c(partial)["G2"]["label"] == "PARTIAL"

    fail = _classification_fixture()
    fail["per_model"]["deepseek-v4-pro"]["arms"]["REP"]["delta"]["estimate"] = 0.70
    assert stage3c_analysis.classify_stage3c(fail)["G2"]["label"] == "FAIL"


def test_classify_stage3c_g3_pass_partial_fail():
    result = _classification_fixture()
    assert stage3c_analysis.classify_stage3c(result)["G3"]["label"] == "PASS"

    partial = _classification_fixture()
    for model in partial["per_model"].values():
        model["arms"]["NB"]["delta"]["estimate"] = 0.60
        model["arms"]["NC"]["delta"]["estimate"] = 0.60
    partial["per_model"]["deepseek-v4-pro"]["arms"]["NB"]["delta"]["estimate"] = 0.75
    assert stage3c_analysis.classify_stage3c(partial)["G3"]["label"] == "PARTIAL"

    fail = _classification_fixture()
    for model in fail["per_model"].values():
        for arm in ("NB", "NC"):
            model["arms"][arm]["delta"]["estimate"] = 0.60
    assert stage3c_analysis.classify_stage3c(fail)["G3"]["label"] == "FAIL"


def test_stage3c_analysis_end_to_end_with_mock_runner(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner, "ROOT", str(tmp_path))
    shutil.copytree(ROOT / "data/scenarios/v2", tmp_path / "data/scenarios/v2")
    config = ROOT / "configs/stage3c.yaml"
    models = ROOT / "configs/models.mock.yaml"
    phases = (("S3C_G", "G"), ("S3C_REP", "REP"), ("S3C_N1", "N1"),
              ("S3C_NB", "NB"), ("S3C_NC", "NC"))
    paths = {}
    for phase, arm in phases:
        assert runner.main([
            "--phase", phase, "--config", str(config), "--models-file", str(models),
            "--models", "mock-noisy", "--yes", "--run-id", f"mock_{phase}",
        ]) == 0
        paths[arm] = tmp_path / "runs/mock/parsed" / f"mock_{phase}" / "decision_trials.csv"
    capsys.readouterr()

    out = tmp_path / "analysis/stage3c"
    stage3c_analysis.main([
        "--g", str(paths["G"]), "--rep", str(paths["REP"]), "--n1", str(paths["N1"]),
        "--nb", str(paths["NB"]), "--nc", str(paths["NC"]), "--out", str(out), "--boot", "100",
        "--raw-dir", str(tmp_path / "runs/mock/raw"),
    ])
    captured = capsys.readouterr().out
    result = json.loads((out / "results.json").read_text(encoding="utf-8"))
    markdown = (out / "results.md").read_text(encoding="utf-8")
    assert result["bootstrap_replicates"] == 100
    assert result["per_model"]["mock-noisy"]["arms"]["G"]["n_total"] == 80
    assert result["per_model"]["mock-noisy"]["arms"]["REP"]["valid_rate"] is not None
    assert "Auto-classification (prereg rule):" in markdown
    assert "Auto-classification (prereg rule):" in captured
