# Impl-2 Testing Flows

## Flow A - ATDD-First

Story 3.4 uses executable acceptance tests before production implementation. The RED command, failing IDs, output, HEAD, and authentic missing seam are captured in `evidence/impl2/atdd/story-3.4-red.txt`. Green must not be relabeled as Flow B.

## Flow B - Test-Along

After the authentic Story 3.4 RED reached Green, the well-understood pure unresolved-policy function evolved with `tests/unit/test_connectivity_policy.py`. A concurrent duplicate branch was also added alongside repository/service hardening in `tests/acceptance/test_story_3_4_connectivity_flapping.py`. These are Flow B support tests; they are not relabeled ATDD Green criteria and were not part of the captured RED count.

## Flow C - Test-After Hardening

The post-Green branch-coverage review found no meaningful non-duplicative gap in Impl-1 Stories 3.1-3.3. Core policy coverage is already heartbeat policy 100%, node reducer 100%, liveness service 100%, and heartbeat service 97%; integration coverage includes cross-node idempotency conflicts, clock rollback, exact silence boundary, stored thermal precision, retained reasons, and atomic alert behavior. **No Flow C regression test was added**; a deficiency was not invented for the assignment.

## Later Flows

Flow D (k6/NFR) belongs to Story 3.5 and Flow E (Playwright/POM) belongs to Story 3.6. Neither behavior is implemented in Run 1.
