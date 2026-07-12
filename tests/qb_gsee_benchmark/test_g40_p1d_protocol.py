from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "feature_schema"


def test_p1d_protocol_and_cost_gate_are_frozen_before_pilot() -> None:
    protocol = (OUT / "g40_p1d_interaction_spectrum_protocol.md").read_text()
    cost = (OUT / "g40_p1d_compute_cost_estimate.md").read_text()
    assert "sqrt(2)" in protocol
    assert "1e-2, 1e-4, 1e-6" in protocol
    assert "driver=\"evd\"" in protocol
    assert "partial eigensolver" in protocol
    assert "184 rows" in protocol
    assert "upper bound of 12" in cost
    assert "node-hours" in cost
    assert "16,109" in cost


def test_p1d_pilot_selection_is_unique_cross_band_and_contains_g21() -> None:
    selected = (OUT / "g40_p1d_pilot_selection.txt").read_text().splitlines()
    assert len(selected) == len(set(selected)) == 25
    assert {
        "3d343ddb-a898-5c0e-afc9-42b62d588c5e",
        "6cd8382a-9a9a-5c43-83b1-616c9f301ab1",
        "dd80e2eb-9220-53ee-bac4-a087306dc309",
        "cb5392c3-fd91-50f3-be40-149559ae7b96",
    } <= set(selected)
    assert "fc432cd0-4856-54f2-a240-9813d9fda019" in selected
    assert "5e53cc08-b541-5163-bbf2-66e195a6492f" in selected


def test_p1d_legacy_comparison_selection_is_frozen_at_184_rows() -> None:
    selected = (
        OUT / "g40_p1d_legacy_comparison_selection.txt"
    ).read_text().splitlines()
    assert len(selected) == len(set(selected)) == 184
