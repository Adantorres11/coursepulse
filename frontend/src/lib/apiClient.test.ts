import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createClass, getQuiz } from "./apiClient";

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
});
