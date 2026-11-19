import { describe, expect, it } from "vitest";
import {
  lectureScoreText,
  nextPlayablePart,
  partAction,
  partScoreText,
  partsOf,
  showMoreLecturesHeader,
} from "./lectureParts";
import type { ClassLectureStat, LecturePartStat } from "../types/api";

function part(overrides: Partial<LecturePartStat> = {}): LecturePartStat {
  return {
    part: 1,
    question_count: 10,
    completed: false,
    best_score: 0,
    correct_count: 0,
    in_progress: false,
    ...overrides,
  };
}

function lecture(overrides: Partial<ClassLectureStat> = {}): ClassLectureStat {
  return {
    id: 5,
    title: "Lecture 5",
    published_at: "2026-11-01T00:00:00Z",
    question_count: 30,
    best_score: 800,
    correct_count: 8,
    is_new: false,
    parts: [part({ completed: true, best_score: 800 })],
    ...overrides,
  };
}

describe("lecture part labels", () => {
  it("reads a finished part as a score", () => {
    expect(partScoreText(part({ completed: true, best_score: 800 }))).toBe("Best score 800 pts");
    expect(lectureScoreText(lecture())).toBe("Best score 800 pts");
  });

  it("does not describe an unplayed part as progress through the questions", () => {
    expect(partScoreText(part())).toBe("Not played");
    expect(lectureScoreText(lecture({ is_new: true, best_score: 0, parts: [part()] }))).toBeNull();
    expect(partScoreText(part({ completed: true, best_score: 800 }))).not.toMatch(/of \d+ correct/);
  });

  it("offers start, resume, or replay", () => {
    expect(partAction(part())).toBe("start");
    expect(partAction(part({ in_progress: true }))).toBe("resume");
    expect(partAction(part({ completed: true, in_progress: true }))).toBe("resume");
    expect(partAction(part({ completed: true }))).toBe("replay");
  });

  it("picks the in-progress part before the next unplayed one", () => {
    const parts = [
      part({ part: 1, completed: true }),
      part({ part: 2, in_progress: true }),
      part({ part: 3 }),
    ];
    expect(nextPlayablePart(parts)?.part).toBe(2);
    expect(nextPlayablePart([part({ part: 1, completed: true }), part({ part: 2 })])?.part).toBe(2);
    expect(nextPlayablePart([part({ completed: true })])).toBeNull();
  });

  it("falls back to one part when the payload has no part list", () => {
    const item = lecture({ parts: undefined, is_new: true, question_count: 5 });
    expect(partsOf(item)).toEqual([
      {
        part: 1,
        question_count: 5,
        completed: false,
        best_score: 800,
        correct_count: 8,
        in_progress: false,
      },
    ]);
  });

  it("hides the More lectures header when nothing was pulled out as Up Next", () => {
    expect(showMoreLecturesHeader(null, 3)).toBe(false);
    expect(showMoreLecturesHeader({ id: 1 }, 0)).toBe(false);
    expect(showMoreLecturesHeader({ id: 1 }, 2)).toBe(true);
  });
});
