import type {
  ApiResult,
  AuthResponse,
  HealthResponse,
  Lecture,
  LoginPayload,
  Quiz,
  RegisterPayload,
  User,
} from "../types/api";
import sampleLectures from "../data/lectures.sample.json" with { type: "json" };
import sampleQuizzes from "../data/quizzes.sample.json" with { type: "json" };

export type {
  ApiResult,
  AuthResponse,
  DifficultyLevel,
  HealthResponse,
  Lecture,
  LoginPayload,
  Quiz,
  QuizQuestion,
  RegisterPayload,
  User,
  UserRole,
} from "../types/api";

const TOKEN_KEY = "coursepulse_token";
const USER_KEY = "coursepulse_user";

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Ignore localStorage errors
  }
}

export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User | null): void {
  try {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  } catch {
    // Ignore localStorage errors
  }
}

export function clearSession(): void {
  setStoredToken(null);
  setStoredUser(null);
}

/**
 * Resolves the API base URL from Vite or runtime environment variables.
 * Checks VITE_API_URL, then VITE_API_BASE_URL, and falls back to
 * http://localhost:8000/api for local Django development.
 */
function resolveApiBaseUrl(): string {
  const metaEnv =
    typeof import.meta !== "undefined" && import.meta.env
      ? (import.meta.env.VITE_API_URL as string | undefined) ||
        (import.meta.env.VITE_API_BASE_URL as string | undefined)
      : undefined;

  const nodeEnv = (
    globalThis as unknown as {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process?.env;

  const raw = (
    metaEnv ||
    nodeEnv?.VITE_API_URL ||
    nodeEnv?.VITE_API_BASE_URL ||
    "http://localhost:8000/api"
  ).trim();

  const trimmed = raw.replace(/\/+$/, "");

  // Ensure base URL points to the DRF /api prefix
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
}

export const API_BASE_URL: string = resolveApiBaseUrl();

/**
 * Wraps fetch with consistent JSON parsing and error handling.
 * Automatically injects the Authorization token from session if available.
 * Never throws — callers can safely inspect `data` and `error`.
 */
export async function request<T>(
  path: string,
  options?: RequestInit
): Promise<ApiResult<T>> {
  try {
    const formattedPath = path.startsWith("/") ? path : `/${path}`;
    const url = `${API_BASE_URL}${formattedPath}`;

    const headers = new Headers(options?.headers || {});

    // Automatically inject Authorization header if a session token is stored
    const token = getStoredToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Token ${token}`);
    }

    if (!headers.has("Content-Type") && options?.body && typeof options.body === "string") {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorMessage = `Request failed (${response.status} ${response.statusText || "Error"})`;

      try {
        const errorJson = (await response.json()) as Record<string, unknown>;
        if (errorJson && typeof errorJson === "object") {
          if (typeof errorJson.detail === "string") {
            errorMessage = errorJson.detail;
          } else if (typeof errorJson.message === "string") {
            errorMessage = errorJson.message;
          } else if (typeof errorJson.error === "string") {
            errorMessage = errorJson.error;
          } else {
            // Handle field-level DRF errors (e.g. { email: ["..."], password: ["..."] })
            const messages: string[] = [];
            for (const [_, val] of Object.entries(errorJson)) {
              if (Array.isArray(val)) {
                messages.push(val.join(" "));
              } else if (typeof val === "string") {
                messages.push(val);
              }
            }
            if (messages.length > 0) {
              errorMessage = messages.join(" ");
            }
          }
        }
      } catch {
        // Non-JSON response, keep the status-based error message
      }

      return { data: null, error: errorMessage };
    }

    const data = (await response.json()) as T;
    return { data, error: null };
  } catch (err) {
    // Network errors, DNS failures, connection refused, backend offline, etc.
    const message = err instanceof Error ? err.message : "Unknown network error";
    return { data: null, error: `Could not reach API: ${message}` };
  }
}

/**
 * Fetch all published lectures.
 * Matches API contract: GET /api/lectures/
 * Falls back to local sample data until the backend endpoint is available.
 */
export async function getLectures(): Promise<ApiResult<Lecture[]>> {
  const result = await request<Lecture[]>("/lectures/");

  if (result.error) {
    // Backend endpoint is not available or returned an error; fall back to sample data
    return { data: sampleLectures as Lecture[], error: null };
  }

  return result;
}

/**
 * Fetch the full quiz for a given lecture id.
 * Matches API contract: GET /api/lectures/{id}/quiz/
 * Falls back to local sample data until the backend endpoint is available.
 */
export async function getQuiz(id: string | number): Promise<ApiResult<Quiz>> {
  const queryId = String(id).trim();

  // Primary contract endpoint: GET /api/lectures/{id}/quiz/
  let result = await request<Quiz>(`/lectures/${encodeURIComponent(queryId)}/quiz/`);

  // Secondary fallback for legacy/alternative route /quizzes/{id}/ if contract endpoint 404s
  if (result.error && !result.error.includes("Could not reach API")) {
    const altResult = await request<Quiz>(`/quizzes/${encodeURIComponent(queryId)}/`);
    if (!altResult.error) {
      result = altResult;
    }
  }

  // If backend endpoint is unavailable or returned an error, fallback to local sample data
  if (result.error) {
    const quizzesRecord = sampleQuizzes as Record<string, Quiz>;
    const fallback =
      quizzesRecord[queryId] ??
      Object.values(quizzesRecord).find(
        (q) =>
          String(q.id) === queryId ||
          String(q.lecture_id) === queryId ||
          String(q.lectureId) === queryId
      );

    if (fallback) {
      return { data: fallback, error: null };
    }

    const isNetworkError = result.error?.startsWith("Could not reach API");
    const isStatusError = result.error?.startsWith("Request failed");

    return {
      data: null,
      error:
        result.error && !isNetworkError && !isStatusError
          ? result.error
          : `Quiz for lecture "${queryId}" not found in API or sample data.`,
    };
  }

  return result;
}

/**
 * Liveness health check.
 * Matches API contract: GET /api/health/
 */
export async function getHealth(): Promise<ApiResult<HealthResponse>> {
  return request<HealthResponse>("/health/");
}

/**
 * Log in using email and password.
 * Matches API contract: POST /api/auth/login/
 * Automatically persists session token and user info on success.
 */
export async function login(payload: LoginPayload): Promise<ApiResult<AuthResponse>> {
  const result = await request<AuthResponse>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({
      email: payload.email.trim().toLowerCase(),
      password: payload.password,
    }),
  });

  if (result.data) {
    setStoredToken(result.data.token);
    setStoredUser(result.data.user);
  }

  return result;
}

/**
 * Register a new user account.
 * Matches API contract: POST /api/auth/register/
 * Automatically persists session token and user info on success.
 */
export async function register(payload: RegisterPayload): Promise<ApiResult<AuthResponse>> {
  const result = await request<AuthResponse>("/auth/register/", {
    method: "POST",
    body: JSON.stringify({
      email: payload.email.trim().toLowerCase(),
      password: payload.password,
      role: payload.role || "student",
    }),
  });

  if (result.data) {
    setStoredToken(result.data.token);
    setStoredUser(result.data.user);
  }

  return result;
}

/**
 * Get currently authenticated user details.
 * Matches API contract: GET /api/auth/me/
 */
export async function getCurrentUser(): Promise<ApiResult<User>> {
  const result = await request<User>("/auth/me/");

  if (result.data) {
    setStoredUser(result.data);
  } else if (
    result.error &&
    (result.error.includes("401") ||
      result.error.includes("Invalid token") ||
      result.error.includes("credentials were not provided"))
  ) {
    clearSession();
  }

  return result;
}

/**
 * Log out and clear session tokens.
 */
export function logout(): void {
  clearSession();
}
