import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getQuiz } from "./apiClient";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("getQuiz", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    const store = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
      clear: () => store.clear(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getQuiz returns the quiz from the real endpoint", async () => {
    fetchMock.mockResolvedValue(
      json({
        lecture_id: 7,
        title: "T",
        questions: [],
        answered_question_ids: [],
        total_points: 0,
      })
    );
    const result = await getQuiz(7);
    expect(result.data?.title).toBe("T");
    expect(result.error).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/lectures\/7\/quiz\/$/);
  });

  it("getQuiz does not fall back to sample data on a server error", async () => {
    fetchMock.mockResolvedValue(json({}, 500));
    const result = await getQuiz(7);
    expect(result.data).toBeNull();
    expect(result.error).toBe("The server had a problem. Try again shortly.");
    expect(result.status).toBe(500);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("getQuiz returns the 404 status", async () => {
    fetchMock.mockResolvedValue(json({ detail: "Not found." }, 404));
    const result = await getQuiz(7);
    expect(result.status).toBe(404);
    expect(result.data).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("getQuiz keeps the server detail message", async () => {
    fetchMock.mockResolvedValue(
      json({ detail: "You must be enrolled in this class." }, 403)
    );
    const result = await getQuiz(7);
    expect(result.error).toBe("You must be enrolled in this class.");
    expect(result.status).toBe(403);
  });

  it("getQuiz reports a network failure without sample data", async () => {
    fetchMock.mockRejectedValue(new Error("boom"));
    const result = await getQuiz(7);
    expect(result.data).toBeNull();
    expect(result.error?.startsWith("Could not reach API")).toBe(true);
  });
});
