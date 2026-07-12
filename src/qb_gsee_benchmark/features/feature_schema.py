# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Four-axis feature metadata and model eligibility for G-40."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

PROVENANCE_TIERS = {"T0", "T1", "T2", "T-probe", "T3", "N/A"}
REPRESENTATION_TAGS = {"INV", "BAS", "BAS+ORD", "GAUGE", "N/A"}
PROTOCOL_TAGS = {"NONE", "MF-PROTO", "AFQMC-PROTO", "N/A"}
ROLE_TAGS = {"accuracy", "runtime", "representation-sensitivity", "audit-only"}

@dataclass(frozen=True)
class FeatureColumnMetadata:
    column: str
    column_kind: str
    provenance_tier: str
    representation: str
    protocol: str
    role: str
    model_eligible: bool
    exclusion_reason: str
    scaling: str
    cost_class: str
    definition: str
    implementation_status: str = "current"

    def __post_init__(self) -> None:
        if self.provenance_tier not in PROVENANCE_TIERS:
            raise ValueError(f"invalid provenance tier for {self.column}")
        if self.representation not in REPRESENTATION_TAGS:
            raise ValueError(f"invalid representation tag for {self.column}")
        if self.protocol not in PROTOCOL_TAGS:
            raise ValueError(f"invalid protocol tag for {self.column}")
        if self.role not in ROLE_TAGS:
            raise ValueError(f"invalid role tag for {self.column}")
        if self.model_eligible and self.exclusion_reason:
            raise ValueError(f"eligible column {self.column} has an exclusion reason")
        if not self.model_eligible and not self.exclusion_reason:
            raise ValueError(f"excluded column {self.column} lacks a reason")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

def _feature(
    column: str, tier: str, representation: str, *, protocol: str = "NONE",
    role: str = "accuracy", eligible: bool = True, reason: str = "",
    scaling: str = "intensive", cost: str = "integral_postprocess",
    definition: str | None = None, status: str = "current",
) -> FeatureColumnMetadata:
    return FeatureColumnMetadata(
        column=column, column_kind="feature", provenance_tier=tier,
        representation=representation, protocol=protocol, role=role,
        model_eligible=eligible, exclusion_reason=reason, scaling=scaling,
        cost_class=cost, definition=definition or column.replace("_", " "),
        implementation_status=status,
    )

def _audit(column: str, kind: str, reason: str) -> FeatureColumnMetadata:
    return FeatureColumnMetadata(
        column=column, column_kind=kind, provenance_tier="N/A",
        representation="N/A", protocol="N/A", role="audit-only",
        model_eligible=False, exclusion_reason=reason, scaling="N/A",
        cost_class="metadata", definition=column.replace("_", " "),
    )

