// Shared types for API data. Conforms to docs/api-contract.md.

export type DifficultyLevel = "easy" | "medium" | "hard";

export interface Lecture {
  id: number | string;
  title: string;
  classroom_id: number;
  classroom: string;
  published_at: string; // ISO date string
  question_count: number;

  // Optional legacy aliases for backwards compatibility
  description?: string;
  durationMinutes?: number;
  publishedAt?: string;
}

export interface ClassLectureStat {
  id: number;
  title: string;
  published_at: string; // ISO date string
  question_count: number;
  best_score: number;
  correct_count: number;
  is_new: boolean;
}

export interface ClassSummary {
  id: number;
  name: string;
  course_code: string;
  professor: { id: number; name: string } | null;
  quiz_count: number;
  new_quiz_count: number;
}

export interface ClassStats {
  classroom_id: number;
  classroom: string;
  total_points: number;
  rank: number;
  points_to_next_rank: number;
  quizzes_played: number;
  quizzes_total: number;
  day_streak: number;
  answer_streak: number;
  up_next: ClassLectureStat | null;
  lectures: ClassLectureStat[];
}

export interface QuizQuestion {
  id: number | string;
  prompt: string;
  choices: string[];
  difficulty?: DifficultyLevel;
}

export interface Quiz {
  id?: number | string;
  lecture_id: number | string;
  title: string;
  questions: QuizQuestion[];
  // For the logged-in student's open attempt. Empty and 0 when there is none.
  // Optional only because the offline sample data lacks them; the API always sends them (see docs/api-contract.md).
  answered_question_ids?: number[];
  total_points?: number;

  // Optional legacy alias for backwards compatibility
  lectureId?: number | string;
}

export interface AnswerRequest {
  question_id: number;
  chosen_index: number | null; // 0-3, or null when time ran out
}

export interface QuestionStart {
  question_id: number;
  started_at: string;
}

export interface AnswerResult {
  is_correct: boolean;
  points_awarded: number;
  total_points: number;
  correct_index: number;
}

export interface HealthResponse {
  status: string;
  service: string;
}

// Every API function returns this shape instead of throwing, so calling
// components can just check `error` rather than wrapping calls in try/catch.
export interface ApiResult<T> {
  data: T | null;
  error: string | null;
  /** HTTP status of a non-OK response. Not set for network errors. */
  status?: number;
}

// One row of GET /api/classes/{id}/leaderboard/
export interface LeaderboardEntry {
  rank: number;
  display_name: string;
  points: number;
  is_current_user: boolean;
}

// GET /api/professor/classes/
export interface ProfessorClass {
  id: number;
  name: string;
  access_code: string;
  student_count: number;
  lecture_count: number;
}

// POST /api/classes/ response
export interface CreateClassResponse {
  id: number;
  name: string;
  access_code: string;
}

