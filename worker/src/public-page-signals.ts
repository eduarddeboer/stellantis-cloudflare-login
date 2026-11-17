/** Sanitized public page indicators; never return page text, URL, DOM or cookies. */
export type PublicPageSignals = {
  body_present: boolean;
  gigya_form_present: boolean;
  email_input_present: boolean;
  password_input_present: boolean;
  submit_control_present: boolean;
  cookie_dialog_present: boolean;
  challenge_control_present: boolean;
  // Used only for fixed classification, never returned verbatim.
  document_content_type?: string;
  root_element_name?: string;
};

export type PublicPageReport = Omit<PublicPageSignals, "document_content_type" | "root_element_name"> & {
  page_category: "peugeot_entry" | "peugeot_identity" | "peugeot_site" | "other" | "unknown";
  navigation_status: number | null;
  iframe_count: number;
  document_kind: "html" | "xrds_discovery" | "xml_other" | "other" | "unknown";
};

/** Detect discovery XML without retaining any document content. */
export function classifyDocumentKind(
  contentType: unknown,
  rootElement: unknown,
): PublicPageReport["document_kind"] {
  const mime = typeof contentType === "string" ? contentType.split(";")[0].trim().toLowerCase() : "";
  const root = typeof rootElement === "string" ? rootElement.toLowerCase() : "";
  if (root === "xrds" && (mime.includes("xml") || !mime)) return "xrds_discovery";
  if ((mime === "text/html" || mime === "application/xhtml+xml") && (root === "html" || !root)) return "html";
  if (mime.includes("xml") || root === "xrds") return "xml_other";
  if (mime || root) return "other";
  return "unknown";
}

export function sanitizePublicPageReport(
  url: string,
  navigationStatus: number | null,
  frames: number,
  signals: PublicPageSignals,
): PublicPageReport {
  let host = "";
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch { /* Do not expose unparseable URLs. */ }
  const page_category =
    host === "idpcvs.peugeot.com" ? "peugeot_entry" :
    host === "id-dcr.peugeot.com" ? "peugeot_identity" :
    host === "my.peugeot.com" ? "peugeot_site" :
    host ? "other" : "unknown";
  return {
    page_category,
    document_kind: classifyDocumentKind(signals.document_content_type, signals.root_element_name),
    navigation_status:
      Number.isInteger(navigationStatus) &&
      navigationStatus !== null && navigationStatus >= 100 && navigationStatus <= 599
        ? navigationStatus : null,
    iframe_count: Number.isInteger(frames) ? Math.min(12, Math.max(0, frames - 1)) : 0,
    body_present: signals.body_present === true,
    gigya_form_present: signals.gigya_form_present === true,
    email_input_present: signals.email_input_present === true,
    password_input_present: signals.password_input_present === true,
    submit_control_present: signals.submit_control_present === true,
    cookie_dialog_present: signals.cookie_dialog_present === true,
    challenge_control_present: signals.challenge_control_present === true,
  };
}
