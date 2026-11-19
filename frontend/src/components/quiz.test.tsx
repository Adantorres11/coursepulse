// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { postAnswer, startQuestion } from "../lib/apiClient";
import QuizGame from "./quiz";

vi.mock("../lib/apiClient", () => ({
  postAnswer: vi.fn(),
  startQuestion: vi.fn(async () => ({
    data: { question_id: 1, started_at: "2026-11-19T00:00:00Z" },
    error: null,
  })),
}));

vi.mock("canvas-confetti", () => ({
  default: vi.fn(() => Promise.resolve()),
}));

const questions = [
  {
    id: 1,
    prompt: "In Scrum, what is a Sprint?",
    choices: ["Alpha", "Beta", "Gamma", "Delta"],
    difficulty: "easy" as const,
  },
  {
    id: 2,
    prompt: "Which Git command shows your current branch?",
    choices: ["Alpha", "Beta", "Gamma", "Delta"],
    difficulty: "medium" as const,
  },
];

function mockMotion(reduce: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reduce && String(query).includes("prefers-reduced-motion"),
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

async function reachFirstQuestion() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3200);
  });
}

async function choose(name: RegExp) {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name }));
    await vi.advanceTimersByTimeAsync(0);
  });
}

describe("QuizGame play", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockMotion(false);
    vi.mocked(startQuestion).mockClear();
    vi.mocked(postAnswer).mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("shows 35 seconds as the single question limit", () => {
    render(<QuizGame questions={questions} />);
    expect(screen.getByText("35 sec each")).toBeTruthy();
  });

  it("drains the question timer with one continuous 35 second animation", async () => {
    render(<QuizGame questions={questions} lectureId="4" />);
    await reachFirstQuestion();

    const bar = screen.getByTestId("question-timer-bar");
    expect(bar.style.animationDuration).toBe("35s");
    expect(bar.className).toContain("quiz-timer-bar");
    expect(screen.getByText("0:35")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Alpha/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("sends the part with the start and the answer", async () => {
    vi.mocked(postAnswer).mockResolvedValue({
      data: {
        is_correct: true,
        points_awarded: 100,
        total_points: 100,
        correct_index: 0,
      },
      error: null,
    });
    render(<QuizGame questions={questions} lectureId="4" part={2} />);
    await reachFirstQuestion();
    expect(vi.mocked(startQuestion)).toHaveBeenCalledWith("4", 1, 2);
    await choose(/Alpha/);
    const body = vi.mocked(postAnswer).mock.calls[0][1];
    expect(body.part).toBe(2);
    expect(body.chosen_index).toBe(0);
    expect(body.question_id).toBe(1);
  });

  it("asks the page to reload the quiz on replay", () => {
    const onReplay = vi.fn();
    render(
      <QuizGame
        questions={questions}
        initialAnsweredIds={[1, 2]}
        initialAnswers={[
          { question_id: 1, is_correct: true, points_awarded: 100 },
          { question_id: 2, is_correct: false, points_awarded: 0 },
        ]}
        onReplay={onReplay}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /Replay/ }));
    expect(onReplay).toHaveBeenCalledTimes(1);
  });

  it("lists earlier answers vertically with the points they earned", () => {
    render(
      <QuizGame
        questions={questions}
        initialAnsweredIds={[1, 2]}
        initialAnswers={[
          { question_id: 1, is_correct: true, points_awarded: 150 },
          { question_id: 2, is_correct: false, points_awarded: 0 },
        ]}
        initialScore={150}
      />
    );

    const list = screen.getByRole("list");
    expect(list.className).toContain("flex-col");
    expect(list.className).toContain("overflow-y-auto");
    expect(list.className).not.toContain("flex-row");
    expect(screen.getAllByText("Answered earlier")).toHaveLength(2);
    expect(screen.getByText("Easy")).toBeTruthy();
    expect(screen.getByText("Medium")).toBeTruthy();
    expect(screen.getByText("+150")).toBeTruthy();
    expect(screen.getByText("+0")).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
  });
});

describe("QuizGame feedback", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockMotion(false);
    vi.mocked(postAnswer).mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("bursts confetti and floats the points when the answer is right", async () => {
    const confetti = (await import("canvas-confetti")).default as unknown as ReturnType<typeof vi.fn>;
    vi.mocked(postAnswer).mockResolvedValue({
      data: {
        is_correct: true,
        points_awarded: 100,
        total_points: 100,
        correct_index: 0,
      },
      error: null,
    });
    render(<QuizGame questions={questions} lectureId="4" />);
    await reachFirstQuestion();
    await choose(/Alpha/);

    expect(confetti).toHaveBeenCalledTimes(1);
    const popup = screen.getByTestId("points-pop");
    expect(popup.textContent).toContain("+100 points");
    expect(popup.className).toContain("quiz-points-pop");
  });

  it("shakes the choices when the answer is wrong", async () => {
    vi.mocked(postAnswer).mockResolvedValue({
      data: {
        is_correct: false,
        points_awarded: 0,
        total_points: 0,
        correct_index: 0,
      },
      error: null,
    });
    render(<QuizGame questions={questions} lectureId="4" />);
    await reachFirstQuestion();
    await choose(/Beta/);

    expect(screen.getByTestId("choices").className).toContain("quiz-shake");
    expect(screen.queryByTestId("points-pop")).toBeNull();
  });

  it("skips confetti, the floating popup, and the shake when motion is reduced", async () => {
    mockMotion(true);
    const confetti = (await import("canvas-confetti")).default as unknown as ReturnType<typeof vi.fn>;
    vi.mocked(postAnswer).mockResolvedValue({
      data: {
        is_correct: true,
        points_awarded: 100,
        total_points: 100,
        correct_index: 0,
      },
      error: null,
    });
    const { unmount } = render(<QuizGame questions={questions} lectureId="4" />);
    await reachFirstQuestion();
    await choose(/Alpha/);

    expect(confetti).not.toHaveBeenCalled();
    const popup = screen.getByTestId("points-pop");
    expect(popup.textContent).toContain("+100 points");
    expect(popup.className).not.toContain("quiz-points-pop");
    unmount();

    vi.mocked(postAnswer).mockResolvedValue({
      data: {
        is_correct: false,
        points_awarded: 0,
        total_points: 0,
        correct_index: 0,
      },
      error: null,
    });
    render(<QuizGame questions={questions} lectureId="4" />);
    await reachFirstQuestion();
    await choose(/Beta/);
    expect(screen.getByTestId("choices").className).not.toContain("quiz-shake");
  });
});
