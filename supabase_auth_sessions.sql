-- Durable Streamlit auth sessions (opaque sid → JWT).
-- Run once in Supabase → SQL Editor.
-- App reads/writes via service_role only (bypasses RLS).
-- Do NOT grant anon/authenticated access — sid in the URL is the secret.

create table if not exists public.auth_sessions (
    sid text primary key,
    user_id uuid,
    email text,
    access_token text,
    refresh_token text,
    updated_at timestamptz not null default now(),
    expires_at timestamptz not null default (now() + interval '30 days')
);

create index if not exists auth_sessions_expires_at_idx
  on public.auth_sessions (expires_at);

create index if not exists auth_sessions_user_id_idx
  on public.auth_sessions (user_id);

alter table public.auth_sessions enable row level security;

-- No policies for anon/authenticated → they cannot SELECT/INSERT.
-- service_role bypasses RLS for the Streamlit server / nightly jobs.

-- Optional cleanup helper (run manually or via cron):
-- delete from public.auth_sessions where expires_at < now();

grant usage on schema public to postgres, service_role;
grant all on table public.auth_sessions to postgres, service_role;

notify pgrst, 'reload schema';
