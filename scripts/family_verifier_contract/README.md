# Family Verifier Contract

`verify_family.py` is the read-only admission verifier required for new FCIDUMP
families. A family config supplies its candidate, schema, artifact hashes,
reference matches, detector fields, redistribution evidence, and allowed S3
prefixes. The verifier reports exactly nine contract checks and never writes to
S3.

Run the promoted-family self-test from the project workspace root:

```bash
python qb-gsee-benchmark/scripts/family_verifier_contract/selftest.py
```

New family goals should copy the config shape, declare only their authorized
object-key prefixes, and require a green report before emission.
