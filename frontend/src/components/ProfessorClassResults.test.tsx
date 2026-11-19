// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import { getClassResults } from "../lib/apiClient";
import type { ClassResults } from "../types/api";
import { ProfessorClassResults } from "./ProfessorClassResults";

vi.mock("../lib/apiClient", async () => {
  const actual = await vi.importActual<typeof import("../lib/apiClient")>("../lib/apiClient");
  return {
    ...actual,
    getStoredToken: () => null,
    getStoredUser: () => null,
    getClassResults: vi.fn(),
  };
});

const results: ClassResults = {
  classroom_id: 1,
  classroom: "Software Engineering",
  students: [
    {
      student_id: 1,
      name: "Ada Lovelace",
      username: "ada",
      total_points: 100,
      quizzes_played: 1,
      lectures: [
        { lecture_id: 7, played: true, score: 300, correct_count: 2 },
        { lecture_id: 8, played: false, score: null, correct_count: null },
      ],
    },
    {
      student_id: 2,
      name: "grace@school.edu",
      username: "gben",
      total_points: 0,
      quizzes_played: 0,
      lectures: [
        { lecture_id: 7, played: false, score: null, correct_count: null },
        { lecture_id: 8, played: false, score: null, correct_count: null },
      ],
    },
  ],
  lectures: [
    {
      lecture_id: 7,
      title: "Agile",
      questions: [
        {
          question_id: 1,
          prompt: "What is a sprint?",
          answer_count: 2,
          correct_count: 1,
          accuracy_percent: 50,
        },
      ],
    },
    {
      lecture_id: 8,
      title: "Scrum",
      questions: [
        {
          question_id: 2,
          prompt: "What is a backlog?",
          answer_count: 0,
          correct_count: 0,
          accuracy_percent: null,
        },
      ],
    },
  ],
};

function renderResults() {
  return render(
    <MemoryRouter initialEntries={["/professor/class/1/results"]}>
      <AuthProvider>
        <Routes>
          <Route path="/professor/class/:classId/results" element={<ProfessorClassResults />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("ProfessorClassResults", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(getClassResults).mockReset();
  });

  it("shows each student's lecture score, not played, and question accuracy", async () => {
    vi.mocked(getClassResults).mockResolvedValue({ data: results, error: null });

    renderResults();

    expect(await screen.findByRole("heading", { name: "Software Engineering results" })).toBeTruthy();
    expect(screen.getByText("300 pts · 2 correct")).toBeTruthy();
    expect(screen.getAllByText("Not played").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ada").length).toBeGreaterThan(1);
    expect(screen.getAllByText("gben").length).toBeGreaterThan(1);
    expect(screen.queryByText("Ada Lovelace")).toBeNull();
    expect(screen.queryByText("grace@school.edu")).toBeNull();
    expect(screen.getByText("1 of 2 students answered correctly")).toBeTruthy();
    expect(screen.getByText("50%")).toBeTruthy();
    expect(screen.getByText("No students have answered")).toBeTruthy();
    expect(screen.getByRole("link", { name: "← Back to class" }).getAttribute("href"))
      .toBe("/professor/class/1");
  });
});