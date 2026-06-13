import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// The signup page is the module under test; it does not exist yet.
import SignupPage from "@/app/(auth)/signup/page";

// Supabase auth calls are network I/O — mock the client module so tests run in jsdom.
const mockSignUp = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: vi.fn(() => ({
    auth: {
      signUp: mockSignUp,
    },
  })),
}));

// next/navigation router mock (signup redirects on success)
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

function renderSignup(): ReturnType<typeof render> {
  return render(<SignupPage />);
}

describe("Sign-up form — ToS gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSignUp.mockResolvedValue({ data: { session: {} }, error: null });
    renderSignup();
  });

  it("submit button is disabled when the ToS checkbox is unchecked", () => {
    const submit = screen.getByRole("button", { name: /sign up|create account/i });
    expect(submit).toBeDisabled();
  });

  it("submit button becomes enabled once the ToS checkbox is checked", async () => {
    const user = userEvent.setup();
    const checkbox = screen.getByRole("checkbox", { name: /terms of service|tos|i agree/i });
    const submit = screen.getByRole("button", { name: /sign up|create account/i });

    await user.click(checkbox);

    expect(submit).not.toBeDisabled();
  });

  it("submit button returns to disabled when ToS checkbox is unchecked again", async () => {
    const user = userEvent.setup();
    const checkbox = screen.getByRole("checkbox", { name: /terms of service|tos|i agree/i });
    const submit = screen.getByRole("button", { name: /sign up|create account/i });

    await user.click(checkbox);
    await user.click(checkbox);

    expect(submit).toBeDisabled();
  });

  it("ToS copy states the didactic-notes-only / no-PHI restriction (FR-009)", () => {
    // The no-PHI clause is the entire point of the gate — the generic
    // "I agree to the Terms of Service" label is not acceptable.
    const checkbox = screen.getByRole("checkbox", {
      name: /didactic lecture notes only.*no patient-identifying information \(PHI\)/i,
    });
    expect(checkbox).toBeInTheDocument();
  });
});

describe("Sign-up form — Zod validation errors", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSignUp.mockResolvedValue({ data: { session: {} }, error: null });
    renderSignup();
  });

  it("shows an error message when the email field contains an invalid address", async () => {
    const user = userEvent.setup();

    const emailInput = screen.getByRole("textbox", { name: /email/i });
    const checkbox = screen.getByRole("checkbox", { name: /terms of service|tos|i agree/i });
    const submit = screen.getByRole("button", { name: /sign up|create account/i });

    await user.type(emailInput, "not-an-email");
    await user.click(checkbox);
    await user.click(submit);

    await waitFor(() => {
      expect(screen.getByText(/invalid email|valid email/i)).toBeInTheDocument();
    });
  });

  it("shows an error message when the password is too short (< 8 characters)", async () => {
    const user = userEvent.setup();

    const emailInput = screen.getByRole("textbox", { name: /email/i });
    const passwordInput = screen.getByLabelText(/^password/i);
    const checkbox = screen.getByRole("checkbox", { name: /terms of service|tos|i agree/i });
    const submit = screen.getByRole("button", { name: /sign up|create account/i });

    await user.type(emailInput, "student@example.com");
    await user.type(passwordInput, "short");
    await user.click(checkbox);
    await user.click(submit);

    await waitFor(() => {
      expect(screen.getByText(/at least 8 characters|password too short|minimum/i)).toBeInTheDocument();
    });
  });
});

describe("Sign-up form — successful submission", () => {
  it("calls signUp with the entered credentials and records ToS acceptance", async () => {
    vi.clearAllMocks();
    mockSignUp.mockResolvedValue({ data: { session: {} }, error: null });
    renderSignup();

    const user = userEvent.setup();
    const emailInput = screen.getByRole("textbox", { name: /email/i });
    const passwordInput = screen.getByLabelText(/^password/i);
    const checkbox = screen.getByRole("checkbox", { name: /terms of service|tos|i agree/i });
    const submit = screen.getByRole("button", { name: /sign up|create account/i });

    await user.type(emailInput, "student@example.com");
    await user.type(passwordInput, "securepassword1");
    await user.click(checkbox);
    await user.click(submit);

    await waitFor(() => {
      expect(mockSignUp).toHaveBeenCalledWith({
        email: "student@example.com",
        password: "securepassword1",
        // Acceptance is stamped on the account so the ToS gate is auditable,
        // not just a client-side checkbox.
        options: {
          data: { tos_accepted_at: expect.any(String) },
        },
      });
    });
  });
});

describe("Sign-up form — failure copy", () => {
  it("shows a generic error and never echoes the Supabase message (account enumeration)", async () => {
    vi.clearAllMocks();
    mockSignUp.mockResolvedValue({
      data: { session: null },
      error: { message: "User already registered" },
    });
    renderSignup();

    const user = userEvent.setup();
    const emailInput = screen.getByRole("textbox", { name: /email/i });
    const passwordInput = screen.getByLabelText(/^password/i);
    const checkbox = screen.getByRole("checkbox", { name: /terms of service|tos|i agree/i });
    const submit = screen.getByRole("button", { name: /sign up|create account/i });

    await user.type(emailInput, "student@example.com");
    await user.type(passwordInput, "securepassword1");
    await user.click(checkbox);
    await user.click(submit);

    await waitFor(() => {
      expect(screen.getByText(/could not create account/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/already registered/i)).not.toBeInTheDocument();
  });
});
