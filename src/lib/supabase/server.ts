import { createServerClient as createSsrServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { getClientEnv } from "@/lib/env";

type CookieToSet = {
  name: string;
  value: string;
  options?: Record<string, unknown>;
};

/**
 * Minimal cookie-store contract the server client needs. Mirrors the
 * `getAll`/`setAll` shape provided by Next.js `cookies()` and by
 * `@supabase/ssr`. The deprecated per-cookie `get`/`set`/`remove` methods are
 * intentionally not part of this contract.
 */
export type CookieStore = {
  getAll: () => Array<{ name: string; value: string }>;
  setAll: (cookies: CookieToSet[]) => void;
};

/**
 * Creates a Supabase client for server-side use (Server Components, Route
 * Handlers, the proxy). Session cookies are read and written exclusively
 * through the `getAll`/`setAll` pattern — never the deprecated
 * `get`/`set`/`remove` methods — so token refreshes round-trip correctly.
 */
export function createServerClient(cookieStore: CookieStore): SupabaseClient {
  const { NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY } = getClientEnv();

  // Eagerly read existing session cookies up front so a server client always
  // restores any current session on creation, independent of @supabase/ssr's
  // lazy auth initialization.
  cookieStore.getAll();

  return createSsrServerClient(NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        cookieStore.setAll(cookiesToSet);
      },
    },
  });
}
