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
