# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Audit-only applicability flags introduced by G40 retag wave R."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qb_gsee_benchmark.features.determinant_coupling_features import (
    diagonal_reference_boundary_tie,
)
from qb_gsee_benchmark.features.fcidump_sparse import (
    SparseFcidump,
    read_sparse_fcidump,
)
from qb_gsee_benchmark.features.orderability_features import (
    mpo_pair_rank_applicable,
)

RETAG_AUDIT_VERSION = "g40_retag_audit_v1"


def compute_retag_audit_features(
    source: str | Path | SparseFcidump,
    *,
    ms2_override: int | None = None,
) -> dict[str, Any]:
    data = (
        source
        if isinstance(source, SparseFcidump)
        else read_sparse_fcidump(source, ms2_override=ms2_override)
    )
    return {
        "det_coupling_reference_boundary_tie": diagonal_reference_boundary_tie(data),
        "mpo_pair_rank_applicable": mpo_pair_rank_applicable(data),
        "retag_audit_features_version": RETAG_AUDIT_VERSION,
    }
