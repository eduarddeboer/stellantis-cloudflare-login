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
