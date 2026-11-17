/** Extract an authorization code only from the Stellantis custom-scheme callback. */
const PSA_CALLBACK_SCHEMES = new Set([
  "mymap:",       // MyPeugeot
  "mymacsdk:",   // MyCitroen
  "mymdssdk:",   // MyDS
  "mymopsdk:",   // MyOpel
  "mymvxsdk:",   // MyVauxhall
]);

/** Extract OAuth code only from registered PSA mobile app callbacks. */
export function extractAuthorizationCode(rawUrl: string): string | null {
  try {
    const parsed = new URL(rawUrl);
    if (!PSA_CALLBACK_SCHEMES.has(parsed.protocol.toLowerCase())) return null;
    if (parsed.hostname.toLowerCase() !== "oauth2redirect" || parsed.username || parsed.password || parsed.port) return null;
    const values = parsed.searchParams.getAll("code");
    if (values.length !== 1 || !values[0] || values[0].length > 4096) return null;
    return values[0];
  } catch {
    return null;
  }
}

/** Exact hostname matching; no suffix or wildcard matches. */
export function allowedLoginUrl(rawUrl: string, allowedHosts: string): boolean {
  try {
    const parsed = new URL(rawUrl);
    const hosts = allowedHosts.split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
    return parsed.protocol === "https:" && !parsed.username && !parsed.password &&
      (!parsed.port || parsed.port === "443") &&
      hosts.includes(parsed.hostname.toLowerCase());
  } catch {
    return false;
  }
}


/** Only the known Stellantis OAuth authorization entrypoint may start login.
 * Reuse this for credential-bearing login and credential-free page checks.
 * Allowing arbitrary paths or redirect URIs would enlarge the trusted surface.
 */
export function allowedAuthorizeUrl(rawUrl: string, allowedHosts: string): boolean {
  if (!allowedLoginUrl(rawUrl, allowedHosts)) return false;
  try {
    const url = new URL(rawUrl);
    if (url.pathname !== "/am/oauth2/authorize" ||
        url.searchParams.get("response_type") !== "code" ||
        !url.searchParams.get("client_id")) return false;

    const redirectRaw = url.searchParams.get("redirect_uri");
    if (!redirectRaw) return false;
    const redirect = new URL(redirectRaw);
    if (!PSA_CALLBACK_SCHEMES.has(redirect.protocol.toLowerCase()) ||
        redirect.hostname.toLowerCase() !== "oauth2redirect" ||
        redirect.username || redirect.password || redirect.port ||
        redirect.search || redirect.hash || !redirect.pathname.startsWith("/")) {
      return false;
    }

    const accepted = new Set(["client_id", "response_type", "redirect_uri", "scope", "locale"]);
    const seen = new Set<string>();
    let invalid = false;
    url.searchParams.forEach((_value, key) => {
      if (!accepted.has(key) || seen.has(key)) invalid = true;
      seen.add(key);
    });
    return !invalid;
  } catch {
    return false;
  }
}
