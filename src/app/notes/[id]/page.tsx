import { cookies } from "next/headers";
import { notFound } from "next/navigation";

import { NoteEditor } from "@/components/editor/note-editor";
import { createServerClient, type CookieStore } from "@/lib/supabase/server";
import type { Note } from "@/types/note";

const NOTES_TABLE = "notes";
const EVENTS_TABLE = "events";

type NotePageProps = {
  params: Promise<{ id: string }>;
};

/**
 * Adapts Next.js `cookies()` to the server client's `getAll`/`setAll` contract.
 *
 * Writing cookies during a Server Component render is not allowed by Next.js, so
 * `setAll` is wrapped in a try/catch: a token refresh that wants to persist new
 * cookies fails harmlessly here (middleware handles refresh writes instead).
 */
function toCookieStore(store: Awaited<ReturnType<typeof cookies>>): CookieStore {
  return {
    getAll() {
      return store.getAll();
    },
    setAll(cookiesToSet) {
      try {
        for (const { name, value, options } of cookiesToSet) {
          store.set(name, value, options);
        }
      } catch {
        // Server Components cannot set cookies; safe to ignore.
      }
    },
  };
}

/**
 * Per-user note editor route. Loads the note for the signed-in user via the
 * server client and renders the editor seeded with its content. Returns 404
 * when the note is missing or owned by another user (the query is scoped to the
 * current `user_id`, and RLS enforces the same boundary at the database).
 */
export default async function NotePage({ params }: NotePageProps) {
  const { id } = await params;

  const cookieStore = await cookies();
  const supabase = createServerClient(toCookieStore(cookieStore));

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    notFound();
  }

  const { data, error } = await supabase
    .from(NOTES_TABLE)
    .select("*")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();

  if (error || !data) {
    notFound();
  }

  const note = data as Note;

  // Telemetry only — fire-and-forget, never blocks rendering and never carries
  // note content (event row references the note via note_id). user_id is
  // defaulted from the caller's JWT by the table's auth.uid() default.
  void supabase
    .from(EVENTS_TABLE)
    .insert({ type: "note_opened", note_id: note.id })
    .then(() => {}, () => {});

  return (
    <NoteEditor noteId={note.id} initialTitle={note.title} initialContent={note.content} />
  );
}
