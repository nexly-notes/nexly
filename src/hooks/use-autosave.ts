import type { Editor } from "@tiptap/react";
import { useEffect, useLayoutEffect, useRef } from "react";

import { saveNote } from "@/lib/notes";
import { useNoteStore } from "@/stores/note-store";

// Autosave cadence (tech-spec budget): a fixed 30s interval, so a student
// typing continuously through a lecture still persists every 30 seconds.
const AUTOSAVE_INTERVAL_MS = 30_000;

// Minimal slice of the Tiptap JSON tree we need to count words.
type ProseMirrorNode = {
  text?: string;
  content?: ProseMirrorNode[];
};

/**
 * Walks a Tiptap JSON document and concatenates every text node, separating
 * blocks with a space so words never run together across paragraphs.
 */
function collectText(node: ProseMirrorNode): string {
  if (typeof node.text === "string") {
    return node.text;
  }
  if (!node.content) {
    return "";
  }
  return node.content.map(collectText).join(" ");
}

function countWords(doc: ProseMirrorNode): number {
  return collectText(doc)
    .split(/\s+/)
    .filter(Boolean).length;
}

/**
 * Persists the open note on a fixed 30s interval whenever it has unsaved
 * changes, plus once more on unmount (flush) so no edits are lost when the
 * user navigates away. Dirtiness comes from the store: the editor's onUpdate
 * and the title input both set saveStatus to "unsaved".
 *
 * Reading the editor through a ref (synced every render) means the interval
 * picks the instance up on its next tick even though useEditor returns null
 * on the first render (immediatelyRender: false).
 *
 * Save status lifecycle: "saving" while the call is in flight, "saved" on
 * success, back to "unsaved" on failure so the next tick retries (plain save,
 * no backoff per spec).
 */
export function useAutosave(editor: Editor | null, noteId: string | null): void {
  // Keep the live editor / id in refs so the interval and the unmount cleanup
  // always see the latest values without re-arming the timer on every render.
  const editorRef = useRef(editor);
  const noteIdRef = useRef(noteId);

  // Keep refs in sync with the latest values without causing a re-render.
  // useLayoutEffect (not render-phase assignment) is required by the React
  // refs/hooks linting rules.
  useLayoutEffect(() => {
    editorRef.current = editor;
    noteIdRef.current = noteId;
  });

  useEffect(() => {
    async function save(): Promise<void> {
      const currentEditor = editorRef.current;
      const currentNoteId = noteIdRef.current;
      if (!currentEditor || currentEditor.isDestroyed || !currentNoteId) {
        return;
      }

      const { saveStatus, setSaveStatus, title } = useNoteStore.getState();
      // Only persist dirty content. "saving" means a save is already in
      // flight, so the tick is skipped rather than doubled up.
      if (saveStatus !== "unsaved") {
        return;
      }

      const content = currentEditor.getJSON();
      setSaveStatus("saving");
      try {
        await saveNote(currentNoteId, {
          title: title ?? "",
          content,
          word_count: countWords(content as ProseMirrorNode),
        });
        // Edits made while the request was in flight set the status back to
        // "unsaved" — only mark clean when nothing changed underneath the save.
        if (useNoteStore.getState().saveStatus === "saving") {
          setSaveStatus("saved");
        }
      } catch {
        // Surface the dirty state again so the next 30s tick retries.
        if (useNoteStore.getState().saveStatus === "saving") {
          setSaveStatus("unsaved");
        }
      }
    }

    const timer = setInterval(() => {
      void save();
    }, AUTOSAVE_INTERVAL_MS);

    return () => {
      clearInterval(timer);
      // Flush on unmount so navigating away never loses edits.
      void save();
    };
  }, []);
}
