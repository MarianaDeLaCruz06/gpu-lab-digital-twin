# Deferred Work

- source_spec: `docs/spec-1-1-see-the-complete-simulated-fleet.md`
  summary: Multi-writer hardening — a database-level ingest sequencer and a test for the `event_id` unique-violation branch, so a concurrent identical replay that loses the race returns the recorded `DUPLICATE` result.
  evidence: Unverified while writes are serialized by the single-process lock (documented in README). If the service ever runs with more than one worker, `MAX(ingest_offset)+1` collides (unmapped → 503), and a losing identical replay gets 409 instead of `DUPLICATE`. Settle it by running two processes against one PostgreSQL database and replaying the same heartbeat concurrently. Natural home: Story 1.2.
- source_spec: `docs/spec-1-3-detect-silence-at-the-exact-boundary.md`
  summary: Test a storage-level failure (IntegrityError) inside `commit_transition` and assert atomicity of the silence transition.
  evidence: Per-node isolation is tested with a raised DomainError, but the IntegrityError mapping and the no-partial-write guarantee of the transition path are not exercised. Settle it with a fault-injecting session or a constraint violation in a PostgreSQL test.
- source_spec: `docs/spec-2-1-cordon-an-overheating-workstation.md`
  summary: A heartbeat above 88 °C that also carries reboot evidence is rejected (409) and its thermal reading is not applied, so the node keeps its prior eligibility.
  evidence: Real but contract-consistent. Rejected input mutates nothing (P-H3), and Story 1.1 D2 fails reboots closed. Story 2.2 accepts proven reboots, after which the thermal rule applies to the same heartbeat. Settle it with a 2.2 test: proven reboot + 91 °C → RECOVERING, cordoned, ERR_THERMAL_88 active.
