import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — isolate saveNote and useNoteStore from real Supabase / module state
// ---------------------------------------------------------------------------

const mockSaveNote = vi.fn();

vi.mock("@/lib/notes", () => ({
  saveNote: mockSaveNote,
}));

// Stateful store stub: setSaveStatus mutates the same state object getState
// returns, mirroring the real Zustand store so the hook's dirty-gating
// (only save when saveStatus === "unsaved") is exercised for real.
type StoreState = {
  saveStatus: "saved" | "saving" | "unsaved";
  title: string;
  setSaveStatus: (status: "saved" | "saving" | "unsaved") => void;
};

let storeState: StoreState;
const mockSetSaveStatus = vi.fn((status: "saved" | "saving" | "unsaved") => {
  storeState.saveStatus = status;
});
const mockGetState = vi.fn(() => storeState);

vi.mock("@/stores/note-store", () => ({
  useNoteStore: {
    getState: mockGetState,
  },
}));

// ---------------------------------------------------------------------------
// Minimal editor stub matching the Tiptap Editor shape expected by the hook
// ---------------------------------------------------------------------------

function makeFakeEditor(textContent = "hello world") {
  return {
    isDestroyed: false,
    getJSON: vi.fn().mockReturnValue({
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: textContent }] }],
    }),
    state: {
      doc: { textContent },
    },
  };
}

// Marks the note dirty, as note-editor's onUpdate / the title input do.
function simulateEdit(): void {
  storeState.saveStatus = "unsaved";
}

describe("useAutosave", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
    vi.clearAllMocks();

    storeState = {
      saveStatus: "unsaved",
      title: "",
      setSaveStatus: mockSetSaveStatus,
    };
    mockGetState.mockImplementation(() => storeState);
    mockSaveNote.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.resetModules();
  });

  it("saves after the 30-second interval elapses", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    const editor = makeFakeEditor();
    renderHook(() => useAutosave(editor as never, "note-1"));

    // Advance exactly 30 seconds
    await vi.advanceTimersByTimeAsync(30_000);

    expect(mockSaveNote).toHaveBeenCalledTimes(1);
    expect(mockSaveNote).toHaveBeenCalledWith(
      "note-1",
      expect.objectContaining({ content: expect.any(Object) }),
    );
  });

  it("saves on a fixed cadence — two saves across 60s when edits continue", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    const editor = makeFakeEditor();
    renderHook(() => useAutosave(editor as never, "note-1"));

    await vi.advanceTimersByTimeAsync(30_000);
    expect(mockSaveNote).toHaveBeenCalledTimes(1);

    simulateEdit();
    await vi.advanceTimersByTimeAsync(30_000);

    expect(mockSaveNote).toHaveBeenCalledTimes(2);
  });

  it("saves on the next tick when the editor arrives after mount (immediatelyRender: false)", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    // useEditor returns null on the first render when immediatelyRender is
    // false; the instance only shows up on a later render.
    const { rerender } = renderHook(
      ({ editor }: { editor: ReturnType<typeof makeFakeEditor> | null }) =>
        useAutosave(editor as never, "note-1"),
      { initialProps: { editor: null as ReturnType<typeof makeFakeEditor> | null } },
    );

    await vi.advanceTimersByTimeAsync(30_000);
    expect(mockSaveNote).not.toHaveBeenCalled();

    rerender({ editor: makeFakeEditor() });
    await vi.advanceTimersByTimeAsync(30_000);

    expect(mockSaveNote).toHaveBeenCalledTimes(1);
  });

  it("skips the tick when there are no unsaved changes", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    storeState.saveStatus = "saved";
    const editor = makeFakeEditor();
    renderHook(() => useAutosave(editor as never, "note-1"));

    await vi.advanceTimersByTimeAsync(30_000);

    expect(mockSaveNote).not.toHaveBeenCalled();
  });

  it("sets saveStatus to 'saving' before the save call resolves", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    // Never resolves during the synchronous part of this assertion
    let resolveSave!: () => void;
    mockSaveNote.mockReturnValue(new Promise<void>((r) => { resolveSave = r; }));

    const editor = makeFakeEditor();
    renderHook(() => useAutosave(editor as never, "note-1"));

    await vi.advanceTimersByTimeAsync(30_000);

    // 'saving' must have been set before the promise settled
    expect(mockSetSaveStatus).toHaveBeenCalledWith("saving");

    // Resolve so the hook can clean up
    resolveSave();
    await vi.advanceTimersByTimeAsync(0);
  });

  it("sets saveStatus to 'saved' after a successful save", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    const editor = makeFakeEditor();
    renderHook(() => useAutosave(editor as never, "note-1"));

    await vi.advanceTimersByTimeAsync(30_000);
    await vi.advanceTimersByTimeAsync(0);

    expect(mockSetSaveStatus).toHaveBeenCalledWith("saved");
    expect(storeState.saveStatus).toBe("saved");
  });

  it("marks the note dirty again after a failed save so the next tick retries", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    mockSaveNote.mockRejectedValueOnce(new Error("network down"));

    const editor = makeFakeEditor();
    renderHook(() => useAutosave(editor as never, "note-1"));

    await vi.advanceTimersByTimeAsync(30_000);
    await vi.advanceTimersByTimeAsync(0);

    expect(mockSaveNote).toHaveBeenCalledTimes(1);
    expect(storeState.saveStatus).toBe("unsaved");

    await vi.advanceTimersByTimeAsync(30_000);

    expect(mockSaveNote).toHaveBeenCalledTimes(2);
  });

  it("fires a save on unmount (flush on cleanup)", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    const editor = makeFakeEditor();
    const { unmount } = renderHook(() => useAutosave(editor as never, "note-2"));

    // Unmount before the 30s interval fires
    unmount();

    await vi.runAllTimersAsync();

    expect(mockSaveNote).toHaveBeenCalledWith(
      "note-2",
      expect.objectContaining({ content: expect.any(Object) }),
    );
  });

  it("does not flush on unmount when the note is already clean", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    storeState.saveStatus = "saved";
    const editor = makeFakeEditor();
    const { unmount } = renderHook(() => useAutosave(editor as never, "note-2"));

    unmount();
    await vi.runAllTimersAsync();

    expect(mockSaveNote).not.toHaveBeenCalled();
  });

  it("does not fire a save when noteId is null", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    const editor = makeFakeEditor();
    renderHook(() => useAutosave(editor as never, null));

    await vi.advanceTimersByTimeAsync(30_000);

    expect(mockSaveNote).not.toHaveBeenCalled();
  });

  it("does not fire a save when editor is null", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    renderHook(() => useAutosave(null, "note-1"));

    await vi.advanceTimersByTimeAsync(30_000);

    expect(mockSaveNote).not.toHaveBeenCalled();
  });

  it("computes word_count from editor.getJSON() text content", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useAutosave } = await import("@/hooks/use-autosave");

    const editor = makeFakeEditor("cardiac output ventricular");
    renderHook(() => useAutosave(editor as never, "note-3"));

    await vi.advanceTimersByTimeAsync(30_000);
    await vi.advanceTimersByTimeAsync(0);

    const [, patch] = mockSaveNote.mock.calls[0] as [string, { word_count: number }];
    expect(patch.word_count).toBe(3);
  });
});
