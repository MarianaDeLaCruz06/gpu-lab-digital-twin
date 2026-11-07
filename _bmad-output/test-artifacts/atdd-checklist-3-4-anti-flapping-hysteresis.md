---
stepsCompleted: ['step-01-preflight-and-context', 'step-02-generation-mode', 'step-03-test-strategy', 'step-04-generate-tests', 'step-04c-aggregate', 'step-05-validate-and-complete']
lastStep: 'step-05-validate-and-complete'
lastSaved: '2026-11-07'
storyId: '3.4'
storyKey: '3-4-anti-flapping-hysteresis'
storyFile: 'docs/spec-3-4-anti-flapping-hysteresis.md'
atddChecklistPath: '_bmad-output/test-artifacts/atdd-checklist-3-4-anti-flapping-hysteresis.md'
generatedTestFiles:
  - 'tests/acceptance/test_story_3_4_connectivity_flapping.py'
inputDocuments:
  - 'docs/spec-3-4-anti-flapping-hysteresis.md'
  - 'planning/ARCHITECTURE.md'
  - 'docs/contracts/behavioral-contracts.md'
  - 'tests/conftest.py'
  - '.agents/skills/bmad-testarch-atdd/resources/knowledge/data-factories.md'
  - '.agents/skills/bmad-testarch-atdd/resources/knowledge/component-tdd.md'
  - '.agents/skills/bmad-testarch-atdd/resources/knowledge/test-quality.md'
  - '.agents/skills/bmad-testarch-atdd/resources/knowledge/test-healing-patterns.md'
  - '.agents/skills/bmad-testarch-atdd/resources/knowledge/test-levels-framework.md'
  - '.agents/skills/bmad-testarch-atdd/resources/knowledge/test-priorities-matrix.md'
  - '.agents/skills/bmad-testarch-atdd/resources/knowledge/ci-burn-in.md'
acceptanceCriteria:
  - {id: 'AC-1', idSource: supplied, text: 'Five-second pulses preserve the stable public tuple and revision.'}
  - {id: 'AC-2', idSource: supplied, text: 'Exactly three and four transitions do not invent unresolved ODD-5 classification.'}
  - {id: 'AC-3', idSource: supplied, text: 'One unresolved diagnostic, zero flapping alerts, and one audit per unique observation.'}
  - {id: 'AC-4', idSource: supplied, text: 'Duplicate evidence is idempotent and conflicting reuse is rejected atomically.'}
---

# ATDD Preflight - Story 3.4

- Detected stack: backend (`pyproject.toml`, pytest `tests/conftest.py`).
- Mode: BMad-integrated; story, architecture, contracts, and existing test patterns loaded.
- Framework: pytest 9.2.0 with Hypothesis and SQLite integration fixtures; baseline 130/130 passing.
- Risk: P0 canonical test `ST-FLAP-001`; architecture/state stability, atomic idempotency, and alert flooding are primary risks.
- Test level: integration acceptance tests through the real application service and SQL repository, with unit policy vectors added only after RED if useful.
- Timing: injected `FakeClock` only; no sleeps or wall-clock assertions.

## Generation Mode

AI generation is selected because this is a backend-only pytest story with explicit canonical acceptance criteria and no browser surface to record.

## Test Strategy

| Criterion | Priority | Level | Primary RED scenario / first criterion assertion | Green branches |
|---|---|---|---|---|
| AC-1 | P0 | Integration acceptance | Container exposes the connectivity observation port, then 12 pulses preserve the public tuple/revision | Per-pulse tuple check |
| AC-2 | P0 | Integration acceptance | Exactly 3 then 4 transitions return a hold classified as `ERR_POLICY_UNRESOLVED` | 60-second boundary remains non-classifying |
| AC-3 | P0 | Integration acceptance | After unique pulses, open `ERR_POLICY_UNRESOLVED` diagnostic count is exactly 1 | zero `ERR_CONNECTIVITY_FLAPPING`; audit count equals unique evidence |
| AC-4 | P1 | Integration acceptance | Replay outcome is `DUPLICATE` | conflicting payload reuse rejects with unchanged counts |

The four criterion scaffolds exercise the real SQL adapter and application orchestration. Pure-policy unit vectors are Green/Refactor support only, avoiding duplicate RED coverage. Every scenario uses `FakeClock`; no browser/E2E layer applies.

## Authentic RED Execution

- Generated and activated: `tests/acceptance/test_story_3_4_connectivity_flapping.py` (4 tests, one per criterion).
- Result: 4 failed for the authentic missing `Container.connectivity` port after prerequisite heartbeat setup passed.
- Evidence: `evidence/impl2/atdd/story-3.4-red.txt`.

## Completion Validation

- The task's stricter requirement overrode the generic scaffold convention: tests were activated immediately, witnessed failing, and retained active. No `skip` marker remains.
- Criterion mapping: the four RED test names carry AC-1 through AC-4; Green support branches cover concurrency and invalid time without inflating the RED count.
- Final Story 3.4 selection: 8/8 passed (6 acceptance tests plus two parameterized pure-policy cases).
- Full suite: 138 passed, 0 failed, 0 skipped.
- Key assumption: ODD-5 remains unresolved; therefore no numeric flapping classification or flapping alert is claimed.
- No browser/CLI sessions or random temp artifacts were created.
