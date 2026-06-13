// Canonical mode values — "Lecture" is only the UI label for `create`.
export type NoteMode = "create" | "study";

export const NOTE_MODE_LABELS: Record<NoteMode, string> = {
  create: "Lecture",
  study: "Study",
};
