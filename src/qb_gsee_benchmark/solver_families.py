# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Versioned solver-family and parameterized-variant metadata."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

SOLVER_FAMILY_CATALOG_RELATIVE_PATH = Path(
    "analysis/solver_taxonomy/solver_families.v1.json"
)
DEFAULT_SOLVER_FAMILY_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / SOLVER_FAMILY_CATALOG_RELATIVE_PATH
)
FAMILY_UUID_PREFIX = "qb-gsee-benchmark:solver-family:"


@dataclass(frozen=True)
class SolverVariantMetadata:
    """Resolved metadata for one concrete solver UUID."""

    family_id: str
    family_uuid: str
    family_display_name: str
    solver_uuid: str
    solver_short_name: str
    variant_id: str
    variant_display_name: str
    implementation_id: str
    result_semantics: str
    catalog_status: str
    resource_axis: Mapping[str, Any] | None

    def as_attempt_fields(self) -> dict[str, Any]:
        """Return flat fields suitable for metrics, ML, and dashboard rows."""

        axis = self.resource_axis or {}
        return {
            "solver_uuid": self.solver_uuid,
            "solver_family_id": self.family_id,
            "solver_family_uuid": self.family_uuid,
            "solver_family_display_name": self.family_display_name,
            "solver_variant_id": self.variant_id,
            "solver_variant_short_name": self.solver_short_name,
            "solver_variant_display_name": self.variant_display_name,
            "solver_implementation_id": self.implementation_id,
            "solver_result_semantics": self.result_semantics,
            "solver_catalog_status": self.catalog_status,
            "solver_resource_ladder_id": axis.get("ladder_id"),
            "solver_resource_axis_name": axis.get("name"),
            "solver_resource_value": axis.get("value"),
            "solver_resource_units": axis.get("units"),
            "solver_resource_rank": axis.get("rank"),
        }


class SolverFamilyCatalog:
    """Validated lookup over the canonical solver-family catalog."""

    def __init__(self, document: Mapping[str, Any]):
        _validate_document(document)
        self.document = dict(document)
        self.families = {
            str(row["solver_family_id"]): dict(row) for row in document["families"]
        }
        self.variants = {
            str(row["solver_uuid"]): dict(row) for row in document["variants"]
        }

    def resolve(
        self, solver_uuid: str, solver_short_name: str | None = None
    ) -> SolverVariantMetadata:
        """Resolve an exact solver UUID and optionally cross-check its name."""

        try:
            variant = self.variants[str(solver_uuid)]
        except KeyError as exc:
            raise KeyError(
                f"solver UUID is absent from solver_families.v1: {solver_uuid}"
            ) from exc
        registered_name = str(variant["solver_short_name"])
        if solver_short_name is not None and str(solver_short_name) != registered_name:
            raise ValueError(
                "solver-family UUID/name mismatch: "
                f"{solver_uuid} is {registered_name!r}, not {solver_short_name!r}"
            )
        family = self.families[str(variant["solver_family_id"])]
        axis = variant.get("resource_axis")
        return SolverVariantMetadata(
            family_id=str(family["solver_family_id"]),
            family_uuid=str(family["solver_family_uuid"]),
            family_display_name=str(family["display_name"]),
            solver_uuid=str(variant["solver_uuid"]),
            solver_short_name=registered_name,
            variant_id=str(variant["solver_variant_id"]),
            variant_display_name=str(variant["display_name"]),
            implementation_id=str(variant["implementation_id"]),
            result_semantics=str(variant["result_semantics"]),
            catalog_status=str(variant["catalog_status"]),
            resource_axis=dict(axis) if isinstance(axis, Mapping) else None,
        )


def _require_uuid(value: Any, context: str) -> str:
    text = str(value)
    try:
        parsed = uuid.UUID(text)
    except ValueError as exc:
        raise ValueError(f"{context} is not a UUID: {text!r}") from exc
    if str(parsed) != text:
        raise ValueError(f"{context} is not a canonical UUID: {text!r}")
    return text


