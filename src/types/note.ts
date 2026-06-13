// Canonical mode values — "Lecture" is only the UI label for `create`.
export type NoteMode = "create" | "study";

// Matches the notes table row; content stores Tiptap JSON.
export type Note = {
  id: string;
  user_id: string;
  title: string;
  content: object;
  word_count: number;
  created_at: string;
  updated_at: string;
};

export const NOTE_MODE_LABELS: Record<NoteMode, string> = {
  create: "Lecture",
  study: "Study",
};
