from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "analysis" / "feature_schema" / "g40_p2_mfproto_v3.md"


def _text() -> str:
    return " ".join(PROTOCOL.read_text().split())


def test_mfproto_ratification_freezes_required_numerics() -> None:
    text = _text()
    for required in (
        "production remains held pending goals-review 16",
        "g40_p2_mfproto_v3",
        "PySCF 2.8.0",
        "G1 core",
        "G2 shipped",
        "G3 alternating",
        "G4 thermal core",
        "second-order augmented-Hessian",
        "abs(delta_E) < 1e-9 Ha",
        "1e-6 Ha",
        "four smallest finite Hessian diagonal elements",
        "(spin block, occupied index, virtual index)",
        "kappa in {infinity,1.45,1.1} Ha^-1",
        "220 GB",
    ):
        assert required in text


def test_mfproto_ratification_contains_all_required_doc_fixes() -> None:
    text = _text()
    for required in (
        "recursively pin the tied subspace",
        "projected-index tied-subspace count",
        "natural_occupation_out_of_range",
        "mask **only** the natural-occupation panel",
        "minimum and maximum raw occupation",
        "boundary included",
        "uniform projector diagonal",
        "linear-relaxation",
        "partial_mask",
        "protocol-version bump",
        "degenerate-Fock lattice tasks",
        "unreachable in corpus, fixture-covered",
        "mean-field analogue of the R6.2",
        "after the primary solve and after the fallback",
        "0.5 * curvature",
        "amplitude-shape",
        "RHF before UHF",
        "future sign-odd column",
        "future cliff-sensitive column requires an explicit band mask",
        "consistency check between the declarations and frozen selection",
        "across the selected rotation-pair set",
        "Zero observed drift across the whole selected set also fails closed",
        "stationary-point-identity certificate",
        "mapped by the pair's checksum-bound unitary",
        "goals-review 14",
        "Stability-follow outputs are diagnostic-only",
        "protocol-selected solution",
        "## Changelog",
    ):
        assert required in text


def test_mfproto_marks_binding_resolutions_and_v3_exclusions() -> None:
    text = _text()
    assert text.count("PI-ratified resolution") >= 3
    assert text.count("PI-ratified by goals-review 12") >= 2
    assert "Krylov-Ritz and RPA are absent from MFPROTO-v3" in text
    assert "iterative lowest-pole formulation is the admissible post-v3 route" in text
    assert "Goals-review 12.5 accepted" in text
    for obsolete in (
        "proposal for PI ratification",
        "Krylov-Ritz amendment request",
        "RPA amendment request",
        "nocc*nvirt <= 4096",
        "direct ring RPA",
        "no P2 pilot or production claim is authorized",
        "authorizes the P2 pilot without another pre-pilot review",
        "without another pre-pilot review",
    ):
        assert obsolete not in text
