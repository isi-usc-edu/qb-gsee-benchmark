"""Artifact orchestration for the predeclared ML-3 robustness rerun."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.interim import (
    MODEL_LABELS,
    load_instance_tasks,
    load_pinned_inputs,
    majority_oof,
    oof_probabilities,
    scored_label_frame,
    sha256_file,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.interim_runner import _cell_data
from qb_gsee_benchmark.ml.interim_v2 import (
    INTERIM_STATEMENT,
    family_balanced_scores_v2,
    holm_bonferroni,
    paired_family_bootstrap,
)


def _baseline_probabilities(data: pd.DataFrame, protocol: str) -> dict[str, np.ndarray]:
    log_dimension, _ = oof_probabilities(
        data, ["log_fci_dim"], "size_log_dimension", protocol, {}
    )
    spline, _ = oof_probabilities(
        data, ["n_elec", "n_orbs"], "size_spline_gate", protocol, {}
    )
    return {
        "majority_class": majority_oof(data, protocol),
        "size_log_dimension": log_dimension,
        "size_spline_gate": spline,
    }


def _feature_spec(
    manifest: Mapping[str, Any], feature_set: str
) -> tuple[list[str], set[str] | None]:
    universal = list(manifest["features"]["universal_core"]["columns"])
    if feature_set == "universal_core":
        return universal, None
    extension = next(
        row
        for row in manifest["features"]["domain_extensions"]
        if row["name"] == feature_set
    )
    return universal + list(extension["columns"]), set(extension["task_uuids"])


def _comparison_id(record: Mapping[str, Any], prefix: str) -> str:
    fields = [
        prefix,
        record["solver"],
        record["campaign"],
        record["feature_set"],
        record.get("protocol", "leave_one_family_out"),
        record["model"],
        record.get("class_treatment", "full_class"),
        record.get("identifier_screen", "with_identifiers"),
    ]
    return "|".join(map(str, fields))


def _delta_record(
    identity: Mapping[str, Any], paired: Mapping[str, Any], family: str
) -> dict[str, Any]:
    composite = paired["size_composite_average_precision"]
    record = dict(identity)
    record.update(
        {
            "comparison_family": family,
            "comparison_id": _comparison_id(identity, family),
            "point_improvement": composite["point_improvement"],
            "lower_95": composite["lower_95"],
            "upper_95": composite["upper_95"],
            "two_sided_p": composite["two_sided_p"],
            "resamples": composite["resamples"],
            "paired_deltas": paired,
        }
    )
    return record


def _prediction_payload(prior: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) | {"interim": True} for row in prior]


def _evaluate_historical(
    manifest: Mapping[str, Any],
    prior_results: Sequence[Mapping[str, Any]],
    features: pd.DataFrame,
    labels: pd.DataFrame,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    evaluations = []
    all_deltas = []
    gate_deltas = []
    contexts: dict[str, dict[str, Any]] = {}
    grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = {}
    for row in prior_results:
        key = tuple(
            str(row[field])
            for field in ("solver", "campaign", "feature_set", "protocol")
        )
        grouped.setdefault(key, []).append(row)
    grids = manifest["models"]["hyperparameter_grids"]
    resamples = int(manifest["paired_delta_gate"]["resamples"])
    for key in sorted(grouped):
        solver, campaign, feature_set, protocol = key
        source_rows = sorted(grouped[key], key=lambda row: str(row["model"]))
        columns, task_filter = _feature_spec(manifest, feature_set)
        data = _cell_data(labels, features, solver, campaign, task_filter)
        ok_rows = [row for row in source_rows if row["status"] == "ok"]
        if not ok_rows:
            evaluations.extend([dict(row) | {"interim": True} for row in source_rows])
            continue
        baselines = _baseline_probabilities(data, protocol)
        for source in source_rows:
            if source["status"] != "ok":
                evaluations.append(dict(source) | {"interim": True})
                continue
            model = str(source["model"])
            probabilities, _ = oof_probabilities(
                data, columns, model, protocol, grids.get(model, {})
            )
            paired = paired_family_bootstrap(
                data, probabilities, baselines, resamples=resamples
            )
            identity = {
                "solver": solver,
                "campaign": campaign,
                "feature_set": feature_set,
                "protocol": protocol,
                "model": model,
                "class_treatment": "full_class",
                "identifier_screen": "with_identifiers",
            }
            delta = _delta_record(identity, paired, "historical_lofo")
            evaluations.append(
                dict(source)
                | {
                    "interim": True,
                    "macro_ap_v2": paired["model_scores"],
                    "baseline_scores_v2": paired["baseline_scores"],
                    "paired_deltas": paired,
                }
            )
            all_deltas.append(delta)
            if protocol == "leave_one_family_out":
                gate_deltas.append(delta)
                contexts[delta["comparison_id"]] = {
                    "data": data,
                    "columns": columns,
                    "model": model,
                    "protocol": protocol,
                    "grid": grids.get(model, {}),
                    "labels": list(MODEL_LABELS),
                    "observed": delta["point_improvement"],
                }
            else:
                delta["comparison_family"] = "historical_diagnostic_excluded"
                delta["comparison_id"] = _comparison_id(
                    identity, "historical_diagnostic_excluded"
                )
                delta["multiplicity_exclusion"] = "random-fold leakage diagnostic only"
                delta["holm_adjusted_p"] = None
                delta["passes_multiplicity"] = False
                delta["passes_paired_gate"] = False
    adjusted = holm_bonferroni(gate_deltas)
    adjusted_lookup = {row["comparison_id"]: row for row in adjusted}
    all_deltas = [adjusted_lookup.get(row["comparison_id"], row) for row in all_deltas]
    lookup = {row["comparison_id"]: row for row in adjusted}
    for evaluation in evaluations:
        if (
            evaluation.get("status") == "ok"
            and evaluation.get("protocol") == "leave_one_family_out"
        ):
            identity = {
                "solver": evaluation["solver"],
                "campaign": evaluation["campaign"],
                "feature_set": evaluation["feature_set"],
                "protocol": evaluation["protocol"],
                "model": evaluation["model"],
                "class_treatment": "full_class",
                "identifier_screen": "with_identifiers",
            }
            evaluation["paired_gate"] = lookup[
                _comparison_id(identity, "historical_lofo")
            ]
    return evaluations, all_deltas, adjusted, contexts


def _evaluate_shci(
    manifest: Mapping[str, Any], features: pd.DataFrame, labels: pd.DataFrame
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    records = []
    contexts: dict[str, dict[str, Any]] = {}
    universal = list(manifest["features"]["universal_core"]["columns"])
    identifiers = set(manifest["family_identifier_screen"]["identifier_columns"])
    grids = manifest["models"]["hyperparameter_grids"]
    resamples = int(manifest["paired_delta_gate"]["resamples"])
    for cell in manifest["sensitivity_plan"]["shci_var_cells"]:
        original = _cell_data(labels, features, cell["solver"], cell["campaign"])
        for treatment, treatment_labels in manifest["sensitivity_plan"][
            "class_treatments"
        ].items():
            data = original[original["outcome"].isin(treatment_labels)].reset_index(
                drop=True
            )
            for screen in manifest["sensitivity_plan"]["identifier_column_sets"]:
                columns = (
                    universal
                    if screen == "with_identifiers"
                    else [column for column in universal if column not in identifiers]
                )
                baselines = _baseline_probabilities(data, "leave_one_family_out")
                for model in manifest["sensitivity_plan"]["models"]:
                    probabilities, _ = oof_probabilities(
                        data,
                        columns,
                        model,
                        "leave_one_family_out",
                        grids.get(model, {}),
                    )
                    paired = paired_family_bootstrap(
                        data,
                        probabilities,
                        baselines,
                        labels=treatment_labels,
                        resamples=resamples,
                    )
                    identity = {
                        "solver": cell["solver"],
                        "campaign": cell["campaign"],
                        "feature_set": "universal_core",
                        "protocol": "leave_one_family_out",
                        "model": model,
                        "class_treatment": treatment,
                        "identifier_screen": screen,
                    }
                    delta = _delta_record(identity, paired, "shci_confirmatory")
                    records.append(delta)
                    contexts[delta["comparison_id"]] = {
                        "data": data,
                        "columns": columns,
                        "model": model,
                        "protocol": "leave_one_family_out",
                        "grid": grids.get(model, {}),
                        "labels": list(treatment_labels),
                        "observed": delta["point_improvement"],
                    }
    return holm_bonferroni(records), contexts


def _shuffle_nulls(
    manifest: Mapping[str, Any],
    gate_records: Sequence[Mapping[str, Any]],
    contexts: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output = []
    permutations = int(manifest["shuffle_null"]["permutations"])
    seed = int(manifest["seeds"]["shuffle"])
    for record in gate_records:
        if not record.get("passes_paired_gate"):
            continue
        context = contexts[record["comparison_id"]]
        null_values = []
        for permutation in range(permutations):
            shuffled = context["data"].copy()
            rng = np.random.default_rng(seed + permutation)
            shuffled["outcome"] = shuffled.groupby("family", sort=True)[
                "outcome"
            ].transform(lambda values: rng.permutation(values.to_numpy()))
            model_probabilities, _ = oof_probabilities(
                shuffled,
                context["columns"],
                context["model"],
                context["protocol"],
                context["grid"],
            )
            baselines = _baseline_probabilities(shuffled, context["protocol"])
            model_ap = family_balanced_scores_v2(
                shuffled, model_probabilities, labels=context["labels"]
            )["average_precision"]
            size_aps = [
                family_balanced_scores_v2(shuffled, value, labels=context["labels"])[
                    "average_precision"
                ]
                for name, value in baselines.items()
                if name.startswith("size_")
            ]
            null_values.append(
                None
                if model_ap is None or any(value is None for value in size_aps)
                else float(model_ap - max(size_aps))
            )
        finite = [value for value in null_values if value is not None]
        output.append(
            {
                "comparison_id": record["comparison_id"],
                "observed_point_improvement": context["observed"],
                "permutation_point_improvements": null_values,
                "survives_shuffle_null": bool(
                    finite
                    and context["observed"] is not None
                    and context["observed"] > max(finite)
                ),
            }
        )
    return output


def bundle_schema_v2() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "ml_v2_interim_2.schema.json",
        "type": "object",
        "required": [
            "bundle_version",
            "interim",
            "adjudication",
            "evaluations",
            "per_task_predictions",
            "paired_delta_results",
            "identifier_screen",
            "shuffle_nulls",
        ],
        "properties": {
            "bundle_version": {"const": "ml-v2-interim-2"},
            "interim": {"const": True},
            "adjudication": {"type": "object"},
            "evaluations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["interim"],
                    "properties": {"interim": {"const": True}},
                },
            },
            "per_task_predictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["interim"],
                    "properties": {"interim": {"const": True}},
                },
            },
            "paired_delta_results": {"type": "object"},
            "identifier_screen": {"type": "object"},
            "shuffle_nulls": {"type": "array"},
        },
        "additionalProperties": True,
    }


def run_interim_v2_evaluation(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != "ml-v2-interim-2":
        raise ValueError("Refusing ML-3 run without manifest_v2")
    features, _, metrics = load_pinned_inputs(repo_root)
    labels = scored_label_frame(
        metrics, load_instance_tasks(repo_root / "problem_instances")
    )
    prior_results = json.loads((repo_root / "analysis/ml_v2/results.json").read_text())
    prior_predictions = json.loads(
        (repo_root / "analysis/ml_v2/predictions.json").read_text()
    )
    evaluations, historical_all, historical_gate, historical_contexts = (
        _evaluate_historical(manifest, prior_results, features, labels)
    )
    shci, shci_contexts = _evaluate_shci(manifest, features, labels)
    contexts = historical_contexts | shci_contexts
    shuffle = _shuffle_nulls(manifest, historical_gate + shci, contexts)
    paired_payload = {
        "protocol": manifest["paired_delta_gate"],
        "historical_all_scored": historical_all,
        "historical_gate_family": historical_gate,
        "shci_confirmatory": shci,
    }
    analysis = repo_root / "analysis/ml_v2"
    stable_json_dump(paired_payload, analysis / "paired_deltas.json")
    stable_json_dump(shuffle, analysis / "shuffle_nulls.json")
    stable_json_dump(
        manifest["family_identifier_screen"], analysis / "identifier_screen.json"
    )
    prior_bundle = json.loads(
        (repo_root / "scripts/dashboard_data/ml_v2_interim_1.json").read_text()
    )
    predictions = _prediction_payload(prior_predictions)
    bundle = dict(prior_bundle) | {
        "$schema": "ml_v2_interim_2.schema.json",
        "bundle_version": "ml-v2-interim-2",
        "interim": True,
        "manifest_sha256": sha256_file(manifest_path),
        "adjudication": manifest["adjudication"],
        "evaluations": evaluations,
        "per_task_predictions": predictions,
        "paired_delta_results": paired_payload,
        "identifier_screen": manifest["family_identifier_screen"],
        "shci_var_investigation": shci,
        "shuffle_nulls": shuffle,
    }
    dashboard = repo_root / "scripts/dashboard_data"
    stable_json_dump(bundle, dashboard / "ml_v2_interim_2.json")
    stable_json_dump(bundle_schema_v2(), dashboard / "ml_v2_interim_2.schema.json")
    survivors = [row for row in historical_gate + shci if row["passes_paired_gate"]]
    shuffle_survivors = [row for row in shuffle if row["survives_shuffle_null"]]
    n_identifiers = len(manifest["family_identifier_screen"]["identifier_columns"])
    n_shuffle_survivors = len(shuffle_survivors)
    readme = "\n".join(
        [
            "# INTERIM (pre-mean-field feature set): ML v2",
            "",
            "ML-1/ML-2 artifacts are retained; bundle v2 supersedes bundle v1.",
            "",
            f"- Goals-review 13: {manifest['adjudication']['legacy_flag_disposition']}",
            f"- Interim statement: {INTERIM_STATEMENT}",
            f"- Family-identifier columns: {n_identifiers}",
            f"- Historical paired results (all scored): {len(historical_all)}",
            f"- Historical LOFO gate comparisons: {len(historical_gate)}",
            f"- SHCI_var confirmatory comparisons: {len(shci)}",
            f"- Multiplicity-controlled paired-gate survivors: {len(survivors)}",
            f"- Paired-gate survivors clearing shuffle null: {n_shuffle_survivors}",
            "",
        ]
    )
    (analysis / "README.md").write_text(readme, encoding="utf-8")
    return {
        "n_evaluations": len(evaluations),
        "n_predictions": len(predictions),
        "n_historical_paired_results": len(historical_all),
        "n_historical_gate_comparisons": len(historical_gate),
        "n_shci_comparisons": len(shci),
        "n_paired_gate_survivors": len(survivors),
        "n_shuffle_survivors": len(shuffle_survivors),
    }
