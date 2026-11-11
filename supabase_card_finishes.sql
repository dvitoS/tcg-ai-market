-- Soft Ink card finish labels (Normal / Holofoil / Reverse Holofoil / …).
-- Run once in Supabase → SQL Editor, then reload schema cache if needed.

alter table public.cards add column if not exists finishes text;
notify pgrst, 'reload schema';
