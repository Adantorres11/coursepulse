import type { ClassResultLectureScore } from "../types/api";

export function formatUploadDate(iso: string | null | undefined): string {
  if (!iso) return "Upload date unavailable";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Upload date unavailable";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatQuestionCount(count: number): string {
  return count === 1 ? "1 question" : `${count} questions`;
}

export function formatPlayedCount(count: number): string {
  return count === 1 ? "1 student played" : `${count} students played`;
}

export function formatClassAverage(average: number | null | undefined): string {
  if (average === null || average === undefined || Number.isNaN(average)) {
    return "No average yet";
  }
  const rounded = Math.round(average * 10) / 10;
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  return `Avg ${text}`;
}

export function formatLectureMeta(lecture: {
  uploaded_at?: string | null;
  question_count?: number;
  students_played?: number;
  class_average?: number | null;
}): string {
  return [
    formatUploadDate(lecture.uploaded_at),
    formatQuestionCount(lecture.question_count ?? 0),
    formatPlayedCount(lecture.students_played ?? 0),
    formatClassAverage(lecture.class_average),
  ].join(" · ");
}

export function formatLectureScore(row: Pick<
  ClassResultLectureScore,
  "played" | "score" | "correct_count" | "parts_completed" | "parts_total"
>): string {
  if (!row.played || row.score === null || row.correct_count === null) {
    return "Not played";
  }
  const correct = row.correct_count === 1
    ? "1 correct"
    : `${row.correct_count} correct`;
  const score = `${row.score} pts · ${correct}`;
  if (
    row.parts_total !== undefined
    && row.parts_total > 1
    && row.parts_completed !== undefined
  ) {
    return `${score} · ${row.parts_completed}/${row.parts_total} parts`;
  }
  return score;
}

export function formatStudentAccuracy(question: {
  answer_count: number;
  correct_count: number;
  accuracy_percent: number | null;
}): string {
  if (question.answer_count === 0 || question.accuracy_percent === null) {
    return "No students have answered";
  }
  const students = question.answer_count === 1 ? "student" : "students";
  return `${question.correct_count} of ${question.answer_count} ${students} answered correctly`;
}

export function formatPercent(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  if (Number.isInteger(rounded)) return `${rounded}%`;
  return `${rounded.toFixed(2)}%`;
}
