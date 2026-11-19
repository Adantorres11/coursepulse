import type { ClassLectureStat, LecturePartStat } from "../types/api";

/** Parts from the class stats payload, or one part when an older response has none. */
export function partsOf(lecture: ClassLectureStat): LecturePartStat[] {
  if (lecture.parts && lecture.parts.length > 0) {
    return lecture.parts;
  }
  return [
    {
      part: 1,
      question_count: lecture.question_count,
      completed: !lecture.is_new,
      best_score: lecture.best_score,
      correct_count: lecture.correct_count,
      in_progress: false,
    },
  ];
}

/** The part a Start button should open: an in-progress part, else the first unfinished one. */
export function nextPlayablePart(parts: LecturePartStat[]): LecturePartStat | null {
  return parts.find((part) => part.in_progress) ?? parts.find((part) => !part.completed) ?? null;
}

export type PartAction = "start" | "resume" | "replay";

export function partAction(part: LecturePartStat): PartAction {
  if (part.in_progress) return "resume";
  if (part.completed) return "replay";
  return "start";
}

/** Score copy. A finished part reads as a score. An unplayed part is not a fraction of a quiz. */
export function partScoreText(part: Pick<LecturePartStat, "completed" | "best_score">): string {
  if (!part.completed) return "Not played";
  return `Best score ${part.best_score} pts`;
}

export function lectureScoreText(lecture: ClassLectureStat): string | null {
  const played = partsOf(lecture).some((part) => part.completed);
  if (!played) return null;
  return `Best score ${lecture.best_score} pts`;
}

export function lectureSizeText(lecture: ClassLectureStat): string {
  const count = partsOf(lecture).length;
  if (count > 1) {
    return `${lecture.question_count} questions · ${count} parts`;
  }
  return `${lecture.question_count} questions`;
}

/** "More lectures" only makes sense when an Up Next lecture is already pulled out of the list. */
export function showMoreLecturesHeader(
  upNext: { id: number } | null,
  moreCount: number
): boolean {
  return upNext != null && moreCount > 0;
}
