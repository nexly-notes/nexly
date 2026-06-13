import { create } from "zustand";
import { immer } from "zustand/middleware/immer";

import type { NoteMode } from "@/types/note";

// Persistence lifecycle of the open note: "unsaved" once content changes,
// "saving" while a save is in flight, "saved" after it succeeds.
export type SaveStatus = "saved" | "saving" | "unsaved";

type NoteState = {
  mode: NoteMode;
  setMode: (mode: NoteMode) => void;
  toggleMode: () => void;
  noteId: string | null;
  title: string;
  saveStatus: SaveStatus;
  setNoteId: (noteId: string | null) => void;
  setTitle: (title: string) => void;
  setSaveStatus: (saveStatus: SaveStatus) => void;
};

export const useNoteStore = create<NoteState>()(
  immer((set) => ({
    mode: "create",
    setMode: (mode) =>
      set((state) => {
        state.mode = mode;
      }),
    toggleMode: () =>
      set((state) => {
        state.mode = state.mode === "create" ? "study" : "create";
      }),
    noteId: null,
    title: "",
    saveStatus: "unsaved",
    setNoteId: (noteId) =>
      set((state) => {
        state.noteId = noteId;
      }),
    setTitle: (title) =>
      set((state) => {
        state.title = title;
      }),
    setSaveStatus: (saveStatus) =>
      set((state) => {
        state.saveStatus = saveStatus;
      }),
  })),
);