def _validate_document(document: Mapping[str, Any]) -> None:
    if (
        document.get("catalog_id") != "solver_families_v1"
        or document.get("schema_version") != 1
        or document.get("status") != "effective"
    ):
        raise ValueError("solver-family catalog identity/status is invalid")
    families = document.get("families")
    variants = document.get("variants")
    if not isinstance(families, list) or not isinstance(variants, list):
        raise ValueError("solver-family catalog requires family and variant arrays")

    family_ids: set[str] = set()
    family_uuids: set[str] = set()
    for family in families:
        if not isinstance(family, Mapping):
            raise ValueError("solver-family rows must be objects")
        family_id = str(family.get("solver_family_id", ""))
        family_uuid = _require_uuid(
            family.get("solver_family_uuid"), f"family {family_id} UUID"
        )
        expected_uuid = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"{FAMILY_UUID_PREFIX}{family_id}:v1")
        )
        if family_uuid != expected_uuid:
            raise ValueError(f"family {family_id} UUID is not deterministic")
        if not family_id or family_id in family_ids or family_uuid in family_uuids:
            raise ValueError(f"duplicate or empty solver family: {family_id!r}")
        if not all(
            isinstance(family.get(key), str) and family[key]
            for key in ("display_name", "method_class", "description")
        ):
            raise ValueError(f"family {family_id} has incomplete display metadata")
        family_ids.add(family_id)
        family_uuids.add(family_uuid)

    solver_uuids: set[str] = set()
    variant_keys: set[tuple[str, str]] = set()
    ladders: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for variant in variants:
        if not isinstance(variant, Mapping):
            raise ValueError("solver-variant rows must be objects")
        solver_uuid = _require_uuid(variant.get("solver_uuid"), "solver variant UUID")
        family_id = str(variant.get("solver_family_id", ""))
        variant_id = str(variant.get("solver_variant_id", ""))
        key = (family_id, variant_id)
        if family_id not in family_ids:
            raise ValueError(
                f"variant {variant_id} references unknown family {family_id}"
            )
        if solver_uuid in solver_uuids or key in variant_keys or not variant_id:
            raise ValueError(f"duplicate or empty solver variant: {key}")
        if not all(
            isinstance(variant.get(field), str) and variant[field]
            for field in (
                "solver_short_name",
                "display_name",
                "implementation_id",
                "result_semantics",
            )
        ):
            raise ValueError(f"variant {key} has incomplete display metadata")
        if variant.get("catalog_status") not in {"committed", "reserved_g50"}:
            raise ValueError(f"variant {key} has invalid catalog status")
        axis = variant.get("resource_axis")
        if axis is not None:
            if not isinstance(axis, Mapping):
                raise ValueError(f"variant {key} resource axis must be an object")
            if not all(
                field in axis
                for field in (
                    "ladder_id",
                    "name",
                    "value",
                    "units",
                    "rank",
                    "value_direction",
                )
            ):
                raise ValueError(f"variant {key} has an incomplete resource axis")
            if not isinstance(axis["value"], (int, float)) or isinstance(
                axis["value"], bool
            ):
                raise ValueError(f"variant {key} resource value must be numeric")
            if not isinstance(axis["rank"], int) or axis["rank"] < 0:
                raise ValueError(f"variant {key} resource rank must be nonnegative")
            if axis["value_direction"] not in {"increasing", "decreasing"}:
                raise ValueError(f"variant {key} resource direction is invalid")
            ladders[str(axis["ladder_id"])].append(variant)
        solver_uuids.add(solver_uuid)
        variant_keys.add(key)

    for ladder_id, members in ladders.items():
        axes = [member["resource_axis"] for member in members]
        for field in ("name", "units", "value_direction"):
            if len({axis[field] for axis in axes}) != 1:
                raise ValueError(f"ladder {ladder_id} mixes {field}")
        if len({member["solver_family_id"] for member in members}) != 1:
            raise ValueError(f"ladder {ladder_id} crosses solver families")
        ordered = sorted(axes, key=lambda axis: axis["rank"])
        if [axis["rank"] for axis in ordered] != list(range(len(ordered))):
            raise ValueError(f"ladder {ladder_id} ranks are not contiguous")
        values = [float(axis["value"]) for axis in ordered]
        if len(set(values)) != len(values):
            raise ValueError(f"ladder {ladder_id} resource values are duplicated")
        direction = ordered[0]["value_direction"]
        expected = sorted(values, reverse=direction == "decreasing")
        if values != expected:
            raise ValueError(f"ladder {ladder_id} values disagree with rank direction")

    counts = document.get("counts")
    actual_counts = {
        "families": len(families),
        "variants": len(variants),
        "committed_variants": sum(
            row["catalog_status"] == "committed" for row in variants
        ),
        "reserved_g50_variants": sum(
            row["catalog_status"] == "reserved_g50" for row in variants
        ),
        "resource_ladders": len(ladders),
    }
    if counts != actual_counts:
        raise ValueError(
            f"solver-family catalog counts do not recount: {counts!r} != {actual_counts!r}"
        )


