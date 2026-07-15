# G40 P2 MFPROTO-v3 production report

## Result

- Status: **passed**.
- Corpus states merged: **591/591**.
- Feature table: **591 x 253** to **591 x 580**.
- New columns: **327**.
- Contract-shape compatibility rows: **4** (no-converged-SCF child panels null-filled; raw states unchanged).
- Newly populated cells: **167907**.
- Existing populated P2 cells audited: **0**.
- Changed populated cells: **0**.
- PBS jobs: **16/16** successful; actual allocation **31.191 node-hours**.
- Representation gate: **passed** (6/6).
- Output table SHA-256: `8f0d89ec2cc7cf933a57c4ace7d32cd62d478c0fb8f8272aae4d36d387d45b2b`.

The merge is additive and corpus-manifest-driven. It changes no problem
instance, reference, solution record, solver harness, or S3 object.
