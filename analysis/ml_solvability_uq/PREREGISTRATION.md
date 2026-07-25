# ML-8D preregistration — UQ solvability estimator + solvability-ratio v2

Status: **frozen before any estimator is fitted.** Committed strictly before the
commit carrying results (GR21-O4(a)).

Order of record: `work/ML_GOALS.md`, "PI ORDER 2026-07-25 — ML-8", part
**ML-8D**. Its gate ("after A and C") is satisfied: ML-8A census committed at
`967b5eb8` and ML-8C sensitivity annex at `d42bb3f6`, both two-run
byte-identical and independently verified.

Restores the prototype paper's feature-space classifier and "solvability ratio"
as a **two-track estimator, both tracks over gradeable tasks only**.

## 1. Pinned inputs

| input | path | SHA-256 |
|---|---|---|
| Gradeability census | `analysis/ml_gradeability_census/held_v1/census.csv` | `9487c30d4738dbb2964160bf8ae54e06dbdf248519b900ef4cb3accad913daab` |
| Masked labels (ML-8C) | `analysis/ml_g50_solver_families/sensitivity_gradeable_mask_v1/masked_observations.csv` | `1d03218a4b476796415522abf83c294aa4df8a66a3663cb3e49674160c49d5eb` |
| Gradeable design weights (ML-8C) | `analysis/ml_g50_solver_families/sensitivity_gradeable_mask_v1/gradeable_selection_weights.csv` | `02aba247003b10a616bde6358ffd4a9307c7d1c4bf768100d05202941f3f7538` |
| ML-8C report (population accounting) | `analysis/ml_g50_solver_families/sensitivity_gradeable_mask_v1/report.json` | `d28c67023b722e81cd182786072eb6ab143d06ec490168422285b57fdeb2e065` |
| kNN comparison predictions (ML-8C) | `analysis/ml_g50_solver_families/sensitivity_gradeable_mask_v1/predictions.csv` | `a38f8d9003d6ada7b3f1836c6304aecbb92e0d188c15b56b042b5c4a3e0d31b5` |
| Feature table | `scripts/Hamiltonian_features.csv` | `b5f8a78c3fd8fa9ba1e5dce4e8e2986bfc19346b26375e22763816efa5cdc8f7` |
| Column metadata | `analysis/feature_schema/feature_column_metadata.csv` | `3efad3a89b7fd2463da7d777a6c3e6c99759a04b15e007584266d24f44ec6590` |
| Canonical taxonomy | `analysis/feature_schema/canonical_families_v1.json` | `4bc9404feba3313cea64df734364a3ecbb45dbfda6f41bd337231181fef67942` |
| Identifier screen | `analysis/ml_v2/identifier_screen.json` | `f4ca6d170215d2f87fba67de8df3ce6d6987fb2f635c37eeb0506500ced4650d` |
| Parent G-50 preregistration | `analysis/ml_g50_solver_families/preregistration.json` | feature/label policy re-used verbatim via the frozen loaders |

Geometry, feature policy, and the 18 variant identities are re-used from the
frozen parent chain; ML-8D introduces no new feature, label, or variant.

## 2. Track 1 — design-based ratio (the ratio of record)

Estimator, over the ML-8C gradeable construction:

`R_design(v) = Σ_c w(c)·1[success_v(c)] / Σ_c w(c)`

over the 80 retained gradeable centers, with `w` the gradeable-population
Voronoi weights (sum 577 of the 609 gradeable corpus tasks; the 32 orphaned
tasks are disclosed, never reassigned — the estimand is the **covered**
gradeable subpopulation). Point estimates are already computed in ML-8C; ML-8D
adds uncertainty.

**Bootstrap (frozen):** B = 2,000 draws, seed 20260725, percentile 95%
intervals.

- **PRIMARY — family-grouped:** resample the canonical families present among
  the retained centers, with replacement, drawing as many families as there
  are; the estimator uses every center in the drawn families with its weight.
  Family-grouped resampling is mandatory house practice (feature-space
  near-duplication, ML-4: 92.6% same-family neighbour purity) and is the
  primary interval.
- **SENSITIVITY — center-level:** resample the retained centers with
  replacement. Reported alongside; narrower by construction, and labelled as
  the sensitivity, never the headline.

A draw whose resampled weight total is zero is rejected and redrawn; the
attempted and accepted counts are recorded.

**This design-based ratio is the ratio of record.** No model output may
displace it.

## 3. Track 2 — model-based calibrated estimator with posterior uncertainty

### 3.1 Classifier

Gaussian-process classification with the Laplace approximation
(Rasmussen & Williams Alg. 3.1/3.2), Bernoulli-logit likelihood, over the
**frozen block-aware distance** — no re-derived geometry, no cross-domain
imputation, no family input.

Kernel: `K(i,j) = exp(−D(i,j)² / (2ℓ²))`, unit prior variance, on the frozen
`with_jw` block-aware distance `D` for the variant's solver family.

- **Lengthscale ℓ (frozen rule):** the median of the strictly positive
  pairwise training-fold distances (median heuristic). Deterministic; no
  marginal-likelihood optimisation, so no fold-level tuning can leak.
- **Sensitivity:** ℓ ∈ {0.5·median, 2·median}, reported; the median rule is
  primary.
- **PSD guard:** `D` is a block-averaged metric and is not guaranteed
  Euclidean, so `K` is not guaranteed positive semidefinite. The run computes
  the minimum eigenvalue; if it is below `−1e-10` the negative eigenvalues are
  clipped to zero (nearest-PSD projection) and the artifact records, per fitted
  kernel, the pre-projection minimum eigenvalue and the Frobenius norm of the
  correction. A jitter of `1e-8` is added to the diagonal for numerical
  stability. This correction is disclosed, never silent.
