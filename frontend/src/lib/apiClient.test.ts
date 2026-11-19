import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createClass,
  createLectureQuestion,
  deleteLectureQuestion,
  getLectureQuestions,
  getQuiz,
  publishLecture,
  updateLectureQuestion,
} from "./apiClient";

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

  it("getQuiz asks for one part when a part number is passed", async () => {
    fetchMock.mockResolvedValue(
      json({
        lecture_id: 7,
        title: "T",
        part: 2,
        part_count: 3,
        questions: [],
        answered_question_ids: [],
        total_points: 0,
      })
    );
    const result = await getQuiz(7, 2);
    expect(result.data?.part).toBe(2);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/lectures\/7\/quiz\/\?part=2$/);
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

describe("createClass", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    const store = new Map<string, string>();
    store.set("coursepulse_token", "test-token-123");
    const mockStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
      clear: () => store.clear(),
    };
    vi.stubGlobal("sessionStorage", mockStorage);
    vi.stubGlobal("localStorage", mockStorage);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends POST to /classes/ with class name and auth header", async () => {
    fetchMock.mockResolvedValue(
      json(
        {
          id: 42,
          name: "CS 3398 Software Engineering",
          access_code: "ABC123",
        },
        201
      )
    );

    const result = await createClass("CS 3398 Software Engineering");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/classes\/$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ name: "CS 3398 Software Engineering" });
    expect(init.headers.Authorization || init.headers.get?.("Authorization")).toBe("Token test-token-123");

    expect(result.error).toBeNull();
    expect(result.data).toEqual({
      id: 42,
      name: "CS 3398 Software Engineering",
      access_code: "ABC123",
    });
  });

  it("returns readable server error when class name is blank or invalid", async () => {
    fetchMock.mockResolvedValue(
      json({ detail: "This field may not be blank." }, 400)
    );

    const result = await createClass("");

    expect(result.status).toBe(400);
    expect(result.data).toBeNull();
    expect(result.error).toBe("This field may not be blank.");
  });

  it("handles forbidden response when user is not a professor", async () => {
    fetchMock.mockResolvedValue(
      json({ detail: "Only professors can create classes." }, 403)
    );

    const result = await createClass("Unauthorized Class");

    expect(result.status).toBe(403);
    expect(result.data).toBeNull();
    expect(result.error).toBe("Only professors can create classes.");
  });

  it("keeps the name field on a blank-name error", async () => {
    fetchMock.mockResolvedValue(
      json({ name: ["This field may not be blank."] }, 400)
    );

    const result = await createClass(" ");

    expect(result.fields?.name).toEqual(["This field may not be blank."]);
    expect(result.error).toBe("This field may not be blank.");
    expect(result.fields?.recording).toBeUndefined();
  });
});

describe("lecture questions", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    const store = new Map<string, string>();
    store.set("coursepulse_token", "prof-token");
    const mockStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
      clear: () => store.clear(),
    };
    vi.stubGlobal("sessionStorage", mockStorage);
    vi.stubGlobal("localStorage", mockStorage);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads draft questions with the correct answer", async () => {
    fetchMock.mockResolvedValue(
      json([
        {
          id: 3,
          prompt: "What is a sprint?",
          choices: ["A", "B", "C", "D"],
          correct_index: 0,
          difficulty: "easy",
          position: 1,
        },
      ])
    );

    const result = await getLectureQuestions(8);

    expect(result.error).toBeNull();
    expect(result.data?.[0].correct_index).toBe(0);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/lectures\/8\/questions\/$/);
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Token prof-token");
  });

  it("creates, updates, publishes, and deletes a question", async () => {
    fetchMock
      .mockResolvedValueOnce(json({ id: 4, position: 2 }, 201))
      .mockResolvedValueOnce(json({ id: 4, prompt: "Updated" }))
      .mockResolvedValueOnce(json({ id: 8, published_at: "2026-11-19T00:00:00Z", message: "Quiz published successfully." }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const created = await createLectureQuestion(8, {
      prompt: "New",
      choices: ["A", "B", "C", "D"],
      correct_index: 1,
      difficulty: "medium",
    });
    const updated = await updateLectureQuestion(8, 4, { prompt: "Updated" });
    const published = await publishLecture(8);
    const deleted = await deleteLectureQuestion(8, 4);

    expect(created.data?.position).toBe(2);
    expect(updated.data?.prompt).toBe("Updated");
    expect(published.data?.message).toBe("Quiz published successfully.");
    expect(deleted.error).toBeNull();
    expect(deleted.data).toBeNull();
    expect(deleted.status).toBe(204);

    const methods = fetchMock.mock.calls.map((call) => call[1].method);
    expect(methods).toEqual(["POST", "PATCH", "POST", "DELETE"]);
    expect(String(fetchMock.mock.calls[2][0])).toMatch(/\/lectures\/8\/publish\/$/);
    expect(String(fetchMock.mock.calls[3][0])).toMatch(/\/lectures\/8\/questions\/4\/$/);
  });
});
