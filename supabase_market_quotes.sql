-- Precomputed catalog board (signals + confidence) for fast Streamlit boots.
-- Run once in Supabase → SQL Editor.
-- Written by nightly / load_exchange via service_role; readable by anon.

create table if not exists public.market_quotes (
    card_id text primary key references public.cards (id) on delete cascade,
    name text,
    set_name text,
    rarity text,
    supertype text,
    rarity_encoded double precision,
    supertype_encoded double precision,
    price double precision,
    market_price double precision,
    predicted_price double precision,
    expected_change_pct double precision,
    price_change_3d_pct double precision,
    price_change_7d_pct double precision,
    pred_lo_pct double precision,
    pred_hi_pct double precision,
    conformal_ok boolean not null default true,
    signal text,
    confidence_ok boolean not null default true,
    confidence_level text,
    history_points integer not null default 0,
    updated_at timestamptz not null default now()
);

create index if not exists market_quotes_signal_idx on public.market_quotes (signal);
create index if not exists market_quotes_updated_at_idx on public.market_quotes (updated_at desc);

alter table public.market_quotes enable row level security;

drop policy if exists "anon_read_market_quotes" on public.market_quotes;
create policy "anon_read_market_quotes" on public.market_quotes
  for select to anon, authenticated using (true);

-- Existing deployments: add encoding columns used by scanner / detail forecasts.
alter table public.market_quotes
  add column if not exists rarity_encoded double precision;
alter table public.market_quotes
  add column if not exists supertype_encoded double precision;
alter table public.market_quotes
  add column if not exists price_change_3d_pct double precision;
alter table public.market_quotes
  add column if not exists price_change_7d_pct double precision;
alter table public.market_quotes
  add column if not exists pred_lo_pct double precision;
alter table public.market_quotes
  add column if not exists pred_hi_pct double precision;
alter table public.market_quotes
  add column if not exists conformal_ok boolean not null default true;

grant usage on schema public to postgres, anon, authenticated, service_role;
grant select on table public.market_quotes to anon, authenticated;
grant all on table public.market_quotes to postgres, service_role;

notify pgrst, 'reload schema';