IDENTIFIERS = {
    "problem_instance_uuid", "problem_instance_short_name", "task_uuid",
    "instance_data_object_uuid", "instance_data_object_file_name",
    "instance_data_object_url", "equivalence_group_id", "ml_split_group_id",
    "orbital_representation", "lattice_model_family",
}
PROCEDURAL = {
    "date_of_calculation", "version_of_features_calculation_script",
    "ham_features_calc_time", "features_version", "pyscf_diagnostics_version",
    "structure_proxy_features_version", "representation_features_version",
    "fragment_detector_version", "sign_free_detector_version",
    "pair_structure_features_version", "representation_invariant_feature_names",
    "representation_covariant_feature_names", "df_eig_decay_fit_reason",
    "pyscf_homo_lumo_gap_reason", "pyscf_uhf_s2_reason",
    "mp2_corr_energy_reason", "mp2_corr_energy_per_electron_reason",
    "ccsd_t1_diagnostic_reason", "ccsd_d1_diagnostic_reason",
    "ccsd_max_t2_reason", "fragment_partition_tracks",
    "fragment_ml_default_track", "fragment_oracle_permission",
    "fragment_partition_assignments_agree", "fragment_calibration_role",
    "sign_free_condition", "g24_coverage_group",
    "mp2_spin_decomposition_status", "pair_structure_basis",
    "U_eff_over_W_reason", "universal_t0_linear_features_version",
    "fcidump_symmetry_status", "fcidump_symmetry_atol",
    "fcidump_symmetry_rtol", "fcidump_container_format",
    "fcidump_container_member", "fcidump_ms2_source",
    "retag_audit_features_version",
}
DUPLICATE_SIZE = {"num_orbitals", "num_electrons", "ms2"}
LEGACY_JW_ARCHIVE = {
    "one_norm", "min_weight", "max_edge_order", "one_norm_per_orbital",
    "one_norm_per_pauli_term", "min_edge_order",
}
LEGACY_JW_MODEL = {
    "max_vertex_degree", "min_vertex_degree", "mean_vertex_degree",
    "std_dev_vertex_degree", "max_weight", "mean_weight", "std_dev_weight",
    "mean_edge_order", "std_dev_edge_order", "number_of_terms",
    "pauli_terms_per_orbital_quartic", "mean_vertex_degree_per_orbital",
    "max_vertex_degree_per_orbital", "vertex_degree_coefficient_of_variation",
    "edge_order_coefficient_of_variation",
}
DF_MODEL = {
    "df_rank", "df_gap", "df_eig_decay_exponent", "df_rank_per_orbital",
}
DF_AUDIT = {"df_eigs", "df_eig_decay_r2", "df_eig_decay_npoints"}
SOLVER_DERIVED = {
    "pyscf_homo_lumo_gap", "pyscf_uhf_s2", "mp2_corr_energy",
    "mp2_corr_energy_per_electron", "ccsd_t1_diagnostic",
    "ccsd_d1_diagnostic", "ccsd_max_t2",
}
REPRESENTATION_MODEL = {
    "h1_offdiag_frobenius", "eri_self_repulsion_sum",
    "nonzero_integrals_1e_10",
}
REPRESENTATION_AUDIT = {
    "ecore_hartree", "trace_h1", "pair_space_eri_trace", "fci_energy_hartree",
}
FRAGMENT_MODEL = {
    "fragment_inferred_one_body_inter_intra_ratio",
    "fragment_inferred_two_body_inter_intra_ratio",
}
FRAGMENT_AUDIT = {
    "fragment_count", "h2_bond_length_angstrom",
    "fragment_center_separation_angstrom", "lambda_interfragment",
    "fragment_oracle_one_body_inter_intra_ratio",
    "fragment_oracle_two_body_inter_intra_ratio",
}
SIGN_METADATA = {
    "lattice_bipartite", "lattice_filling_electrons_per_site",
    "interaction_sign", "sign_free_condition_flag",
}
PAIR_T0_MODEL = {
    "eri_full_l1_norm", "eri_full_l2_norm",
    "pair_scattering_eri_l1_fraction", "pair_scattering_eri_l2_fraction",
    "seniority_preserving_eri_l1_fraction",
    "seniority_preserving_eri_l2_fraction",
    "pair_to_density_eri_l2_ratio",
    "pair_to_seniority_breaking_eri_l2_ratio",
}
PAIR_T1_MODEL = {"hf_fock_ov_l2_norm", "hf_fock_ov_max_abs"}
PAIR_T2_MODEL = {
    "mp2_os_corr_energy_hartree", "mp2_ss_corr_energy_hartree",
    "mp2_corr_energy_hartree", "mp2_os_energy_abs_fraction",
    "mp2_ss_energy_abs_fraction", "mp2_pair_double_amplitude_l1_fraction",
    "mp2_pair_double_amplitude_l2_fraction",
}
PAIR_AUDIT = {
    "one_body_duplicate_orientation_records_skipped",
    "one_body_duplicate_max_abs_difference",
    "one_body_duplicate_max_rel_difference",
    "one_body_symmetry_conflict_records",
    "two_body_input_record_count", "two_body_unique_record_count",
    "two_body_duplicate_orientation_records_skipped",
    "two_body_duplicate_max_abs_difference",
    "two_body_duplicate_max_rel_difference",
    "two_body_symmetry_conflict_records",
    "hf_stationarity_tolerance",
}
UNIVERSAL_T0_AUDIT_OUTPUTS = {
    "one_body_duplicate_orientation_records_skipped",
    "one_body_duplicate_max_abs_difference",
    "one_body_duplicate_max_rel_difference",
    "one_body_symmetry_conflict_records",
    "two_body_input_record_count", "two_body_unique_record_count",
    "two_body_duplicate_orientation_records_skipped",
    "two_body_duplicate_max_abs_difference",
    "two_body_duplicate_max_rel_difference",
    "two_body_symmetry_conflict_records", "U_eff_over_W_reason",
    "fcidump_symmetry_status", "fcidump_symmetry_atol",
    "fcidump_symmetry_rtol", "universal_t0_linear_features_version",
    "fcidump_container_format", "fcidump_container_member",
    "fcidump_ms2_source",
}
UNIVERSAL_T0_INV_MODEL = {
    "effective_h1_frobenius_norm", "bare_one_body_bandwidth",
    "bare_one_body_gap_alpha", "bare_one_body_gap_beta",
    "bare_one_body_gap_min",
}
UNIVERSAL_T0_BAS_MODEL = {
    "fermionic_coefficient_l1_norm", "effective_h1_entrywise_l1_norm",
    "effective_h1_l1_over_frobenius", "eri_l1_over_frobenius",
    "rho_offdiag", "U_eff_over_W",
    *{
        f"{prefix}_fraction_above_rel_1e_{exponent}"
        for prefix in ("effective_h1", "eri")
        for exponent in (12, 10, 8, 6, 4, 2)
    },
}

