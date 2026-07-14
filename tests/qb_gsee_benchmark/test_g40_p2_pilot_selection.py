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
    coverage = manifest["mask_regime_coverage"]
    assert coverage["mp2_denominator_below_threshold"]["status"] == (
        "unreachable in corpus, fixture-covered"
    )
    assert coverage["natural_occupation_out_of_range"]["fixture_tests"]
    assert coverage["all_amplitudes_masked"]["task_uuids"] == [
        "3d343ddb-a898-5c0e-afc9-42b62d588c5e",
        "6cd8382a-9a9a-5c43-83b1-616c9f301ab1",
        "ac3a023f-8d31-5d79-803e-c54e947c8d75",
        "fcc8fbc8-87b5-5a77-b3e2-38539824873e",
    ]
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


def test_p2_postpilot_amendment_is_one_row_and_byte_rebuildable() -> None:
    module = _builder_module()
    frozen = json.loads((OUT / "g40_p2_pilot_selection.json").read_text())
    amended_path = OUT / "g40_p2_pilot_selection_v3_postpilot_amendment_gr16.json"
    amended = json.loads(amended_path.read_text())

    assert (
        module.build_postpilot_amendment(ROOT / "scripts" / "Hamiltonian_features.csv")
        == amended
    )
    assert amended["manifest_version"] == (
        "g40_p2_pilot_selection_v3_postpilot_amendment_gr16"
    )
    assert amended["amendment"]["status"] == "adjudicated_post_pilot"
    assert amended["amendment"]["review_id"] == "goals-review-16"
    assert "not a retroactive preregistration" in amended["selection_policy"]
    assert "historical evidence" in amended["amendment"]["non_retroactivity"]

    regime = "natural_occupation_out_of_range"
    task_uuid = "beabcf8f-a6c0-5e32-9385-110ff65cbbf0"
    assert amended["mask_regime_coverage"][regime]["status"] == "corpus-reachable"
    assert amended["mask_regime_coverage"][regime]["task_uuids"] == [task_uuid]
    assert amended["coverage_counts"]["expected_mask_regime"][regime] == 1
    for name, declaration in frozen["mask_regime_coverage"].items():
        if name != regime:
            assert amended["mask_regime_coverage"][name] == declaration

    frozen_tasks = {task["task_uuid"]: task for task in frozen["tasks"]}
    amended_tasks = {task["task_uuid"]: task for task in amended["tasks"]}
    assert frozen_tasks.keys() == amended_tasks.keys()
    for current_uuid in frozen_tasks:
        frozen_masks = frozen_tasks[current_uuid]["expected_masks"]
        amended_masks = amended_tasks[current_uuid]["expected_masks"]
        if current_uuid == task_uuid:
            assert amended_masks == [*frozen_masks, regime]
        else:
            assert amended_masks == frozen_masks
