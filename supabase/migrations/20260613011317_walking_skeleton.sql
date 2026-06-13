-- VS-001 Walking Skeleton: notes + events tables with per-user RLS.
--
-- Mirrors the data model in project/specs/mvp/tech-specs.md (section 5).
-- All tables live in the `public` schema, so RLS is mandatory: it is the only
-- thing standing between one beta user's notes and another's.

-- ---------------------------------------------------------------------------
-- updated_at trigger helper
-- ---------------------------------------------------------------------------
-- Stamps updated_at on every UPDATE so the 30s autosave path always records a
-- fresh server-side timestamp, regardless of what the client sends.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- notes
-- ---------------------------------------------------------------------------
-- user_id defaults to auth.uid() so authenticated clients never send it:
-- the database stamps ownership from the caller's JWT, and the RLS WITH CHECK
-- below guarantees it can only ever be the caller's own id.
create table if not exists public.notes (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title       text not null default '',
  content     jsonb not null default '{}'::jsonb,   -- Tiptap document JSON
  word_count  integer not null default 0,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Notes are always loaded/listed by owner; index the access path.
create index if not exists notes_user_id_idx on public.notes (user_id);

create trigger notes_set_updated_at
  before update on public.notes
  for each row
  execute function public.set_updated_at();

alter table public.notes enable row level security;

-- Per-user isolation. Each command gets its own policy so the ownership
-- predicate is explicit, and UPDATE carries WITH CHECK so a user cannot
-- reassign a note to someone else.
create policy "Users can read their own notes"
  on public.notes for select
  to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users can insert their own notes"
  on public.notes for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

create policy "Users can update their own notes"
  on public.notes for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "Users can delete their own notes"
  on public.notes for delete
  to authenticated
  using ((select auth.uid()) = user_id);

-- ---------------------------------------------------------------------------
-- events (FR-012 beta instrumentation)
-- ---------------------------------------------------------------------------
-- Metadata only — never note content (tech-specs section 5). `value` is an
-- optional numeric count (accepted characters, duration ms); `note_id`
-- references the note an event is about (note_created / note_opened). The
-- `type` length cap bounds row size so a client cannot flood the table with
-- oversized payloads under its own RLS scope.
create table if not exists public.events (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  type        text not null check (char_length(type) <= 64),
  value       integer,
  note_id     uuid references public.notes (id) on delete set null,
  created_at  timestamptz not null default now()
);

create index if not exists events_user_id_idx on public.events (user_id);

alter table public.events enable row level security;

-- Insert-own only: clients may record their own usage events but never read
-- the events table. The product team reads aggregates via the service role,
-- which bypasses RLS.
create policy "Users can insert their own events"
  on public.events for insert
  to authenticated
  with check ((select auth.uid()) = user_id);
