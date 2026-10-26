-- Module 3 Solu-2 schema contract. PostgreSQL; timestamps are stored as timestamptz (UTC instants).
-- No production migration runner or application logic is included.

CREATE TYPE node_kind AS ENUM ('WORKSTATION', 'SERVER');
CREATE TYPE node_state AS ENUM ('UNKNOWN','HEALTHY','DEGRADED','RECOVERING','DRAINING','MAINTENANCE','OFFLINE');
CREATE TYPE connectivity_status AS ENUM ('UNKNOWN','ONLINE','SILENT','CONNECTIVITY_UNSTABLE');
CREATE TYPE driver_health AS ENUM ('HEALTHY','UNHEALTHY','UNKNOWN');
CREATE TYPE telemetry_disposition AS ENUM ('APPLIED','LATE_IGNORED','BOOT_CHANGE_DETECTED');

CREATE TABLE nodes (
    node_id varchar(63) PRIMARY KEY CHECK (node_id ~ '^[a-z0-9][a-z0-9-]{0,62}$'),
    kind node_kind NOT NULL,
    state node_state NOT NULL DEFAULT 'UNKNOWN',
    cordoned boolean NOT NULL DEFAULT true,
    connectivity connectivity_status NOT NULL DEFAULT 'UNKNOWN',
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    evidence_epoch bigint NOT NULL DEFAULT 0 CHECK (evidence_epoch >= 0),
    current_boot_session_id varchar(128),
    heartbeat_interval_ms bigint NOT NULL CHECK (heartbeat_interval_ms > 0),
    storage_capacity_gb numeric(12,3) NOT NULL CHECK (storage_capacity_gb > 0),
    last_accepted_event_at timestamptz,
    last_accepted_receive_at timestamptz,
    active_reason_codes text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT nodes_state_cordon_ck CHECK (state = 'HEALTHY' OR cordoned = true),
    CONSTRAINT nodes_last_times_ck CHECK (
      last_accepted_event_at IS NULL OR last_accepted_receive_at IS NOT NULL
    )
);

CREATE TABLE gpu_devices (
    gpu_device_id varchar(128) PRIMARY KEY,
    node_id varchar(63) NOT NULL REFERENCES nodes(node_id) ON DELETE RESTRICT,
    ordinal smallint NOT NULL CHECK (ordinal >= 0),
    vram_capacity_gb numeric(8,3) NOT NULL CHECK (vram_capacity_gb IN (24,48)),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (node_id, ordinal),
    UNIQUE (node_id, gpu_device_id)
);

CREATE TABLE telemetry_snapshots (
    telemetry_id uuid PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE,
    node_id varchar(63) NOT NULL REFERENCES nodes(node_id) ON DELETE RESTRICT,
    payload_hash char(64) NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    schema_version varchar(16) NOT NULL CHECK (schema_version = '1.0'),
    occurred_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL,
    ingest_offset bigint NOT NULL UNIQUE CHECK (ingest_offset >= 0),
    source_sequence bigint CHECK (source_sequence >= 0),
    boot_session_id varchar(128) NOT NULL,
    previous_boot_session_id varchar(128),
    evidence_epoch bigint NOT NULL CHECK (evidence_epoch >= 0),
    state_loss boolean NOT NULL,
    driver_health driver_health NOT NULL,
    storage_free_gb numeric(12,3) NOT NULL CHECK (storage_free_gb >= 0),
    external_context jsonb,
    disposition telemetry_disposition NOT NULL,
    is_current boolean NOT NULL DEFAULT false,
    explanation jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT telemetry_external_source_ck CHECK (
      external_context IS NULL OR external_context ->> 'source' = 'EXTERNAL_MOCK'
    )
);

CREATE UNIQUE INDEX telemetry_one_current_per_node_uq
  ON telemetry_snapshots(node_id) WHERE is_current;
CREATE UNIQUE INDEX telemetry_sequence_per_session_uq
  ON telemetry_snapshots(node_id, boot_session_id, source_sequence)
  WHERE source_sequence IS NOT NULL AND disposition IN ('APPLIED','BOOT_CHANGE_DETECTED');

