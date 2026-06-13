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

describe("note store title", () => {
  beforeEach(() => {
    useNoteStore.setState({ mode: "create", title: "" });
  });

  it("defaults title to an empty string", () => {
    expect(useNoteStore.getState().title).toBe("");
  });

  it("setTitle stores the provided title", () => {
    useNoteStore.getState().setTitle("Cardiac Output");

    expect(useNoteStore.getState().title).toBe("Cardiac Output");
  });
});
