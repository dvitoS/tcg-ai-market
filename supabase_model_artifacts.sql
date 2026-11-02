-- Persisted XGBoost artifact for Streamlit (avoid retrain on every cold start).
-- Run once in Supabase → SQL Editor.
-- Written by nightly_update / retrain_model via service_role; read by the app.
-- Rows: id='latest' (7d board/scanner), id='latest_30d' (portfolio outlook).

create table if not exists public.model_artifacts (
    id text primary key default 'latest',
    algo text not null default 'xgboost',
    blob_b64 text not null,
    metrics jsonb,
    feature_columns jsonb,
    trained_at timestamptz not null default now()
);

alter table public.model_artifacts enable row level security;

-- Public read so anon can load the model; writes stay service_role-only (no write policy).
drop policy if exists "anon_read_model_artifacts" on public.model_artifacts;
create policy "anon_read_model_artifacts" on public.model_artifacts
  for select to anon, authenticated using (true);

grant usage on schema public to postgres, anon, authenticated, service_role;
grant select on table public.model_artifacts to anon, authenticated;
grant all on table public.model_artifacts to postgres, service_role;

notify pgrst, 'reload schema';