P1B_MODEL = {
    "det_coupling_scale", "det_coupling_nonzero_degree",
    "det_coupling_participation_ratio", "det_coupling_tail_loglog_slope",
    *{f"det_coupling_count_above_rel_1e_{exponent}" for exponent in (12, 10, 8, 6, 4, 2)},
    *{f"det_coupling_top_{top_k}_l2_mass_fraction" for top_k in (1, 10, 100)},
    *{f"random_det_expected_degree_rel_1e_{exponent}" for exponent in (12, 10, 8, 6, 4, 2)},
}
P1B_AUDIT = {
    "det_coupling_reference", "det_coupling_reference_boundary_tie",
    "random_det_branching_seed",
    "random_det_branching_determinants",
    "random_det_branching_excitation_samples_per_class",
    "random_det_branching_double_method",
    "random_det_branching_exact_double_max_eri_records",
    "determinant_coupling_features_version",
    *{f"random_det_expected_degree_mc_se_rel_1e_{exponent}" for exponent in (12, 10, 8, 6, 4, 2)},
}
P1B_LEGACY_AUDIT = {"random_det_branching_excitation_samples_per_det"}

P1C_RETAG_BAS_ORD_MODEL = {
    *{f"cut_weight_{name}_{metric}" for name in ("rcm", "minimum_degree") for metric in ("max", "p95", "sum")},
    *{f"cut_weight_heuristic_spread_{metric}" for metric in ("max", "p95", "sum")},
    *{f"cut_weight_{name}_{metric}" for name in ("fiedler", "linear_relaxation", "best") for metric in ("max", "p95", "sum")},
    "min_fill_width_upper_bound",
}
P1C_BAS_MODEL = {
    "interaction_graph_edge_count", "interaction_graph_total_weight",
    "min_fill_width_upper_bound",
    *{f"cut_weight_{name}_{metric}" for name in ("fiedler", "rcm", "minimum_degree", "linear_relaxation", "best") for metric in ("max", "p95", "sum")},
    *{f"cut_weight_heuristic_spread_{metric}" for metric in ("max", "p95", "sum")},
} - P1C_RETAG_BAS_ORD_MODEL
P1C_BAS_ORD_MODEL = {
    *{f"cut_weight_{name}_{metric}" for name in ("file", "random") for metric in ("max", "p95", "sum")},
    *{f"cut_weight_improvement_vs_{name}_{metric}" for name in ("file", "random") for metric in ("max", "p95", "sum")},
    "mpo_pair_rank_max", "mpo_pair_rank_p95", "mpo_pair_rank_mean",
    *P1C_RETAG_BAS_ORD_MODEL,
}
P1C_AUDIT = {
    "orderability_random_seed", "orderability_features_version",
    "orderability_laplacian_lambda23_relative_split",
    "orderability_laplacian_lambda23_split_applicable",
    "orderability_fiedler_min_coordinate_gap",
    "orderability_degeneracy_features_version",
    "mpo_ordering_heuristic", "mpo_pair_rank_applicable",
    *{f"cut_weight_best_{metric}_heuristic" for metric in ("max", "p95", "sum")},
}
P1D_MODEL = {
    "interaction_spectrum_effective_rank",
    "interaction_spectrum_participation_rank",
    "interaction_spectrum_decay_exponent",
    "interaction_spectrum_relative_gap",
    *{f"interaction_spectrum_rank_rel_1e_{exponent}" for exponent in (2, 4, 6)},
}
P1D_AUDIT = {
    "interaction_spectrum_negative_mass_fraction",
    "interaction_spectrum_max_abs_eigenvalue",
    "interaction_spectrum_pair_dimension",
    "interaction_spectrum_active_pair_dimension",
    "interaction_spectrum_zero_rtol",
    "interaction_spectrum_zero_atol",
    "interaction_spectrum_features_version",
}

