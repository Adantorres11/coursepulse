/**
 * Maps lecture status and progress_message onto the professor-facing pipeline.
 * The server reports "part X of Y" while it transcribes and while it writes questions.
 */

export const LECTURE_STATUS_POLL_MS = 3000;

export type PipelineStage = "uploading" | "transcribing" | "writing" | "ready" | "failed";

export type StepState = "complete" | "current" | "upcoming" | "failed";

export interface PipelineStepView {
  id: "uploading" | "transcribing" | "writing" | "ready";
  label: string;
  state: StepState;
}

export interface PartProgress {
  current: number;
  total: number;
}

const STEP_ORDER = ["uploading", "transcribing", "writing", "ready"] as const;

const STEP_LABELS: Record<(typeof STEP_ORDER)[number], string> = {
  uploading: "Uploading",
  transcribing: "Transcribing",
  writing: "Writing questions",
  ready: "Ready",
};

const PART_PATTERN = /\bpart\s+(\d+)\s+of\s+(\d+)\b/i;

/** Question-generation heartbeats. Transcription heartbeats stay in the earlier stage. */
const QUESTION_STAGE =
  /key concepts|writing questions|writing more questions|checking questions|balancing answer|saving questions|trying that part again|question generation|transcript ready/i;

const WRITING_MARKS: ReadonlyArray<readonly [RegExp, number]> = [
  [/saving questions/i, 96],
  [/balancing answer/i, 90],
  [/checking questions/i, 84],
  [/writing more questions/i, 70],
  [/transcript ready|question generation/i, 8],
  [/trying that part again/i, 45],
  [/writing questions/i, 55],
  [/key concepts/i, 28],
];

const TRANSCRIBING_MARKS: ReadonlyArray<readonly [RegExp, number]> = [
  [/preparing audio/i, 24],
  [/checking the recording/i, 12],
  [/waiting to retry/i, 40],
];

export function lectureNeedsLiveProgress(status: string): boolean {
  return status === "pending" || status === "processing" || status === "failed";
}

/** Pulls "part 3 of 7" out of a progress message. Rejects backwards or empty ranges. */
export function parsePartProgress(message: string): PartProgress | null {
  const match = PART_PATTERN.exec(message);
  if (!match) return null;
  const current = Number(match[1]);
  const total = Number(match[2]);
  if (!Number.isInteger(current) || !Number.isInteger(total)) return null;
  if (total < 1 || current < 1 || current > total) return null;
  return { current, total };
}

export function partProgressPercent(part: PartProgress): number {
  return Math.round((part.current / part.total) * 100);
}

export function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function stageForLecture(status: string, progressMessage = ""): PipelineStage {
  if (status === "uploading") return "uploading";
  if (status === "failed") return "failed";
  if (status === "ready" || status === "published") return "ready";
  if (status === "processing" && QUESTION_STAGE.test(progressMessage)) return "writing";
  return "transcribing";
}

/**
 * Fill amount for the active stage. Part counts from the server win over fixed hints.
 * Returns null when the stage has no measurable progress yet (draw an indeterminate bar).
 */
export function stageBarPercent(options: {
  stage: PipelineStage;
  progressMessage?: string;
  uploadPercent?: number | null;
  status?: string;
}): number | null {
  const message = options.progressMessage ?? "";
  if (options.stage === "ready" || options.stage === "failed") return null;
  if (options.stage === "uploading") {
    if (options.uploadPercent == null) return null;
    return clampPercent(options.uploadPercent);
  }

  const part = parsePartProgress(message);
  if (part) return partProgressPercent(part);

  const marks = options.stage === "writing" ? WRITING_MARKS : TRANSCRIBING_MARKS;
  for (const [pattern, value] of marks) {
    if (pattern.test(message)) return value;
  }

  if (options.stage === "transcribing" && message.trim() === "" && options.status !== "processing") {
    return 8;
  }
  return null;
}

export function pipelineMessage(options: {
  stage: PipelineStage;
  progressMessage?: string;
  errorMessage?: string;
  status?: string;
}): string {
  const progress = (options.progressMessage ?? "").trim();
  const error = (options.errorMessage ?? "").trim();
  if (options.stage === "uploading") return "Uploading the recording";
  if (options.stage === "failed") return error || "Processing failed. Try again.";
  if (options.stage === "ready") return "Questions are ready for review.";
  if (progress) return progress;
  if (options.status === "processing") return "Working on this lecture";
  return "Waiting for processing to start";
}

export function pipelineSteps(stage: PipelineStage): PipelineStepView[] {
  if (stage === "failed") {
    return STEP_ORDER.map((id) => ({
      id,
      label: id === "ready" ? "Failed" : STEP_LABELS[id],
      state: id === "ready" ? "failed" : "upcoming",
    }));
  }
  if (stage === "ready") {
    return STEP_ORDER.map((id) => ({
      id,
      label: STEP_LABELS[id],
      state: "complete",
    }));
  }
  const currentIndex = STEP_ORDER.indexOf(stage);
  return STEP_ORDER.map((id, index) => ({
    id,
    label: STEP_LABELS[id],
    state: index < currentIndex ? "complete" : index === currentIndex ? "current" : "upcoming",
  }));
}
