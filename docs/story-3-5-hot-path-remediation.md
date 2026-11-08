# Story 3.5 Hot-Path Remediation Analysis (pre-implementation)

**Branch:** `feature/story-3.5-nfr-remediation` (baseline `b90ff5c`)  
**Scope:** focused architecture remediation spike for heartbeat NFR. No SQLite/PostgreSQL tuning reruns in this phase. No historical evidence modified.

## Phase 1 — Current hot path (evidence)

### 1. Entry and global serialization

- **HTTP route:** `src/gpu_lab_twin/api/routes/telemetry.py:17-28` — `POST /v1/nodes/{nodeId}/heartbeats` is a **sync** FastAPI handler that calls `container.heartbeats.ingest_heartbeat(...)` and returns the validated response in the same request.
- **Composition:** `src/gpu_lab_twin/bootstrap.py:46-83` wires a single process-wide `threading.Lock()` (`write_lock`, line 51) into `HeartbeatService` (59-66), `LivenessService` (67-73), `ConnectivityService` (75-80), and `MaintenanceService` (82). `DurableHeartbeatBatchWriter` (`src/gpu_lab_twin/application/heartbeat_batch_writer.py`) is **not imported or instantiated** anywhere in production code (only referenced in docs/spec text).
- **Service critical section:** `src/gpu_lab_twin/application/heartbeat_service.py:29-33,58-164` documents and implements: `with self._write_lock:` spans **the entire ingest decision path** — clock read, `validate_heartbeat`, idempotency lookup (`find_heartbeat`), node load (`get_node`), clock-order/late/boot checks, deterministic evaluation, explanation/result construction, `commit_heartbeat(...)`, and post-commit `downsampler.observe(...)` (162-164). The lock is released only after the method returns to the caller (end of `with`).
- **Conclusion (1):** The global critical section is effectively **validate + read + decide + durable commit + response preparation** for every heartbeat request (and it contends with liveness/connectivity/maintenance using the same lock). It is **not** limited to offset assignment/commit.

### 2. SQL work per normal APPLIED heartbeat (single-commit path)

`SqlNodeRepository.commit_heartbeat` (`adapters/db/node_repository.py:165-169`) delegates to `commit_heartbeat_batch((commit,))`. For one `HeartbeatCommit` in one transaction (`177-234`):

| Step | Location | Typical SQL (happy path, applied, transition/alert cases vary) |
|---|---|---|
| Begin transaction | `session_factory.begin()` | transaction begin |
| Base ingest offset | `178` `select coalesce(max(telemetry_snapshots.ingest_offset)+1,0)` | **1 SELECT** (aggregate scan/index behavior DB-dependent) |
| Clear `is_current` for affected nodes | `186-191` | **1 UPDATE** on `telemetry_snapshots` (`node_id`, `is_current`) |
| CAS projection | `520-545` `_compare_and_set` | **1 UPDATE ... RETURNING revision** (+ possible SELECT on conflict path, not happy path) |
| Telemetry append | `548-604` `_append_telemetry` | **1 INSERT** telemetry snapshot + **1 flush** boundary + **1..N INSERTs** GPU samples (`596-604`, one row per configured GPU sample) |
| State history (only if transitioned) | `607-624` | **0 or 1 INSERT** |
| Close alerts | `627-634` | **0 or 1 UPDATE** (when `closed_alert_reasons`) |
| Upsert open alerts | `637-661` per `alert_reason` | **1 UPSERT** per observed reason (dialect insert/on-conflict) |
| Audit | `664-677` | **1 INSERT** |
| Commit | context exit | **1 COMMIT** |

**Approximate normal APPLIED case (no transition, no closed alerts, 1 observed reason, 1-2 GPU samples):** ~8–12 SQL statements in **1 DB transaction** (offset SELECT + is_current UPDATE + CAS UPDATE + telemetry INSERT/flush + GPU sample INSERT(s) + alert UPSERT + audit INSERT + commit). More when transitioning, closing alerts, or multiple alert reasons.

### 3. Transactions per heartbeat

- **1 durable DB transaction per heartbeat command** in the current implementation (each `commit_heartbeat`/single-item batch is one `begin()` block). Batch method supports multiple commits in one transaction, but production never calls it with >1 item.
- **HTTP response** is returned only after `commit_heartbeat` completes successfully (`heartbeat_service.py:147-164,27` of `telemetry.py`).

### 4. Work that genuinely requires global ordering

From repository text:

