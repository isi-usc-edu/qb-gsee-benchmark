from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "analysis" / "feature_schema" / "g40_p2_mfproto_v1.md"


def test_mfproto_layer2_proposal_freezes_required_numerics() -> None:
    text = " ".join(PROTOCOL.read_text().split())
    for required in (
        "proposal for PI ratification",
        "g40_p2_mfproto_v1",
        "PySCF 2.8.0",
        "G1 core",
        "G2 shipped",
        "G3 alternating",
        "G4 thermal core",
        "second-order augmented-Hessian",
        "abs(delta_E) < 1e-9 Ha",
        "1e-6 Ha",
        "kappa in {infinity,1.45,1.1} Ha^-1",
        "nocc*nvirt <= 4096",
        "220-GB",
    ):
        assert required in text


def test_mfproto_proposal_records_both_required_amendment_decisions() -> None:
    text = " ".join(PROTOCOL.read_text().split())
    assert "Recommend dropping this rung from MFPROTO-v1" in text
    assert "Reintroducing a probe requires a separate `T-probe` version" in text
    assert "Do not claim dense direct RPA as corpus-wide" in text
    assert "no P2 pilot or production claim is authorized" in text
