import { afterEach, describe, expect, it, vi } from "vitest";
import { writeClipboard } from "./clipboard";

describe("writeClipboard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns true only after writeText succeeds", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    await expect(writeClipboard("ABC123")).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith("ABC123");
  });

  it("returns false when writeText rejects", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    await expect(writeClipboard("ABC123")).resolves.toBe(false);
  });

  it("returns false when the clipboard is missing", async () => {
    vi.stubGlobal("navigator", {});

    await expect(writeClipboard("ABC123")).resolves.toBe(false);
  });
});
