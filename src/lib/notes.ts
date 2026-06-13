import { z } from "zod";

import { createClient } from "@/lib/supabase/client";
import { logEvent } from "@/lib/events";
import type { Note } from "@/types/note";

// PostgREST "no rows returned" — emitted by `.single()` when nothing matches.
// For getNote this means "missing or not visible under RLS", not a real failure.
const NO_ROWS_FOUND = "PGRST116";

// Empty Tiptap document — the starting content for a brand-new note.
const EMPTY_DOC = { type: "doc", content: [] } as const;

const NOTES_TABLE = "notes";

// Bound the persisted patch at the boundary (project rule: treat all external
// input as hostile). Title length is capped; content must be a Tiptap JSON
// object; word_count is a non-negative integer.
const notePatchSchema = z.object({
  title: z.string().max(1000),
  content: z.looseObject({}),
  word_count: z.number().int().min(0),
});

export type NotePatch = z.infer<typeof notePatchSchema>;

/**
 * Inserts a new, empty note for the current user and returns the created row.
 *
 * `user_id` is populated server-side by the table's `auth.uid()` default under
 * RLS, so the client only sends the editable fields. Emits a `note_created`
 * event keyed by the new note id (fire-and-forget; never blocks creation).
 */
export async function createNote(): Promise<Note> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from(NOTES_TABLE)
    .insert({ title: "Untitled", content: EMPTY_DOC, word_count: 0 })
    .select()
    .single();

  if (error || !data) {
    throw new Error(`Failed to create note: ${error?.message ?? "no row returned"}`);
  }

  const note = data as Note;
  logEvent("note_created", { noteId: note.id });
  return note;
}

/**
 * Returns the note with the given id, or `null` when it does not exist or is
 * not visible to the current user (RLS). Never throws on a missing row.
 */
export async function getNote(id: string): Promise<Note | null> {
  const supabase = createClient();

  const { data, error } = await supabase.from(NOTES_TABLE).select("*").eq("id", id).single();

  if (error) {
    if (error.code === NO_ROWS_FOUND) {
      return null;
    }
    throw new Error(`Failed to load note: ${error.message}`);
  }

  return (data as Note) ?? null;
}

/**
 * Returns every note visible to the current user (RLS scopes this to the
 * owner), or an empty array when there are none.
 */
export async function listNotes(): Promise<Note[]> {
  const supabase = createClient();

  const { data, error } = await supabase.from(NOTES_TABLE).select("*");

  if (error) {
    throw new Error(`Failed to list notes: ${error.message}`);
  }

  return (data as Note[]) ?? [];
}

/**
 * Persists editable fields on the note identified by `id`, bumping
 * `updated_at`. RLS ensures only the owner's row is affected.
 */
export async function saveNote(id: string, patch: NotePatch): Promise<void> {
  const supabase = createClient();

  // Validate before persisting — reject malformed/oversized payloads at the
  // boundary rather than letting them reach the database.
  const validated = notePatchSchema.parse(patch);

  const { error } = await supabase
    .from(NOTES_TABLE)
    .update({
      title: validated.title,
      content: validated.content,
      word_count: validated.word_count,
      updated_at: new Date().toISOString(),
    })
    .eq("id", id);

  if (error) {
    throw new Error(`Failed to save note: ${error.message}`);
  }
}
