import { afterEach, describe, expect, it, vi } from "vitest";
import {
  formatClassAverage,
  formatLectureMeta,
  formatLectureScore,
  formatPercent,
  formatStudentAccuracy,
  formatUploadDate,
} from "./lectureSummary";

function localUploadDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

describe("lecture row summary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("formats the upload date in the viewer's local timezone", () => {
    // 9:30pm in America/Chicago on Nov 18 is already Nov 19 in UTC.
    const eveningInChicago = "2026-11-19T03:30:00Z";
    const spy = vi.spyOn(Date.prototype, "toLocaleDateString");
    const formatted = formatUploadDate(eveningInChicago);
    const options = spy.mock.calls[0]?.[1] as Intl.DateTimeFormatOptions | undefined;

    expect(formatted).toBe(localUploadDate(eveningInChicago));
    expect(options?.timeZone).toBeUndefined();
    expect(formatUploadDate(null)).toBe("Upload date unavailable");
    expect(formatUploadDate("not-a-date")).toBe("Upload date unavailable");
    expect(new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "America/Chicago",
    }).format(new Date(eveningInChicago))).toBe("Nov 18, 2026");
    expect(new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date(eveningInChicago))).toBe("Nov 19, 2026");
  });

  it("joins upload date, questions, players, and average", () => {
    const uploadedAt = "2026-11-18T15:00:00Z";
    expect(formatLectureMeta({
      uploaded_at: uploadedAt,
      question_count: 12,
      students_played: 8,
      class_average: 240,
    })).toBe(`${localUploadDate(uploadedAt)} · 12 questions · 8 students played · Avg 240`);
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
    expect(formatLectureScore({
      played: true,
      score: 900,
      correct_count: 14,
      parts_completed: 2,
      parts_total: 2,
    })).toBe("900 pts · 14 correct · 2/2 parts");
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
