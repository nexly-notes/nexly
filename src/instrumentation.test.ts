import { afterEach, beforeEach, describe, expect, it } from "vitest";

// register() runs once at server startup (Next.js instrumentation hook) and
// must validate the full server env eagerly so a bad deployment fails fast.

const REQUIRED_VARS = {
  NEXT_PUBLIC_SUPABASE_URL: "https://test.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "anon-key-value",
  SUPABASE_SECRET_KEY: "service-role-secret",
};

describe("instrumentation register()", () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
    for (const [key, value] of Object.entries(REQUIRED_VARS)) {
      process.env[key] = value;
    }
    delete process.env.NEXT_RUNTIME;
  });

  afterEach(() => {
    for (const key of Object.keys(REQUIRED_VARS)) {
      delete process.env[key];
    }
    Object.assign(process.env, originalEnv);
  });

  it("resolves when all required env vars are present", async () => {
    const { register } = await import("@/instrumentation");

    await expect(register()).resolves.toBeUndefined();
  });

  it("throws at startup with a clear message when SUPABASE_SECRET_KEY is missing", async () => {
    delete process.env.SUPABASE_SECRET_KEY;
    const { register } = await import("@/instrumentation");

    await expect(register()).rejects.toThrow(/SUPABASE_SECRET_KEY/i);
  });

  it("throws at startup when NEXT_PUBLIC_SUPABASE_URL is missing", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    const { register } = await import("@/instrumentation");

    await expect(register()).rejects.toThrow(/NEXT_PUBLIC_SUPABASE_URL/i);
  });
});
