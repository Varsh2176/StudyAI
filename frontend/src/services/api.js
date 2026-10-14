import axios from "axios";
import { clearAuthSession, getAccessToken } from "../auth/authStorage";

/**
 * Resolve the backend base URL from Vite env.
 * - Development: falls back to http://127.0.0.1:8000 when unset.
 * - Production: uses VITE_API_BASE_URL when set; otherwise same-origin ("")
 *   so the bundle never hardcodes a developer localhost address.
 * Never put secrets in VITE_* variables (they are embedded in the client bundle).
 */
export function resolveApiBaseUrl() {
  const raw = import.meta.env.VITE_API_BASE_URL;
  const configured = raw != null && String(raw).trim() !== "";

  if (!configured) {
    if (import.meta.env.DEV) {
      // Local-dev fallback (stripped from production builds by Vite).
      return "http://127.0.0.1:8000";
    }
    return "/api";
  }

  const trimmed = String(raw).trim().replace(/\/+$/, "");
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
    return trimmed;
  } catch {
    console.error(
      `[StudyWise] Invalid VITE_API_BASE_URL=${JSON.stringify(String(raw))}. ` +
        "Expected an absolute http(s) URL."
    );
    if (import.meta.env.DEV) {
      return "http://127.0.0.1:8000";
    }
    return "";
  }
}

export const API_BASE_URL = resolveApiBaseUrl();

export function getApiUnreachableMessage() {
  const target = API_BASE_URL || "the same origin as this page";
  return (
    `Cannot reach the API at ${target}. ` +
    "Confirm the backend is running and that VITE_API_BASE_URL matches the deployed API URL."
  );
}

const API = axios.create({
  baseURL: API_BASE_URL,
});

API.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

API.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url = String(error?.config?.url || "");
    const isAuthEndpoint =
      url.includes("/auth/login") ||
      url.includes("/auth/register") ||
      url.includes("/auth/me");
    if (status === 401 && !isAuthEndpoint) {
      clearAuthSession();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.assign(`/login?next=${next}`);
      }
    }
    return Promise.reject(error);
  }
);

export default API;
