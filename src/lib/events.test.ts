import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the browser Supabase client to control insert behavior.
const mockInsert = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    from: vi.fn(() => ({
      insert: mockInsert,
    })),
  })),
}));

describe("logEvent(type, details?)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("calls supabase insert on the events table", async () => {
    mockInsert.mockResolvedValue({ data: null, error: null });

    const { logEvent } = await import("@/lib/events");
    logEvent("note_created");

    // Allow the fire-and-forget promise to settle before asserting.
    await vi.waitFor(() => {
      expect(mockInsert).toHaveBeenCalled();
    });
  });

  it("inserts an event row containing the event type", async () => {
    mockInsert.mockResolvedValue({ data: null, error: null });

    const { logEvent } = await import("@/lib/events");
    logEvent("note_opened");

    await vi.waitFor(() => {
      const [insertArg] = mockInsert.mock.calls[0] as [Record<string, unknown>];
      expect(insertArg).toMatchObject({ type: "note_opened" });
    });
  });

  it("does not send user_id (the database defaults it from the caller's JWT)", async () => {
    mockInsert.mockResolvedValue({ data: null, error: null });

    const { logEvent } = await import("@/lib/events");
    logEvent("note_created", { noteId: "note-uuid-1" });

    await vi.waitFor(() => {
      const [insertArg] = mockInsert.mock.calls[0] as [Record<string, unknown>];
      expect(insertArg).not.toHaveProperty("user_id");
    });
  });

  it("inserts an event row that contains no note content", async () => {
    mockInsert.mockResolvedValue({ data: null, error: null });

    const { logEvent } = await import("@/lib/events");
    logEvent("note_created");

    await vi.waitFor(() => {
      const [insertArg] = mockInsert.mock.calls[0] as [Record<string, unknown>];
      // The row must not contain note body / content fields
      expect(insertArg).not.toHaveProperty("content");
      expect(insertArg).not.toHaveProperty("body");
      expect(insertArg).not.toHaveProperty("text");
    });
  });

  it("puts a note reference in note_id, not in value (value is a numeric count per spec)", async () => {
    mockInsert.mockResolvedValue({ data: null, error: null });

    const { logEvent } = await import("@/lib/events");
    logEvent("note_created", { noteId: "note-uuid-1" });

    await vi.waitFor(() => {
      const [insertArg] = mockInsert.mock.calls[0] as [Record<string, unknown>];
      expect(insertArg).toMatchObject({ type: "note_created", note_id: "note-uuid-1" });
      expect(insertArg).not.toHaveProperty("value");
    });
  });

  it("includes a numeric value when one is provided", async () => {
    mockInsert.mockResolvedValue({ data: null, error: null });

    const { logEvent } = await import("@/lib/events");
    logEvent("perf_timing", { value: 480 });

    await vi.waitFor(() => {
      const [insertArg] = mockInsert.mock.calls[0] as [Record<string, unknown>];
      expect(insertArg).toMatchObject({ type: "perf_timing", value: 480 });
    });
  });

  it("swallows supabase errors without rethrowing", async () => {
    mockInsert.mockRejectedValue(new Error("network failure"));

    const { logEvent } = await import("@/lib/events");

    // logEvent() must not throw synchronously or return a rejected promise.
    expect(() => logEvent("note_created")).not.toThrow();
    // Allow the rejected promise to settle; no unhandled rejection should propagate.
    await new Promise((resolve) => setTimeout(resolve, 10));
  });

  it("swallows supabase insert errors returned via error field without rethrowing", async () => {
    mockInsert.mockResolvedValue({ data: null, error: { message: "RLS violation" } });

    const { logEvent } = await import("@/lib/events");

    expect(() => logEvent("note_opened")).not.toThrow();
    await new Promise((resolve) => setTimeout(resolve, 10));
  });
});
