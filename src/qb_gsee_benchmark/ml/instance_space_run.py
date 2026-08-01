"""Deterministic ML-9A Instance Space Analysis finalization."""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import platform
from collections import Counter
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from instancespace import InstanceSpace, InstanceSpaceOptions, Metadata
from instancespace.data.model import Footprint
from instancespace.data.options import (
    AutoOptions,
    BoundOptions,
    CloisterOptions,
    NormOptions,
    OutputOptions,
    ParallelOptions,
    PerformanceOptions,
    PilotOptions,
    PythiaOptions,
    SelvarsOptions,
    SiftedOptions,
    TraceOptions,
)
from instancespace.stages.cloister import CloisterStage
from instancespace.stages.pilot import PilotStage
from instancespace.stages.prelim import PrelimStage
from instancespace.stages.preprocessing import PreprocessingStage
from instancespace.stages.pythia import PythiaStage
from instancespace.stages.sifted import SiftedStage
from instancespace.stages.trace import TraceOutputs, TraceStage
from scipy.spatial.distance import cdist, pdist
from scipy.stats import pearsonr
from shapely.geometry import Polygon, mapping
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold

from qb_gsee_benchmark.ml.core_set import (
    _logical_block,
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.g50_solver_families import derive_feature_policy
from qb_gsee_benchmark.ml.instance_space import (
    EXPECTED_FAMILY_VARIANTS,
    apply_coordinate_preprocessing,
    coordinate_preprocessing,
)


FAMILY_ORDER = ("dmrg", "ipie_afqmc", "shci", "trimci")
TARGET_ORDER = (*FAMILY_ORDER, "portfolio_union")
THRESHOLD_FACTORS = (0.5, 1.0, 2.0)
PREFLIGHT_MANIFEST_SHA256 = (
    "adbeb4cfd1f05eae61b7d10b55ac83ba882742916bbede241cc7b408b0623467"
)


@dataclass(frozen=True)
class PreparedIsaData:
    preregistration: dict[str, Any]
    panel: pd.DataFrame
    features_raw: pd.DataFrame
    features_transformed: pd.DataFrame
    panel_features_transformed: pd.DataFrame
    preprocessing_parameters: pd.DataFrame
    canonical_family: pd.Series  # type: ignore[type-arg]
    gradeable: pd.Series  # type: ignore[type-arg]
    family_costs: pd.DataFrame
    all_costs: pd.DataFrame
    labels: dict[float, pd.DataFrame]
    feature_columns: tuple[str, ...]
    jw_columns: tuple[str, ...]
    input_hashes: dict[str, str]


@dataclass(frozen=True)
class ProjectionResult:
    selected_features: tuple[str, ...]
    selected_feature_matrix: np.ndarray
    projection_matrix: np.ndarray
    panel_coordinates: np.ndarray
    corpus_coordinates: np.ndarray
    z_edge: np.ndarray
    z_ecorr: np.ndarray
    toolkit_pilot_r2: np.ndarray
    topological_preservation_correlation: float


@dataclass(frozen=True)
class PythiaResult:
    gate_rows: list[dict[str, Any]]
    panel_probabilities: dict[tuple[float, str], np.ndarray]
    corpus_probabilities: dict[tuple[float, str], np.ndarray]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_input(root: Path, specification: Mapping[str, Any], label: str) -> Path:
    path = root / str(specification["path"])
    _require(path.is_file(), f"missing ML-9A input {label}: {path}")
    _require(
        sha256_file(path) == str(specification["sha256"]),
        f"changed ML-9A input {label}: {path}",
    )
    return path


def _true(series: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    return series.astype(str).str.lower().eq("true")


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def prepare_isa_data(root: Path, preregistration_path: Path) -> PreparedIsaData:
    """Load and enforce the frozen ML-9A inputs, including observed responses."""

    preregistration = _read_json(preregistration_path)
    _require(
        preregistration.get("artifact_id") == "ml9a_instance_space_preregistration_v1",
        "wrong ML-9A preregistration",
    )
    _require(
        preregistration.get("frozen_before_benchmark_fit") is True,
        "ML-9A preregistration is not frozen",
    )
    preflight_manifest = (
        root / "analysis/ml9_instance_space/preflight_v1/artifact_manifest.json"
    )
    _require(preflight_manifest.is_file(), "missing ML-9A outcome-blind preflight")
    _require(
        sha256_file(preflight_manifest) == PREFLIGHT_MANIFEST_SHA256,
        "ML-9A outcome-blind preflight changed",
    )
    preflight = _read_json(preflight_manifest)
    _require(preflight.get("status") == "pass", "ML-9A preflight did not pass")
    _require(
        preflight.get("scientific_outcomes_consumed") is False,
        "ML-9A preflight consumed outcomes",
    )
    _require(preflight.get("model_fitted") is False, "ML-9A preflight fit a model")
    _require(
        preflight["preregistration_sha256"] == sha256_file(preregistration_path),
        "ML-9A preregistration/preflight binding changed",
    )

    paths: dict[str, Path] = {}
    input_hashes: dict[str, str] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path = _verify_input(root, specification, name)
        paths[name] = path
        input_hashes[name] = sha256_file(path)

    metadata = pd.read_csv(paths["feature_metadata"])
    identifiers = _read_json(paths["identifier_screen"])["identifier_columns"]
    policy = derive_feature_policy(metadata, identifiers)
    feature_columns = tuple(policy["selected"])
    jw_columns = tuple(policy["jw"])
    _require(len(feature_columns) == 193, "ML-9A feature count changed")
    _require(len(jw_columns) == 17, "ML-9A JW feature count changed")

    features = pd.read_csv(paths["feature_table"], low_memory=False)
    features["task_uuid"] = features["task_uuid"].astype(str)
    _require(
        len(features) == 718 and features["task_uuid"].is_unique,
        "feature task census changed",
    )
    features_raw = features.set_index("task_uuid")[list(feature_columns)].apply(
        pd.to_numeric,
        errors="coerce",
    )

    panel = pd.read_csv(paths["panel_of_record"])
    panel["task_uuid"] = panel["task_uuid"].astype(str)
    _require(len(panel) == 96 and panel["task_uuid"].is_unique, "panel changed")
    panel_ids = list(panel["task_uuid"])
    panel_raw = features_raw.reindex(panel_ids)
    panel_transformed, parameters = coordinate_preprocessing(panel_raw)
    features_transformed = apply_coordinate_preprocessing(features_raw, parameters)

    canonical_payload = _read_json(paths["canonical_families"])
    canonical_map = {
        str(row["task_uuid"]): str(row["canonical_family_recommended"])
        for row in canonical_payload["tasks"]
    }
    canonical = pd.Series(canonical_map).reindex(features_raw.index)
    _require(bool(canonical.notna().all()), "canonical family missing")

    gradeability = pd.read_csv(paths["gradeability_census"])
    gradeability["task_uuid"] = gradeability["task_uuid"].astype(str)
    gradeability_map = pd.Series(
        _true(gradeability["gradeable_for_campaign_scoring"]).to_numpy(),
        index=gradeability["task_uuid"],
    )
    gradeable = gradeability_map.reindex(features_raw.index)
    _require(bool(gradeable.notna().all()), "gradeability role missing")
    _require(int((~gradeable.astype(bool)).sum()) == 109, "gradeability census changed")

    variants = _read_json(paths["solver_variants"])
    counts = Counter(str(row["solver_family_id"]) for row in variants)
    _require(
        dict(sorted(counts.items())) == EXPECTED_FAMILY_VARIANTS,
        "variant census changed",
    )

    observations = pd.read_csv(paths["normalized_observations"])
    observations["task_uuid"] = observations["task_uuid"].astype(str)
    _require(len(observations) == 1728, "observation count changed")
    _require(
        observations["task_uuid"].nunique() == 96, "observation task count changed"
    )
    _require(
        observations["solver_variant_id"].nunique() == 18,
        "observation variant count changed",
    )
    _require(
        not observations.duplicated(["task_uuid", "solver_variant_id"]).any(),
        "duplicate task/variant observation",
    )
    _require(
        set(observations["task_uuid"]) == set(panel_ids), "observation panel changed"
    )
    _require(
        set(observations["observed_outcome"]) == {"success", "fail"},
        "outcome vocabulary changed",
    )

    residual = pd.to_numeric(observations["graded_residual"], errors="coerce")
    finite = np.isfinite(residual)
    _require(bool((residual[finite] >= 0).all()), "negative graded residual")
    failure_cap = float(preregistration["response_construction"]["failure_cap"])
    observations = observations.assign(
        _family_cost=np.where(finite, np.minimum(residual, failure_cap), failure_cap),
        _accepted_success=observations["observed_outcome"].eq("success"),
    )
    family_costs = (
        observations.groupby(["task_uuid", "solver_family_id"], sort=True)[
            "_family_cost"
        ]
        .min()
        .unstack()
        .reindex(index=panel_ids, columns=list(FAMILY_ORDER))
    )
    _require(bool(np.isfinite(family_costs.to_numpy()).all()), "non-finite family cost")
    accepted = (
        observations.groupby(["task_uuid", "solver_family_id"], sort=True)[
            "_accepted_success"
        ]
        .any()
        .unstack()
        .reindex(index=panel_ids, columns=list(FAMILY_ORDER))
    )
    _require(
        np.array_equal((family_costs <= 1.0).to_numpy(), accepted.to_numpy()),
        "1x family union differs from accepted labels",
    )

    all_costs = family_costs.copy()
    all_costs["portfolio_union"] = family_costs.min(axis=1)
    labels = {factor: all_costs.le(factor) for factor in THRESHOLD_FACTORS}
    for factor, frame in labels.items():
        _require(
            all(
                min(int(frame[column].sum()), int((~frame[column]).sum())) >= 2
                for column in TARGET_ORDER
            ),
            f"threshold {factor} contains a one-class target",
        )

    return PreparedIsaData(
        preregistration=preregistration,
        panel=panel,
        features_raw=features_raw,
        features_transformed=features_transformed,
        panel_features_transformed=panel_transformed,
        preprocessing_parameters=parameters,
        canonical_family=canonical.astype(str),
        gradeable=gradeable.astype(bool),
        family_costs=family_costs,
        all_costs=all_costs,
        labels=labels,
        feature_columns=feature_columns,
        jw_columns=jw_columns,
        input_hashes=input_hashes,
    )


def _instance_space_options(preregistration: Mapping[str, Any]) -> InstanceSpaceOptions:
    sifted = preregistration["sifted"]
    pilot = preregistration["pilot"]
    cloister = preregistration["cloister"]
    trace = preregistration["trace"]
    return InstanceSpaceOptions(
        parallel=ParallelOptions.default(flag=False, n_cores=1),
        perf=PerformanceOptions.default(
            max_perf=False,
            abs_perf=True,
            epsilon=1.0,
            beta_threshold=0.55,
        ),
        auto=AutoOptions.default(preproc=False),
        bound=BoundOptions.default(flag=False),
        norm=NormOptions.default(flag=False),
        selvars=SelvarsOptions.default(density_flag=False),
        sifted=SiftedOptions.default(
            flag=True,
            rho=float(sifted["rho"]),
            k=int(sifted["k"]),
            n_trees=int(sifted["n_trees"]),
            max_iter=int(sifted["max_iter"]),
            replicates=int(sifted["replicates"]),
            num_generations=int(sifted["num_generations"]),
            num_parents_mating=int(sifted["num_parents_mating"]),
            sol_per_pop=int(sifted["solutions_per_population"]),
            parent_selection_type=str(sifted["parent_selection_type"]),
            k_tournament=int(sifted["k_tournament"]),
            keep_elitism=int(sifted["keep_elitism"]),
            crossover_type=str(sifted["crossover_type"]),
            cross_over_probability=float(sifted["crossover_probability"]),
            mutation_type=str(sifted["mutation_type"]),
            mutation_probability=float(sifted["mutation_probability"]),
            stop_criteria=str(sifted["stop_criteria"]),
        ),
        pilot=PilotOptions.default(
            analytic=False,
            n_tries=int(pilot["n_tries"]),
        ),
        cloister=CloisterOptions.default(
            p_val=float(cloister["p_value"]),
            c_thres=float(cloister["correlation_threshold"]),
        ),
        pythia=PythiaOptions.default(
            cv_folds=5,
            is_poly_krnl=False,
            use_weights=False,
            use_grid_search=False,
        ),
        trace=TraceOptions.default(
            use_sim=False,
            purity=float(trace["purity_threshold"]),
        ),
        outputs=OutputOptions.default(csv=False, web=False, png=False),
    )


def _prelim_no_toolkit_preprocessing(
    x: np.ndarray,
    y: np.ndarray,
    x_raw: np.ndarray,
    y_raw: np.ndarray,
    s: pd.Series | None,  # type: ignore[type-arg]
    inst_labels: pd.Series,  # type: ignore[type-arg]
    prelim_options: Any,
    selvars_options: Any,
) -> tuple[Any, ...]:
    """Reproduce the Instance Space 0.2.1 no-bound/no-normalize path.

    Version 0.2.1 returns uninitialized diagnostic variables when both options
    are false. The frozen ML-9A transform requires both to remain false, so this
    supplies neutral diagnostics while preserving the toolkit's response-label
    calculation exactly. Downstream stages consume x, y, y_bin, p, and beta;
    they do not consume these disabled-preprocessing diagnostics.
    """

    _require(
        importlib_metadata.version("instancespace") == "0.2.1",
        "PRELIM compatibility path is pinned to instancespace 0.2.1",
    )
    _require(
        not prelim_options.bound and not prelim_options.norm,
        "PRELIM compatibility path requires disabled bounding and normalization",
    )
    _require(
        not prelim_options.max_perf and prelim_options.abs_perf,
        "PRELIM compatibility path requires frozen minimizing absolute performance",
    )
    del x_raw, y_raw, s, inst_labels, selvars_options

    y_aux = y.copy()
    y_aux[np.isnan(y_aux)] = np.inf
    y_best = np.min(y_aux, axis=1)
    p = np.argmin(y_aux, axis=1) + 1
    y_bin = y_aux <= prelim_options.epsilon
    num_good_algos = np.sum(y_bin, axis=1)
    beta = num_good_algos > (prelim_options.beta_threshold * y.shape[1])

    feature_diagnostic = np.full(x.shape[1], np.nan, dtype=float)
    algorithm_diagnostic = np.full(y.shape[1], np.nan, dtype=float)
    return (
        x,
        y,
        y_bin,
        y_best,
        p,
        num_good_algos,
        beta,
        feature_diagnostic.copy(),
        feature_diagnostic.copy(),
        feature_diagnostic.copy(),
        feature_diagnostic.copy(),
        feature_diagnostic.copy(),
        feature_diagnostic.copy(),
        feature_diagnostic.copy(),
        feature_diagnostic.copy(),
        float("nan"),
        algorithm_diagnostic.copy(),
        algorithm_diagnostic.copy(),
        algorithm_diagnostic.copy(),
    )


@contextlib.contextmanager
def _instancespace_021_prelim_compatibility():
    """Temporarily repair the disabled-preprocessing return path."""

    original = PrelimStage.__dict__["prelim"]
    PrelimStage.prelim = staticmethod(_prelim_no_toolkit_preprocessing)
    try:
        yield
    finally:
        PrelimStage.prelim = original


def fit_projection(data: PreparedIsaData) -> ProjectionResult:
    """Run stock PRELIM/SIFTED/PILOT/CLOISTER on the four family responses."""

    panel_ids = list(data.panel["task_uuid"].astype(str))
    metadata = Metadata(
        feature_names=list(data.feature_columns),
        algorithm_names=list(FAMILY_ORDER),
        instance_labels=pd.Series(panel_ids),
        instance_sources=pd.Series(
            data.canonical_family.reindex(panel_ids).to_numpy(),
            index=range(len(panel_ids)),
        ),
        features=data.panel_features_transformed.to_numpy(dtype=float),
        algorithms=data.family_costs.to_numpy(dtype=float),
    )
    stages = [
        PreprocessingStage,
        PrelimStage,
        SiftedStage,
        PilotStage,
        CloisterStage,
    ]
    space = InstanceSpace(
        metadata, _instance_space_options(data.preregistration), stages=stages
    )
    outputs: dict[str, Any] = {}
    with (
        _instancespace_021_prelim_compatibility(),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        for event in space.run_iter():
            outputs.update(event.output._asdict())

    selected_features = tuple(map(str, outputs["feat_labels"]))
    acceptable = data.preregistration["sifted"]["acceptable_projection_feature_count"]
    _require(
        int(acceptable[0]) <= len(selected_features) <= int(acceptable[1]),
        f"SIFTED selected {len(selected_features)} features outside frozen range",
    )
    x_selected = np.asarray(outputs["x"], dtype=float)
    projection_matrix = np.asarray(outputs["a"], dtype=float)
    panel_coordinates = np.asarray(outputs["z"], dtype=float)
    _require(
        projection_matrix.shape == (2, len(selected_features)),
        "PILOT projection shape changed",
    )
    _require(panel_coordinates.shape == (96, 2), "PILOT coordinate shape changed")
    _require(bool(np.isfinite(panel_coordinates).all()), "non-finite PILOT coordinates")

    corpus_selected = data.features_transformed.loc[
        :, list(selected_features)
    ].to_numpy(dtype=float)
    corpus_coordinates = corpus_selected @ projection_matrix.T
    _require(corpus_coordinates.shape == (718, 2), "corpus projection shape changed")
    _require(
        bool(np.isfinite(corpus_coordinates).all()), "non-finite corpus coordinates"
    )
    distance_feature = pdist(x_selected, metric="euclidean")
    distance_projection = pdist(panel_coordinates, metric="euclidean")
    topology = float(pearsonr(distance_feature, distance_projection).statistic)
    _require(math.isfinite(topology), "topological preservation is non-finite")

    return ProjectionResult(
        selected_features=selected_features,
        selected_feature_matrix=x_selected,
        projection_matrix=projection_matrix,
        panel_coordinates=panel_coordinates,
        corpus_coordinates=corpus_coordinates,
        z_edge=np.asarray(outputs["z_edge"], dtype=float),
        z_ecorr=np.asarray(outputs["z_ecorr"], dtype=float),
        toolkit_pilot_r2=np.asarray(outputs["r2"], dtype=float),
        topological_preservation_correlation=topology,
    )


def _fit_one_pythia_target(
    panel_z: np.ndarray,
    corpus_z: np.ndarray,
    labels: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    positives = int(labels.sum())
    negatives = int((~labels).sum())
    minority = min(positives, negatives)
    folds = min(5, minority)
    majority_baseline = max(positives, negatives) / len(labels)
    if folds < 2:
        probability = float(positives / len(labels))
        panel_probability = np.full(len(labels), probability)
        corpus_probability = np.full(len(corpus_z), probability)
        predicted = panel_probability >= 0.5
        row = {
            "positive": positives,
            "negative": negatives,
            "cv_folds": folds,
            "raw_accuracy": float(accuracy_score(labels, predicted)),
            "balanced_accuracy": float(balanced_accuracy_score(labels, predicted)),
            "precision": float(precision_score(labels, predicted, zero_division=0)),
            "recall": float(recall_score(labels, predicted, zero_division=0)),
            "majority_baseline": majority_baseline,
            "box_constraint": None,
            "kernel_scale": None,
            "gate_passed": False,
            "gate_reason": "structural_failure_minority_class_below_2",
        }
        return row, panel_probability, corpus_probability

    mu, sigma, normalized_panel = PythiaStage._compute_znorm(panel_z)  # noqa: SLF001
    normalized_corpus = (corpus_z - np.asarray(mu)) / np.asarray(sigma)
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=0)
    parameter_space = PythiaStage._generate_params(  # noqa: SLF001
        False,
        np.random.default_rng(seed=0),
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        result = PythiaStage._fitmatsvm(  # noqa: SLF001
            z=normalized_panel,
            y_bin=labels,
            w=np.ones(len(labels), dtype=float),
            skf=splitter,
            is_poly_kernel=False,
            param_space=parameter_space,
            use_grid_search=False,
            parallel_options=ParallelOptions.default(flag=False, n_cores=1),
        )
    raw_accuracy = float(accuracy_score(labels, result.Ysub))
    balanced_accuracy = float(balanced_accuracy_score(labels, result.Ysub))
    threshold = max(0.70, majority_baseline + 0.05)
    gate_passed = raw_accuracy >= threshold and balanced_accuracy >= 0.60
    classes = list(result.svm.classes_)
    positive_index = classes.index(True)
    corpus_probability = result.svm.predict_proba(normalized_corpus)[:, positive_index]
    row = {
        "positive": positives,
        "negative": negatives,
        "cv_folds": folds,
        "raw_accuracy": raw_accuracy,
        "balanced_accuracy": balanced_accuracy,
        "precision": float(precision_score(labels, result.Ysub, zero_division=0)),
        "recall": float(recall_score(labels, result.Ysub, zero_division=0)),
        "majority_baseline": majority_baseline,
        "box_constraint": float(result.c),
        "kernel_scale": float(result.g),
        "gate_passed": gate_passed,
        "gate_reason": "pass" if gate_passed else "feature_adequacy_gate_failed",
    }
    return row, np.asarray(result.Psub, dtype=float), corpus_probability


def fit_pythia(data: PreparedIsaData, projection: ProjectionResult) -> PythiaResult:
    gate_rows: list[dict[str, Any]] = []
    panel_probabilities: dict[tuple[float, str], np.ndarray] = {}
    corpus_probabilities: dict[tuple[float, str], np.ndarray] = {}
    for factor in THRESHOLD_FACTORS:
        for target in TARGET_ORDER:
            row, panel_probability, corpus_probability = _fit_one_pythia_target(
                projection.panel_coordinates,
                projection.corpus_coordinates,
                data.labels[factor][target].to_numpy(dtype=bool),
            )
            row.update(
                {
                    "threshold_factor": factor,
                    "target": target,
                    "kernel": "rbf",
                    "output_kind": "estimate",
                }
            )
            gate_rows.append(row)
            panel_probabilities[(factor, target)] = panel_probability
            corpus_probabilities[(factor, target)] = corpus_probability
    return PythiaResult(gate_rows, panel_probabilities, corpus_probabilities)


def _run_trace(
    z: np.ndarray,
    labels: pd.DataFrame,
    family_costs: pd.DataFrame,
    purity: float,
) -> TraceOutputs:
    family_labels = labels.loc[:, list(FAMILY_ORDER)].to_numpy(dtype=bool)
    all_labels = labels.loc[:, list(TARGET_ORDER)].to_numpy(dtype=bool)
    best_family = np.argmin(family_costs.to_numpy(dtype=float), axis=1)
    beta = family_labels.sum(axis=1) > (0.55 * len(FAMILY_ORDER))
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        return TraceStage.trace(
            z=z,
            y_bin=all_labels,
            p=best_family,
            beta=beta,
            algo_labels=list(TARGET_ORDER),
            trace_opts=TraceOptions.default(use_sim=False, purity=purity),
            parallel_opts=ParallelOptions.default(flag=False, n_cores=1),
        )


def _footprint_metrics(
    footprint: Footprint, space: Footprint
) -> dict[str, float | int]:
    summary = TraceStage.summary(footprint, space.area, space.density)
    return {
        "area": float(summary[0]),
        "area_normalized": float(summary[1]),
        "density": float(summary[2]),
        "density_normalized": float(summary[3]),
        "purity": float(summary[4]),
        "elements": int(footprint.elements),
        "good_elements": int(footprint.good_elements),
    }


def _geometry_payload(footprint: Footprint) -> dict[str, Any] | None:
    if footprint.polygon is None or footprint.polygon.is_empty:
        return None
    normalized = footprint.polygon.normalize()
    return mapping(normalized)


def trace_point_estimates(
    data: PreparedIsaData,
    projection: ProjectionResult,
    pythia: PythiaResult,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[float, TraceOutputs]]:
    gate = {
        (float(row["threshold_factor"]), str(row["target"])): bool(row["gate_passed"])
        for row in pythia.gate_rows
    }
    rows: list[dict[str, Any]] = []
    polygons: dict[str, Any] = {
        "artifact_id": "ml9a_trace_polygons_v1",
        "output_kind": "estimate",
        "thresholds": {},
    }
    traces: dict[float, TraceOutputs] = {}
    purity = float(data.preregistration["trace"]["purity_threshold"])
    for factor in THRESHOLD_FACTORS:
        trace = _run_trace(
            projection.panel_coordinates,
            data.labels[factor],
            data.family_costs,
            purity,
        )
        traces[factor] = trace
        threshold_polygons: dict[str, Any] = {
            "empirical_space": _geometry_payload(trace.space),
            "good": {},
            "best": {},
        }
        for index, target in enumerate(TARGET_ORDER):
            for kind, footprint in (("good", trace.good[index]),):
                metrics = _footprint_metrics(footprint, trace.space)
                rows.append(
                    {
                        "threshold_factor": factor,
                        "target": target,
                        "footprint_kind": kind,
                        **metrics,
                        "pythia_gate_passed": gate[(factor, target)],
                        "interpretation": (
                            "descriptive_geometry"
                            if gate[(factor, target)]
                            else "caveated_feature_adequacy_gate_failed"
                        ),
                        "status": "estimated" if footprint.area > 0 else "degenerate",
                        "output_kind": "estimate",
                    }
                )
                threshold_polygons[kind][target] = _geometry_payload(footprint)
            if target in FAMILY_ORDER:
                footprint = trace.best[index]
                metrics = _footprint_metrics(footprint, trace.space)
                rows.append(
                    {
                        "threshold_factor": factor,
                        "target": target,
                        "footprint_kind": "best",
                        **metrics,
                        "pythia_gate_passed": gate[(factor, target)],
                        "interpretation": (
                            "descriptive_geometry"
                            if gate[(factor, target)]
                            else "caveated_feature_adequacy_gate_failed"
                        ),
                        "status": "estimated" if footprint.area > 0 else "degenerate",
                        "output_kind": "estimate",
                    }
                )
                threshold_polygons["best"][target] = _geometry_payload(footprint)
        polygons["thresholds"][format(factor, ".1f")] = threshold_polygons
    return rows, polygons, traces


def bootstrap_trace(
    data: PreparedIsaData,
    projection: ProjectionResult,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the frozen 2,000-draw primary-threshold family-block bootstrap."""

    factor = 1.0
    panel_ids = list(data.panel["task_uuid"].astype(str))
    panel_families = data.canonical_family.reindex(panel_ids)
    groups = sorted(panel_families.unique())
    indices = {
        family: np.flatnonzero(panel_families.to_numpy() == family) for family in groups
    }
    rng = np.random.default_rng(seed=int(data.preregistration["bootstrap"]["seed"]))
    replicates = int(data.preregistration["bootstrap"]["replicates"])
    purity = float(data.preregistration["trace"]["purity_threshold"])
    draw_rows: list[dict[str, Any]] = []
    for replicate in range(replicates):
        selected_groups = rng.choice(groups, size=len(groups), replace=True)
        draw_indices = np.concatenate(
            [indices[str(group)] for group in selected_groups]
        )
        draw_labels = data.labels[factor].iloc[draw_indices].reset_index(drop=True)
        draw_costs = data.family_costs.iloc[draw_indices].reset_index(drop=True)
        trace = _run_trace(
            projection.panel_coordinates[draw_indices],
            draw_labels,
            draw_costs,
            purity,
        )
        objects: list[tuple[str, str, Footprint]] = [
            ("empirical_space", "space", trace.space)
        ]
        objects.extend(
            (target, "good", trace.good[index])
            for index, target in enumerate(TARGET_ORDER)
        )
        objects.extend(
            (target, "best", trace.best[index])
            for index, target in enumerate(FAMILY_ORDER)
        )
        for target, kind, footprint in objects:
            draw_rows.append(
                {
                    "replicate": replicate,
                    "threshold_factor": factor,
                    "sampled_blocks": len(selected_groups),
                    "sampled_rows": len(draw_indices),
                    "target": target,
                    "footprint_kind": kind,
                    **_footprint_metrics(footprint, trace.space),
                    "status": "estimated" if footprint.area > 0 else "degenerate",
                    "output_kind": "estimate",
                }
            )

    draw_frame = pd.DataFrame(draw_rows)
    interval_rows: list[dict[str, Any]] = []
    metrics = ["area", "area_normalized", "density", "density_normalized", "purity"]
    for (target, kind), group in draw_frame.groupby(
        ["target", "footprint_kind"], sort=True
    ):
        for metric in metrics:
            values = group[metric].to_numpy(dtype=float)
            interval_rows.append(
                {
                    "threshold_factor": factor,
                    "target": target,
                    "footprint_kind": kind,
                    "metric": metric,
                    "estimate_mean": float(np.mean(values)),
                    "estimate_median": float(np.median(values)),
                    "ci_lower": float(np.quantile(values, 0.025)),
                    "ci_upper": float(np.quantile(values, 0.975)),
                    "replicates": replicates,
                    "degenerate_draws": int((group["status"] == "degenerate").sum()),
                    "interval_scope": "family_block_bootstrap_conditional_on_projection",
                    "output_kind": "estimate",
                }
            )
    return draw_rows, interval_rows


def _valid_polygon(points: np.ndarray) -> Polygon:
    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    _require(not polygon.is_empty and polygon.area > 0, "empty CLOISTER polygon")
    return polygon.normalize()


def cloister_outputs(
    projection: ProjectionResult, primary_trace: TraceOutputs
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    boundaries: list[dict[str, Any]] = []
    for boundary_id, points in (
        ("unconstrained", projection.z_edge),
        ("correlation_pruned", projection.z_ecorr),
    ):
        for index, point in enumerate(points):
            boundaries.append(
                {
                    "boundary_id": boundary_id,
                    "vertex_index": index,
                    "z1": float(point[0]),
                    "z2": float(point[1]),
                    "output_kind": "estimate",
                }
            )
    theoretical = _valid_polygon(projection.z_ecorr)
    empirical = primary_trace.space.polygon
    _require(empirical is not None and not empirical.is_empty, "empty empirical space")
    empirical = empirical.normalize()
    unoccupied = theoretical.difference(empirical)
    outside = empirical.difference(theoretical)
    coverage = {
        "artifact_id": "ml9a_cloister_coverage_v1",
        "output_kind": "estimate",
        "theoretical_boundary": mapping(theoretical),
        "empirical_boundary": mapping(empirical),
        "unoccupied_theoretical_region": mapping(unoccupied.normalize()),
        "empirical_region_outside_theoretical_boundary": mapping(outside.normalize()),
        "theoretical_area": float(theoretical.area),
        "empirical_area": float(empirical.area),
        "unoccupied_theoretical_area": float(unoccupied.area),
        "unoccupied_theoretical_area_fraction": float(
            unoccupied.area / theoretical.area
        ),
        "empirical_outside_theoretical_area": float(outside.area),
        "interpretation": "corpus coverage gap within CLOISTER feasible boundary",
    }
    return boundaries, coverage


def _minmax(values: np.ndarray) -> np.ndarray:
    low = float(np.min(values))
    high = float(np.max(values))
    return np.zeros_like(values) if high == low else (values - low) / (high - low)


def priority_targets(
    data: PreparedIsaData,
    projection: ProjectionResult,
    pythia: PythiaResult,
) -> list[dict[str, Any]]:
    corpus_ids = list(data.features_raw.index.astype(str))
    panel_ids = list(data.panel["task_uuid"].astype(str))
    panel_set = set(panel_ids)
    candidate_positions = [
        index
        for index, task_uuid in enumerate(corpus_ids)
        if task_uuid not in panel_set
    ]
    candidate_ids = [corpus_ids[index] for index in candidate_positions]
    candidate_z = projection.corpus_coordinates[candidate_positions]
    novelty_raw = cdist(candidate_z, projection.panel_coordinates).min(axis=1)
    novelty = _minmax(novelty_raw)
    portfolio_probability = pythia.corpus_probabilities[(1.0, "portfolio_union")][
        candidate_positions
    ]
    uncertainty = 1.0 - 2.0 * np.abs(portfolio_probability - 0.5)
    panel_family_counts = Counter(data.canonical_family.reindex(panel_ids))
    maximum_count = max(panel_family_counts.values())
    family_deficit = np.array(
        [
            1.0
            - panel_family_counts.get(data.canonical_family.loc[task_uuid], 0)
            / maximum_count
            for task_uuid in candidate_ids
        ],
        dtype=float,
    )
    feature_coverage = data.features_raw.notna().sum(axis=1).reindex(
        candidate_ids
    ).to_numpy(dtype=float) / len(data.feature_columns)
    score = feature_coverage * (
        0.50 * novelty + 0.30 * uncertainty + 0.20 * family_deficit
    )
    rows = []
    for index, task_uuid in enumerate(candidate_ids):
        is_gradeable = bool(data.gradeable.loc[task_uuid])
        rows.append(
            {
                "task_uuid": task_uuid,
                "canonical_family": data.canonical_family.loc[task_uuid],
                "gradeable_for_campaign_scoring": is_gradeable,
                "coverage_role": (
                    "unlabeled_gradeable"
                    if is_gradeable
                    else "prediction_target_or_coverage"
                ),
                "z1": float(candidate_z[index, 0]),
                "z2": float(candidate_z[index, 1]),
                "nearest_panel_distance": float(novelty_raw[index]),
                "novelty_component": float(novelty[index]),
                "portfolio_probability_estimate": float(portfolio_probability[index]),
                "portfolio_uncertainty_component": float(uncertainty[index]),
                "family_deficit_component": float(family_deficit[index]),
                "observed_feature_fraction": float(feature_coverage[index]),
                "priority_score_estimate": float(score[index]),
                "recommended_next_step": (
                    "candidate_for_future_solver_labeling"
                    if is_gradeable
                    else "reference_or_gradeability_work_first"
                ),
                "authorizes_solver_run": False,
                "output_kind": "estimate",
            }
        )
    rows.sort(
        key=lambda row: (-float(row["priority_score_estimate"]), str(row["task_uuid"]))
    )
    for rank, row in enumerate(rows, start=1):
        row["priority_rank"] = rank
    return rows


def _write_report(
    output_directory: Path,
    projection: ProjectionResult,
    pythia_rows: Sequence[Mapping[str, Any]],
    trace_rows: Sequence[Mapping[str, Any]],
    intervals: Sequence[Mapping[str, Any]],
    coverage: Mapping[str, Any],
    priorities: Sequence[Mapping[str, Any]],
) -> None:
    primary_portfolio = next(
        row
        for row in trace_rows
        if row["threshold_factor"] == 1.0
        and row["target"] == "portfolio_union"
        and row["footprint_kind"] == "good"
    )
    primary_gates = [row for row in pythia_rows if row["threshold_factor"] == 1.0]
    passed = sum(bool(row["gate_passed"]) for row in primary_gates)
    report = {
        "artifact_id": "ml9a_instance_space_report_v1",
        "status": "complete_internal_descriptive",
        "output_kind": "estimate",
        "internal_only": True,
        "validated_predictor_claim": False,
        "ratio_of_record": "design_based_unchanged",
        "panel_tasks": 96,
        "corpus_tasks_projected": 718,
        "non_gradeable_coverage_points": 109,
        "projection_features": list(projection.selected_features),
        "projection_feature_count": len(projection.selected_features),
        "topological_preservation_correlation": projection.topological_preservation_correlation,
        "pythia_primary_gates_passed": passed,
        "pythia_primary_gates_total": len(primary_gates),
        "portfolio_primary": dict(primary_portfolio),
        "bootstrap_replicates": 2000,
        "bootstrap_interval_rows": len(intervals),
        "unoccupied_theoretical_area_fraction": coverage[
            "unoccupied_theoretical_area_fraction"
        ],
        "priority_rows": len(priorities),
        "headline_priority_rows": 25,
        "fitted_surface_integral": False,
        "new_solver_runs": False,
    }
    stable_json_dump(report, output_directory / "report.json")

    text = f"""# ML-9A Instance Space Analysis — internal iteration one

Status: complete internal descriptive artifact. Every model-derived quantity is
an estimate. The design-based ratio remains the ratio of record; no fitted
surface is integrated and no validated-predictor claim is made.

The accepted 96-task, 18-variant post-G59 panel was reduced to four
solver-family performance tracks. SIFTED selected {len(projection.selected_features)}
features for the projection basis only; all 193 modeling features remain
eligible for later analyses. PILOT's optimized 2D projection has pairwise-
distance topological-preservation correlation
{projection.topological_preservation_correlation:.6f}. All 718 corpus tasks
are projected with per-task feature-coverage fields, including the 109
non-gradeable prediction-target/coverage points.

At the primary stored threshold, {passed}/{len(primary_gates)} PYTHIA targets
pass the preregistered accuracy gate. A failed target's observed TRACE geometry
remains present and is explicitly caveated as a feature-adequacy finding.

The primary portfolio-union good footprint has normalized area
{float(primary_portfolio['area_normalized']):.6f}, normalized density
{float(primary_portfolio['density_normalized']):.6f}, and purity
{float(primary_portfolio['purity']):.6f}. Area, density, and purity intervals
come from 2,000 canonical-task-family block bootstrap draws conditional on the
frozen projection. The correlation-pruned CLOISTER boundary leaves
{float(coverage['unoccupied_theoretical_area_fraction']):.6f} of its area
unoccupied by the empirical corpus footprint.

The acquisition table ranks {len(priorities)} tasks outside the labeled panel;
the first 25 form the iteration-one planning list. It authorizes no solver run.
"""
    (output_directory / "REPORT.md").write_text(text, encoding="utf-8")


def run_finalization(
    root: Path,
    preregistration_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Run and serialize one complete deterministic ML-9A finalization."""

    os.environ.setdefault("PYTHONHASHSEED", "0")
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"

    data = prepare_isa_data(root, preregistration_path)
    projection = fit_projection(data)
    pythia = fit_pythia(data, projection)
    trace_rows, trace_polygons, traces = trace_point_estimates(data, projection, pythia)
    bootstrap_rows, interval_rows = bootstrap_trace(data, projection)
    boundary_rows, coverage = cloister_outputs(projection, traces[1.0])
    priorities = priority_targets(data, projection, pythia)

    output_directory.mkdir(parents=True, exist_ok=True)
    metadata = pd.read_csv(root / "analysis/feature_schema/feature_column_metadata.csv")
    metadata_rows = metadata.set_index("column").to_dict(orient="index")
    selected_set = set(projection.selected_features)
    preprocessing_rows = []
    for column in data.feature_columns:
        parameters = data.preprocessing_parameters.loc[column]
        preprocessing_rows.append(
            {
                "column": column,
                "logical_block": _logical_block(column, metadata_rows[column]),
                "jw_feature": column in data.jw_columns,
                "panel_observed": int(
                    data.features_raw.reindex(data.panel["task_uuid"])[column]
                    .notna()
                    .sum()
                ),
                "corpus_observed": int(data.features_raw[column].notna().sum()),
                "completion_median": float(parameters["median"]),
                "scale": float(parameters["scale"]),
                "scale_source": str(parameters["scale_source"]),
                "constant_after_completion": bool(
                    parameters["constant_after_completion"]
                ),
                "selected_for_projection": column in selected_set,
                "later_feature_eligible": True,
            }
        )
    stable_csv_dump(
        preprocessing_rows,
        list(preprocessing_rows[0]),
        output_directory / "feature_preprocessing.csv",
    )

    projection_feature_rows = [
        {
            "projection_rank": index + 1,
            "column": column,
            "logical_block": _logical_block(column, metadata_rows[column]),
            "jw_feature": column in data.jw_columns,
            "prunes_feature_eligibility": False,
            "output_kind": "estimate",
        }
        for index, column in enumerate(projection.selected_features)
    ]
    stable_csv_dump(
        projection_feature_rows,
        list(projection_feature_rows[0]),
        output_directory / "projection_features.csv",
    )
    matrix_rows = [
        {
            "axis": axis + 1,
            "column": column,
            "coefficient": float(projection.projection_matrix[axis, index]),
            "output_kind": "estimate",
        }
        for axis in range(2)
        for index, column in enumerate(projection.selected_features)
    ]
    stable_csv_dump(
        matrix_rows,
        list(matrix_rows[0]),
        output_directory / "projection_matrix.csv",
    )
    topology_rows = [
        {
            "metric": "pairwise_distance_pearson_correlation",
            "value": projection.topological_preservation_correlation,
            "selected_feature_count": len(projection.selected_features),
            "panel_tasks": 96,
            "output_kind": "estimate",
        }
    ]
    stable_csv_dump(
        topology_rows,
        list(topology_rows[0]),
        output_directory / "topological_preservation.csv",
    )
    stable_csv_dump(
        boundary_rows,
        list(boundary_rows[0]),
        output_directory / "cloister_boundary.csv",
    )
    stable_json_dump(coverage, output_directory / "cloister_coverage.json")

    panel_ids = list(data.panel["task_uuid"].astype(str))
    panel_positions = {
        task: index for index, task in enumerate(data.features_raw.index)
    }
    panel_coordinate_rows = []
    for index, task_uuid in enumerate(panel_ids):
        raw = data.features_raw.loc[task_uuid]
        row: dict[str, Any] = {
            "task_uuid": task_uuid,
            "canonical_family": data.canonical_family.loc[task_uuid],
            "z1": float(projection.panel_coordinates[index, 0]),
            "z2": float(projection.panel_coordinates[index, 1]),
            "observed_feature_count": int(raw.notna().sum()),
            "observed_feature_fraction": float(raw.notna().mean()),
            "output_kind": "estimate",
        }
        for target in TARGET_ORDER:
            row[f"solvable_1x_{target}"] = bool(data.labels[1.0].loc[task_uuid, target])
        panel_coordinate_rows.append(row)
        _require(
            np.allclose(
                projection.panel_coordinates[index],
                projection.corpus_coordinates[panel_positions[task_uuid]],
                rtol=0,
                atol=1.0e-12,
            ),
            "panel/corpus projection mismatch",
        )
    stable_csv_dump(
        panel_coordinate_rows,
        list(panel_coordinate_rows[0]),
        output_directory / "panel_coordinates.csv",
    )

    panel_set = set(panel_ids)
    corpus_coordinate_rows = []
    primary_portfolio_probability = pythia.corpus_probabilities[
        (1.0, "portfolio_union")
    ]
    for index, task_uuid in enumerate(data.features_raw.index.astype(str)):
        raw = data.features_raw.loc[task_uuid]
        corpus_coordinate_rows.append(
            {
                "task_uuid": task_uuid,
                "canonical_family": data.canonical_family.loc[task_uuid],
                "in_labeled_panel": task_uuid in panel_set,
                "gradeable_for_campaign_scoring": bool(data.gradeable.loc[task_uuid]),
                "coverage_role": (
                    "labeled_panel"
                    if task_uuid in panel_set
                    else (
                        "unlabeled_gradeable"
                        if bool(data.gradeable.loc[task_uuid])
                        else "prediction_target_or_coverage"
                    )
                ),
                "z1": float(projection.corpus_coordinates[index, 0]),
                "z2": float(projection.corpus_coordinates[index, 1]),
                "observed_feature_count": int(raw.notna().sum()),
                "observed_feature_fraction": float(raw.notna().mean()),
                "portfolio_probability_estimate_1x": float(
                    primary_portfolio_probability[index]
                ),
                "output_kind": "estimate",
            }
        )
    stable_csv_dump(
        corpus_coordinate_rows,
        list(corpus_coordinate_rows[0]),
        output_directory / "corpus_coordinates.csv",
    )

    label_rows = []
    for factor in THRESHOLD_FACTORS:
        for task_uuid in panel_ids:
            for target in TARGET_ORDER:
                label_rows.append(
                    {
                        "task_uuid": task_uuid,
                        "canonical_family": data.canonical_family.loc[task_uuid],
                        "threshold_factor": factor,
                        "target": target,
                        "continuous_cost_capped": float(
                            data.all_costs.loc[task_uuid, target]
                        ),
                        "solvable": bool(data.labels[factor].loc[task_uuid, target]),
                        "label_of_record_mutated": False,
                        "output_kind": "derived_observed_label",
                    }
                )
    stable_csv_dump(
        label_rows,
        list(label_rows[0]),
        output_directory / "labels_by_threshold.csv",
    )
    stable_csv_dump(
        pythia.gate_rows,
        list(pythia.gate_rows[0]),
        output_directory / "pythia_gate.csv",
    )
    stable_csv_dump(
        trace_rows,
        list(trace_rows[0]),
        output_directory / "trace_footprints.csv",
    )
    stable_json_dump(trace_polygons, output_directory / "trace_polygons.json")
    stable_csv_dump(
        bootstrap_rows,
        list(bootstrap_rows[0]),
        output_directory / "bootstrap_draws.csv",
    )
    stable_csv_dump(
        interval_rows,
        list(interval_rows[0]),
        output_directory / "bootstrap_intervals.csv",
    )
    stable_csv_dump(
        priorities,
        list(priorities[0]),
        output_directory / "priority_targets.csv",
    )
    stable_csv_dump(
        priorities[:25],
        list(priorities[0]),
        output_directory / "priority_targets_top25.csv",
    )

    environment = {
        "artifact_id": "ml9a_runtime_environment_v1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: importlib_metadata.version(name)
            for name in (
                "instancespace",
                "numpy",
                "scipy",
                "pandas",
                "scikit-learn",
                "scikit-optimize",
                "shapely",
                "alphashape",
                "pygad",
            )
        },
        "instancespace_wheel_sha256": data.preregistration["toolkit"]["wheel_sha256"],
        "numeric_threads": 1,
        "python_hash_seed": 0,
        "compatibility": {
            "component": "instancespace 0.2.1 PRELIM",
            "condition": "toolkit bounding and normalization disabled",
            "effect": "neutral disabled-preprocessing diagnostics supplied; transformed features and response labels unchanged",
        },
        "output_kind": "environment_record",
    }
    stable_json_dump(environment, output_directory / "environment.json")
    _write_report(
        output_directory,
        projection,
        pythia.gate_rows,
        trace_rows,
        interval_rows,
        coverage,
        priorities,
    )

    required = set(data.preregistration["outputs"]["required_files"])
    produced_before_manifest = {
        path.name for path in output_directory.iterdir() if path.is_file()
    }
    _require(
        required - {"artifact_manifest.json"} <= produced_before_manifest,
        f"missing required ML-9A outputs: {sorted(required - produced_before_manifest)}",
    )
    files = []
    for path in sorted(output_directory.iterdir()):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        files.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "artifact_id": "ml9a_instance_space_manifest_v1",
        "status": "complete_internal_descriptive",
        "output_kind": "estimate",
        "internal_only": True,
        "validated_predictor_claim": False,
        "ratio_of_record": "design_based_unchanged",
        "fitted_surface_integral": False,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "preregistration_sha256": sha256_file(preregistration_path),
        "preflight_manifest_sha256": PREFLIGHT_MANIFEST_SHA256,
        "input_hashes": data.input_hashes,
        "toolkit_version": importlib_metadata.version("instancespace"),
        "toolkit_wheel_sha256": data.preregistration["toolkit"]["wheel_sha256"],
        "census": {
            "panel_tasks": 96,
            "corpus_tasks": 718,
            "non_gradeable_coverage_points": 109,
            "solver_families": 4,
            "portfolio_objects": 1,
            "threshold_factors": 3,
            "projection_features": len(projection.selected_features),
            "bootstrap_replicates": 2000,
            "priority_rows": len(priorities),
        },
        "files": files,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    _require(
        {path.name for path in output_directory.iterdir() if path.is_file()}
        == required,
        "ML-9A output member set differs from preregistration",
    )
    return manifest
