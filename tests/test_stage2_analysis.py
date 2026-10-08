import json
import os
import shutil
import sys
from pathlib import Path

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "analysis"))

import runner
import stage2_analysis


def test_stage2_mock_recovery_and_analysis(tmp_path, monkeypatch):
    repo = Path(ROOT)
    shutil.copytree(repo / "data/scenarios/v2", tmp_path / "data/scenarios/v2")
    monkeypatch.setattr(runner, "ROOT", str(tmp_path))

    common = ["--config", str(repo / "configs/stage2.yaml"),
              "--models-file", str(repo / "configs/models.mock.yaml"), "--yes"]
    for phase, run_id in (("S2_G", "TEST_S2_G"), ("S2_X", "TEST_S2_X"), ("S2_REC", "TEST_S2_REC")):
        assert runner.main(["--phase", phase, *common, "--run-id", run_id]) == 0

    runs = tmp_path / "runs/mock/parsed"
    graph = runs / "TEST_S2_G/decision_trials.csv"
    explicit = runs / "TEST_S2_X/decision_trials.csv"
    rec = runs / "TEST_S2_REC/recognition_trials.csv"
    out = tmp_path / "analysis/stage2"
    stage2_analysis.main(["--graph", str(graph), "--explicit", str(explicit), "--rec", str(rec),
                          "--out", str(out), "--boot", "200"])

    result = json.loads((out / "results.json").read_text(encoding="utf-8"))
    model = "mock-cost-sensitive"
    assert result["delta_explicit"]["per_model"][model]["estimate"] > 0.45
    assert abs(result["delta_graph"]["per_model"][model]["estimate"]) < 0.30
    assert result["gap"]["per_model"][model]["estimate"] > 0.35
