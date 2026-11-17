import { launch } from "@cloudflare/playwright";
import { extractAuthorizationCode, allowedLoginUrl, allowedAuthorizeUrl } from "./oauth";
import { accessStatus, loginRateLimitStatus } from "./security";
import {
  EMAIL_SELECTORS, PASSWORD_SELECTORS, LOGIN_BUTTON_SELECTORS,
  CONSENT_BUTTON_SELECTORS, firstVisible,
} from "./peugeot-form";
import { diagnostic, safeFailureKind, type LoginStage } from "./diagnostics";
import { sanitizePublicPageReport, type PublicPageSignals } from "./public-page-signals";
import { summarizeFrameVisibility, type FrameVisibility } from "./form-visibility";

interface Env {
  BROWSER: BrowserRun;
  API_KEY: string;
  ALLOWED_LOGIN_HOSTS: string;
  LOGIN_RATE_LIMITER: RateLimit;
}

interface LoginRequest {
  url?: string;
  email?: string;
  password?: string;
  timeout_page?: number;
  timeout_input?: number;
}

function reply(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function failure(message: string, status: number): Response {
  return reply({ message, code: status }, status);
}

function boundedTimeout(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.max(1000, Math.min(60000, value))
    : 50000;
}

/** Code may arrive immediately after login, without a consent page. */
async function codeWithin(captured: Promise<string>, ms: number): Promise<string | null> {
  return Promise.race([
    captured,
    new Promise<null>(resolve => setTimeout(() => resolve(null), ms)),
  ]);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const pathname = new URL(request.url).pathname;
    if (request.method === "GET" && pathname === "/health") {
      return reply({ status: "ok", ready: Boolean(env.API_KEY && env.ALLOWED_LOGIN_HOSTS) });
    }
    const deniedStatus = accessStatus(request.method, pathname, request.headers.get("authorization"), env.API_KEY);
    if (deniedStatus !== null) {
      return failure(deniedStatus === 401 ? "Unauthorized" : "Not found", deniedStatus);
    }
    if (!request.headers.get("content-type")?.includes("application/json")) {
      return failure("Expected JSON", 415);
    }
    const declaredLength = Number(request.headers.get("content-length") || 0);
    if (declaredLength > 16384) return failure("Payload too large", 413);
    let body: LoginRequest;
    try {
      const raw = await request.text();
      if (raw.length > 16384) return failure("Payload too large", 413);
      body = JSON.parse(raw) as LoginRequest;
    } catch {
      return failure("Invalid JSON", 400);
    }
    // Authenticated, credential-free check of the Cloudflare Browser Run binding.
    // Never contacts Peugeot and never accepts secrets in a request body.
    if (pathname === "/browser-check") {
      if (!body || typeof body !== "object" || Array.isArray(body) ||
          Object.keys(body).length !== 0) {
        return failure("Expected empty JSON object", 400);
      }
      let checkBrowser: Awaited<ReturnType<typeof launch>> | undefined;
      let checkStage: LoginStage = "browser_launch";
      try {
        checkBrowser = await launch(env.BROWSER);
        checkStage = "browser_context";
        const checkContext = await checkBrowser.newContext();
        try {
          checkStage = "browser_page";
          const checkPage = await checkContext.newPage();
          await checkPage.goto("about:blank", { waitUntil: "load", timeout: 10000 });
          return reply({ status: "ok", browser: true });
        } finally {
          try { await checkContext.close(); } catch { /* Keep original outcome. */ }
        }
      } catch (error) {
        console.warn("Browser-only check failed", checkStage, safeFailureKind(error));
        return reply(diagnostic(checkStage, error), 502);
      } finally {
        if (checkBrowser) {
          try { await checkBrowser.close(); } catch { /* Keep original outcome. */ }
        }
      }
    }
    // Read-only, authenticated configuration check. No account credentials
    // are accepted, and no Browser Run session is started by this endpoint.
    if (pathname === "/validate") {
      if (!body || typeof body !== "object" || Array.isArray(body) ||
          typeof body.url !== "string" || !body.url || body.url.length > 8192 ||
          "email" in body || "password" in body) {
        return failure("Expected login URL only", 400);
      }
      return reply({ allowed: allowedLoginUrl(body.url, env.ALLOWED_LOGIN_HOSTS || "") });
    }
    // Credentials-free inspection of the *public* Peugeot login page.
    // This uses Browser Run but never submits a login or handles a password.
    if (pathname === "/login-page-check") {
      if (!body || typeof body !== "object" || Array.isArray(body) ||
          Object.keys(body).length !== 1 || typeof body.url !== "string" ||
          body.url.length > 8192 || !allowedAuthorizeUrl(body.url, env.ALLOWED_LOGIN_HOSTS || "")) {
        return failure("Expected public OAuth URL only", 400);
      }
      let checkBrowser: Awaited<ReturnType<typeof launch>> | undefined;
      let checkStage: LoginStage = "browser_launch";
      try {
        checkBrowser = await launch(env.BROWSER);
        checkStage = "browser_context";
        const checkContext = await checkBrowser.newContext();
        try {
          checkStage = "browser_page";
          const checkPage = await checkContext.newPage();
          let navigationStatus: number | null = null;
          try {
            checkStage = "login_navigation";
            const navResponse = await checkPage.goto(body.url, { waitUntil: "domcontentloaded", timeout: 30000 });
            navigationStatus = navResponse?.status() ?? null;
            checkStage = "login_email_field";
            // Give the dynamically rendered Gigya email field the full
            // timeout instead of dividing it across hidden template selectors.
            await firstVisible(s => checkPage.locator(s).first(), EMAIL_SELECTORS, 30000);
            checkStage = "login_password_field";
            // Peugeot may expose only the email step initially. Don't hold
            // a credential-free inspection open for a nonexistent next step.
            await firstVisible(s => checkPage.locator(s).first(), PASSWORD_SELECTORS, 10000);
            checkStage = "login_submit";
            await firstVisible(s => checkPage.locator(s).first(), LOGIN_BUTTON_SELECTORS, 10000);
            return reply({ status: "ok", login_form: true });
          } catch (error) {
            // The public page may contain OAuth parameters, but these indicators
            // are strict booleans/counts plus fixed categories. Never serialize
            // body text, redirect URLs, cookies, screenshots, or exception text.
            let publicPage;
            try {
              const signals: PublicPageSignals = await checkPage.evaluate(() => ({
                // These document properties are used for fixed categorization
                // only; neither value is exposed in the API response or logs.
                document_content_type: document.contentType,
                root_element_name: document.documentElement?.localName ?? "",
                body_present: !!document.body,
                gigya_form_present: !!document.querySelector("#gigya-login-form"),
                email_input_present: !!document.querySelector(
                  'input[name="username"],input[name="loginID"],input[name="email"],input[type="email"]',
                ),
                password_input_present: !!document.querySelector('input[type="password"]'),
                submit_control_present: !!document.querySelector('button[type="submit"],input[type="submit"]'),
                cookie_dialog_present: !!document.querySelector(
                  "#onetrust-banner-sdk,#onetrust-consent-sdk,#onetrust-accept-btn-handler",
                ),
                challenge_control_present: !!document.querySelector(
                  'iframe[src*="recaptcha"],iframe[src*="challenges.cloudflare.com"],' +
                  'iframe[src*="hcaptcha"],input[name="cf-turnstile-response"]',
                ),
              }));
              publicPage = sanitizePublicPageReport(
                checkPage.url(), navigationStatus, checkPage.frames().length, signals,
              );
            } catch {
              // Page may be closed or inaccessible; keep only stage/error.
            }
            // Inspect visibility without interacting with login or CAPTCHA.
            // Every frame evaluates locally and returns booleans only. The
            // source HTML, URLs, frame origins and exceptions are discarded.
            let formVisibility;
            try {
              const mainFrame = checkPage.mainFrame();
              const frames = [mainFrame, ...checkPage.frames().filter(frame => frame !== mainFrame)].slice(0, 13);
              const sampled: Array<FrameVisibility | null> = await Promise.all(
                frames.map(async frame => {
                  try {
                    return await frame.evaluate(() => {
                      const isShown = (element: Element | null): boolean => {
                        if (!(element instanceof HTMLElement)) return false;
                        const rect = element.getBoundingClientRect();
                        const css = getComputedStyle(element);
                        return rect.width > 0 && rect.height > 0 &&
                          css.display !== "none" && css.visibility !== "hidden" &&
                          css.visibility !== "collapse" && css.opacity !== "0";
                      };
                      const visible = (selector: string): boolean =>
                        Array.from(document.querySelectorAll(selector))
                          .slice(0, 12).some(isShown);
                      const challengeIframes = Array.from(
                        document.querySelectorAll("iframe"),
                      ).slice(0, 20);
                      const providers = challengeIframes.map(frame =>
                        (frame.getAttribute("src") || "").toLowerCase());
                      const recaptcha = (src: string) =>
                        src.includes("recaptcha") || src.includes("google.com/recaptcha");
                      const hcaptcha = (src: string) => src.includes("hcaptcha");
                      const turnstile = (src: string) => src.includes("challenges.cloudflare.com");
                      return {
                        email_visible: visible(
                          'input[name="username"],input[name="loginID"],input[name="email"],input[type="email"]',
                        ),
                        password_visible: visible('input[name="password"],input[type="password"]'),
                        submit_visible: visible('button[type="submit"],input[type="submit"]'),
                        first_gigya_email_visible: isShown(
                          document.querySelector('#gigya-login-form input[name="username"]'),
                        ),
                        challenge_widget_visible: challengeIframes.some(frame =>
                          isShown(frame) && (recaptcha((frame.getAttribute("src") || "").toLowerCase()) ||
                            hcaptcha((frame.getAttribute("src") || "").toLowerCase()) ||
                            turnstile((frame.getAttribute("src") || "").toLowerCase()))),
                        recaptcha_present: providers.some(recaptcha),
                        hcaptcha_present: providers.some(hcaptcha),
                        turnstile_present: providers.some(turnstile) ||
                          !!document.querySelector('input[name="cf-turnstile-response"]'),
                      };
                    });
                  } catch {
                    return null;
                  }
                }),
              );
              formVisibility = summarizeFrameVisibility(sampled);
            } catch {
              // Keep the existing public-page diagnosis when frames detach.
            }
            console.warn("Peugeot public login-page check failed", checkStage, safeFailureKind(error));
            return reply({ ...diagnostic(checkStage, error), ...(publicPage ? { public_page: publicPage } : {}), ...(formVisibility ? { form_visibility: formVisibility } : {}) }, 502);
          }
        } finally {
          try { await checkContext.close(); } catch { /* Keep original outcome. */ }
        }
      } catch (error) {
        console.warn("Peugeot login-page check failed", checkStage, safeFailureKind(error));
        return reply(diagnostic(checkStage, error), 502);
      } finally {
        if (checkBrowser) {
          try { await checkBrowser.close(); } catch { /* Keep original outcome. */ }
        }
      }
    }
    if (!body || typeof body.url !== "string" || typeof body.email !== "string" ||
        typeof body.password !== "string" || !body.email || !body.password ||
        body.email.length > 320 || body.password.length > 4096 || body.url.length > 8192) {
      return failure("Missing required params", 400);
    }
    let target: URL;
    try {
      target = new URL(body.url);
      if (!allowedAuthorizeUrl(target.href, env.ALLOWED_LOGIN_HOSTS || "")) {
        return failure("OAuth authorize URL not allowed", 400);
      }
    } catch {
      return failure("Invalid login URL", 400);
    }

    // Only authenticated, well-formed login attempts consume the quota.
    // Missing/broken binding fails closed before launching a browser.
    const loginGate = await loginRateLimitStatus(env.LOGIN_RATE_LIMITER);
    if (loginGate !== null) {
      return failure(loginGate === 429 ? "Too many login attempts" : "Login temporarily unavailable", loginGate);
    }

    let browser: Awaited<ReturnType<typeof launch>> | undefined;
    let stage: LoginStage = "browser_launch";
    try {
      browser = await launch(env.BROWSER);
      stage = "browser_context";
      const context = await browser.newContext();
      try {
        stage = "browser_page";
        const page = await context.newPage();
        const navigationTimeout = boundedTimeout(body.timeout_page);
        const selectorTimeout = boundedTimeout(body.timeout_input);
        let resolveCode!: (code: string) => void;
        const captured = new Promise<string>(resolve => { resolveCode = resolve; });
        const observe = (url: string) => {
          const code = extractAuthorizationCode(url);
          if (code) resolveCode(code);
        };
        page.on("request", req => observe(req.url()));
        page.on("requestfailed", req => observe(req.url()));
        stage = "login_navigation";
        await page.goto(target.href, { waitUntil: "domcontentloaded", timeout: navigationTimeout });
        // Followed redirects must never move the top-level login page off the
        // independently configured exact provider host before receiving secrets.
        // The URL is not printed in errors or diagnostic responses.
        if (!allowedLoginUrl(page.url(), env.ALLOWED_LOGIN_HOSTS || "")) {
          throw new Error("Login navigation left trusted provider host");
        }
        stage = "login_email_field";
        const emailField = await firstVisible(s => page.locator(s).first(), EMAIL_SELECTORS, selectorTimeout);
        if (!allowedLoginUrl(page.url(), env.ALLOWED_LOGIN_HOSTS || "")) {
          throw new Error("Login navigation left trusted provider host");
        }
        await emailField.fill(body.email, { timeout: selectorTimeout });
        stage = "login_password_field";
        const passwordField = await firstVisible(s => page.locator(s).first(), PASSWORD_SELECTORS, selectorTimeout);
        if (!allowedLoginUrl(page.url(), env.ALLOWED_LOGIN_HOSTS || "")) {
          throw new Error("Login navigation left trusted provider host");
        }
        await passwordField.fill(body.password, { timeout: selectorTimeout });
        stage = "login_submit";
        const loginButton = await firstVisible(s => page.locator(s).first(), LOGIN_BUTTON_SELECTORS, selectorTimeout);
        await loginButton.click({ timeout: selectorTimeout });
        // Some existing accounts redirect directly to the callback.
        const immediateCode = await codeWithin(captured, 2500);
        if (immediateCode) return reply({ code: immediateCode });

        stage = "consent_submit";
        try {
          const consentButton = await firstVisible(
            s => page.locator(s).first(), CONSENT_BUTTON_SELECTORS, selectorTimeout,
          );
          await consentButton.click({ timeout: selectorTimeout });
        } catch (error) {
          // On some Peugeot consent pages the form is present but its button
          // is not visible to Playwright. Restrict fallback to known OAuth forms.
          const submitted = await page.evaluate(() => {
            const form = document.querySelector<HTMLFormElement>(
              '#cvs_from, #cvs_form, form[action*="/oauth2/authorize"]',
            );
            if (!form) return false;
            form.requestSubmit();
            return true;
          });
          if (!submitted) {
            const code = await codeWithin(captured, 1500);
            if (code) return reply({ code });
            throw error;
          }
        }
        stage = "oauth_callback";
        const code = await codeWithin(captured, navigationTimeout);
        if (!code) throw new Error("Timed out");
        return reply({ code });
      } finally {
        try { await context.close(); } catch { /* Preserve prior result or error. */ }
      }
    } catch (error) {
      console.warn("Worker login failed", stage, safeFailureKind(error));
      return reply(diagnostic(stage, error), 502);
    } finally {
      if (browser) {
        try { await browser.close(); } catch { /* Do not mask the authentication result. */ }
      }
    }
  },
};
