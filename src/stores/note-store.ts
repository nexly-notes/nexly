import { create } from "zustand";
import { immer } from "zustand/middleware/immer";

import type { NoteMode } from "@/types/note";

type NoteState = {
  mode: NoteMode;
  setMode: (mode: NoteMode) => void;
  toggleMode: () => void;
  title: string;
  setTitle: (title: string) => void;
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
    title: "",
    setTitle: (title) =>
      set((state) => {
        state.title = title;
      }),
  })),
);
