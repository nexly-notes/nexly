"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { createNote, listNotes } from "@/lib/notes";
import { createClient } from "@/lib/supabase/client";
import type { Note } from "@/types/note";

/**
 * Signed-in landing: a bare list of the current user's notes plus New Note and
 * Sign out controls. RLS scopes `listNotes()` to the owner, so no client-side
 * filtering is needed. Creating a note logs `note_created` (inside
 * `createNote`) and routes straight into the editor for the new note.
 */
export default function Home(): React.JSX.Element {
  const router = useRouter();
  const [notes, setNotes] = useState<Note[]>([]);
  const [creating, setCreating] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState("");

  useEffect(() => {
    let active = true;
    listNotes()
      .then((loaded) => {
        if (active) {
          setNotes(loaded);
        }
      })
      .catch(() => {
        if (active) {
          setNotes([]);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleNewNote(): Promise<void> {
    setCreating(true);
    try {
      const note = await createNote();
      router.push(`/notes/${note.id}`);
    } catch {
      setCreating(false);
    }
  }

  // Ends the Supabase session (clears the sb-* cookies) and returns to the
  // login screen. Critical on shared lab machines — without this the next
  // person at the computer inherits the session.
  async function handleSignOut(): Promise<void> {
    setSigningOut(true);
    setSignOutError("");
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signOut();
      if (error) {
        setSignOutError("Could not sign out. Please try again.");
        setSigningOut(false);
        return;
      }
      router.replace("/login");
    } catch {
      setSignOutError("Could not sign out. Please try again.");
      setSigningOut(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Your Notes</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            className="rounded border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-surface disabled:opacity-50"
          >
            Sign out
          </button>
          <button
            type="button"
            onClick={handleNewNote}
            disabled={creating}
            className="rounded bg-[#3ba9ff] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            New Note
          </button>
        </div>
      </div>

      {signOutError ? (
        <p role="alert" className="text-sm text-red-600">
          {signOutError}
        </p>
      ) : null}

      {notes.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No notes yet. Create your first note to get started.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {notes.map((note) => (
            <li key={note.id}>
              <a
                href={`/notes/${note.id}`}
                className="flex items-center justify-between rounded border border-border px-4 py-3 transition-colors hover:bg-surface"
              >
                <span className="truncate font-medium">
                  {note.title || "Untitled"}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {new Date(note.updated_at).toLocaleString()}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
