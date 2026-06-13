import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// The login page is the module under test; it does not exist yet.
import LoginPage from "@/app/(auth)/login/page";

const mockSignIn = vi.fn();
const mockSignOut = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    auth: {
      signInWithPassword: mockSignIn,
      signOut: mockSignOut,
    },
  })),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

describe("Login form — authentication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSignIn.mockResolvedValue({ data: { session: {} }, error: null });
    mockSignOut.mockResolvedValue({ error: null });
    render(<LoginPage />);
  });

  it("renders email input, password input, and submit button", () => {
    expect(screen.getByRole("textbox", { name: /email/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log in|sign in/i })).toBeInTheDocument();
  });

  it("calls signInWithPassword with email and password on submit", async () => {
    const user = userEvent.setup();

    await user.type(screen.getByRole("textbox", { name: /email/i }), "student@example.com");
    await user.type(screen.getByLabelText(/^password/i), "securepassword1");
    await user.click(screen.getByRole("button", { name: /log in|sign in/i }));

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith({
        email: "student@example.com",
        password: "securepassword1",
      });
    });
  });

  it("shows an error message when credentials are wrong", async () => {
    mockSignIn.mockResolvedValueOnce({
      data: { session: null },
      error: { message: "Invalid login credentials" },
    });

    const user = userEvent.setup();

    await user.type(screen.getByRole("textbox", { name: /email/i }), "student@example.com");
    await user.type(screen.getByLabelText(/^password/i), "wrongpassword");
    await user.click(screen.getByRole("button", { name: /log in|sign in/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/invalid credentials|incorrect email or password|invalid login/i),
      ).toBeInTheDocument();
    });
  });
});

describe("Login page — sign-out control is absent for unauthenticated view", () => {
  it("does not show a sign-out button on the login page itself", () => {
    vi.clearAllMocks();
    render(<LoginPage />);

    // The /login page is for unauthenticated users; a sign-out button would be confusing.
    const signOutBtn = screen.queryByRole("button", { name: /sign out|log out/i });
    expect(signOutBtn).not.toBeInTheDocument();
  });
});