- `planning/ARCHITECTURE.md` AD-1 (460-475): “**Every accepted input receives one monotonic `ingest_offset` from the sole serialized sequencer**; only the Node Event Processor may mutate… and it must consume that node's inputs in increasing offset order and atomically commit projection, lock, evidence, alert, and idempotency writes by compare-and-swap on the node revision.” Also states “Events for different nodes may proceed concurrently” is limited by per-node serialization in concept but AD-1 requires offset assignment by sole sequencer and ordered consumption/atomic commit semantics.
- `planning/ARCHITECTURE.md` §6.1 (224-232): sequencer assigns strictly increasing `ingest_offset` under “one serialization point”; per-node processor consumes increasing offsets and “commits… through one DomainUnitOfWork… Failure of any write aborts all writes for that input.”
- `planning/detailed-design/contracts.md` and `docs/contracts/behavioral-contracts.md` §1 concurrency (52-54): “The sole global sequencer assigns `ingestOffset`; one processor serializes each node. The repository performs one conditional update…” and “Events for different nodes may proceed concurrently.”

**Genuinely global (ordering/identity):** assignment of a globally monotonic, unique `ingest_offset` consistent with accepted durable order, and any operation whose correctness depends on that global sequence being committed in that order. The *unit of durable truth* for an accepted heartbeat must include the atomic effects described (projection/CAS, evidence/idempotency-relevant telemetry/audit/history/alerts as applicable) — see Phase 2.

### 5. Work that requires same-node ordering (not global serialization of all prep)

- Per-node: revision CAS (`expected_revision`), `last_accepted_event_at/receive_at`, boot session/epoch succession, current-epoch late detection, `is_current` telemetry semantics, per-node alert episodes/state history continuity. `contracts.md`/AD-1 allow “one processor serializes each node”; different nodes may proceed concurrently **if** global offset assignment and durable commit ordering semantics remain satisfied.

### 6. Work that can occur before global sequenced commit (candidate, contract-dependent)

Potentially parallelizable/preparable **if** final commit/offset order and ack-after-commit are preserved:
- Inventory lookup (`spec`), payload canonical hash (pure), most of `validate_heartbeat` against spec/payload/time inputs (pure given inputs) — but `at` is receive time currently read **under** lock (`60-61`).
- Idempotency precheck is read-heavy but must remain consistent with commit; duplicate-by-event-id with same hash can return recorded response — care needed if racing with in-flight commit of same event (rare) and with global ordering of “first accepted”.
- Building pure domain decisions/explanations for *independent* nodes once required facts are known — but facts include current node snapshot/CAS revision; stale reads break CAS.

### 7. Work groupable across heartbeats in one transaction

- `commit_heartbeat_batch` already implements multi-commit atomic persistence in one transaction with contiguous offsets (`base_offset + idx`), batch `is_current` handling, and per-commit CAS/append logic (`171-234`). **Contract-safe grouping** requires: same atomicity/rollback semantics (failure aborts all writes for that input/batch as specified), per-request outcomes resolved only after commit, preserved per-node ordering, global monotonic unique offsets, and no response before durable commit.

### 8. What prevents the existing batch writer from being used

- **Not wired:** no bootstrap/app instantiation, no route uses `submit()`/`Future`.
- **API/processing mismatch:** `DurableHeartbeatBatchWriter.submit()` enqueues a command and returns a `Future` (`56-68`); `process_batch` callback is expected to process a batch (`40,110,128`). There is **no adapter** that turns `HeartbeatCommand`s into `HeartbeatService` decisions + repository batch commits while preserving per-request `HeartbeatResult`/exceptions.
- **Lock ownership:** batch writer takes `write_lock` around `process_batch` (`109-110,127-128`), but `HeartbeatService.ingest_heartbeat` also takes the same lock internally — composing them directly would deadlock or require refactoring.
- **Sync HTTP path:** route is synchronous; integrating async waiting on futures requires careful design (threadpool/async bridge) without breaking request semantics.
- **Coverage/history:** spec noted it was intentionally unwired and affected repo-wide coverage accounting; using it requires product-quality integration and tests.

## Phase 2 — Contract interpretation (repository text)

### Question
Does the contract require: **A.** one globally serialized COMPLETE request transaction, **B.** globally ordered durable commit / ingest_offset assignment while independent preparation can occur concurrently, or **C.** another model?

### Evidence

