/** Only static diagnostic labels may be returned to an authenticated caller.
 * Never return/log the original exception: it may contain OAuth URLs or tokens.
 */
export type LoginStage =
  | "browser_launch"
  | "browser_context"
  | "browser_page"
  | "login_navigation"
  | "login_email_field"
  | "login_password_field"
  | "login_submit"
  | "consent_submit"
  | "oauth_callback";

export type FailureKind = "browser_limit" | "timeout" | "browser_error";

export function safeFailureKind(error: unknown): FailureKind {
  const message = error instanceof Error ? error.message : "";
  const lower = message.toLowerCase();
  if ((lower.includes("429") && lower.includes("browser")) ||
      lower.includes("browser time limit exceeded") ||
      lower.includes("rate limit")) {
    return "browser_limit";
  }
  if (lower.includes("timeout") || lower.includes("timed out")) return "timeout";
  return "browser_error";
}

export function diagnostic(stage: LoginStage, error: unknown) {
  return {
    message: "Authentication failed or timed out",
    code: 502,
    stage,
    reason: safeFailureKind(error),
  } as const;
}
