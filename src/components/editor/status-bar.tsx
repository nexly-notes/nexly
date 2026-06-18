"use client";

import { useTiptapState } from "@tiptap/react";
import { CircleCheck } from "lucide-react";

import { NOTE_MODE_LABELS, type NoteMode } from "@/types/note";

type StatusBarProps = {
  mode: NoteMode;
};

export function StatusBar({ mode }: StatusBarProps) {
  const { words, characters } = useTiptapState((snapshot) => {
    const text = snapshot.editor.state.doc.textContent;
    return {
      words: text.split(/\s+/).filter(Boolean).length,
      characters: text.length,
    };
  });

  return (
    <footer className="flex items-center justify-between border-t border-border bg-background px-4 py-1.5 text-xs text-muted-foreground">
      <div className="flex items-center gap-4">
        <span>Words: {words.toLocaleString()}</span>
        <span>Characters: {characters.toLocaleString()}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5" data-testid="mode-status">
          <CircleCheck size={14} aria-hidden />
          <span>{NOTE_MODE_LABELS[mode]} Mode</span>
        </span>
      </div>
    </footer>
  );
}