def load_solver_family_catalog(
    path: str | Path = DEFAULT_SOLVER_FAMILY_CATALOG_PATH,
) -> SolverFamilyCatalog:
    """Load and validate a solver-family catalog."""

    artifact_path = Path(path)
    try:
        document = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"unparsable solver-family catalog: {artifact_path}") from exc
    if not isinstance(document, Mapping):
        raise ValueError("solver-family catalog must be a JSON object")
    return SolverFamilyCatalog(document)


def load_repository_solver_family_catalog(
    repository_root: str | Path,
) -> SolverFamilyCatalog | None:
    """Load a repository catalog when present; synthetic fixtures may omit it."""

    path = Path(repository_root) / SOLVER_FAMILY_CATALOG_RELATIVE_PATH
    return load_solver_family_catalog(path) if path.is_file() else None


def solution_solver_metadata(
    document: Mapping[str, Any],
    catalog: SolverFamilyCatalog,
) -> SolverVariantMetadata:
    """Resolve and cross-check the solver identity in one solution document."""

    solver = document.get("solver_details")
    if not isinstance(solver, Mapping):
        raise ValueError("solution document has no solver_details object")
    solver_uuid = str(solver.get("solver_uuid") or "")
    solver_short_name = str(solver.get("solver_short_name") or "")
    if not solver_uuid or not solver_short_name:
        raise ValueError("solution document has an incomplete solver identity")
    return catalog.resolve(solver_uuid, solver_short_name)


def enrich_attempts_with_solver_families(
    repository_root: str | Path,
    attempts: Sequence[Mapping[str, Any]],
    *,
    catalog: SolverFamilyCatalog | None = None,
) -> list[dict[str, Any]]:
    """Join normalized attempts to solver metadata through their source files."""

    root = Path(repository_root).resolve()
    resolved_catalog = catalog or load_repository_solver_family_catalog(root)
    if resolved_catalog is None:
        raise FileNotFoundError(
            f"solver-family catalog is absent: {root / SOLVER_FAMILY_CATALOG_RELATIVE_PATH}"
        )
    by_source: dict[str, dict[str, Any]] = {}
    output: list[dict[str, Any]] = []
    for attempt in attempts:
        source = str(attempt.get("source") or "")
        if not source:
            raise ValueError("normalized attempt has no source path for solver lookup")
        if source not in by_source:
            path = (root / source).resolve()
            if not path.is_relative_to(root):
                raise ValueError(f"attempt source escapes repository root: {source}")
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError(
                    f"unparsable solution file for solver lookup: {path}"
                ) from exc
            if not isinstance(document, Mapping):
                raise ValueError(f"solution file is not a JSON object: {path}")
            metadata = solution_solver_metadata(document, resolved_catalog)
            by_source[source] = metadata.as_attempt_fields()
        fields = by_source[source]
        if str(attempt.get("solver") or "") != fields["solver_variant_short_name"]:
            raise ValueError(
                f"normalized attempt solver disagrees with {source}: "
                f"{attempt.get('solver')!r} != {fields['solver_variant_short_name']!r}"
            )
        enriched = dict(attempt)
        for key, value in fields.items():
            if key in enriched and enriched[key] not in (None, value):
                raise ValueError(
                    f"normalized attempt has conflicting {key} for {source}"
                )
            enriched[key] = value
        output.append(enriched)
    return output
