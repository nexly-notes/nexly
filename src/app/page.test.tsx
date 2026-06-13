import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "@/app/page";

const mockListNotes = vi.fn();
const mockCreateNote = vi.fn();

vi.mock("@/lib/notes", () => ({
  listNotes: (...args: unknown[]) => mockListNotes(...args),
  createNote: (...args: unknown[]) => mockCreateNote(...args),
}));

const mockSignOut = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    auth: {
      signOut: mockSignOut,
    },
  })),
}));

const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}));

describe("Landing page — sign-out", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListNotes.mockResolvedValue([]);
    mockSignOut.mockResolvedValue({ error: null });
  });

  it("renders a Sign out control", async () => {
    render(<Home />);

    expect(
      screen.getByRole("button", { name: /sign out|log out/i }),
    ).toBeInTheDocument();
  });

  it("ends the session and routes to /login when Sign out is clicked", async () => {
    const user = userEvent.setup();
    render(<Home />);

    await user.click(screen.getByRole("button", { name: /sign out|log out/i }));

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalledTimes(1);
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("surfaces an error and stays on the page when sign-out fails", async () => {
    mockSignOut.mockResolvedValue({ error: { message: "boom" } });
    const user = userEvent.setup();
    render(<Home />);

    await user.click(screen.getByRole("button", { name: /sign out|log out/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/could not sign out/i);
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });
});

describe("Landing page — note creation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListNotes.mockResolvedValue([]);
    mockSignOut.mockResolvedValue({ error: null });
  });

  it("creates a note and routes into its editor", async () => {
    mockCreateNote.mockResolvedValue({ id: "note-uuid-9" });
    const user = userEvent.setup();
    render(<Home />);

    await user.click(screen.getByRole("button", { name: /new note/i }));

    await waitFor(() => {
      expect(mockCreateNote).toHaveBeenCalledTimes(1);
      expect(mockPush).toHaveBeenCalledWith("/notes/note-uuid-9");
    });
  });

  it("lists the user's notes once loaded", async () => {
    mockListNotes.mockResolvedValue([
      {
        id: "note-uuid-1",
        user_id: "user-uuid-1",
        title: "Cardiac glycosides",
        content: { type: "doc", content: [] },
        word_count: 2,
        created_at: "2026-06-12T00:00:00Z",
        updated_at: "2026-06-12T00:00:00Z",
      },
    ]);
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Cardiac glycosides")).toBeInTheDocument();
    });
  });
});
