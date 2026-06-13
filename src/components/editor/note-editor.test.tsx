import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NoteEditor } from "@/components/editor/note-editor";
import { useNoteStore } from "@/stores/note-store";

// EditorHeader navigates Home via the app router; mock it for jsdom.
const mockPush = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}));

// ---------------------------------------------------------------------------
// SaveStatus indicator — status bar shows "Auto-saved" when saveStatus=saved
// ---------------------------------------------------------------------------

describe("status bar Auto-saved indicator", () => {
  beforeEach(() => {
    useNoteStore.setState({ mode: "create", saveStatus: "unsaved" });
  });

  it("shows 'Auto-saved' text when saveStatus is 'saved'", async () => {
    render(<NoteEditor />);
    await waitFor(() => {
      expect(document.querySelector(".tiptap")).not.toBeNull();
    });

    useNoteStore.setState({ saveStatus: "saved" });

    await waitFor(() => {
      expect(screen.getByTestId("autosave-status")).toHaveTextContent("Auto-saved");
    });
  });

  it("does not show 'Auto-saved' text when saveStatus is 'unsaved'", async () => {
    render(<NoteEditor />);
    await waitFor(() => {
      expect(document.querySelector(".tiptap")).not.toBeNull();
    });

    useNoteStore.setState({ saveStatus: "unsaved" });

    // Give a moment for any potential render
    await waitFor(() => {
      expect(screen.queryByTestId("autosave-status")).not.toBeInTheDocument();
    });
  });

  it("does not show 'Auto-saved' text when saveStatus is 'saving'", async () => {
    render(<NoteEditor />);
    await waitFor(() => {
      expect(document.querySelector(".tiptap")).not.toBeNull();
    });

    useNoteStore.setState({ saveStatus: "saving" });

    await waitFor(() => {
      expect(screen.queryByTestId("autosave-status")).not.toBeInTheDocument();
    });
  });
});

function getCanvas(): HTMLElement {
  const canvas = document.querySelector<HTMLElement>(".tiptap");
  if (!canvas) {
    throw new Error("Editor canvas is not mounted");
  }
  return canvas;
}

async function renderEditor(initialContent?: string): Promise<void> {
  render(<NoteEditor initialContent={initialContent} />);
  // The editor mounts client-side only (immediatelyRender: false).
  await waitFor(() => {
    expect(document.querySelector(".tiptap")).not.toBeNull();
  });
}

describe("FR-01 two-mode editor", () => {
  beforeEach(() => {
    useNoteStore.setState({ mode: "create" });
  });

  it("opens in Lecture (Write) mode with an editable canvas", async () => {
    await renderEditor();

    expect(getCanvas()).toHaveAttribute("contenteditable", "true");
    expect(screen.getByTestId("mode-status")).toHaveTextContent("Lecture Mode");
    expect(screen.getByRole("toolbar")).toBeInTheDocument();
    expect(screen.queryByTestId("study-badge")).not.toBeInTheDocument();
    expect(screen.queryByTestId("study-tools-panel")).not.toBeInTheDocument();
  });

  it("blocks editing and shows Study layout after Ctrl+M", async () => {
    await renderEditor();

    fireEvent.keyDown(window, { key: "m", ctrlKey: true });

    await waitFor(() => {
      expect(getCanvas()).toHaveAttribute("contenteditable", "false");
    });
    expect(screen.getByTestId("study-badge")).toHaveTextContent("Study Mode");
    expect(screen.getByTestId("study-tools-panel")).toBeInTheDocument();
    expect(screen.getByTestId("mode-status")).toHaveTextContent("Study Mode");
    expect(screen.queryByRole("toolbar")).not.toBeInTheDocument();
  });

  it("returns to an editable Lecture canvas on a second Ctrl+M", async () => {
    await renderEditor();

    fireEvent.keyDown(window, { key: "m", ctrlKey: true });
    await waitFor(() => {
      expect(getCanvas()).toHaveAttribute("contenteditable", "false");
    });

    fireEvent.keyDown(window, { key: "m", ctrlKey: true });

    await waitFor(() => {
      expect(getCanvas()).toHaveAttribute("contenteditable", "true");
    });
    expect(screen.getByTestId("mode-status")).toHaveTextContent("Lecture Mode");
    expect(screen.queryByTestId("study-badge")).not.toBeInTheDocument();
  });

  it("switches modes from the header toggle button", async () => {
    await renderEditor();

    fireEvent.click(
      screen.getByRole("button", { name: /switch to study mode/i }),
    );
    await waitFor(() => {
      expect(getCanvas()).toHaveAttribute("contenteditable", "false");
    });

    fireEvent.click(
      screen.getByRole("button", { name: /switch to lecture mode/i }),
    );
    await waitFor(() => {
      expect(getCanvas()).toHaveAttribute("contenteditable", "true");
    });
  });

  it("toggles when Ctrl+M bubbles up from inside the editor canvas", async () => {
    await renderEditor();

    fireEvent.keyDown(getCanvas(), { key: "m", ctrlKey: true });

    await waitFor(() => {
      expect(getCanvas()).toHaveAttribute("contenteditable", "false");
    });
  });

  it("ignores plain M, Ctrl+Shift+M, and held-key auto-repeat", async () => {
    await renderEditor();

    fireEvent.keyDown(window, { key: "m" });
    expect(useNoteStore.getState().mode).toBe("create");

    fireEvent.keyDown(window, { key: "M", ctrlKey: true, shiftKey: true });
    expect(useNoteStore.getState().mode).toBe("create");

    fireEvent.keyDown(window, { key: "m", ctrlKey: true, repeat: true });
    expect(useNoteStore.getState().mode).toBe("create");

    expect(getCanvas()).toHaveAttribute("contenteditable", "true");
    expect(screen.getByTestId("mode-status")).toHaveTextContent("Lecture Mode");
  });

  it("navigates back to the landing list from the Home button (client-side, so the unmount flush runs)", async () => {
    mockPush.mockClear();
    await renderEditor();

    fireEvent.click(screen.getByRole("button", { name: /home/i }));

    expect(mockPush).toHaveBeenCalledWith("/");
  });

  it("keeps note content across mode toggles (no remount)", async () => {
    await renderEditor("<p>Digoxin toxicity signs</p>");

    fireEvent.keyDown(window, { key: "m", ctrlKey: true });
    await waitFor(() => {
      expect(getCanvas()).toHaveAttribute("contenteditable", "false");
    });
    expect(getCanvas()).toHaveTextContent("Digoxin toxicity signs");

    fireEvent.keyDown(window, { key: "m", ctrlKey: true });
    await waitFor(() => {
      expect(getCanvas()).toHaveAttribute("contenteditable", "true");
    });
    expect(getCanvas()).toHaveTextContent("Digoxin toxicity signs");
  });
});