1. **Global offset / sequencer:** `planning/ARCHITECTURE.md` AD-1: “Every accepted input receives one monotonic `ingest_offset` from the sole serialized sequencer…”; §6.1: “Global Input Sequencer is the sole offset assigner. Under one serialization point it assigns a strictly increasing `ingest_offset`…”; `contracts.md` §1: “The sole global sequencer assigns `ingestOffset`…” (`planning/detailed-design/contracts.md:53`, mirrored in `docs/contracts/behavioral-contracts.md:53`).
2. **Atomic durable commit (all-or-nothing per input):** §6.1: “commits projection, Maintenance Lock, Decision Record, Alert Episode changes, Evidence Ledger entry, and idempotency result through one DomainUnitOfWork… Failure of any write aborts all writes for that input.”; contracts §1 Q34/38: applied work atomically persisted; “All rejected calls guarantee no node projection, lock, telemetry-current, history, alert, or domain-event mutation…”; duplicate/late outcomes have specific no-mutation/record-once semantics.
3. **Exposure/ack ordering:** `contracts.md` §1 latency (59-62): “NFR-11 defines no numeric latency SLA. The binding budget is exposure ordering: state, cordon, alert, and explanation commit before the new fleet version becomes visible…”; AD-1 requires atomic commit of those effects. HTTP ingress is synchronous and returns the outcome (route returns after service) — **no acknowledged success before required durable semantics complete** is consistent with atomic commit-before-response.
4. **Per-node vs global concurrency:** `contracts.md` §1/§2: “one processor serializes each node… Events for different nodes may proceed concurrently.” This conflicts with a literal reading of “globally serialized COMPLETE request transaction” as the *only* allowed model for all work; it explicitly permits cross-node concurrency **subject to** ordering/serialization rules.
5. **Invariants:** I-H1/I-H2 bind to AD-1 (unique event/payload outcome, stale cannot replace current) — require correct ordering/idempotency and durable recording, not necessarily that validation/decision for node B cannot run while node A is being prepared, **provided** final commit/offset/CAS semantics are preserved.

### Interpretation

**Answer: primarily B, with C constraints (not A as stated).**

- **Not A (one globally serialized COMPLETE request transaction for all phases):** repository text explicitly allows events for **different nodes** to proceed concurrently (`contracts.md`) and defines the sequencer’s role as assigning global `ingest_offset` under serialization, while commits are atomic DomainUnitOfWork operations. A smaller critical section is **not forbidden by text alone** if global offset/commit order and per-node CAS/ordering remain correct.
- **B elements required:** globally ordered durable commit / `ingest_offset` assignment consistent with sole sequencer semantics; atomic commit of required effects; no response/exposure before commit.
- **C elements (binding):** same-node serialization/CAS correctness; “failure of any write aborts all writes for that input”; duplicate/late/boot/conflict outcomes and their durability rules preserved; `contracts.md` notes “no SELECT-then-UPDATE mutation is permitted” for repository CAS patterns.

**Conclusion (2):** complete global serialization of the *entire* request (validate+read+decide+persist as one indivisible global critical section across all nodes) is **not explicitly required** by the cited contract text; **globally ordered durable commit/offset sequencing and atomicity are required**. Therefore a smaller critical section / internal batching is **potentially contract-safe** only if implemented without weakening those semantics. This requires careful design (not present today).

## Phase 3+ — Stop/go

- **Contract blocker to material improvement?** No explicit text requires A. **However**, achieving material throughput under B/C is non-trivial: current bottleneck is global lock + 1 transaction/heartbeat + offset allocation (`max+1`) and multi-statement commits. Any redesign must preserve ack-after-commit, deterministic ordering, and all canonical dispositions.
- **Implementation not performed in this phase.** Next step (if pursued): design per-node preparation + globally sequenced batch commit with contiguous offset reservation, bounded queue/backpressure, futures resolved only post-commit, and full regression/NFR gates per spike instructions.

## Files inspected

- `src/gpu_lab_twin/application/heartbeat_service.py`
- `src/gpu_lab_twin/application/heartbeat_batch_writer.py`
- `src/gpu_lab_twin/adapters/db/node_repository.py`
- `src/gpu_lab_twin/adapters/db/engine.py`
- `src/gpu_lab_twin/domain/heartbeat_policy.py`
- `src/gpu_lab_twin/domain/telemetry_downsampling.py`
- `src/gpu_lab_twin/domain/heartbeat.py`
- `src/gpu_lab_twin/api/routes/telemetry.py`
- `src/gpu_lab_twin/api/app.py`
- `src/gpu_lab_twin/bootstrap.py`
- `src/gpu_lab_twin/application/liveness_service.py`
- `src/gpu_lab_twin/ports/outbound/node_repository.py`
- `planning/ARCHITECTURE.md` (AD-1, §6.1, NFR/stack notes)
- `planning/detailed-design/contracts.md`, `docs/contracts/behavioral-contracts.md`
- `docs/story-3-5-nfr-bottleneck-analysis.md`, `docs/spec-3-5-telemetry-storm.md` (context)
