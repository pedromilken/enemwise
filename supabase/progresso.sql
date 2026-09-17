-- ENEMWise: progresso de treino por usuário, protegido por RLS.
-- Rode uma vez no SQL Editor do Supabase.

create table if not exists public.progresso (
  user_id       uuid primary key references auth.users(id) on delete cascade,
  estado        jsonb not null,
  atualizado_em timestamptz not null default now()
);

alter table public.progresso enable row level security;

-- cada pessoa só enxerga e altera a própria linha
drop policy if exists "progresso: ler o próprio" on public.progresso;
drop policy if exists "progresso: inserir o próprio" on public.progresso;
drop policy if exists "progresso: atualizar o próprio" on public.progresso;
drop policy if exists "progresso: apagar o próprio" on public.progresso;

create policy "progresso: ler o próprio" on public.progresso
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "progresso: inserir o próprio" on public.progresso
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "progresso: atualizar o próprio" on public.progresso
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "progresso: apagar o próprio" on public.progresso
  for delete to authenticated using ((select auth.uid()) = user_id);
