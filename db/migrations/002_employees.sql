-- Migration: 002_employees
-- Description: Create employees reference table
-- Date: 2025-11-27

CREATE TABLE IF NOT EXISTS employees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id UUID NOT NULL REFERENCES shops(id),
  tm_id INTEGER NOT NULL,

  -- Core fields
  first_name TEXT,
  last_name TEXT,
  email TEXT,
  role INTEGER,                        -- 1=Admin, 2=Advisor, 3=Tech, 4=Owner
  role_name TEXT,                      -- Human readable
  hourly_rate INTEGER,                 -- cents (for technicians)
  status TEXT,                         -- ACTIVE, INACTIVE

  -- Store all TM fields
  username TEXT,
  phone TEXT,
  hire_date DATE,
  termination_date DATE,
  commission_rate DECIMAL(5,4),
  can_clock_in BOOLEAN,
  can_sell BOOLEAN,
  can_tech BOOLEAN,

  -- TM overflow (any fields we don't have columns for)
  tm_extra JSONB,

  -- Sync tracking
  tm_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(shop_id, tm_id)
);

CREATE INDEX IF NOT EXISTS idx_employees_shop_role ON employees(shop_id, role);
CREATE INDEX IF NOT EXISTS idx_employees_shop_status ON employees(shop_id, status);
CREATE INDEX IF NOT EXISTS idx_employees_tm_id ON employees(tm_id);

COMMENT ON TABLE employees IS 'Employees from TM. Role: 1=Admin, 2=Advisor, 3=Tech, 4=Owner. Status: ACTIVE, INACTIVE.';
COMMENT ON COLUMN employees.hourly_rate IS 'Technician hourly cost rate in cents';
