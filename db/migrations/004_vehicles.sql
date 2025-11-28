-- Migration: 004_vehicles
-- Description: Create vehicles reference table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS vehicles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,
  customer_id UUID REFERENCES customers(id),
  tm_customer_id INTEGER,              -- Denormalized for sync

  -- Vehicle info
  year INTEGER,
  make TEXT,
  make_id INTEGER,
  model TEXT,
  model_id INTEGER,
  sub_model TEXT,
  sub_model_id INTEGER,
  engine TEXT,
  engine_id INTEGER,
  transmission TEXT,
  transmission_id INTEGER,
  drive_type TEXT,
  drive_type_id INTEGER,
  body_style TEXT,

  -- Identifiers
  vin TEXT,
  license_plate TEXT,
  license_state TEXT,
  unit_number TEXT,
  fleet_number TEXT,

  -- Appearance
  color TEXT,
  interior_color TEXT,

  -- Odometer
  odometer INTEGER,
  odometer_unit TEXT,                  -- miles, km
  odometer_date DATE,

  -- Custom
  custom_description TEXT,
  notes TEXT,

  -- TM references
  base_vehicle_id INTEGER,

  -- TM overflow
  tm_extra JSONB,

  -- Sync
  tm_created_at TIMESTAMPTZ,
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, tm_id)
);

CREATE INDEX IF NOT EXISTS idx_vehicles_shop ON vehicles(shop_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_customer ON vehicles(shop_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_vin ON vehicles(shop_id, vin) WHERE vin IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_vehicles_tm_id ON vehicles(tm_id);

COMMENT ON TABLE vehicles IS 'Vehicle records from TM. Linked to customers via customer_id.';
