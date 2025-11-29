-- Migration: 016_employee_pay_fields
-- Description: Add salary and pay type fields to employees
-- Date: 2025-11-29

-- Add salary (annual, in cents)
ALTER TABLE employees ADD COLUMN IF NOT EXISTS salary INTEGER;
COMMENT ON COLUMN employees.salary IS 'Annual salary in cents (e.g., 13520000 = $135,200/yr)';

-- Add pay type (FLAT, HOURLY, SALARY, etc.)
ALTER TABLE employees ADD COLUMN IF NOT EXISTS pay_type TEXT;
COMMENT ON COLUMN employees.pay_type IS 'Pay type code from TM: FLAT, HOURLY, SALARY, etc.';

-- Add can_perform_work (clearer name than can_tech)
ALTER TABLE employees ADD COLUMN IF NOT EXISTS can_perform_work BOOLEAN;
COMMENT ON COLUMN employees.can_perform_work IS 'True if employee is a technician who can be assigned labor';
