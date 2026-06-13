import { z } from "zod";

/**
 * Centralized, Zod-validated access to environment variables.
 *
 * Validation runs at call time (not module load) so the values reflect the
 * current `process.env`. Two shapes are exposed:
 *  - `getEnv()` — the full server-side shape, including the server-only secret.
 *  - `getClientEnv()` — only the browser-safe `NEXT_PUBLIC_` vars.
 *
 * Never import `getEnv()` (or `SUPABASE_SECRET_KEY`) into client components —
 * the secret must never reach the browser bundle.
 */

const PUBLIC_ENV_SHAPE = {
  NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: z.string().min(1),
} as const;

const SERVER_ENV_SHAPE = {
  ...PUBLIC_ENV_SHAPE,
  SUPABASE_SECRET_KEY: z.string().min(1),
} as const;

const clientEnvSchema = z.object(PUBLIC_ENV_SHAPE);
const serverEnvSchema = z.object(SERVER_ENV_SHAPE);

export type ClientEnv = z.infer<typeof clientEnvSchema>;
export type ValidatedEnv = z.infer<typeof serverEnvSchema>;

/**
 * Builds a clear, field-referencing error message from Zod issues so callers
 * (and tests) can tell exactly which variable is missing or malformed.
 */
function formatEnvError(error: z.ZodError): string {
  const details = error.issues
    .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
    .join("; ");
  return `Invalid environment variables — ${details}`;
}

function parseEnv<T extends z.ZodTypeAny>(
  schema: T,
  source: Record<string, string | undefined>,
): z.infer<T> {
  const result = schema.safeParse(source);
  if (!result.success) {
    throw new Error(formatEnvError(result.error));
  }
  return result.data;
}

// Each variable below MUST be referenced as a static `process.env.X` member
// expression: Next.js inlines NEXT_PUBLIC_ values into the client bundle only
// at static reference sites — dynamic lookups (passing `process.env` as an
// object) are never inlined and resolve to an empty object in the browser.

/** Full server-side environment, including the server-only secret. */
export function getEnv(): ValidatedEnv {
  return parseEnv(serverEnvSchema, {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_SECRET_KEY: process.env.SUPABASE_SECRET_KEY,
  });
}

/** Browser-safe environment — only the `NEXT_PUBLIC_` variables. */
export function getClientEnv(): ClientEnv {
  return parseEnv(clientEnvSchema, {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  });
}
