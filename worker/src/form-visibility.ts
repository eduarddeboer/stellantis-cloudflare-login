/**
 * Read-only, privacy-preserving assessment of the public Peugeot login UI.
 * Only boolean visibility signals and a fixed challenge-provider category survive.
 * No raw DOM, text, iframe URL or account data may leave the browser.
 */
export type ChallengeType = "none" | "recaptcha" | "hcaptcha" | "turnstile" | "multiple";
export interface FrameVisibility {
  email_visible: boolean;
  password_visible: boolean;
  submit_visible: boolean;
  first_gigya_email_visible: boolean;
  challenge_widget_visible: boolean;
  recaptcha_present: boolean;
  hcaptcha_present: boolean;
  turnstile_present: boolean;
}
export interface FormVisibilityReport {
  main_email_visible: boolean;
  main_password_visible: boolean;
  main_submit_visible: boolean;
  first_gigya_email_visible: boolean;
  iframe_email_visible: boolean;
  iframe_password_visible: boolean;
  iframe_submit_visible: boolean;
  inspected_iframes: number;
  challenge_widget_visible: boolean;
  challenge_type: ChallengeType;
}
export function summarizeFrameVisibility(results: readonly (FrameVisibility | null)[]): FormVisibilityReport {
  const main = results[0] ?? null;
  const children = results.slice(1, 13).filter((v): v is FrameVisibility => v !== null);
  const all = results.slice(0, 13).filter((v): v is FrameVisibility => v !== null);
  const types = [
    all.some(v => v.recaptcha_present) ? "recaptcha" : null,
    all.some(v => v.hcaptcha_present) ? "hcaptcha" : null,
    all.some(v => v.turnstile_present) ? "turnstile" : null,
  ].filter((v): v is Exclude<ChallengeType, "none" | "multiple"> => v !== null);
  const challengeType: ChallengeType =
    types.length > 1 ? "multiple" : types.length === 1 ? types[0] : "none";
  return {
    main_email_visible: main?.email_visible === true,
    main_password_visible: main?.password_visible === true,
    main_submit_visible: main?.submit_visible === true,
    first_gigya_email_visible: main?.first_gigya_email_visible === true,
    iframe_email_visible: children.some(v => v.email_visible),
    iframe_password_visible: children.some(v => v.password_visible),
    iframe_submit_visible: children.some(v => v.submit_visible),
    inspected_iframes: Math.min(12, children.length),
    challenge_widget_visible: all.some(v => v.challenge_widget_visible),
    challenge_type: challengeType,
  };
}
