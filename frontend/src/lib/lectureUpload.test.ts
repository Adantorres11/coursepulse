import { describe, expect, it } from "vitest";
import { isAllowedRecording, RECORDING_ACCEPT, uploadErrorMessage } from "./lectureUpload";

describe("isAllowedRecording", () => {
  it("accepts the formats the backend accepts, in any case", () => {
    expect(isAllowedRecording("lecture.mp3")).toBe(true);
    expect(isAllowedRecording("Lecture 4.MOV")).toBe(true);
    expect(isAllowedRecording("talk.webm")).toBe(true);
  });

  it("rejects formats the backend rejects", () => {
    expect(isAllowedRecording("notes.pdf")).toBe(false);
    expect(isAllowedRecording("clip.3gp")).toBe(false);
    expect(isAllowedRecording("mp3")).toBe(false);
  });

  it("builds the accept attribute from the same list", () => {
    expect(RECORDING_ACCEPT.split(",")).toContain(".mkv");
  });
});

describe("uploadErrorMessage", () => {
  it("reads the recording field error from the backend", () => {
    const body = JSON.stringify({ recording: ["Invalid audio or video file."] });
    expect(uploadErrorMessage(400, body)).toBe("Invalid audio or video file.");
  });

  it("reads the title error and the permission detail", () => {
    expect(uploadErrorMessage(400, JSON.stringify({ title: ["This field is required."] }))).toBe(
      "This field is required."
    );
    expect(
      uploadErrorMessage(403, JSON.stringify({ detail: "Only the class owner can upload lectures." }))
    ).toBe("Only the class owner can upload lectures.");
  });

  it("falls back to the HTTP status when the body is not useful", () => {
    expect(uploadErrorMessage(502, "<html>Bad Gateway</html>")).toBe(
      "Upload failed (HTTP 502). Please try again."
    );
    expect(uploadErrorMessage(500, "{}")).toBe("Upload failed (HTTP 500). Please try again.");
  });
});
