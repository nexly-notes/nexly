"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { z } from "zod";

import { createClient } from "@/lib/supabase/client";

// Sign-up requires a valid email and an 8+ character password (FR-009 ToS gate
// is enforced separately via the checkbox-gated submit button).
const signupSchema = z.object({
  email: z.email(),
  password: z.string().min(8, { message: "Password must be at least 8 characters" }),
});

type FieldErrors = {
  email?: string;
  password?: string;
};

export default function SignupPage(): React.JSX.Element {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [acceptedTos, setAcceptedTos] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setFormError("");

    const parsed = signupSchema.safeParse({ email, password });
    if (!parsed.success) {
      const fieldErrors = parsed.error.flatten().fieldErrors;
      setErrors({
        email: fieldErrors.email?.[0],
        password: fieldErrors.password?.[0],
      });
      return;
    }
    setErrors({});

    setSubmitting(true);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.signUp({
        email: parsed.data.email,
        password: parsed.data.password,
        // Stamp ToS acceptance on the account so the no-PHI gate is auditable.
        // user_metadata is never used for authorization decisions.
        options: {
          data: { tos_accepted_at: new Date().toISOString() },
        },
      });
      if (error) {
        // Generic copy only — echoing the Supabase message ("User already
        // registered") would let anyone enumerate which emails have accounts.
        setFormError("Could not create account. Check your details or try logging in.");
        return;
      }
      // Email confirmation is disabled for the beta, so sign-up returns an
      // immediate session — go straight to the app.
      router.replace("/");
    } catch {
      setFormError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold">Create your account</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <div className="flex flex-col gap-1">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="rounded border px-3 py-2"
          />
          {errors.email ? (
            <p role="alert" className="text-sm text-red-600">
              {errors.email}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="rounded border px-3 py-2"
          />
          {errors.password ? (
            <p role="alert" className="text-sm text-red-600">
              {errors.password}
            </p>
          ) : null}
        </div>

        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            checked={acceptedTos}
            onChange={(event) => setAcceptedTos(event.target.checked)}
            className="mt-1"
          />
          <span className="text-sm">
            I agree to the beta Terms of Service — didactic lecture notes only;
            no patient-identifying information (PHI)
          </span>
        </label>

        {formError ? (
          <p role="alert" className="text-sm text-red-600">
            {formError}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={!acceptedTos || submitting}
          className="rounded bg-[#3ba9ff] px-4 py-2 text-white disabled:opacity-50"
        >
          Sign up
        </button>
      </form>
    </main>
  );
}
