/** Check HTTP access without reading a credential-bearing request body. */
export function accessStatus(
  method: string,
  pathname: string,
  authorization: string | null,
  apiKey: string | undefined,
): 401 | 404 | null {
  if (method !== "POST" || (pathname !== "/" && pathname !== "/validate" && pathname !== "/browser-check" && pathname !== "/login-page-check")) return 404;
  if (!apiKey || authorization !== `Bearer ${apiKey}`) return 401;
  return null;
}

/** One approximate per-location admission check for POST / only.
 * Never use email, password, Authorization, OAuth code or client IP as key.
 * A missing or failing Cloudflare binding must never start Browser Rendering.
 */
export async function loginRateLimitStatus(
  limiter: { limit(options: { key: string }): Promise<{ success: boolean }> } | undefined,
): Promise<429 | 503 | null> {
  if (!limiter) return 503;
  try {
    const result = await limiter.limit({ key: "oauth-login" });
    if (result?.success === true) return null;
    if (result?.success === false) return 429;
    return 503;
  } catch {
    return 503;
  }
}
