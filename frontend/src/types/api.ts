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

export interface LecturePartStat {
  part: number;
  question_count: number;
  completed: boolean;
  best_score: number;
  correct_count: number;
  in_progress: boolean;
}

export interface ClassLectureStat {
  id: number;
  title: string;
  published_at: string; // ISO date string
  question_count: number;
  part_count?: number;
  parts?: LecturePartStat[];
  best_score: number;
  correct_count: number;
  is_new: boolean;
  is_complete?: boolean;
}

export interface ClassSummary {
  id: number;
  name: string;
  course_code: string;
  professor: { id: number; name: string; username?: string } | null;
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
  // Null on the unscoped quiz. Set when the quiz was loaded with ?part=.
  part?: number | null;
  part_count?: number;

  // Optional legacy alias for backwards compatibility
  lectureId?: number | string;
}

export interface AnswerRequest {
  question_id: number;
  chosen_index: number | null; // 0-3 in the order the quiz returned, or null when time ran out
  // 1-based part. Send it whenever the quiz was loaded with ?part=.
  part?: number;
}

export interface PartReviewQuestion {
  id: number;
  prompt: string;
  your_answer: string | null;
  correct_answer: string;
  is_correct: boolean;
  points_awarded: number;
}

export interface PartReview {
  lecture_id: number;
  title: string;
  part: number;
  part_count: number;
  question_count: number;
  total_points: number;
  correct_count: number;
  questions: PartReviewQuestion[];
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

// User and Auth interfaces conforming to docs/api-contract.md
export type UserRole = "student" | "professor";

export interface User {
  id: number;
  email: string;
  username: string;
  role: UserRole | null;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface RegisterPayload {
  email: string;
  username: string;
  password: string;
  role?: UserRole;
}

export interface LoginPayload {
  email: string;
  password: string;
}

// Every API function returns this shape instead of throwing, so calling
// components can just check `error` rather than wrapping calls in try/catch.
export interface ApiResult<T> {
  data: T | null;
  error: string | null;
  /** HTTP status of a non-OK response. Also set for 204. Not set for network errors. */
  status?: number;
  /** Field errors from a JSON body, keyed by the field name. */
  fields?: Record<string, string[]>;
}

// One row of GET /api/classes/{id}/leaderboard/
export interface LeaderboardEntry {
  rank: number;
  display_name: string;
  username?: string;
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

export interface ClassResultLectureScore {
  lecture_id: number;
  played: boolean;
  score: number | null;
  correct_count: number | null;
  parts_completed?: number;
  parts_total?: number;
}

export interface ClassResultStudent {
  student_id: number;
  name: string;
  username?: string | null;
  total_points: number;
  quizzes_played: number;
  lectures: ClassResultLectureScore[];
}

export interface ClassResultQuestion {
  question_id: number;
  prompt: string;
  answer_count: number;
  correct_count: number;
  accuracy_percent: number | null;
}

export interface ClassResultLecture {
  lecture_id: number;
  title: string;
  questions: ClassResultQuestion[];
}

export interface ClassResults {
  classroom_id: number;
  classroom: string;
  students: ClassResultStudent[];
  lectures: ClassResultLecture[];
}

export interface ClassRosterStudent {
  name: string;
  username?: string | null;
  joined_at: string;
}

export interface LectureProcessingStatus {
  id: number;
  status: "pending" | "processing" | "ready" | "failed";
  progress_message: string;
  error_message: string;
  notice?: string;
}

export interface ProfessorLecture {
  id: number;
  title: string;
  status: LectureProcessingStatus["status"] | "published";
  published_at: string | null;
  uploaded_at: string;
  question_count: number;
  students_played: number;
  class_average: number | null;
}

// GET/POST/PATCH /api/lectures/{id}/questions/ for the owning professor.
// Students never receive this shape. correct_index stays off the student quiz.
// The stored generation record is never part of this response.
export interface ProfessorQuestion {
  id: number;
  prompt: string;
  choices: string[];
  correct_index: number;
  difficulty: DifficultyLevel;
  position: number;
}

export interface ProfessorQuestionInput {
  prompt: string;
  choices: string[];
  correct_index: number;
  difficulty: DifficultyLevel;
}

export interface PublishLectureResponse {
  id: number;
  published_at: string;
  message: string;
}

export interface UnpublishLectureResponse {
  id: number;
  published_at: string | null;
}
