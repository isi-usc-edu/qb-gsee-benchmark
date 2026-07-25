# ML-5c gradeable-eligible reselection — HELD (pending PI ack)

Reselection of the k=96 `floor_free` campaign panel over the gradeable
candidate set, under the unchanged binding doctrine. **Supersedes
nothing**: `d1627e66…` remains the
campaign-scope manifest of record until a PI ack for ML-5c is issued and
consumed. `binding_selection` is `false` in every payload.

## Candidate set

- corpus tasks: 718
- gradeable candidates (ML-8A census): **609**
- excluded as panel-ineligible per Matt O43: 109
- every candidate placeable in the metric: **true** (minimum shared blocks among candidate pairs: 5)

## Selection

| mode | role | coverage radius | q95 | families hit | families unsampled |
|---|---|---|---|---|---|
| `pure_reselection` | PRIMARY | 0.543087186606 | 0.489786936827 | 23 | 17 |
| `retain_and_extend` | SECONDARY_LABELLED_VARIANT | 0.537879115692 | 0.489739580505 | 23 | 17 |

### Delta against the manifest of record

| mode | retained | leaving | entering | rerun tasks | rerun cells (× 4 locked solvers) |
|---|---|---|---|---|---|
| `pure_reselection` | 78 | 18 | 18 | 18 | 72 |
| `retain_and_extend` | 80 | 16 | 16 | 16 | 64 |

Solver identities are NOT reopened; the bill of materials names the four
locked identities only.

## Two weight sets, two populations

- `selection_weights_609` — Voronoi cluster sizes over the 609 gradeable candidates. **Scored-population weighting**; the only one admissible for population success-rate statements. max weight 125, min 1.
- `coverage_weights_718` — all 718 corpus tasks mapped to their nearest selected center. **Coverage/deployment map only, NOT a scored-population weighting**; every row is labelled. max weight 128.

## Zero-gradeable families — no population statements

6 canonical families have no gradeable task and are unrepresentable in any gradeable panel. Scored weight attributed to them: **0**.

| canonical family | corpus tasks |
|---|---|
| `catalyst_fe_red` | 9 |
| `tight_binding_controls` | 5 |
| `validation_ccpvdz` | 4 |
| `catalyst_mo2_n2` | 3 |
| `catalyst_vonburg_ru_ix_cas16_fb_68e62o` | 1 |
| `diamond_2x2x2_periodic_solid` | 1 |

## FLAG — 191 vs 193 column metric divergence

Pre-existing in the accepted record, not introduced here, and
scientifically material. The ML-5 binding selection used **191** columns; the accepted
G-50/ML-8C/ML-8D chain uses **193**. The two extra columns
(max_edge_order, min_edge_order) are populated on only **184/718** tasks, so admitting them adds a
narrow applicability block. The primary run uses the 191-column metric
exactly as ordered, so the delta above is attributable solely to the
gradeable-eligibility restriction; the 193-column run is reported as a
sensitivity. ML-5c does not rule on which metric should be canonical.

Sensitivity overlap (primary vs 193-column, same mode and seed): **84/96** centers shared (0.875000).

## Deployment-target estimate layer

109 non-gradeable tasks × 18 eligible variants = **1962** estimate rows, each carrying the ML-8D
posterior mean and 95% credible interval plus the assigned nearest
gradeable center. Every row is `output_kind=estimate` with
`validated_predictor_claim=false`, and the ML-8D adjudication travels
verbatim:

> at the accessible panel size, model calibration could be neither established nor refuted

Variants certified calibrated: **0**. The design-based
track remains the sole ratio of record and the ML-6
no-validated-predictor rule stands unamended.

## Fences honoured

- held; `binding_selection=false`; no promotion commit in this wave
- outcome-blind: no solver outcome, label, or metric bundle read in the
  selection
- family is reporting-only, never a selection or assignment input
- solver identities not reopened; no solver run, submission, or PBS work
