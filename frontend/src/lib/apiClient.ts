import type {
  AnswerRequest,
  AnswerResult,
  ApiResult,
  AuthResponse,
  ClassStats,
  ClassSummary,
  ClassRosterStudent,
  CreateClassResponse,
  HealthResponse,
  LeaderboardEntry,
  Lecture,
  LectureProcessingStatus,
  LoginPayload,
  ProfessorClass,
  ProfessorLecture,
  ProfessorQuestion,
  ProfessorQuestionInput,
  PartReview,
  PublishLectureResponse,
  Quiz,
  QuestionStart,
  RegisterPayload,
  UnpublishLectureResponse,
  User,
  ClassResults,
} from "../types/api";
import sampleLectures from "../data/lectures.sample.json" with { type: "json" };

export type {
  AnswerRequest,
  AnswerResult,
  ApiResult,
  AuthResponse,
  ClassStats,
  ClassSummary,
  CreateClassResponse,
  DifficultyLevel,
  HealthResponse,
  LeaderboardEntry,
  Lecture,
  LoginPayload,
  ProfessorClass,
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
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      sessionStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Ignore storage errors
  }
}

export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User | null): void {
  try {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
      sessionStorage.setItem(USER_KEY, JSON.stringify(user));
      if (user.role) {
        localStorage.setItem("coursepulse_role", user.role);
        sessionStorage.setItem("coursepulse_role", user.role);
      } else {
        localStorage.removeItem("coursepulse_role");
        sessionStorage.removeItem("coursepulse_role");
      }
    } else {
      localStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(USER_KEY);
      localStorage.removeItem("coursepulse_role");
      sessionStorage.removeItem("coursepulse_role");
    }
  } catch {
    // Ignore storage errors
  }
}

