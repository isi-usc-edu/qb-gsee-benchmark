# ML-9C primary-hardness promotion evidence

Date: 2026-08-02

The PI-authorized decoupling amendment was frozen in standalone commit
`72f94b57` before either ML-9D target was parsed. The amendment JSON SHA-256 is
`b8fead0bd18c1069a9d37d2b656f49a11a8885a4acf8751bb23230fe20e43464`.
Implementation followed in commit `feb46960`.

Two scoped promotion builds were made from the two original retained ML-9C raw
trees. All seven contracted files are byte-identical, both build trees remain
under `primary_promotion_raw_runs_v1`, and promoted `final_v1` recursively
matches build 1. The identity report SHA-256 is
`0b6c3894dc8c79df0084ce979330c32fa79e27fe6e5df75a5cee9624b8bcd77c`;
the promoted manifest SHA-256 is
`1ec1807bd0d48627e7dbec25c9741b17a0179eccfc47a06108f2a190675bc541`.

The promoted artifact is scoped to the family-aware binary Rasch
task-difficulty posterior. The 96-row handoff remains byte-for-byte unchanged
at SHA-256
`b8fac83b33da755361dd5049f4627e9f60495d0370a42b601a547617d295490a`.
Its full-posterior diagnostics pass: zero divergences, maximum R-hat
1.0052426278344706, minimum bulk ESS 2755.437918419625, and minimum tail ESS
2174.109214388564.

No factor product enters `final_v1`. The complete original, v2, and v3 trees
remain retained. Solver-side dimensionality remains exploratory, unreliable,
and unsupported; recovery is closed at v3 and no fourth attempt is authorized.
No solver run, reselection, or label change occurred.
