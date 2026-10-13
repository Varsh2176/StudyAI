const TOKEN_KEY = "studyai_access_token";
const EMAIL_KEY = "studyai_auth_email";
const NAME_KEY = "studyai_auth_name";
/** Legacy key kept in sync so existing pages keep reading the signed-in email. */
const LEGACY_EMAIL_KEY = "student_email";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function getAuthEmail() {
  return localStorage.getItem(EMAIL_KEY) || localStorage.getItem(LEGACY_EMAIL_KEY) || "";
}

export function getAuthName() {
  return localStorage.getItem(NAME_KEY) || "";
}

export function isAuthenticated() {
  return Boolean(getAccessToken() && getAuthEmail());
}

export function persistAuthSession({ accessToken, email, name }) {
  if (accessToken) localStorage.setItem(TOKEN_KEY, accessToken);
  if (email) {
    localStorage.setItem(EMAIL_KEY, email);
    localStorage.setItem(LEGACY_EMAIL_KEY, email);
  }
  if (name) localStorage.setItem(NAME_KEY, name);
  window.dispatchEvent(new Event("studyai-identity-changed"));
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EMAIL_KEY);
  localStorage.removeItem(NAME_KEY);
  localStorage.removeItem(LEGACY_EMAIL_KEY);
  window.dispatchEvent(new Event("studyai-identity-changed"));
}
