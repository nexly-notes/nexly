import { afterEach, beforeEach, describe, expect, it } from "vitest";

// getEnv() reads process.env at call time, so we manipulate process.env
// directly in each test and restore it in afterEach.
const REQUIRED_VARS = {
  NEXT_PUBLIC_SUPABASE_URL: "https://test.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "anon-key-value",
  SUPABASE_SECRET_KEY: "service-role-secret",
};

describe("getEnv()", () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
    // Set all required vars by default so individual tests can remove one.
    for (const [key, value] of Object.entries(REQUIRED_VARS)) {
      process.env[key] = value;
    }
  });

  afterEach(() => {
    // Restore original env so tests don't bleed into each other.
    for (const key of Object.keys(REQUIRED_VARS)) {
      delete process.env[key];
    }
    Object.assign(process.env, originalEnv);
  });

  it("returns typed values when all required vars are present", async () => {
    const { getEnv } = await import("@/lib/env");

    const env = getEnv();

    expect(env.NEXT_PUBLIC_SUPABASE_URL).toBe(REQUIRED_VARS.NEXT_PUBLIC_SUPABASE_URL);
    expect(env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY).toBe(REQUIRED_VARS.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
    expect(env.SUPABASE_SECRET_KEY).toBe(REQUIRED_VARS.SUPABASE_SECRET_KEY);
  });

  it("throws with a clear message when NEXT_PUBLIC_SUPABASE_URL is missing", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    const { getEnv } = await import("@/lib/env");

    expect(() => getEnv()).toThrow(/NEXT_PUBLIC_SUPABASE_URL/i);
  });

  it("throws with a clear message when NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY is missing", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    const { getEnv } = await import("@/lib/env");

    expect(() => getEnv()).toThrow(/NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY/i);
  });

  it("throws with a clear message when SUPABASE_SECRET_KEY is missing", async () => {
    delete process.env.SUPABASE_SECRET_KEY;
    const { getEnv } = await import("@/lib/env");

    expect(() => getEnv()).toThrow(/SUPABASE_SECRET_KEY/i);
  });

  it("throws when NEXT_PUBLIC_SUPABASE_URL is not a valid URL", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "not-a-valid-url";
    const { getEnv } = await import("@/lib/env");

    // Must throw specifically because the URL is malformed, not just because
    // the function is unimplemented. The error message must reference the field.
    expect(() => getEnv()).toThrow(/NEXT_PUBLIC_SUPABASE_URL|url|invalid/i);
  });

  it("SUPABASE_SECRET_KEY is not part of the client-side env shape (public vars only)", async () => {
    const { getClientEnv } = await import("@/lib/env");

    const clientEnv = getClientEnv();

    expect(clientEnv).toHaveProperty("NEXT_PUBLIC_SUPABASE_URL");
    expect(clientEnv).toHaveProperty("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY");
    // SUPABASE_SECRET_KEY must not appear in the client-safe shape
    expect(clientEnv).not.toHaveProperty("SUPABASE_SECRET_KEY");
  });
});
