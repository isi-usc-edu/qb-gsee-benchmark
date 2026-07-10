# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Metadata detector for selected sign-free lattice-model conditions."""

from __future__ import annotations

from typing import Any, Mapping

SIGN_FREE_FEATURES_VERSION = "g23_sign_free_detector_v1"
SIGN_FREE_FEATURE_COLUMNS = (
    "lattice_model_family",
    "lattice_bipartite",
    "lattice_filling_electrons_per_site",
    "interaction_sign",
    "sign_free_condition_flag",
    "sign_free_condition",
    "sign_free_detector_version",
)


def _first_value(*values: object) -> object | None:
    return next((value for value in values if value is not None), None)


def detect_sign_free_features(
    *,
    lattice_model_family: str,
    bipartite: bool,
    filling: float | None,
    interaction: float | None,
    ms2: int,
    spinless: bool = False,
) -> dict[str, Any]:
    """Classify only the explicitly preregistered G-23 sign-free cases."""
    sign = (
        "unknown"
        if interaction is None
        else "negative"
        if interaction < 0
        else "positive"
        if interaction > 0
        else "zero"
    )
    half_filled = filling is not None and abs(float(filling) - 1.0) < 1.0e-12
    spin_balanced = int(ms2) == 0
    if spinless:
        sign_free = False
        condition = "no_general_sign_free_condition_for_2d_spinless_t_v"
    elif sign == "negative" and spin_balanced:
        sign_free = True
        condition = "attractive_hubbard_spin_balanced_any_filling"
    elif sign == "positive" and bipartite and half_filled:
        sign_free = True
        condition = "repulsive_hubbard_half_filled_bipartite"
    else:
        sign_free = False
        condition = "no_selected_sign_free_condition"
    return {
        "lattice_model_family": lattice_model_family,
        "lattice_bipartite": bool(bipartite),
        "lattice_filling_electrons_per_site": filling,
        "interaction_sign": sign,
        "sign_free_condition_flag": sign_free,
        "sign_free_condition": condition,
        "sign_free_detector_version": SIGN_FREE_FEATURES_VERSION,
    }


def detect_hubbard_task(
    instance: Mapping[str, Any], task: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Extract a G-23 Hubbard detector record from public task metadata."""
    features = task.get("features", {})
    independent = task.get("independent_parameters", {})
    model_text = " ".join(
        str(value).lower()
        for value in (
            instance.get("short_name"),
            features.get("model"),
            features.get("hamiltonian_family"),
        )
        if value is not None
    )
    if "hubbard" not in model_text:
        return None
    num_sites = _first_value(
        features.get("hubbard_num_sites"),
        independent.get("num_sites"),
        features.get("num_orbitals"),
        independent.get("num_orbitals"),
    )
    num_electrons = _first_value(
        features.get("num_electrons"),
        independent.get("num_electrons"),
        independent.get("nelec"),
    )
    filling = features.get("hubbard_filling_electrons_per_site")
    if filling is None and num_sites is not None and num_electrons is not None:
        filling = float(num_electrons) / float(num_sites)
    interaction = _first_value(
        features.get("onsite_u_hartree"),
        independent.get("onsite_u_hartree"),
        features.get("u_over_t"),
        independent.get("u_over_t"),
        independent.get("coupling_value"),
    )
    geometry_text = " ".join(
        str(value).lower()
        for value in (
            features.get("geometry"),
            features.get("boundary_condition"),
            instance.get("short_name"),
        )
        if value is not None
    )
    return detect_sign_free_features(
        lattice_model_family="hubbard",
        bipartite=any(
            token in geometry_text for token in ("chain", "square", "ca2cuo3")
        ),
        filling=None if filling is None else float(filling),
        interaction=None if interaction is None else float(interaction),
        ms2=int(_first_value(features.get("ms2"), independent.get("ms2"), 0)),
    )
