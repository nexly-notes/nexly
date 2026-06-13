import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the browser Supabase client so tests run without a real Supabase project.
// Each test configures the mock's resolved values to exercise specific behaviors.
const mockInsert = vi.fn();
const mockSelect = vi.fn();
const mockUpdate = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    from: vi.fn(() => ({
      insert: mockInsert,
      select: mockSelect,
      update: mockUpdate,
    })),
  })),
}));

// A minimal valid Note row returned by Supabase.
const SAMPLE_NOTE = {
  id: "note-uuid-1",
  user_id: "user-uuid-1",
  title: "My first note",
  content: { type: "doc", content: [] },
  word_count: 0,
  created_at: "2026-06-12T00:00:00Z",
  updated_at: "2026-06-12T00:00:00Z",
};

describe("createNote()", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("inserts a notes row and returns the new Note", async () => {
    // Chain: .from('notes').insert(...).select().single()
    const singleMock = vi.fn().mockResolvedValue({ data: SAMPLE_NOTE, error: null });
    const selectAfterInsert = vi.fn(() => ({ single: singleMock }));
    mockInsert.mockReturnValue({ select: selectAfterInsert });

    const { createNote } = await import("@/lib/notes");
    const note = await createNote();

    expect(mockInsert).toHaveBeenCalledWith(
      expect.objectContaining({
        title: expect.any(String),
        content: expect.any(Object),
        word_count: 0,
      }),
    );
    // user_id is intentionally absent from the payload: the migration sets
    // `default auth.uid()` on notes.user_id, so the database fills it under RLS.
    expect(mockInsert.mock.calls[0]?.[0]).not.toHaveProperty("user_id");
    expect(note).toMatchObject({
      id: expect.any(String),
      user_id: expect.any(String),
      title: expect.any(String),
      content: expect.any(Object),
      word_count: expect.any(Number),
      created_at: expect.any(String),
      updated_at: expect.any(String),
    });
  });

  it("does not set NoteMode or mode-related fields on the returned Note", async () => {
    const singleMock = vi.fn().mockResolvedValue({ data: SAMPLE_NOTE, error: null });
    const selectAfterInsert = vi.fn(() => ({ single: singleMock }));
    mockInsert.mockReturnValue({ select: selectAfterInsert });

    const { createNote } = await import("@/lib/notes");
    const note = await createNote();

    expect(note).not.toHaveProperty("mode");
    expect(note).not.toHaveProperty("noteMode");
  });
});

describe("getNote(id)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("returns a Note when the row exists and belongs to the current user", async () => {
    const eqMock = vi.fn().mockReturnValue({ single: vi.fn().mockResolvedValue({ data: SAMPLE_NOTE, error: null }) });
    const selectMock = vi.fn(() => ({ eq: eqMock }));
    mockSelect.mockImplementation(selectMock);

    const { getNote } = await import("@/lib/notes");
    const note = await getNote("note-uuid-1");

    expect(note).toMatchObject({ id: "note-uuid-1" });
  });

  it("returns null (not an exception) when the note does not exist", async () => {
    // PGRST116 is the Supabase PostgREST error code for "no rows found"
    const eqMock = vi.fn().mockReturnValue({
      single: vi.fn().mockResolvedValue({
        data: null,
        error: { code: "PGRST116", message: "Row not found" },
      }),
    });
    const selectMock = vi.fn(() => ({ eq: eqMock }));
    mockSelect.mockImplementation(selectMock);

    const { getNote } = await import("@/lib/notes");
    const result = await getNote("nonexistent-id");

    expect(result).toBeNull();
  });

  it("returns null (not an exception) for a note belonging to another user", async () => {
    // RLS prevents cross-user access; Supabase returns no rows rather than an error
    const eqMock = vi.fn().mockReturnValue({
      single: vi.fn().mockResolvedValue({
        data: null,
        error: { code: "PGRST116", message: "Row not found" },
      }),
    });
    const selectMock = vi.fn(() => ({ eq: eqMock }));
    mockSelect.mockImplementation(selectMock);

    const { getNote } = await import("@/lib/notes");
    const result = await getNote("foreign-note-id");

    expect(result).toBeNull();
  });
});

describe("listNotes()", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("returns an empty array when the user has no notes", async () => {
    mockSelect.mockReturnValue({ data: [], error: null });

    const { listNotes } = await import("@/lib/notes");
    const notes = await listNotes();

    expect(notes).toEqual([]);
  });

  it("returns a list of Note objects when notes exist", async () => {
    mockSelect.mockReturnValue({ data: [SAMPLE_NOTE], error: null });

    const { listNotes } = await import("@/lib/notes");
    const notes = await listNotes();

    expect(Array.isArray(notes)).toBe(true);
    expect(notes.length).toBe(1);
    expect(notes[0]).toMatchObject({ id: "note-uuid-1" });
  });
});

describe("saveNote(id, patch)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("updates title, content, word_count, and updated_at on the matching note row", async () => {
    const eqMock = vi.fn().mockResolvedValue({ data: null, error: null });
    mockUpdate.mockReturnValue({ eq: eqMock });

    const { saveNote } = await import("@/lib/notes");

    const patch = {
      title: "Updated Title",
      content: { type: "doc", content: [{ type: "paragraph" }] },
      word_count: 42,
    };
    await saveNote("note-uuid-1", patch);

    expect(mockUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Updated Title",
        content: { type: "doc", content: [{ type: "paragraph" }] },
        word_count: 42,
        updated_at: expect.any(String),
      }),
    );
    expect(eqMock).toHaveBeenCalledWith("id", "note-uuid-1");
  });

  it("resolves without returning a value (void)", async () => {
    const eqMock = vi.fn().mockResolvedValue({ data: null, error: null });
    mockUpdate.mockReturnValue({ eq: eqMock });

    const { saveNote } = await import("@/lib/notes");
    const result = await saveNote("note-uuid-1", { title: "t", content: {}, word_count: 0 });

    expect(result).toBeUndefined();
  });
});
