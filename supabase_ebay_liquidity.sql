-- Daily eBay liquidity snapshots for model features (active listing depth + ask).
-- Run once in Supabase → SQL Editor after market_quotes.
-- Written by nightly via service_role; readable by anon (optional analytics).

create table if not exists public.ebay_liquidity_snapshots (
    card_id text not null references public.cards (id) on delete cascade,
    snapshot_date date not null,
    active_n integer not null default 0,
    ask_min double precision,
    ask_median double precision,
    ask_max double precision,
    spot double precision,
    ask_premium double precision,
    updated_at timestamptz not null default now(),
    primary key (card_id, snapshot_date)
);

create index if not exists ebay_liquidity_date_idx
  on public.ebay_liquidity_snapshots (snapshot_date desc);
create index if not exists ebay_liquidity_card_idx
  on public.ebay_liquidity_snapshots (card_id, snapshot_date desc);

alter table public.ebay_liquidity_snapshots enable row level security;

drop policy if exists "anon_read_ebay_liquidity" on public.ebay_liquidity_snapshots;
create policy "anon_read_ebay_liquidity" on public.ebay_liquidity_snapshots
  for select to anon, authenticated using (true);

grant usage on schema public to postgres, anon, authenticated, service_role;
grant select on table public.ebay_liquidity_snapshots to anon, authenticated;
grant all on table public.ebay_liquidity_snapshots to postgres, service_role;

notify pgrst, 'reload schema';
