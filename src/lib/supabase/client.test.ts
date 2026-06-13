import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// We test the public contracts:
//   createClient()       → SupabaseClient using NEXT_PUBLIC_* vars (browser)
//   createServerClient() → SupabaseClient using getAll/setAll cookie pattern

const SUPABASE_URL = "https://test.supabase.co";
const PUBLISHABLE_KEY = "anon-key-value";
const SECRET_KEY = "service-role-secret";

describe("createClient() — browser Supabase client", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = SUPABASE_URL;
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = PUBLISHABLE_KEY;
    process.env.SUPABASE_SECRET_KEY = SECRET_KEY;
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    delete process.env.SUPABASE_SECRET_KEY;
    vi.resetModules();
  });

  it("returns an object with auth and from properties (SupabaseClient shape)", async () => {
    const { createClient } = await import("@/lib/supabase/client");

    const client = createClient();

    // A SupabaseClient always exposes these properties
    expect(client).toHaveProperty("auth");
    expect(client).toHaveProperty("from");
  });

  it("uses NEXT_PUBLIC_SUPABASE_URL as the Supabase project URL", async () => {
    const { createClient } = await import("@/lib/supabase/client");

    const client = createClient();

    // supabase-js stores the URL on the client instance as supabaseUrl
    expect((client as unknown as Record<string, unknown>).supabaseUrl).toBe(SUPABASE_URL);
  });

  it("uses NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY as the anon key", async () => {
    const { createClient } = await import("@/lib/supabase/client");

    const client = createClient();

    // supabase-js stores the key on the client as supabaseKey
    expect((client as unknown as Record<string, unknown>).supabaseKey).toBe(PUBLISHABLE_KEY);
  });
});

describe("createServerClient() — server Supabase client with cookie pattern", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = SUPABASE_URL;
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = PUBLISHABLE_KEY;
    process.env.SUPABASE_SECRET_KEY = SECRET_KEY;
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
    delete process.env.SUPABASE_SECRET_KEY;
    vi.resetModules();
  });

  it("returns a SupabaseClient (auth + from)", async () => {
    const { createServerClient } = await import("@/lib/supabase/server");

    const cookieStore = {
      getAll: () => [],
      setAll: () => {},
    };

    const client = createServerClient(cookieStore);

    expect(client).toHaveProperty("auth");
    expect(client).toHaveProperty("from");
  });

  it("calls getAll on the cookie store to read session cookies", async () => {
    const { createServerClient } = await import("@/lib/supabase/server");

    const getAllSpy = vi.fn().mockReturnValue([]);
    const cookieStore = {
      getAll: getAllSpy,
      setAll: vi.fn(),
    };

    createServerClient(cookieStore);

    // @supabase/ssr calls getAll at least once during client construction
    // to restore any existing session from cookies.
    expect(getAllSpy).toHaveBeenCalled();
  });

  it("calls setAll (not deprecated set/remove) when writing session cookies", async () => {
    const { createServerClient } = await import("@/lib/supabase/server");

    const setAllSpy = vi.fn();
    const cookieStore = {
      getAll: vi.fn().mockReturnValue([]),
      setAll: setAllSpy,
    };

    const client = createServerClient(cookieStore);

    // Trigger a sign-out so the SSR helper flushes cookie deletions via setAll.
    await client.auth.signOut();

    expect(setAllSpy).toHaveBeenCalled();
    // Ensure the argument shape: setAll receives an array of { name, value, options }
    const [cookiesArg] = setAllSpy.mock.calls[0] as [Array<{ name: string; value: string }>];
    expect(Array.isArray(cookiesArg)).toBe(true);
  });

  it("does NOT call deprecated get/set/remove cookie methods — only getAll/setAll", async () => {
    const { createServerClient } = await import("@/lib/supabase/server");

    // Provide a cookie store that implements ONLY the new getAll/setAll API.
    // If the implementation calls the old per-cookie get/set/remove methods those
    // will throw a TypeError (method not a function), so we can detect the violation.
    const deprecatedMethodSpy = vi.fn(() => {
      throw new TypeError("Deprecated cookie method called");
    });
    const cookieStore = {
      getAll: vi.fn().mockReturnValue([]),
      setAll: vi.fn(),
      // Deliberately absent: no get/set/remove — calling them throws.
      get: deprecatedMethodSpy,
      set: deprecatedMethodSpy,
      remove: deprecatedMethodSpy,
    };

    const client = createServerClient(cookieStore);

    // Trigger session flush (sign-out writes cookies) to exercise the cookie path.
    await client.auth.signOut();

    // None of the deprecated per-cookie methods should have been invoked.
    expect(deprecatedMethodSpy).not.toHaveBeenCalled();
  });
});