export function clearSession(): void {
  setStoredToken(null);
  setStoredUser(null);
  try {
    sessionStorage.removeItem("coursepulse_role");
    localStorage.removeItem("coursepulse_role");
  } catch {
    // Ignore storage errors
  }
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

function fieldErrorMessages(body: Record<string, unknown>): {
  messages: string[];
  fields: Record<string, string[]>;
} {
  const messages: string[] = [];
  const fields: Record<string, string[]> = {};
  for (const [key, val] of Object.entries(body)) {
    const parts: string[] = [];
    if (Array.isArray(val)) {
      for (const item of val) {
        if (typeof item === "string") parts.push(item);
      }
    } else if (typeof val === "string") {
      parts.push(val);
    }
    if (parts.length === 0) continue;
    fields[key] = parts;
    messages.push(parts.join(" "));
  }
  return { messages, fields };
}

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
      let fields: Record<string, string[]> | undefined;

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
            const parsed = fieldErrorMessages(errorJson);
            if (parsed.messages.length > 0) {
              errorMessage = parsed.messages.join(" ");
              fields = parsed.fields;
            }
          }
        }
      } catch {
        // Non-JSON response, keep the status-based error message
      }

      // Server faults carry no message a student can act on.
      if (response.status >= 500) {
        errorMessage = "The server had a problem. Try again shortly.";
        fields = undefined;
      }

      return {
        data: null,
        error: errorMessage,
        status: response.status,
        ...(fields ? { fields } : {}),
      };
    }

    if (response.status === 204) {
      return { data: null as T, error: null, status: response.status };
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
 * There is no sample-data fallback; errors and status codes pass through.
 */
export async function getQuiz(id: string | number, part?: number): Promise<ApiResult<Quiz>> {
  const query = part !== undefined ? `?part=${encodeURIComponent(String(part))}` : "";
  return request<Quiz>(`/lectures/${encodeURIComponent(String(id).trim())}/quiz/${query}`);
}

/**
 * Submit one answer; the server grades it.
 * Matches API contract: POST /api/lectures/{id}/answers/
 * Requires a logged-in student. There is no sample-data fallback.
 */
export async function postAnswer(
  lectureId: string | number,
  body: AnswerRequest
): Promise<ApiResult<AnswerResult>> {
  const token = sessionStorage.getItem("coursepulse_token");
  return request<AnswerResult>(`/lectures/${encodeURIComponent(String(lectureId).trim())}/answers/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
}

/**
 * Tell the server a question was shown, so it can time the answer.
 * Matches API contract: POST /api/lectures/{id}/questions/{question_id}/start/
 * Requires a logged-in student. Safe to repeat: the server keeps the first start time.
 */
export async function startQuestion(
  lectureId: string | number,
  questionId: number,
  part?: number
): Promise<ApiResult<QuestionStart>> {
  const token = sessionStorage.getItem("coursepulse_token");
  const query = part !== undefined ? `?part=${encodeURIComponent(String(part))}` : "";
  return request<QuestionStart>(
    `/lectures/${encodeURIComponent(String(lectureId).trim())}/questions/${questionId}/start/${query}`,
    {
      method: "POST",
      headers: token ? { Authorization: `Token ${token}` } : {},
    }
  );
}

/** The logged-in student's most recent completed play of one part. */
export async function getPartReview(
  lectureId: string | number,
  part: number
): Promise<ApiResult<PartReview>> {
  const token = sessionStorage.getItem("coursepulse_token");
  return request(
    `/lectures/${encodeURIComponent(String(lectureId).trim())}/parts/${encodeURIComponent(String(part))}/review/`,
    { headers: token ? { Authorization: `Token ${token}` } : {} }
  );
}

/** Auth header for the logged-in student, or an empty object when logged out. */
function authHeaders(): Record<string, string> {
  const token = sessionStorage.getItem("coursepulse_token");
  return token ? { Authorization: `Token ${token}` } : {};
}

/**
 * Reads the active user's role from session storage.
 */
export function getUserRole(): string | null {
  try {
    const rawUser =
      sessionStorage.getItem(USER_KEY) ||
      localStorage.getItem(USER_KEY);
    if (rawUser) {
      const parsed = JSON.parse(rawUser) as { role?: string };
      if (parsed?.role) return parsed.role;
    }
  } catch {
    // Ignore JSON parse error
  }

  const directRole =
    sessionStorage.getItem("coursepulse_role") ||
    localStorage.getItem("coursepulse_role");
  if (directRole) return directRole;

  return null;
}

/**
 * Returns true if the logged-in user is a professor.
 */
export function isProfessor(): boolean {
  return getUserRole() === "professor";
}

/**
 * Resolves the primary classes route based on the logged-in user's role:
 * returns "/professor" for professors and "/hub" for students.
 */
export function getClassesRoute(): string {
  return isProfessor() ? "/professor" : "/hub";
}





/**
 * Fetch the logged-in student's classes.
 * Matches API contract: GET /api/classes/
 */
export async function getClasses(): Promise<ApiResult<ClassSummary[]>> {
  return request<ClassSummary[]>("/classes/", { headers: authHeaders() });
}

/**
 * Fetch the logged-in student's stats for one class.
 * Matches API contract: GET /api/classes/{id}/stats/
 */
export async function getClassStats(classId: number | string): Promise<ApiResult<ClassStats>> {
  return request<ClassStats>(`/classes/${encodeURIComponent(String(classId).trim())}/stats/`, {
    headers: authHeaders(),
  });
}

/**
 * Day streak of the student's first class.
 * Never throws: returns 0 when logged out, when a request fails,
 * or when the student has no classes.
 */
export async function getStudentDayStreak(): Promise<number> {
  try {
    if (!sessionStorage.getItem("coursepulse_token")) return 0;

    const classes = await getClasses();
    const first = classes.data?.[0];
    if (!first) return 0;

    const stats = await getClassStats(first.id);
    return stats.data?.day_streak ?? 0;
  } catch {
    return 0;
  }
}

/**
 * Fetch the ranked students of one class.
 * Matches API contract: GET /api/classes/{id}/leaderboard/
 * Requires a logged-in student. There is no sample-data fallback.
 */
export async function getLeaderboard(
  classId: number | string,
  signal?: AbortSignal
): Promise<ApiResult<LeaderboardEntry[]>> {
  const token = sessionStorage.getItem("coursepulse_token");
  return request<LeaderboardEntry[]>(`/classes/${encodeURIComponent(String(classId).trim())}/leaderboard/`, {
    headers: token ? { Authorization: `Token ${token}` } : {},
    signal,
  });
}

/**
 * Liveness health check.
 * Matches API contract: GET /api/health/
 */
export async function getHealth(): Promise<ApiResult<HealthResponse>> {
  return request<HealthResponse>("/health/");
}

/**
 * Fetch all classes owned by the logged-in professor.
 * Matches API contract: GET /api/professor/classes/
 * Requires a professor account and token authentication.
 */
export async function getProfessorClasses(): Promise<ApiResult<ProfessorClass[]>> {
  return request<ProfessorClass[]>("/professor/classes/", {
    headers: authHeaders(),
  });
}

export async function getClassRoster(
  classId: number | string
): Promise<ApiResult<ClassRosterStudent[]>> {
  return request<ClassRosterStudent[]>(
    `/classes/${encodeURIComponent(String(classId))}/roster/`
  );
}

export async function getProfessorClassLectures(
  classId: number | string
): Promise<ApiResult<ProfessorLecture[]>> {
  return request<ProfessorLecture[]>(
    `/professor/classes/${encodeURIComponent(String(classId))}/lectures/`
  );
}

export async function getLectureStatus(
  lectureId: number | string
): Promise<ApiResult<LectureProcessingStatus>> {
  return request<LectureProcessingStatus>(
    `/lectures/${encodeURIComponent(String(lectureId))}/status/`
  );
}

export async function retryLecture(
  lectureId: number | string
): Promise<ApiResult<Pick<LectureProcessingStatus, "id" | "status" | "error_message">>> {
  return request<Pick<LectureProcessingStatus, "id" | "status" | "error_message">>(
    `/lectures/${encodeURIComponent(String(lectureId))}/retry/`,
    { method: "POST" }
  );
}

export async function getLectureQuestions(
  lectureId: number | string
): Promise<ApiResult<ProfessorQuestion[]>> {
  return request<ProfessorQuestion[]>(
    `/lectures/${encodeURIComponent(String(lectureId))}/questions/`
  );
}

export async function createLectureQuestion(
  lectureId: number | string,
  body: ProfessorQuestionInput
): Promise<ApiResult<ProfessorQuestion>> {
  return request<ProfessorQuestion>(
    `/lectures/${encodeURIComponent(String(lectureId))}/questions/`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function updateLectureQuestion(
  lectureId: number | string,
  questionId: number | string,
  body: Partial<ProfessorQuestionInput>
): Promise<ApiResult<ProfessorQuestion>> {
  return request<ProfessorQuestion>(
    `/lectures/${encodeURIComponent(String(lectureId))}/questions/${encodeURIComponent(String(questionId))}/`,
    { method: "PATCH", body: JSON.stringify(body) }
  );
}

export async function deleteLectureQuestion(
  lectureId: number | string,
  questionId: number | string
): Promise<ApiResult<null>> {
  return request<null>(
    `/lectures/${encodeURIComponent(String(lectureId))}/questions/${encodeURIComponent(String(questionId))}/`,
    { method: "DELETE" }
  );
}

export async function publishLecture(
  lectureId: number | string
): Promise<ApiResult<PublishLectureResponse>> {
  return request<PublishLectureResponse>(
    `/lectures/${encodeURIComponent(String(lectureId))}/publish/`,
    { method: "POST" }
  );
}

export async function unpublishLecture(
  lectureId: number | string
): Promise<ApiResult<UnpublishLectureResponse>> {
  return request<UnpublishLectureResponse>(
    `/lectures/${encodeURIComponent(String(lectureId))}/unpublish/`,
    { method: "POST" }
  );
}

/**
 * Creates a new class owned by the logged-in professor.
 * Matches API contract: POST /api/classes/
 * Requires a professor account and token authentication.
 */
export async function createClass(name: string): Promise<ApiResult<CreateClassResponse>> {
  const token = getStoredToken();
  return request<CreateClassResponse>("/classes/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    body: JSON.stringify({ name }),
  });
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
      username: payload.username.trim(),
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

export async function getClassResults(
  classId: number | string,
  signal?: AbortSignal
): Promise<ApiResult<ClassResults>> {
  return request<ClassResults>(
    `/classes/${encodeURIComponent(String(classId))}/results/`,
    { signal }
  );
}