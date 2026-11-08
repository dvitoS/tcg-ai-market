-- M4.3 — allow Creem trial status on pro_entitlements.
-- Run once in Supabase → SQL Editor after supabase_pro_entitlements.sql.

alter table public.pro_entitlements
    drop constraint if exists pro_entitlements_status_check;

alter table public.pro_entitlements
    add constraint pro_entitlements_status_check
    check (status in ('active', 'trialing', 'canceled', 'past_due', 'expired'));

notify pgrst, 'reload schema';
