// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import { StudentHub } from "./StudentHub";
import { getLeaderboard, getStudentDayStreak, request } from "../lib/apiClient";

vi.mock("../lib/apiClient", async () => {
  const actual = await vi.importActual<typeof import("../lib/apiClient")>("../lib/apiClient");
  return {
    ...actual,
    isProfessor: () => false,
    getStoredToken: () => "token",
    getStoredUser: () => ({ id: 1, email: "a@example.com", role: "student" as const }),
    getCurrentUser: vi.fn(async () => ({
      data: { id: 1, email: "a@example.com", role: "student" },
      error: null,
    })),
    clearSession: vi.fn(),
    getStudentDayStreak: vi.fn(async () => 2),
    request: vi.fn(),
    getLeaderboard: vi.fn(),
  };
});

describe("All-classes dashboard rank", () => {
  beforeEach(() => {
    vi.mocked(request).mockImplementation(async (path: string) => {
      if (path === "/classes/") {
        return {
          data: [
            {
              id: 4,
              name: "Software Engineering",
              course_code: "CS 3398",
              professor: { id: 2, name: "Ada Lovelace" },
              quiz_count: 2,
              new_quiz_count: 1,
            },
          ],
          error: null,
        };
      }
      return { data: [], error: null };
    });
    vi.mocked(getLeaderboard).mockResolvedValue({
      data: [
        { rank: 1, display_name: "Ada L.", points: 1200, is_current_user: true },
      ],
      error: null,
    });
    vi.mocked(getStudentDayStreak).mockResolvedValue(2);
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => (key === "coursepulse_token" ? "token" : null),
      setItem: () => undefined,
      removeItem: () => undefined,
      clear: () => undefined,
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows a small rank and points on the class card", async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <StudentHub />
        </AuthProvider>
      </MemoryRouter>
    );

    expect(await screen.findByText("#1")).toBeTruthy();
    expect(screen.getByText(`${(1200).toLocaleString()} pts`)).toBeTruthy();
    expect(screen.queryByText(/your rank/i)).toBeNull();
    expect(screen.queryByText(/view leaderboard/i)).toBeNull();
  });
});
