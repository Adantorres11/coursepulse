// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import { getLectureStatus, getProfessorClassLectures, retryLecture } from "../lib/apiClient";
import { LECTURE_STATUS_POLL_MS } from "../lib/lectureProgress";
import type { LectureProcessingStatus } from "../types/api";
import { LectureProcessing, LectureProcessingPage } from "./LectureProcessing";

vi.mock("../lib/apiClient", async () => {
  const actual = await vi.importActual<typeof import("../lib/apiClient")>("../lib/apiClient");
  return {
    ...actual,
    getLectureStatus: vi.fn(),
    retryLecture: vi.fn(),
    getProfessorClassLectures: vi.fn(),
  };
});

function status(overrides: Partial<LectureProcessingStatus>): LectureProcessingStatus {
  return {
    id: 4,
    status: "processing",
    progress_message: "",
    error_message: "",
    notice: "",
    ...overrides,
  };
}

function renderProcessing(onSettled?: (value: LectureProcessingStatus) => void) {
  return render(
    <MemoryRouter>
      <LectureProcessing lectureId={4} classId={2} onSettled={onSettled} />
    </MemoryRouter>
  );
}

async function flush() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

describe("LectureProcessing", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(getLectureStatus).mockReset();
    vi.mocked(retryLecture).mockReset();
    vi.mocked(getProfessorClassLectures).mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("shows the part progress and stops polling when the lecture is ready", async () => {
    const onSettled = vi.fn();
    let calls = 0;
    vi.mocked(getLectureStatus).mockImplementation(async () => {
      calls += 1;
      if (calls < 3) {
        return {
          data: status({ progress_message: "Transcribing part 2 of 7" }),
          error: null,
        };
      }
      return {
        data: status({
          status: "ready",
          progress_message: "",
          notice: "Generated 12 questions (target 15). Add more in review if needed.",
        }),
        error: null,
      };
    });

    renderProcessing(onSettled);
    await flush();

    expect(screen.getByText("Transcribing part 2 of 7")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Transcribing" }).getAttribute("aria-valuenow")).toBe(
      "29"
    );
    expect(screen.getByRole("listitem", { current: "step" }).textContent).toMatch(/Transcribing/);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LECTURE_STATUS_POLL_MS);
    });
    expect(calls).toBe(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LECTURE_STATUS_POLL_MS);
    });

    expect(screen.getByText("Questions are ready for review.")).toBeTruthy();
    expect(
      screen.getByText("Generated 12 questions (target 15). Add more in review if needed.")
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Review" }).getAttribute("href")).toBe(
      "/professor/class/2/lectures/4"
    );
    expect(onSettled).toHaveBeenCalledTimes(1);

    const stopped = calls;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LECTURE_STATUS_POLL_MS * 3);
    });
    expect(calls).toBe(stopped);
  });

  it("moves the writing-questions bar from part X of Y", async () => {
    vi.mocked(getLectureStatus).mockResolvedValue({
      data: status({ progress_message: "Writing questions (part 1 of 6)" }),
      error: null,
    });

    renderProcessing();
    await flush();

    expect(screen.getByRole("listitem", { current: "step" }).textContent).toMatch(/Writing questions/);
    expect(
      screen.getByRole("progressbar", { name: "Writing questions" }).getAttribute("aria-valuenow")
    ).toBe("17");
  });

  it("stops polling when the screen is closed", async () => {
    let calls = 0;
    vi.mocked(getLectureStatus).mockImplementation(async () => {
      calls += 1;
      return {
        data: status({ progress_message: "Checking the recording" }),
        error: null,
      };
    });

    const view = renderProcessing();
    await flush();
    const afterFirst = calls;
    view.unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LECTURE_STATUS_POLL_MS * 4);
    });
    expect(calls).toBe(afterFirst);
  });

  it("shows the error and retries a failed lecture", async () => {
    vi.mocked(getLectureStatus)
      .mockResolvedValueOnce({
        data: status({
          status: "failed",
          error_message: "No speech was detected.",
        }),
        error: null,
      })
      .mockResolvedValue({
        data: status({ progress_message: "Checking the recording" }),
        error: null,
      });
    vi.mocked(retryLecture).mockResolvedValue({
      data: { id: 4, status: "pending", error_message: "" },
      error: null,
    });

    renderProcessing();
    await flush();

    expect(screen.getByRole("alert").textContent).toMatch(/No speech was detected/);
    expect(screen.getByRole("listitem", { current: "step" }).textContent).toMatch(/Failed/);

    await act(async () => {
      screen.getByRole("button", { name: "Retry" }).click();
    });
    await flush();

    expect(retryLecture).toHaveBeenCalledWith(4);
    expect(screen.getByText("Checking the recording")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("keeps polling after a status request fails", async () => {
    vi.mocked(getLectureStatus)
      .mockResolvedValueOnce({ data: null, error: "Could not reach API: offline" })
      .mockResolvedValue({
        data: status({ progress_message: "Preparing audio" }),
        error: null,
      });

    renderProcessing();
    await flush();
    expect(screen.getByText("Could not reach API: offline")).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LECTURE_STATUS_POLL_MS);
    });
    expect(screen.getByText("Preparing audio")).toBeTruthy();
    expect(screen.queryByText("Could not reach API: offline")).toBeNull();
  });
});

describe("LectureProcessingPage", () => {
  beforeEach(() => {
    vi.mocked(getLectureStatus).mockReset();
    vi.mocked(getProfessorClassLectures).mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("loads the lecture title on the status route", async () => {
    vi.mocked(getLectureStatus).mockResolvedValue({
      data: status({ progress_message: "Preparing audio" }),
      error: null,
    });
    vi.mocked(getProfessorClassLectures).mockResolvedValue({
      data: [
        {
          id: 4,
          title: "Pipelining and Data Hazards",
          status: "processing",
          published_at: null,
        },
      ],
      error: null,
    });

    render(
      <MemoryRouter initialEntries={["/professor/class/2/lectures/4/status"]}>
        <AuthProvider>
          <Routes>
            <Route
              path="/professor/class/:classId/lectures/:lectureId/status"
              element={<LectureProcessingPage />}
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Pipelining and Data Hazards" })).toBeTruthy();
    expect(await screen.findByText("Preparing audio")).toBeTruthy();
  });
});
