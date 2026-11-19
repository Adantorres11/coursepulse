import { describe, expect, it } from "vitest";
import {
  lectureNeedsLiveProgress,
  parsePartProgress,
  partProgressPercent,
  pipelineMessage,
  pipelineSteps,
  stageBarPercent,
  stageForLecture,
} from "./lectureProgress";

describe("parsePartProgress", () => {
  it("reads part counts from transcription and question messages", () => {
    expect(parsePartProgress("Transcribing part 3 of 7")).toEqual({ current: 3, total: 7 });
    expect(parsePartProgress("Finding key concepts (part 1 of 7)")).toEqual({
      current: 1,
      total: 7,
    });
    expect(parsePartProgress("Writing questions (part 1 of 6)")).toEqual({
      current: 1,
      total: 6,
    });
    expect(parsePartProgress("WRITING QUESTIONS (PART 6 OF 6)")).toEqual({
      current: 6,
      total: 6,
    });
  });

  it("ignores messages that are not a forward part range", () => {
    expect(parsePartProgress("Preparing audio")).toBeNull();
    expect(parsePartProgress("Checking the recording")).toBeNull();
    expect(parsePartProgress("part 0 of 5")).toBeNull();
    expect(parsePartProgress("part 8 of 7")).toBeNull();
    expect(parsePartProgress("part 2 of 0")).toBeNull();
  });

  it("turns a part range into a percent of that stage", () => {
    expect(partProgressPercent({ current: 1, total: 7 })).toBe(14);
    expect(partProgressPercent({ current: 1, total: 6 })).toBe(17);
    expect(partProgressPercent({ current: 3, total: 7 })).toBe(43);
    expect(partProgressPercent({ current: 7, total: 7 })).toBe(100);
  });
});

describe("stageForLecture", () => {
  it("keeps upload, failure, and ready as their own stages", () => {
    expect(stageForLecture("uploading")).toBe("uploading");
    expect(stageForLecture("failed", "Transcribing part 1 of 4")).toBe("failed");
    expect(stageForLecture("ready")).toBe("ready");
    expect(stageForLecture("published")).toBe("ready");
  });

  it("treats pending and transcription heartbeats as transcribing", () => {
    expect(stageForLecture("pending")).toBe("transcribing");
    expect(stageForLecture("processing", "Checking the recording")).toBe("transcribing");
    expect(stageForLecture("processing", "Preparing audio")).toBe("transcribing");
    expect(stageForLecture("processing", "Transcribing part 2 of 4")).toBe("transcribing");
    expect(stageForLecture("processing", "Waiting to retry")).toBe("transcribing");
    expect(stageForLecture("processing", "")).toBe("transcribing");
  });

  it("treats question-generation heartbeats as writing questions", () => {
    expect(stageForLecture("processing", "Transcript ready. Starting question generation.")).toBe(
      "writing"
    );
    expect(stageForLecture("processing", "Finding key concepts (part 1 of 7)")).toBe("writing");
    expect(stageForLecture("processing", "Writing questions (part 1 of 6)")).toBe("writing");
    expect(stageForLecture("processing", "Writing more questions")).toBe("writing");
    expect(stageForLecture("processing", "Checking questions")).toBe("writing");
    expect(stageForLecture("processing", "Balancing answer choices")).toBe("writing");
    expect(stageForLecture("processing", "Saving questions")).toBe("writing");
    expect(stageForLecture("processing", "Trying that part again")).toBe("writing");
  });
});

