// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import { ClassHub } from "./ClassHub";
import { getClassStats, getClasses } from "../lib/apiClient";
import type { ClassLectureStat, ClassStats } from "../types/api";

vi.mock("../lib/apiClient", async () => {
  const actual = await vi.importActual<typeof import("../lib/apiClient")>("../lib/apiClient");
  return {
    ...actual,
    isProfessor: () => false,
    getClassesRoute: () => "/hub",
    getStoredToken: () => null,
    getStoredUser: () => null,
    getCurrentUser: vi.fn(async () => ({ data: null, error: null })),
    clearSession: vi.fn(),
    getClassStats: vi.fn(),
    getClasses: vi.fn(),
  };
});

function lecture(overrides: Partial<ClassLectureStat>): ClassLectureStat {
  return {
    id: 1,
    title: "Lecture 5",
    published_at: "2026-11-01T00:00:00Z",
    question_count: 30,
    best_score: 0,
    correct_count: 0,
    is_new: true,
    parts: [
      { part: 1, question_count: 10, completed: false, best_score: 0, correct_count: 0, in_progress: false },
      { part: 2, question_count: 10, completed: false, best_score: 0, correct_count: 0, in_progress: false },
      { part: 3, question_count: 10, completed: false, best_score: 0, correct_count: 0, in_progress: false },
    ],
    ...overrides,
  };
}

function stats(lectures: ClassLectureStat[], upNext: ClassLectureStat | null): ClassStats {
  return {
    classroom_id: 4,
    classroom: "Software Engineering",
    total_points: 800,
    rank: 1,
    points_to_next_rank: 0,
    quizzes_played: 1,
    quizzes_total: 3,
    day_streak: 1,
    answer_streak: 0,
    up_next: upNext,
    lectures,
  };
}

function renderHub() {
  return render(
    <MemoryRouter initialEntries={["/class/4"]}>
      <AuthProvider>
        <Routes>
          <Route path="/class/:classId" element={<ClassHub />} />
          <Route path="/quiz/:lectureId" element={<p>Quiz page</p>} />
          <Route path="/quiz/:lectureId/review" element={<p>Review page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("Class hub parts", () => {
  beforeEach(() => {
    vi.mocked(getClasses).mockResolvedValue({
      data: [
        {
          id: 4,
          name: "Software Engineering",
          course_code: "CS 3398",
          professor: { id: 2, name: "Ada Lovelace" },
          quiz_count: 1,
          new_quiz_count: 0,
        },
      ],
      error: null,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("shows one circle per part and a score, then replay and review", async () => {
    const played = lecture({
      id: 5,
      title: "Lecture 5",
      is_new: false,
      best_score: 800,
      parts: [
        { part: 1, question_count: 10, completed: true, best_score: 800, correct_count: 8, in_progress: false },
        { part: 2, question_count: 10, completed: false, best_score: 0, correct_count: 0, in_progress: false },
        { part: 3, question_count: 10, completed: true, best_score: 200, correct_count: 2, in_progress: false },
      ],
    });
    vi.mocked(getClassStats).mockResolvedValue({
      data: stats([played], null),
      error: null,
    });

    renderHub();

    expect(await screen.findByText("Lecture 5")).toBeTruthy();
    expect(screen.queryByText(/of \d+ correct/)).toBeNull();
    expect(screen.queryByText("More Lectures")).toBeNull();
    expect(screen.getByText("Best score 800 pts")).toBeTruthy();

    const circles = document.querySelectorAll('[data-testid="lecture-5"] .rounded-full.border-2');
    expect(circles.length).toBeGreaterThanOrEqual(3);

    await userEvent.click(screen.getByRole("button", { name: "Show parts of Lecture 5" }));
    expect(screen.getByText("Part 1")).toBeTruthy();
    expect(screen.getByText("Best score 200 pts")).toBeTruthy();
    expect(screen.getByText("Not played")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Replay" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Review" })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Start" })).toBeTruthy();

    await userEvent.click(screen.getAllByRole("button", { name: "Review" })[0]);
    expect(await screen.findByText("Review page")).toBeTruthy();
  });

  it("keeps the More lectures header when an up next lecture is separate", async () => {
    const upcoming = lecture({ id: 9, title: "Lecture 9" });
    const older = lecture({
      id: 5,
      title: "Lecture 5",
      is_new: false,
      best_score: 100,
      parts: [
        { part: 1, question_count: 10, completed: true, best_score: 100, correct_count: 1, in_progress: false },
      ],
    });
    vi.mocked(getClassStats).mockResolvedValue({
      data: stats([upcoming, older], upcoming),
      error: null,
    });

    renderHub();
    expect(await screen.findByText("More Lectures")).toBeTruthy();
    expect(screen.getByText("Up Next")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Start quiz/ })).toBeTruthy();
  });
});
