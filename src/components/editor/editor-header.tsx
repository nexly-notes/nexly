"use client";

import { BookOpen, House, PenLine } from "lucide-react";

import { useNoteStore } from "@/stores/note-store";
import { NOTE_MODE_LABELS, type NoteMode } from "@/types/note";

type EditorHeaderProps = {
  mode: NoteMode;
  onToggleMode: () => void;
};

export function EditorHeader({ mode, onToggleMode }: EditorHeaderProps) {
  const title = useNoteStore((state) => state.title);
  const setTitle = useNoteStore((state) => state.setTitle);
  const isStudyMode = mode === "study";
  const targetMode: NoteMode = isStudyMode ? "create" : "study";
  const targetLabel = NOTE_MODE_LABELS[targetMode];

  return (
    <header className="flex items-center gap-3 border-b border-border bg-background px-4 py-3">
      <button
        type="button"
        aria-label="Home"
        className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
      >
        <House size={18} aria-hidden />
      </button>

      {isStudyMode ? (
        <div className="flex min-w-0 items-center gap-3">
          <h1 className="truncate text-xl font-semibold">
            {title || "Untitled Note"}
          </h1>
          <span
            data-testid="study-badge"
            className="shrink-0 rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs font-medium"
          >
            Study Mode
          </span>
        </div>
      ) : (
        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Untitled Note"
          aria-label="Note title"
          className="w-full max-w-md truncate rounded-md border border-transparent bg-transparent px-2 py-1 text-xl font-semibold placeholder:text-muted-foreground hover:border-muted focus:border-brand focus:outline-none"
        />
      )}

      <div className="ml-auto flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onToggleMode}
          aria-label={`Switch to ${targetLabel} Mode`}
          title={`Switch to ${targetLabel} Mode (Ctrl+M)`}
          className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-surface"
        >
          {isStudyMode ? (
            <PenLine size={16} aria-hidden />
          ) : (
            <BookOpen size={16} aria-hidden />
          )}
          <span>{targetLabel}</span>
        </button>
      </div>
    </header>
  );
}
