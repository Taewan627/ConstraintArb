import json
import csv
import io
import tempfile
from pathlib import Path

from conftest import ROOT
from scenario_generator import NEUTRAL_REQUEST, generate


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_v2_scenarios_are_neutral_valid_and_pairwise_identical_except_amendments():
    v1_dir = Path(ROOT) / "data/scenarios/generated"
    v2_dir = Path(ROOT) / "data/scenarios/v2"
    v2 = sorted(v2_dir.glob("*.json"))
    assert len(v2) == 120

    ignored = {"scenario_id", "request_text", "scenario_hash", "scenario_version"}
    for path in v2:
        s2 = _read_json(path)
        assert s2["scenario_version"] == 2
        assert s2["expected"]["valid_for_pilot"] is True
        assert s2["request_text"] == NEUTRAL_REQUEST.format(T=s2["entity_names"]["T"])
        old_id = path.name.removeprefix("S2-")
        s1 = _read_json(v1_dir / old_id)
        assert s1["expected"] == s2["expected"]
        assert {k: v for k, v in s1.items() if k not in ignored} == {
            k: v for k, v in s2.items() if k not in ignored
        }


def test_version1_generation_reproduces_existing_files_byte_for_byte():
    root = Path(ROOT)
    with tempfile.TemporaryDirectory() as temp:
        out_dir = Path(temp) / "generated"
        audit = Path(temp) / "feasibility_audit.csv"
        pairs = Path(temp) / "matched_pairs.csv"
        generate(str(out_dir), str(audit), str(pairs), version=1)

        for generated in out_dir.glob("*.json"):
            assert generated.read_bytes() == (root / "data/scenarios/generated" / generated.name).read_bytes()
        for generated, existing in ((audit, root / "analysis/feasibility_audit.csv"),
                                    (pairs, root / "data/matched_pairs/matched_pairs.csv")):
            actual_rows = list(csv.reader(io.StringIO(generated.read_text(encoding="utf-8"))))
            expected_rows = list(csv.reader(io.StringIO(existing.read_text(encoding="utf-8"))))
            assert actual_rows == expected_rows
