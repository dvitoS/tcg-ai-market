-- One-shot harden for EXISTING Supabase projects.
-- Run in Supabase → SQL Editor after deploying the multi-user JWT path.
-- service_role (nightly / AUTH_DISABLED) still bypasses RLS.

-- Drop open catalog write policies (anon must not mutate cards/history).
drop policy if exists "service_write_cards" on public.cards;
drop policy if exists "service_write_price_history" on public.price_history;
drop policy if exists "service_read_cards" on public.cards;
drop policy if exists "service_read_price_history" on public.price_history;

drop policy if exists "anon_read_cards" on public.cards;
create policy "anon_read_cards" on public.cards
  for select to anon, authenticated using (true);

drop policy if exists "anon_read_price_history" on public.price_history;
create policy "anon_read_price_history" on public.price_history
  for select to anon, authenticated using (true);

-- Critical: remove using(true) portfolio/watchlist policies.
drop policy if exists "service_read_portfolio" on public.portfolio;
drop policy if exists "service_write_portfolio" on public.portfolio;
drop policy if exists "service_read_watchlist" on public.watchlist;
drop policy if exists "service_write_watchlist" on public.watchlist;

drop policy if exists "portfolio_select_own" on public.portfolio;
create policy "portfolio_select_own" on public.portfolio
  for select to authenticated using (auth.uid() = user_id);
drop policy if exists "portfolio_insert_own" on public.portfolio;
create policy "portfolio_insert_own" on public.portfolio
  for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "portfolio_update_own" on public.portfolio;
create policy "portfolio_update_own" on public.portfolio
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "portfolio_delete_own" on public.portfolio;
create policy "portfolio_delete_own" on public.portfolio
  for delete to authenticated using (auth.uid() = user_id);

drop policy if exists "watchlist_select_own" on public.watchlist;
create policy "watchlist_select_own" on public.watchlist
  for select to authenticated using (auth.uid() = user_id);
drop policy if exists "watchlist_insert_own" on public.watchlist;
create policy "watchlist_insert_own" on public.watchlist
  for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "watchlist_update_own" on public.watchlist;
create policy "watchlist_update_own" on public.watchlist
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "watchlist_delete_own" on public.watchlist;
create policy "watchlist_delete_own" on public.watchlist
  for delete to authenticated using (auth.uid() = user_id);

notify pgrst, 'reload schema';
