import { beforeEach, describe, expect, it } from "vitest";

import { useNoteStore } from "@/stores/note-store";

describe("note store mode", () => {
  beforeEach(() => {
    useNoteStore.setState({ mode: "create" });
  });

  it("defaults to create mode (Write)", () => {
    expect(useNoteStore.getState().mode).toBe("create");
  });

  it("toggles from create to study", () => {
    useNoteStore.getState().toggleMode();

    expect(useNoteStore.getState().mode).toBe("study");
  });

  it("toggles from study back to create", () => {
    useNoteStore.setState({ mode: "study" });

    useNoteStore.getState().toggleMode();

    expect(useNoteStore.getState().mode).toBe("create");
  });

  it("sets an explicit mode", () => {
    useNoteStore.getState().setMode("study");

    expect(useNoteStore.getState().mode).toBe("study");
  });
});

describe("note store — noteId, title, saveStatus", () => {
  beforeEach(() => {
    useNoteStore.setState({
      mode: "create",
      noteId: null,
      title: "",
      saveStatus: "unsaved",
    });
  });

  it("defaults noteId to null", () => {
    expect(useNoteStore.getState().noteId).toBeNull();
  });

  it("defaults title to an empty string", () => {
    expect(useNoteStore.getState().title).toBe("");
  });

  it("defaults saveStatus to 'unsaved'", () => {
    expect(useNoteStore.getState().saveStatus).toBe("unsaved");
  });

  it("setNoteId stores the provided id", () => {
    useNoteStore.getState().setNoteId("note-abc");

    expect(useNoteStore.getState().noteId).toBe("note-abc");
  });

  it("setTitle stores the provided title", () => {
    useNoteStore.getState().setTitle("Cardiac Output");

    expect(useNoteStore.getState().title).toBe("Cardiac Output");
  });

  it("setSaveStatus transitions to 'saving'", () => {
    useNoteStore.getState().setSaveStatus("saving");

    expect(useNoteStore.getState().saveStatus).toBe("saving");
  });

  it("setSaveStatus transitions to 'saved'", () => {
    useNoteStore.getState().setSaveStatus("saved");

    expect(useNoteStore.getState().saveStatus).toBe("saved");
  });

  it("setSaveStatus transitions back to 'unsaved'", () => {
    useNoteStore.getState().setSaveStatus("saved");
    useNoteStore.getState().setSaveStatus("unsaved");

    expect(useNoteStore.getState().saveStatus).toBe("unsaved");
  });
});