- **Newton solve:** at most 100 iterations, convergence tolerance `1e-9` on the
  log marginal likelihood; non-convergence is a hard failure, not a warning.
- **Predictive probability:** the MacKay/probit approximation
  `σ(κ·f̄)` with `κ = (1 + πσ²_f/8)^(−1/2)`, giving a per-point mean and a
  per-point latent posterior standard deviation.

**Declared fallback (no-gate clause):** if the GP fails to converge or to scale
on any variant, that variant falls back to isotonic-calibrated logistic
regression on the same geometry, and the fallback is recorded per variant in
the artifact. The GP is attempted first for every variant regardless.

### 3.2 Protocol

Leave-one-canonical-family-out, identical to the parent: for each query family,
fit on the retained gradeable labels of all other families and predict every
corpus task in the query family. Training labels are the 80 gradeable panel
tasks (ML-8C); predictions cover all 718 corpus tasks.

### 3.3 Calibration is the validation gate

The gate is **calibration, not discrimination** — reliability, not a
beat-the-baseline comparison. Assessed on the LOFO out-of-fold predictions at
the 80 labelled gradeable panel tasks.

Frozen instruments:

1. **Reliability curve** over **5 equal-count (quantile) bins** — 16 labelled
   tasks per bin at n = 80; 10 bins would be too thin to read.
2. **Expected calibration error** `ECE = Σ_b (n_b/N)·|mean_pred_b − freq_b|`.
3. **Calibration slope and intercept** from a logistic regression of the
   observed label on `logit(p)`; perfect calibration is slope 1, intercept 0.
   Predictions are clipped to `[1e-6, 1−1e-6]` before the logit.
4. **Brier decomposition** into reliability, resolution, and uncertainty.
5. Family-grouped bootstrap (B = 2,000, seed 20260725) intervals for ECE and
   the calibration slope.

**Frozen gate — a variant PASSES calibration iff BOTH hold:**

- `ECE ≤ 0.10`, and
- the family-grouped 95% interval of the calibration slope contains 1.0.

Both thresholds are frozen here, before any value is computed. Variants are
reported individually; no pooling across variants and no multiplicity claim.

### 3.4 Model-based ratio

`R_model(v) = (1/N_g) Σ_{gradeable corpus tasks} p_v(i)`, `N_g = 609`.

The model track is **unweighted**: a model predicts at every corpus point, so
no selection weighting is needed. Selection weights exist to extrapolate from a
sample, which is the design track's job. This asymmetry is deliberate and
stated in the artifact.

**Credible intervals:** S = 2,000 joint latent posterior samples per LOFO fold
(the fold's joint predictive covariance is respected), pushed through the
logistic link and averaged; seed 20260725. Different folds' posteriors are
treated as **independent** — a declared approximation that ignores cross-family
posterior correlation. It is recorded in the artifact as an approximation, and
the resulting interval is labelled accordingly.

### 3.5 The miscalibration this track exists to test

Of record from the PI order: the existing kNN corpus predictions are
uncalibrated — DMRG@256 predicted 0.150 against a design-weighted 0.398. The
artifact therefore reports, per variant, side by side: the design-based ratio,
**two** kNN quantities recomputed from the pinned predictions — the argmax
**hard-label rate** and the **mean predicted probability** — and the GP
model-based ratio, with the gap to the design ratio for every model quantity.

Both kNN quantities are required, and this is frozen here for a reason: the
quoted 0.150 is a hard-label rate at the 0.5 cutoff, while the design-based
ratio is a probability-scale quantity. Comparing only the hard-label rate would
attribute to probability miscalibration what may be a thresholding effect.
Reporting both makes the distinction visible in the artifact rather than
resolved by assumption. Whether the GP narrows either gap is a reported number,
not an assumed outcome.

## 4. Outputs (`analysis/ml_solvability_uq/held_v1/`)

`design_based_ratios.csv`, `model_based_ratios.csv`,
`per_task_posterior.csv` (718 tasks × eligible variants; mean, latent sd, 95%
credible bounds), `calibration.csv`, `reliability_bins.csv`,
`calibration_gate.csv`, `lengthscale_sensitivity.csv`,
`kernel_psd_diagnostics.csv`, `ratio_comparison.csv`, `report.json`,
`REPORT.md`, `schemas/report.schema.json`, `artifact_manifest.json`.

Held-artifact discipline: `status = held_pending_pi_review`,
`effective = false`, `validated_predictor_claim = false`,
`ratio_of_record = design_based`. Every model output is labelled an estimate.

## 5. STOP-AT

- The ML-6 **no-validated-predictor rule stands**. Nothing here may present the
  model track as a validated predictor.
- **If any variant PASSES the frozen calibration gate, that is a claim-language
  decision, not an ML-agent conclusion: FLAG it, report the numbers plainly,
  and stop short of ALL interpretation.** Matt acks claim language; the PI
  reviews first. No prose, no paper framing, no dashboard placement.
- If every variant fails the gate, that is equally a result and is reported as
  such — the model track then remains an uncalibrated estimate and the design
  track remains the sole ratio of record.

## 6. Fences

- Supersedes nothing. `final_v4`, the ML-8C annex, and the ML-8A census are
  read-only here and must show empty diffs.
- No new label, feature, variant, solver run, or reselection.
- No family, mask, reason, or provenance column enters any model.
- Internal analysis: no public or dashboard placement, so no held → ack cycle
  is owed for placement; the artifact is nonetheless marked held pending PI
  review because it introduces a new estimator class.
- Login-node CPU only; no PBS work; nothing pushed.
- Two complete runs into distinct fresh directories must be recursively
  byte-identical; an independent verifier re-derives the gate arithmetic.
