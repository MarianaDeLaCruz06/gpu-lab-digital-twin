# Impl-2 Presentation Evidence

## A. Process / Problems / Learnings

- Attempt: map Annex Story 3.4 onto binding Plan-2/Solu-2 before writing tests or code.
- Design conflict: the Annex prescribes `FLAPPING_CORDONED` and `>3` transitions in 60 seconds; canonical AD-5 explicitly leaves ODD-5 numeric policy unresolved.
- Human decision: reject the new state and invented threshold. Implement evidence-only containment with one unresolved diagnostic.
- Learning: safe containment can prevent oscillation and flooding without falsely claiming that an unapproved classifier exists.
- RED failure: four acceptance tests failed at the missing `Container.connectivity` inbound port after HEALTHY setup succeeded. This is the authentic unimplemented Story 3.4 seam.

## B. Execution / Tests

- Pre-change baseline: `uv run pytest -q -ra` -> 130 passed, 0 failed, 0 skipped in 10.43 seconds.
- RED: `uv run pytest tests/acceptance/test_story_3_4_connectivity_flapping.py -q -ra` -> 4 failed in 1.19s at HEAD `3abc6f2dc4001a8bb3d72d3fd70ad7eb1d504017`.
- GREEN: `uv run pytest tests/acceptance/test_story_3_4_connectivity_flapping.py tests/unit/test_connectivity_policy.py -q -ra` -> 8 passed in 1.17s.
- Full suite after refactor: 138 passed, 0 failed, 0 skipped in 11.93s; Ruff lint and format PASS.

## C. Git / Time / TLOC

- Baseline HEAD: `3abc6f2dc4001a8bb3d72d3fd70ad7eb1d504017` (`2026-10-26T01:23:42-05:00`, `fix: readme`).
- Impl-2 commits created in this run: none. Work remains uncommitted for human review.
- Intentional tracked changes: 111 added / 1 deleted line. Intentional new text/code/lock artifacts: 2,292 added lines, of which 1,625 are the generated `uv.lock`. Total recorded task delta excluding the supplied PDF and pre-existing dirty Story 1.1 file: 2,403 additions / 1 deletion.
- No elapsed engineering time is inferred from wall-clock timestamps.

## D. Teamwork / Validation

- Team: Mariana De La Cruz and Julian Motta.
- Julian authorized preserving the pre-existing dirty Story 1.1 spec untouched and directed canonical-contract precedence over Annex examples.
- Validation plan: authentic RED, targeted Green, full pytest, Ruff lint/format, static sleep scan, and final dirty-file hash comparison.
- Final validation: 138 tests pass; no skips; no hardcoded sleeps; Story 1.1 dirty-file hash remained `9b849aca052448ffbd69ba9e470bee65139e248c`.
