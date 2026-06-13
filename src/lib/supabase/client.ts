import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { getClientEnv } from "@/lib/env";

/**
 * Creates a Supabase client for use in the browser.
 *
 * Uses only the browser-safe `NEXT_PUBLIC_` variables; the server secret never
 * reaches client code. `@supabase/ssr` manages session cookies automatically
 * via `document.cookie`.
 */
export function createClient(): SupabaseClient {
  const { NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY } = getClientEnv();
  return createBrowserClient(NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
}
