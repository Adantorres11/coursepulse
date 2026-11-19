import { describe, expect, it } from "vitest";
import {
  formatClassAverage,
  formatLectureMeta,
  formatLectureScore,
  formatPercent,
  formatStudentAccuracy,
  formatUploadDate,
} from "./lectureSummary";

describe("lecture row summary", () => {
  it("formats the upload date in UTC", () => {
    expect(formatUploadDate("2026-11-18T15:00:00Z")).toBe("Nov 18, 2026");
    expect(formatUploadDate(null)).toBe("Upload date unavailable");
  });

  it("joins upload date, questions, players, and average", () => {
    expect(formatLectureMeta({
      uploaded_at: "2026-11-18T15:00:00Z",
      question_count: 12,
      students_played: 8,
      class_average: 240,
    })).toBe("Nov 18, 2026 · 12 questions · 8 students played · Avg 240");
  });

  it("says when nobody has a score yet", () => {
    expect(formatClassAverage(null)).toBe("No average yet");
    expect(formatClassAverage(0)).toBe("Avg 0");
    expect(formatClassAverage(180.26)).toBe("Avg 180.3");
  });
});

describe("results copy", () => {
  it("shows not played instead of a zero", () => {
    expect(formatLectureScore({
      played: false,
      score: null,
      correct_count: null,
    })).toBe("Not played");
  });

  it("shows the lecture score and correct count", () => {
    expect(formatLectureScore({
      played: true,
      score: 300,
      correct_count: 1,
    })).toBe("300 pts · 1 correct");
    expect(formatLectureScore({
      played: true,
      score: 0,
      correct_count: 0,
    })).toBe("0 pts · 0 correct");
  });

  it("describes the share of students who answered correctly", () => {
    expect(formatStudentAccuracy({
      answer_count: 2,
      correct_count: 1,
      accuracy_percent: 50,
    })).toBe("1 of 2 students answered correctly");
    expect(formatStudentAccuracy({
      answer_count: 0,
      correct_count: 0,
      accuracy_percent: null,
    })).toBe("No students have answered");
    expect(formatPercent(50)).toBe("50%");
    expect(formatPercent(66.67)).toBe("66.67%");
  });
});
