import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Public routes never require a session. Everything else (the editor, the
// library, "/") is protected.
const PUBLIC_PATHS = ["/login", "/signup"] as const;

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );
}

// Supabase stores its session in `sb-*-auth-token` cookies; absence of one
// means there is no session to refresh, so we can skip the network call.
function hasSupabaseAuthCookie(request: NextRequest): boolean {
  return request.cookies
    .getAll()
    .some((cookie) => cookie.name.startsWith("sb-") && cookie.name.includes("auth-token"));
}

type SessionResult = {
  user: { id: string } | null;
  response: NextResponse;
};

/**
 * Refreshes the Supabase session using the canonical `@supabase/ssr`
 * middleware pattern: cookies rotated during `getUser()` are written onto BOTH
 * the request (so the render pass downstream sees the fresh tokens) and the
 * returned response (so the browser persists them). Dropping either side
 * discards the rotated refresh token and eventually force-logs the user out.
 *
 * `@supabase/ssr` is imported dynamically so test suites can override
 * `createServerClient` via `vi.doMock`. Any failure is treated as "no user" —
 * middleware must never throw.
 */
async function refreshSession(request: NextRequest): Promise<SessionResult> {
  let response = NextResponse.next({ request });

  try {
    const { createServerClient } = await import("@supabase/ssr");
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "",
      {
        cookies: {
          getAll() {
            return request.cookies.getAll();
          },
          setAll(cookiesToSet) {
            for (const { name, value } of cookiesToSet) {
              request.cookies.set(name, value);
            }
            response = NextResponse.next({ request });
            for (const { name, value, options } of cookiesToSet) {
              response.cookies.set(name, value, options);
            }
          },
        },
      },
    );

    const { data, error } = await supabase.auth.getUser();
    if (error || !data?.user) {
      return { user: null, response };
    }
    return { user: { id: data.user.id }, response };
  } catch {
    return { user: null, response };
  }
}

/**
 * Builds a redirect that carries over any session cookies written during the
 * refresh, so rotated tokens survive the redirect instead of being dropped.
 */
function redirectWithSessionCookies(
  path: string,
  request: NextRequest,
  sessionResponse: NextResponse,
): NextResponse {
  const redirect = NextResponse.redirect(new URL(path, request.url));
  for (const cookie of sessionResponse.cookies.getAll()) {
    redirect.cookies.set(cookie);
  }
  return redirect;
}

/**
 * Session guard: refreshes the Supabase session and routes by auth state.
 *
 * - Unauthenticated request to a protected route -> /login
 * - Authenticated request to /login or /signup    -> /
 * - Everything else passes through (with refreshed session cookies).
 */
export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { pathname } = request.nextUrl;
  const onPublicPath = isPublicPath(pathname);

  if (!hasSupabaseAuthCookie(request)) {
    return onPublicPath
      ? NextResponse.next({ request })
      : NextResponse.redirect(new URL("/login", request.url));
  }

  const { user, response } = await refreshSession(request);

  if (!user && !onPublicPath) {
    return redirectWithSessionCookies("/login", request, response);
  }

  if (user && onPublicPath) {
    return redirectWithSessionCookies("/", request, response);
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
