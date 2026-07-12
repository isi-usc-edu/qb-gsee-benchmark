import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "feature_schema"


def _builder_module():
    path = ROOT / "scripts" / "build_g40_p2_pilot_selection.py"
    spec = importlib.util.spec_from_file_location("build_g40_p2_pilot_selection", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_p2_pilot_selection_is_frozen_and_satisfies_ratified_coverage() -> None:
    selected = (OUT / "g40_p2_pilot_selection.txt").read_text().splitlines()
    manifest = json.loads((OUT / "g40_p2_pilot_selection.json").read_text())

    assert len(selected) == len(set(selected)) == manifest["selected_tasks"] == 25
    assert selected == [task["task_uuid"] for task in manifest["tasks"]]
    assert all(manifest["coverage_checks"].values())
    assert (
        manifest["coverage_counts"]["expected_mask_regime"][
            "natural_occupation_out_of_range"
        ]
        >= 2
    )
    assert {
        "3d343ddb-a898-5c0e-afc9-42b62d588c5e",
        "6cd8382a-9a9a-5c43-83b1-616c9f301ab1",
        "dd80e2eb-9220-53ee-bac4-a087306dc309",
        "cb5392c3-fd91-50f3-be40-149559ae7b96",
        "beabcf8f-a6c0-5e32-9385-110ff65cbbf0",
        "ac3a023f-8d31-5d79-803e-c54e947c8d75",
    } <= set(selected)


def test_p2_pilot_selection_rebuild_is_byte_exact() -> None:
    module = _builder_module()
    rebuilt = module.build_manifest(ROOT / "scripts" / "Hamiltonian_features.csv")
    committed = json.loads((OUT / "g40_p2_pilot_selection.json").read_text())
    assert rebuilt == committed
