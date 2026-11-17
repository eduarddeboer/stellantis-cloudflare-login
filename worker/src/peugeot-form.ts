/** Visible selectors verified against Peugeot OAuth flow reports.
 * Avoid hidden Gigya template fields by testing selectors individually.
 */
export const EMAIL_SELECTORS = [
  '#gigya-login-form input[name="username"]',
  'input[name="username"]',
  'input[name="loginID"]',
  'input[name="email"]',
  'input[type="email"]',
] as const;

export const PASSWORD_SELECTORS = [
  '#gigya-login-form input[name="password"]',
  'input[name="password"]',
  'input[type="password"]',
] as const;

export const LOGIN_BUTTON_SELECTORS = [
  '#gigya-login-form button[type="submit"]',
  '#gigya-login-form input[type="submit"]',
  'button[type="submit"]',
  'input[type="submit"]',
] as const;

export const CONSENT_BUTTON_SELECTORS = [
  "#consentbutton",
  '#cvs_from button[type="submit"]',
  '#cvs_from input[type="submit"]',
  '#cvs_form button[type="submit"]',
  '#cvs_form input[type="submit"]',
  'form[action*="/oauth2/authorize"] button[type="submit"]',
  'form[action*="/oauth2/authorize"] input[type="submit"]',
] as const;

/**
 * Wait for the first currently visible match across *all* candidate selectors.
 *
 * Old implementation waited for each selector sequentially, e.g. 3.6 s per
 * selector when the page needed 18 s to hydrate. A Gigya hidden template could
 * absorb the entire budget, and the real input appeared just as we failed.
 * One Playwright union selector shares the entire timeout and automatically
 * re-evaluates while Gigya dynamically renders the form.
 *
 * Supported by Playwright's documented CSS :visible pseudo-class. Never return
 * raw locator failures, DOM contents, URLs or credential values.
 */
export async function firstVisible<T extends {
  waitFor: (opts: { state: "visible"; timeout: number }) => Promise<void>;
}>(
  locate: (selector: string) => T,
  selectors: readonly string[],
  totalTimeoutMs: number,
): Promise<T> {
  if (!selectors.length) throw new Error("Expected visible form control not found");
  const combined = selectors.map(selector => `${selector}:visible`).join(", ");
  const control = locate(combined);
  try {
    await control.waitFor({ state: "visible", timeout: Math.max(1000, totalTimeoutMs) });
    return control;
  } catch {
    throw new Error("Expected visible form control not found");
  }
}