describe("stageBarPercent", () => {
  it("uses the browser upload percent during upload", () => {
    expect(
      stageBarPercent({ stage: "uploading", uploadPercent: 42.2, status: "uploading" })
    ).toBe(42);
    expect(stageBarPercent({ stage: "uploading", uploadPercent: 140 })).toBe(100);
    expect(stageBarPercent({ stage: "uploading", uploadPercent: null })).toBeNull();
  });

  it("moves within a stage from part X of Y", () => {
    expect(
      stageBarPercent({
        stage: "transcribing",
        status: "processing",
        progressMessage: "Transcribing part 3 of 7",
      })
    ).toBe(43);
    expect(
      stageBarPercent({
        stage: "writing",
        status: "processing",
        progressMessage: "Finding key concepts (part 1 of 7)",
      })
    ).toBe(14);
    expect(
      stageBarPercent({
        stage: "writing",
        status: "processing",
        progressMessage: "Writing questions (part 6 of 6)",
      })
    ).toBe(100);
  });

  it("uses a fixed hint when the message has no part count", () => {
    expect(
      stageBarPercent({
        stage: "transcribing",
        status: "processing",
        progressMessage: "Checking the recording",
      })
    ).toBe(12);
    expect(
      stageBarPercent({
        stage: "transcribing",
        status: "processing",
        progressMessage: "Preparing audio",
      })
    ).toBe(24);
    expect(
      stageBarPercent({
        stage: "writing",
        status: "processing",
        progressMessage: "Saving questions",
      })
    ).toBe(96);
    expect(
      stageBarPercent({
        stage: "writing",
        status: "processing",
        progressMessage: "Transcript ready. Starting question generation.",
      })
    ).toBe(8);
  });

  it("stays indeterminate for an unknown processing message and hides on a finished lecture", () => {
    expect(
      stageBarPercent({
        stage: "transcribing",
        status: "processing",
        progressMessage: "Doing something new",
      })
    ).toBeNull();
    expect(stageBarPercent({ stage: "transcribing", status: "pending", progressMessage: "" })).toBe(
      8
    );
    expect(stageBarPercent({ stage: "ready", status: "ready" })).toBeNull();
    expect(stageBarPercent({ stage: "failed", status: "failed" })).toBeNull();
  });
});

describe("pipeline copy", () => {
  it("shows the server progress message, the error, or a short waiting line", () => {
    expect(pipelineMessage({ stage: "uploading" })).toBe("Uploading the recording");
    expect(
      pipelineMessage({
        stage: "transcribing",
        status: "processing",
        progressMessage: "Transcribing part 3 of 7",
      })
    ).toBe("Transcribing part 3 of 7");
    expect(pipelineMessage({ stage: "transcribing", status: "pending" })).toBe(
      "Waiting for processing to start"
    );
    expect(
      pipelineMessage({
        stage: "failed",
        status: "failed",
        errorMessage: "No speech was detected.",
      })
    ).toBe("No speech was detected.");
    expect(pipelineMessage({ stage: "ready", status: "ready" })).toBe(
      "Questions are ready for review."
    );
  });

  it("marks the active step and replaces Ready when processing fails", () => {
    expect(pipelineSteps("uploading").map((step) => step.state)).toEqual([
      "current",
      "upcoming",
      "upcoming",
      "upcoming",
    ]);
    expect(pipelineSteps("writing").map((step) => [step.label, step.state])).toEqual([
      ["Uploading", "complete"],
      ["Transcribing", "complete"],
      ["Writing questions", "current"],
      ["Ready", "upcoming"],
    ]);
    expect(pipelineSteps("ready").every((step) => step.state === "complete")).toBe(true);
    expect(pipelineSteps("failed").map((step) => [step.label, step.state])).toEqual([
      ["Uploading", "upcoming"],
      ["Transcribing", "upcoming"],
      ["Writing questions", "upcoming"],
      ["Failed", "failed"],
    ]);
  });

  it("flags lectures that still need the live panel", () => {
    expect(lectureNeedsLiveProgress("pending")).toBe(true);
    expect(lectureNeedsLiveProgress("processing")).toBe(true);
    expect(lectureNeedsLiveProgress("failed")).toBe(true);
    expect(lectureNeedsLiveProgress("ready")).toBe(false);
    expect(lectureNeedsLiveProgress("published")).toBe(false);
  });
});
