// Shared types for API data. Conforms to docs/api-contract.md.

export type DifficultyLevel = "easy" | "medium" | "hard";

export interface Lecture {
  id: number | string;
  title: string;
  classroom: string;
  published_at: string; // ISO date string
  question_count: number;

  // Optional legacy aliases for backwards compatibility
  description?: string;
  durationMinutes?: number;
  publishedAt?: string;
}

export interface QuizQuestion {
  id: number | string;
  prompt: string;
  choices: string[];
  correct_index: number;
  difficulty?: DifficultyLevel;

  // Optional legacy alias for backwards compatibility
  correctChoiceIndex?: number;
}

export interface Quiz {
  id?: number | string;
  lecture_id: number | string;
  title: string;
  questions: QuizQuestion[];

  // Optional legacy alias for backwards compatibility
  lectureId?: number | string;
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
}
