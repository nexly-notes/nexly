"use client";

import { Placeholder } from "@tiptap/extensions";
import { Tiptap, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, useLayoutEffect } from "react";

import { EditorHeader } from "@/components/editor/editor-header";
import { EditorToolbar } from "@/components/editor/editor-toolbar";
import { StatusBar } from "@/components/editor/status-bar";
import { StudyToolsPanel } from "@/components/editor/study-tools-panel";
import { useAutosave } from "@/hooks/use-autosave";
import { useNoteStore } from "@/stores/note-store";

// Tiptap accepts either an HTML string or a JSON document as initial content.
type EditorContent = string | object;

type NoteEditorProps = {
  noteId?: string;
  initialTitle?: string;
  initialContent?: EditorContent;
};

// Pre-paint on the client, plain effect during SSR rendering.
const useClientLayoutEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

export function NoteEditor({ noteId, initialTitle, initialContent }: NoteEditorProps) {
  const mode = useNoteStore((state) => state.mode);
  const toggleMode = useNoteStore((state) => state.toggleMode);
  const setNoteId = useNoteStore((state) => state.setNoteId);
  const setTitle = useNoteStore((state) => state.setTitle);
  const setSaveStatus = useNoteStore((state) => state.setSaveStatus);
  const isWriteMode = mode === "create";

  // Seed note identity / title into the store once when this note opens, so the
  // header, status bar, and autosave all read from a single source of truth.
  useEffect(() => {
    setNoteId(noteId ?? null);
    setTitle(initialTitle ?? "");
    setSaveStatus("saved");
  }, [noteId, initialTitle, setNoteId, setTitle, setSaveStatus]);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: "Start writing..." }),
    ],
    content: initialContent ?? "",
    editable: isWriteMode,
    // Editor renders client-side only to avoid SSR hydration mismatches.
    immediatelyRender: false,
    onUpdate: () => {
      setSaveStatus("unsaved");
    },
  });

  useAutosave(editor, noteId ?? null);

  // Flip editability on the live instance instead of remounting; pre-paint
  // so no frame ever shows Study mode with an editable canvas (<50ms budget).
  // useEditor's own option sync intentionally preserves the current editable
  // state, so this explicit call is required.
  useClientLayoutEffect(() => {
    if (!editor || editor.isEditable === isWriteMode) {
      return;
    }
    editor.setEditable(isWriteMode);
  }, [editor, isWriteMode]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent): void => {
      const isModeShortcut =
        event.ctrlKey &&
        !event.altKey &&
        !event.metaKey &&
        !event.shiftKey &&
        !event.repeat &&
        event.key.toLowerCase() === "m";
      if (!isModeShortcut) {
        return;
      }
      event.preventDefault();
      toggleMode();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleMode]);

  if (!editor) {
    return (
      <div className="flex h-dvh items-center justify-center bg-background text-sm text-muted-foreground">
        Loading editor...
      </div>
    );
  }

  return (
    <Tiptap editor={editor}>
      <div className="flex h-dvh flex-col bg-background text-foreground">
        <EditorHeader mode={mode} onToggleMode={toggleMode} />
        {isWriteMode ? <EditorToolbar /> : null}
        <div className="flex min-h-0 flex-1">
          <main className="min-w-0 flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[900px] px-8 py-6">
              <Tiptap.Content />
            </div>
          </main>
          {isWriteMode ? null : <StudyToolsPanel />}
        </div>
        <StatusBar mode={mode} />
      </div>
    </Tiptap>
  );
}