def metadata_for_column(column: str) -> FeatureColumnMetadata:
    """Return explicit P0 metadata; unknown columns fail closed."""
    if column in IDENTIFIERS:
        return _audit(column, "identifier", "identifier or split-group metadata")
    if column in PROCEDURAL:
        return _audit(column, "procedural", "procedural, status, reason, or version metadata")
    if column in DUPLICATE_SIZE:
        return _feature(column, "T0", "INV", eligible=False,
            reason="duplicate structured-detector copy; canonical size columns are n_orbs/n_elec and header MS2",
            definition=f"audit duplicate {column}")
    if column in {"n_elec", "n_orbs", "log_fci_dim"}:
        definition = {
            "n_elec": "FCIDUMP NELEC", "n_orbs": "FCIDUMP NORB",
            "log_fci_dim": "log10[C(N,n_alpha) C(N,n_beta)] with n_alpha=(NELEC+MS2)/2",
        }[column]
        return _feature(
            column,
            "T0",
            "INV",
            cost="header",
            definition=definition,
        )
    if column in LEGACY_JW_ARCHIVE:
        return _feature(column, "T0", "BAS+ORD", eligible=False,
            reason="legacy Jordan-Wigner/archive quantity superseded or identified as a mapping artifact",
            role="audit-only", scaling="archive", cost="legacy_jw")
    if column in LEGACY_JW_MODEL:
        return _feature(column, "T0", "BAS+ORD", role="representation-sensitivity",
            cost="legacy_jw", definition=f"legacy Jordan-Wigner hypergraph statistic: {column}")
    if column in DF_MODEL:
        return _feature(column, "T0", "INV", cost="df_spectrum",
            definition=("gap between the two largest pair-space ERI eigenvalues; not an energy gap" if column == "df_gap" else column.replace("_", " ")))
    if column in DF_AUDIT:
        return _feature(column, "T0", "INV", eligible=False,
            reason="raw spectrum or fit-quality diagnostic, retained for audit", role="audit-only",
            scaling="diagnostic", cost="df_spectrum")
    if column in SOLVER_DERIVED:
        tier = "T3" if column.startswith("ccsd_") else ("T2" if column.startswith("mp2_") else "T1")
        return _feature(column, tier, "BAS", protocol="MF-PROTO", eligible=False,
            reason="legacy value was parsed from panel solver output; P1/P2 recompute independently from the Hamiltonian",
            role="audit-only", cost="solver_output_postprocess")
    if column in REPRESENTATION_MODEL:
        return _feature(column, "T0", "BAS", role="representation-sensitivity")
    if column in REPRESENTATION_AUDIT:
        tier = "T3" if column == "fci_energy_hartree" else "T0"
        return _feature(column, tier, "INV", eligible=False,
            reason="representation-pair certificate field or correlated reference, retained for audit",
            role="audit-only")
    if column in FRAGMENT_MODEL:
        return _feature(column, "T0", "BAS", role="accuracy")
    if column in FRAGMENT_AUDIT:
        return _feature(column, "T0", "N/A", eligible=False,
            reason="oracle or planted fragmentation parameter", role="audit-only")
    if column in SIGN_METADATA:
        return _feature(column, "T0", "GAUGE", eligible=False,
            reason="metadata-inherited sign flag; model eligibility requires P1 recomputation from FCIDUMP",
            role="audit-only")
    if column in PAIR_T0_MODEL:
        representation = "INV" if column == "eri_full_l2_norm" else "BAS"
        return _feature(column, "T0", representation)
    if column in PAIR_T1_MODEL:
        return _feature(column, "T1", "BAS", protocol="MF-PROTO")
    if column in PAIR_T2_MODEL:
        return _feature(column, "T2", "BAS", protocol="MF-PROTO")
    if column in PAIR_AUDIT:
        return _feature(column, "T0", "BAS", eligible=False,
            reason="parser or mean-field procedural diagnostic", role="audit-only")
    if column in UNIVERSAL_T0_INV_MODEL:
        return _feature(column, "T0", "INV", cost="integral_linear")
    if column in P1B_MODEL:
        return _feature(column, "T0", "BAS+ORD", cost="determinant_coupling")
    if column in P1B_AUDIT | P1B_LEGACY_AUDIT:
        representation = (
            "BAS+ORD" if column == "det_coupling_reference_boundary_tie" else "BAS"
        )
        return _feature(column, "T0", representation, eligible=False,
            reason="deterministic reference, Monte Carlo configuration, uncertainty, or extractor version",
            role="audit-only", cost="determinant_coupling")
    if column in P1C_BAS_MODEL:
        return _feature(column, "T0", "BAS", cost="orderability")
    if column in P1C_BAS_ORD_MODEL:
        return _feature(column, "T0", "BAS+ORD", cost="orderability")
    if column in P1C_AUDIT:
        representation = "BAS" if column == "mpo_pair_rank_applicable" else "BAS+ORD"
        return _feature(column, "T0", representation, eligible=False,
            reason="ordering choice, random seed, or extractor version",
            role="audit-only", cost="orderability")
    if column in P1D_MODEL:
        return _feature(column, "T0", "INV", cost="exact_pair_spectrum")
    if column in P1D_AUDIT:
        return _feature(
            column,
            "T0",
            "INV",
            eligible=False,
            reason="exact-spectrum scale, applicability, tolerance, non-PSD, or version diagnostic",
            role="audit-only",
            cost="exact_pair_spectrum",
        )
    if column in UNIVERSAL_T0_BAS_MODEL:
        return _feature(column, "T0", "BAS", cost="integral_linear")
    raise KeyError(f"G-40 P0 has no metadata classification for column {column!r}")

