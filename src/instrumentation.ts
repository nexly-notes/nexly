import { getEnv } from "@/lib/env";

/**
 * Next.js calls `register()` once when a server instance starts, before it
 * serves any request. Validating the full server env here makes a misconfigured
 * deployment fail fast at boot rather than throwing deep inside a request.
 *
 * The server-only secret only exists in the Node.js runtime, so the full
 * validation is skipped on the Edge runtime (where `getClientEnv()` is what
 * matters). Tests run with `NEXT_RUNTIME` unset and exercise full validation.
 */
export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "edge") {
    return;
  }
  getEnv();
}
