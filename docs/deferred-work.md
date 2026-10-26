# Deferred Work

- source_spec: `docs/spec-1-1-see-the-complete-simulated-fleet.md`
  summary: Multi-writer hardening — a database-level ingest sequencer and a test for the `event_id` unique-violation branch, so a concurrent identical replay that loses the race returns the recorded `DUPLICATE` result.
  evidence: Unverified while writes are serialized by the single-process lock (documented in README). If the service ever runs with more than one worker, `MAX(ingest_offset)+1` collides (unmapped → 503), and a losing identical replay gets 409 instead of `DUPLICATE`. Settle it by running two processes against one PostgreSQL database and replaying the same heartbeat concurrently. Natural home: Story 1.2.