PLANNED_COLUMNS = {
    column: metadata_for_column(column)
    for column in sorted(
        UNIVERSAL_T0_INV_MODEL
        | UNIVERSAL_T0_BAS_MODEL
        | UNIVERSAL_T0_AUDIT_OUTPUTS
        | P1B_MODEL
        | P1B_AUDIT
        | P1C_BAS_MODEL
        | P1C_BAS_ORD_MODEL
        | P1C_AUDIT
        | P1D_MODEL
        | P1D_AUDIT
    )
}
PLANNED_COLUMNS["fermionic_coefficient_l1_norm"] = _feature(
    "fermionic_coefficient_l1_norm", "T0", "BAS", scaling="extensive",
    cost="integral_linear", status="defined_not_populated",
    definition="sum_pq |h_tilde_pq| + 1/2 sum_pqrs |(pq|rs)|",
)
PLANNED_COLUMNS = {
    name: FeatureColumnMetadata(
        **{
            **metadata.to_dict(),
            "implementation_status": "defined_not_populated",
        }
    )
    for name, metadata in PLANNED_COLUMNS.items()
}

def metadata_catalog(columns: Iterable[str], include_planned: bool = True) -> list[FeatureColumnMetadata]:
    column_list = list(columns)
    result = [metadata_for_column(column) for column in column_list]
    if include_planned:
        current_names = set(column_list)
        result.extend(
            metadata for name, metadata in PLANNED_COLUMNS.items()
            if name not in current_names
        )
    names = [row.column for row in result]
    if len(names) != len(set(names)):
        raise ValueError("duplicate columns in feature metadata catalog")
    return result

def model_eligible_columns(columns: Iterable[str]) -> list[str]:
    return [
        row.column
        for row in metadata_catalog(columns, include_planned=False)
        if row.model_eligible and row.implementation_status == "current"
    ]
