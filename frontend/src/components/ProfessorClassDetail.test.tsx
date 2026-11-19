// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, Link } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import {
  getClassRoster,
  getProfessorClasses,
  getProfessorClassLectures,
} from "../lib/apiClient";
import type { ProfessorClass, ProfessorLecture } from "../types/api";
import { ProfessorClassDetail } from "./ProfessorClassDetail";

vi.mock("./LectureUpload", () => ({
  UploadLecturePage: ({ onSuccess }: { onSuccess?: () => void }) => (
    <button type="button" onClick={() => onSuccess?.()}>
      Finish upload
    </button>
  ),
}));

vi.mock("../lib/apiClient", async () => {
  const actual = await vi.importActual<typeof import("../lib/apiClient")>("../lib/apiClient");
  return {
    ...actual,
    getStoredToken: () => null,
    getStoredUser: () => null,
    getProfessorClasses: vi.fn(),
    getProfessorClassLectures: vi.fn(),
    getClassRoster: vi.fn(),
  };
});

const classes: ProfessorClass[] = [
  {
    id: 1,
    name: "Class One",
    access_code: "AAAAAA",
    student_count: 0,
    lecture_count: 1,
  },
  {
    id: 2,
    name: "Class Two",
    access_code: "BBBBBB",
    student_count: 0,
    lecture_count: 1,
  },
];

function lecture(
  id: number,
  title: string,
  status: ProfessorLecture["status"],
  extras: Partial<ProfessorLecture> = {}
): ProfessorLecture {
  return {
    id,
    title,
    status,
    published_at: null,
    uploaded_at: "2026-11-18T15:00:00Z",
    question_count: 4,
    students_played: 0,
    class_average: null,
    ...extras,
  };
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={["/professor/class/1"]}>
      <AuthProvider>
        <Routes>
          <Route path="/professor/class/:classId" element={<ProfessorClassDetail />} />
        </Routes>
        <Link to="/professor/class/2">Open class two</Link>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("ProfessorClassDetail", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(getProfessorClasses).mockReset();
    vi.mocked(getProfessorClassLectures).mockReset();
    vi.mocked(getClassRoster).mockReset();
    vi.mocked(getClassRoster).mockResolvedValue({ data: [], error: null });
  });

  it("refreshes after an upload without flashing the loading screen", async () => {
    const user = userEvent.setup();
    let releaseSecond: () => void = () => {};
    const secondGate = new Promise<void>((resolve) => {
      releaseSecond = resolve;
    });
    let lectureCalls = 0;

    vi.mocked(getProfessorClasses).mockResolvedValue({
      data: [classes[0]],
      error: null,
    });
    vi.mocked(getProfessorClassLectures).mockImplementation(async () => {
      lectureCalls += 1;
      if (lectureCalls > 1) await secondGate;
      const rows =
        lectureCalls > 1
          ? [lecture(1, "Old lecture", "pending"), lecture(2, "Uploaded lecture", "pending")]
          : [lecture(1, "Old lecture", "pending")];
      return { data: rows, error: null };
    });

    renderDetail();
    expect(await screen.findByText("Old lecture")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /upload lecture/i }));
    await user.click(screen.getByRole("button", { name: "Finish upload" }));

    expect(screen.queryByText("Loading class...")).toBeNull();
    expect(screen.getByText("Old lecture")).toBeTruthy();

    releaseSecond();
    expect(await screen.findByText("Uploaded lecture")).toBeTruthy();
  });

  it("ignores a class load that finishes after the professor switches classes", async () => {
    const user = userEvent.setup();
    let releaseFirst: () => void = () => {};
    const firstGate = new Promise<void>((resolve) => {
      releaseFirst = resolve;
    });
    let classCalls = 0;

    vi.mocked(getProfessorClasses).mockImplementation(async () => {
      classCalls += 1;
      if (classCalls === 1) await firstGate;
      return { data: classes, error: null };
    });
    vi.mocked(getProfessorClassLectures).mockImplementation(async (id) => ({
      data: [
        lecture(
          Number(id) * 10,
          Number(id) === 1 ? "Lecture One" : "Lecture Two",
          "ready"
        ),
      ],
      error: null,
    }));

    renderDetail();
    await user.click(screen.getByRole("link", { name: "Open class two" }));

    expect(await screen.findByRole("heading", { name: "Class Two" })).toBeTruthy();
    await act(async () => {
      releaseFirst();
      await Promise.resolve();
    });
    await screen.findByText("Lecture Two");

    expect(screen.queryByRole("heading", { name: "Class One" })).toBeNull();
    expect(screen.queryByText("Lecture One")).toBeNull();
  });

  it("links a ready lecture to review and leaves a processing lecture as status text", async () => {
    vi.mocked(getProfessorClasses).mockResolvedValue({
      data: [classes[0]],
      error: null,
    });
    vi.mocked(getProfessorClassLectures).mockResolvedValue({
      data: [
        lecture(7, "Ready lecture", "ready"),
        lecture(8, "Processing lecture", "processing"),
      ],
      error: null,
    });

    renderDetail();

    const review = await screen.findByRole("link", { name: "Review" });
    expect(review.getAttribute("href")).toBe("/professor/class/1/lectures/7");
    expect(screen.getAllByRole("link", { name: "Review" })).toHaveLength(1);
    expect(screen.getByText("Processing lecture")).toBeTruthy();
    expect(screen.getByText("processing")).toBeTruthy();
  });

  it("shows upload date, question count, players, average, and a results link", async () => {
    vi.mocked(getProfessorClasses).mockResolvedValue({
      data: [classes[0]],
      error: null,
    });
    vi.mocked(getProfessorClassLectures).mockResolvedValue({
      data: [
        lecture(7, "Week 1", "published", {
          published_at: "2026-11-18T18:00:00Z",
          question_count: 12,
          students_played: 8,
          class_average: 240,
        }),
      ],
      error: null,
    });

    renderDetail();

    expect(await screen.findByText(
      "Nov 18, 2026 · 12 questions · 8 students played · Avg 240"
    )).toBeTruthy();
    const results = screen.getByRole("link", { name: "View results" });
    expect(results.getAttribute("href")).toBe("/professor/class/1/results");
  });

  it("shows roster usernames and hides email and full names", async () => {
    vi.mocked(getProfessorClasses).mockResolvedValue({
      data: [classes[0]],
      error: null,
    });
    vi.mocked(getProfessorClassLectures).mockResolvedValue({
      data: [lecture(7, "Week 1", "published")],
      error: null,
    });
    vi.mocked(getClassRoster).mockResolvedValue({
      data: [
        {
          name: "Ada Lovelace",
          username: "ada",
          joined_at: "2026-11-18T00:00:00Z",
        },
        {
          name: "grace@school.edu",
          username: "gben",
          joined_at: "2026-11-18T00:00:00Z",
        },
      ],
      error: null,
    });

    renderDetail();

    expect(await screen.findByText("ada")).toBeTruthy();
    expect(screen.getByText("gben")).toBeTruthy();
    expect(screen.queryByText("Ada Lovelace")).toBeNull();
    expect(screen.queryByText("grace@school.edu")).toBeNull();
    expect(screen.queryByText(/@/)).toBeNull();
  });
});
