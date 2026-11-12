import type { AnswerRequest, AnswerResult, ApiResult, ClassStats, ClassSummary, CreateClassResponse, HealthResponse, LeaderboardEntry, Lecture, ProfessorClass, Quiz, QuestionStart } from "../types/api";
import sampleLectures from "../data/lectures.sample.json" with { type: "json" };
import sampleQuizzes from "../data/quizzes.sample.json" with { type: "json" };

export type { AnswerRequest, AnswerResult, ApiResult, ClassStats, ClassSummary, CreateClassResponse, HealthResponse, LeaderboardEntry, Lecture, ProfessorClass, Quiz, QuizQuestion, DifficultyLevel } from "../types/api";

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
 * Never throws — callers can safely inspect `data` and `error`.
 */
export async function request<T>(
  path: string,
  options?: RequestInit
): Promise<ApiResult<T>> {
  try {
    const formattedPath = path.startsWith("/") ? path : `/${path}`;
    const url = `${API_BASE_URL}${formattedPath}`;
    const response = await fetch(url, options);

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
          }
        }
      } catch {
        // Non-JSON response, keep the status-based error message
      }

      // Server faults carry no message a student can act on.
      if (response.status >= 500) {
        errorMessage = "The server had a problem. Try again shortly.";
      }

      return { data: null, error: errorMessage, status: response.status };
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

  // Send the token (when logged in) so the server can return the student's progress
  const token = sessionStorage.getItem("coursepulse_token");
  const authOptions: RequestInit | undefined = token
    ? { headers: { Authorization: `Token ${token}` } }
    : undefined;

  // Primary contract endpoint: GET /api/lectures/{id}/quiz/
  let result = await request<Quiz>(`/lectures/${encodeURIComponent(queryId)}/quiz/`, authOptions);

  // Secondary fallback for legacy/alternative route /quizzes/{id}/ if contract endpoint 404s
  if (result.error && !result.error.includes("Could not reach API")) {
    const altResult = await request<Quiz>(`/quizzes/${encodeURIComponent(queryId)}/`, authOptions);
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
  questionId: number
): Promise<ApiResult<QuestionStart>> {
  const token = sessionStorage.getItem("coursepulse_token");
  return request<QuestionStart>(
    `/lectures/${encodeURIComponent(String(lectureId).trim())}/questions/${questionId}/start/`,
    {
      method: "POST",
      headers: token ? { Authorization: `Token ${token}` } : {},
    }
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
  const directRole = sessionStorage.getItem("coursepulse_role");
  if (directRole) return directRole;

  try {
    const rawUser = sessionStorage.getItem("coursepulse_user");
    if (rawUser) {
      const parsed = JSON.parse(rawUser) as { role?: string };
      if (parsed?.role) return parsed.role;
    }
  } catch {
    // Ignore JSON parse error
  }

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

/**
 * Creates a new class owned by the logged-in professor.
 * Matches API contract: POST /api/classes/
 * Requires a professor account and token authentication.
 */
export async function createClass(name: string): Promise<ApiResult<CreateClassResponse>> {
  const token = sessionStorage.getItem("coursepulse_token");
  return request<CreateClassResponse>("/classes/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    body: JSON.stringify({ name }),
  });
}

