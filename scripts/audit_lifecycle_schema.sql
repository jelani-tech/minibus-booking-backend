-- Run before deploying the audit backend. No production data is deleted.
ALTER TYPE public.booking_status ADD VALUE IF NOT EXISTS 'expired';
ALTER TABLE public.trips ADD COLUMN IF NOT EXISTS booking_close_at timestamptz;
-- Null means sales close at planned_start_datetime (legacy-compatible).
CREATE INDEX IF NOT EXISTS bookings_pending_expiry_idx
ON public.bookings (trip_id, expires_at) WHERE booking_status = 'pending';
