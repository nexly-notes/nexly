import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";

import { proxy } from "@/proxy";

function makeRequest(
  path: string,
  sessionCookie: string | null = null,
): NextRequest {
  const headers = new Headers();
  if (sessionCookie) {
    headers.set("cookie", `sb-auth-token=${sessionCookie}`);
  }
  return new NextRequest(`http://localhost${path}`, { headers });
}

// The proxy is expected to return a Response-like object.
// We inspect the Location header for redirects.
function locationOf(response: Response): string | null {
  return response.headers.get("location");
}

function isRedirect(response: Response): boolean {
  return response.status >= 300 && response.status < 400;
}

// Mocks @supabase/ssr so the proxy sees an authenticated session. When
// `refreshedCookies` is given, the mock writes them through the proxy's
// `setAll` during getUser(), simulating a token refresh/rotation.
function mockAuthenticatedSupabase(
  refreshedCookies: Array<{ name: string; value: string }> = [],
): void {
  vi.doMock("@supabase/ssr", () => ({
    createServerClient: vi.fn(
      (
        _url: string,
        _key: string,
        options: {
          cookies: {
            setAll: (
              cookies: Array<{ name: string; value: string; options?: object }>,
            ) => void;
          };
        },
      ) => ({
        auth: {
          getUser: vi.fn().mockImplementation(() => {
            if (refreshedCookies.length > 0) {
              options.cookies.setAll(
                refreshedCookies.map((cookie) => ({ ...cookie, options: { path: "/" } })),
              );
            }
            return Promise.resolve({
              data: { user: { id: "user-123" } },
              error: null,
            });
          }),
        },
      }),
    ),
  }));
}

describe("Proxy — unauthenticated redirect", () => {
  it("redirects a request to a protected route (/notes/123) to /login when there is no session", async () => {
    const req = makeRequest("/notes/123", null);
    const res = await proxy(req);

    expect(isRedirect(res)).toBe(true);
    expect(locationOf(res)).toMatch(/\/login/);
  });

  it("redirects an unauthenticated request to / to /login", async () => {
    const req = makeRequest("/", null);
    const res = await proxy(req);

    expect(isRedirect(res)).toBe(true);
    expect(locationOf(res)).toMatch(/\/login/);
  });

  it("does NOT redirect a request already going to /login (avoids redirect loop)", async () => {
    const req = makeRequest("/login", null);
    const res = await proxy(req);

    // Should either pass through (200/no redirect) or not redirect to /login again
    if (isRedirect(res)) {
      expect(locationOf(res)).not.toMatch(/\/login/);
    } else {
      expect(res.status).toBeLessThan(300);
    }
  });

  it("does NOT redirect a request to /signup when unauthenticated", async () => {
    const req = makeRequest("/signup", null);
    const res = await proxy(req);

    if (isRedirect(res)) {
      expect(locationOf(res)).not.toMatch(/\/login/);
    } else {
      expect(res.status).toBeLessThan(300);
    }
  });
});

describe("Proxy — authenticated requests", () => {
  const VALID_SESSION = "fake-session-token";

  it("redirects an authenticated user visiting /login to /", async () => {
    mockAuthenticatedSupabase();
    const req = makeRequest("/login", VALID_SESSION);

    const res = await proxy(req);

    expect(isRedirect(res)).toBe(true);
    expect(locationOf(res)).toMatch(/^http:\/\/localhost\/$/);
  });

  it("redirects an authenticated user visiting /signup to /", async () => {
    mockAuthenticatedSupabase();
    const req = makeRequest("/signup", VALID_SESSION);

    const res = await proxy(req);

    expect(isRedirect(res)).toBe(true);
    expect(locationOf(res)).toMatch(/^http:\/\/localhost\/$/);
  });

  it("passes an authenticated request to a protected route through without redirecting", async () => {
    mockAuthenticatedSupabase();
    const req = makeRequest("/notes/123", VALID_SESSION);

    const res = await proxy(req);

    expect(isRedirect(res)).toBe(false);
    expect(res.status).toBeLessThan(300);
  });
});

describe("Proxy — session cookie persistence (token rotation)", () => {
  const VALID_SESSION = "fake-session-token";
  const REFRESHED = { name: "sb-auth-token", value: "rotated-refresh-token" };

  it("writes refreshed session cookies onto a pass-through response", async () => {
    mockAuthenticatedSupabase([REFRESHED]);
    const req = makeRequest("/notes/123", VALID_SESSION);

    const res = await proxy(req);

    expect(res.headers.get("set-cookie")).toContain("rotated-refresh-token");
  });

  it("writes refreshed session cookies onto a redirect response", async () => {
    mockAuthenticatedSupabase([REFRESHED]);
    const req = makeRequest("/login", VALID_SESSION);

    const res = await proxy(req);

    expect(isRedirect(res)).toBe(true);
    expect(res.headers.get("set-cookie")).toContain("rotated-refresh-token");
  });
});