CREATE TABLE telemetry_gpu_samples (
    telemetry_id uuid NOT NULL REFERENCES telemetry_snapshots(telemetry_id) ON DELETE CASCADE,
    gpu_device_id varchar(128) NOT NULL REFERENCES gpu_devices(gpu_device_id) ON DELETE RESTRICT,
    temperature_c numeric(7,3) NOT NULL CHECK (temperature_c >= 0),
    vram_occupied_gb numeric(8,3) NOT NULL CHECK (vram_occupied_gb >= 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (telemetry_id, gpu_device_id)
);

CREATE TABLE node_state_history (
    transition_id uuid PRIMARY KEY,
    source_event_id uuid NOT NULL,
    node_id varchar(63) NOT NULL REFERENCES nodes(node_id) ON DELETE RESTRICT,
    prior_state node_state NOT NULL,
    result_state node_state NOT NULL,
    prior_cordoned boolean NOT NULL,
    result_cordoned boolean NOT NULL,
    node_revision bigint NOT NULL CHECK (node_revision > 0),
    rule_ids text[] NOT NULL CHECK (cardinality(rule_ids) > 0),
    evidence_ids text[] NOT NULL CHECK (cardinality(evidence_ids) > 0),
    explanation jsonb NOT NULL,
    occurred_at timestamptz NOT NULL,
    schema_version varchar(16) NOT NULL CHECK (schema_version = '1.0'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (node_id, node_revision),
    UNIQUE (source_event_id, node_id, result_state)
);

CREATE TABLE maintenance_locks (
    lock_id uuid PRIMARY KEY,
    request_id uuid NOT NULL UNIQUE,
    request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    node_id varchar(63) NOT NULL REFERENCES nodes(node_id) ON DELETE RESTRICT,
    reason varchar(500) NOT NULL CHECK (length(btrim(reason)) > 0),
    actor varchar(128) NOT NULL CHECK (length(btrim(actor)) > 0),
    acquired_at timestamptz NOT NULL,
    expected_node_revision bigint NOT NULL CHECK (expected_node_revision >= 0),
    active boolean NOT NULL DEFAULT true,
    released_at timestamptz,
    release_request_id uuid UNIQUE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT maintenance_release_ck CHECK (
      (active AND released_at IS NULL) OR (NOT active AND released_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX maintenance_locks_one_active_uq
  ON maintenance_locks(node_id) WHERE active;

CREATE TABLE alerts (
    alert_id uuid PRIMARY KEY,
    node_id varchar(63) NOT NULL REFERENCES nodes(node_id) ON DELETE RESTRICT,
    reason_code varchar(128) NOT NULL,
    opened_at timestamptz NOT NULL,
    last_observed_at timestamptz NOT NULL,
    closed_at timestamptz,
    update_count bigint NOT NULL DEFAULT 1 CHECK (update_count >= 1),
    explanation jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT alerts_close_order_ck CHECK (closed_at IS NULL OR closed_at >= opened_at),
    CONSTRAINT alerts_observed_order_ck CHECK (last_observed_at >= opened_at)
);

CREATE UNIQUE INDEX alerts_one_open_per_reason_uq
  ON alerts(node_id, reason_code) WHERE closed_at IS NULL;

CREATE TABLE audit_events (
    audit_id uuid PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE,
    node_id varchar(63) REFERENCES nodes(node_id) ON DELETE RESTRICT,
    event_type varchar(128) NOT NULL,
    occurred_at timestamptz NOT NULL,
    schema_version varchar(16) NOT NULL CHECK (schema_version = '1.0'),
    rule_ids text[] NOT NULL,
    evidence_ids text[] NOT NULL,
    body jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Atomic mutation pattern required by AD-1. Callers must check that exactly one row returns.
-- No preceding SELECT is permitted for the write decision.
-- UPDATE nodes
-- SET state = :state, cordoned = :cordoned, connectivity = :connectivity,
--     revision = revision + 1, evidence_epoch = :evidence_epoch,
--     active_reason_codes = :reason_codes, updated_at = :now
-- WHERE node_id = :node_id AND revision = :expected_revision
-- RETURNING *;

-- The UPDATE above and all telemetry/history/lock/alert/audit inserts are executed in one
-- PostgreSQL transaction. Unique/partial indexes arbitrate duplicate concurrent opens.
