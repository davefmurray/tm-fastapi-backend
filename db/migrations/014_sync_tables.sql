-- Migration: 014_sync_tables
-- Description: Create sync management tables (sync_cursors, sync_log, tm_raw_payloads)
-- Date: 2025-11-27

-- ============================================================================
-- sync_cursors: Track where we left off for incremental syncs
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_cursors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  entity_type TEXT NOT NULL,           -- 'repair_orders', 'employees', etc.

  -- Cursor state
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_tm_updated TIMESTAMPTZ,         -- Max updatedDate seen from TM
  last_tm_id INTEGER,                  -- Last TM ID processed (for paging)

  -- Additional state
  cursor_data JSONB,

  UNIQUE(shop_id, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_sync_cursors_shop ON sync_cursors(shop_id);

COMMENT ON TABLE sync_cursors IS 'Tracks sync progress for incremental updates. One row per shop per entity type.';

-- ============================================================================
-- sync_log: Audit trail for sync operations
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),

  -- Sync details
  sync_type TEXT NOT NULL,             -- 'full_backfill', 'incremental', 'snapshot_rebuild'
  entity_type TEXT,                    -- 'repair_orders', 'employees', etc.

  -- Timing
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  duration_ms INTEGER,

  -- Status
  status TEXT NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed'

  -- Counts
  records_fetched INTEGER DEFAULT 0,
  records_created INTEGER DEFAULT 0,
  records_updated INTEGER DEFAULT 0,
  records_skipped INTEGER DEFAULT 0,

  -- Errors
  error_count INTEGER DEFAULT 0,
  errors JSONB,                        -- Array of error details

  -- Metadata
  metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_sync_log_shop ON sync_log(shop_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_log_status ON sync_log(status, started_at DESC);

COMMENT ON TABLE sync_log IS 'Audit trail for all sync operations. Retain 30 days via scheduled cleanup.';

-- ============================================================================
-- tm_raw_payloads: Store raw TM API responses for debugging and replay
-- ============================================================================

CREATE TABLE IF NOT EXISTS tm_raw_payloads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),

  -- Source
  endpoint TEXT NOT NULL,              -- '/api/repair-order/123/estimate'
  method TEXT NOT NULL DEFAULT 'GET',
  tm_entity_id INTEGER,                -- RO ID, customer ID, etc.

  -- Payload
  request_params JSONB,
  response_payload JSONB NOT NULL,
  response_status INTEGER,

  -- Timing
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Retention marker (7-day default)
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days')
);

CREATE INDEX IF NOT EXISTS idx_raw_payloads_shop ON tm_raw_payloads(shop_id, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_payloads_expires ON tm_raw_payloads(expires_at);
CREATE INDEX IF NOT EXISTS idx_raw_payloads_entity ON tm_raw_payloads(shop_id, tm_entity_id);

COMMENT ON TABLE tm_raw_payloads IS 'Raw TM API responses for debugging. 7-day retention. Auto-delete via scheduled job.';
COMMENT ON COLUMN tm_raw_payloads.expires_at IS 'Records older than this are eligible for deletion';
