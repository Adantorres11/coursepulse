import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getLectureStatus, getProfessorClassLectures, retryLecture } from "../lib/apiClient";
import { lectureReviewPath } from "../lib/lectureReview";
import {
  LECTURE_STATUS_POLL_MS,
  pipelineMessage,
  pipelineSteps,
  stageBarPercent,
  stageForLecture,
  type PipelineStage,
  type StepState,
} from "../lib/lectureProgress";
import type { LectureProcessingStatus } from "../types/api";
import { ProfessorNav } from "./ProfessorNav";

export interface LecturePipelineViewProps {
  stage: PipelineStage;
  message: string;
  percent: number | null;
  title?: string;
  notice?: string;
  reviewHref?: string | null;
  onRetry?: () => void;
  retrying?: boolean;
  retryError?: string | null;
  pollError?: string | null;
  framed?: boolean;
}

function marker(state: StepState, index: number): string {
  if (state === "complete") return "✓";
  if (state === "failed") return "!";
  return String(index + 1);
}

function markerClass(state: StepState): string {
  if (state === "complete") return "bg-emerald-400 text-slate-950";
  if (state === "current") return "bg-[#38BDF8] text-[#0A101D] ring-4 ring-sky-400/25";
  if (state === "failed") return "bg-rose-400 text-slate-950 ring-4 ring-rose-400/25";
  return "bg-slate-800 text-slate-500 ring-1 ring-slate-700";
}

function labelClass(state: StepState): string {
  if (state === "complete") return "text-emerald-300";
  if (state === "current") return "text-white";
  if (state === "failed") return "text-rose-300";
  return "text-slate-500";
}

export function LecturePipelineView({
  stage,
  message,
  percent,
  title,
  notice,
  reviewHref,
  onRetry,
  retrying = false,
  retryError,
  pollError,
  framed = true,
}: LecturePipelineViewProps) {
  const steps = pipelineSteps(stage);
  const current = steps.find((step) => step.state === "current" || step.state === "failed");
  const showBar = stage !== "ready" && stage !== "failed";

  return (
    <section
      aria-label="Lecture processing"
      className={
        framed
          ? "rounded-xl border border-slate-800 bg-[#0A101F] p-4 sm:p-5"
          : ""
      }
    >
      {title ? <h2 className="mb-4 text-lg font-bold tracking-tight text-white">{title}</h2> : null}

      <ol className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {steps.map((step, index) => (
          <li
            key={step.id}
            aria-current={step.state === "current" || step.state === "failed" ? "step" : undefined}
            className="min-w-0"
          >
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${markerClass(step.state)}`}
            >
              {marker(step.state, index)}
            </span>
            <p className={`mt-2 text-[11px] font-semibold leading-tight sm:text-xs ${labelClass(step.state)}`}>
              {step.label}
            </p>
          </li>
        ))}
      </ol>

      <div className="mt-4 flex items-start justify-between gap-3">
        <p
          aria-live="polite"
          role={stage === "failed" ? "alert" : "status"}
          className={`text-sm font-medium ${stage === "failed" ? "text-rose-300" : "text-slate-200"}`}
        >
          {message}
        </p>
        {showBar && percent != null ? (
          <p className="shrink-0 text-sm font-bold tabular-nums text-[#38BDF8]">{percent}%</p>
        ) : null}
      </div>

      {showBar ? (
        <div
          className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800"
          role="progressbar"
          aria-label={current?.label ?? "Lecture processing"}
          aria-valuemin={0}
          aria-valuemax={100}
          {...(percent == null ? { "aria-busy": true } : { "aria-valuenow": percent })}
        >
          {percent == null ? (
            <div className="h-full w-2/5 animate-pulse rounded-full bg-[#38BDF8]/80" />
          ) : (
            <div
              className="h-full rounded-full bg-[#38BDF8] transition-[width] duration-150"
              style={{ width: `${percent}%` }}
            />
          )}
        </div>
      ) : null}

      {stage === "ready" && notice ? (
        <p className="mt-4 rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-100">
          {notice}
        </p>
      ) : null}

      {stage === "ready" && reviewHref ? (
        <div className="mt-4">
          <Link
            to={reviewHref}
            className="inline-flex items-center rounded-xl bg-[#38BDF8] px-4 py-2 text-sm font-bold text-[#0A101D] hover:bg-[#0EA5E9]"
          >
            Review
          </Link>
        </div>
      ) : null}

      {stage === "failed" && onRetry ? (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying}
            className="rounded-xl bg-rose-400 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-rose-300 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {retrying ? "Retrying…" : "Retry"}
          </button>
          {retryError ? (
            <p role="alert" className="text-sm text-rose-300">
              {retryError}
            </p>
          ) : null}
        </div>
      ) : null}

      {pollError && stage !== "failed" && stage !== "ready" ? (
        <p className="mt-3 text-xs text-amber-300">{pollError}</p>
      ) : null}
    </section>
  );
}

interface LectureProcessingProps {
  lectureId: number;
  classId: string | number;
  title?: string;
  framed?: boolean;
  /** The class-page row already links to review once the lecture is ready. */
  showReviewLink?: boolean;
  onSettled?: (status: LectureProcessingStatus) => void;
}

export function LectureProcessing({
  lectureId,
  classId,
  title,
  framed = true,
  showReviewLink = true,
  onSettled,
}: LectureProcessingProps) {
  const [snapshot, setSnapshot] = useState<LectureProcessingStatus | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);
  const onSettledRef = useRef(onSettled);
  const mountedRef = useRef(true);
  onSettledRef.current = onSettled;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let settled = false;

    const schedule = () => {
      timer = setTimeout(() => {
        void poll();
      }, LECTURE_STATUS_POLL_MS);
    };

    async function poll() {
      const result = await getLectureStatus(lectureId);
      if (cancelled) return;
      if (result.data) {
        setSnapshot(result.data);
        setPollError(null);
        const terminal = result.data.status === "ready" || result.data.status === "failed";
        if (terminal) {
          if (!settled) {
            settled = true;
            onSettledRef.current?.(result.data);
          }
          return;
        }
      } else {
        setPollError(result.error ?? "Couldn't refresh status.");
      }
      if (!cancelled) schedule();
    }

    void poll();
    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [lectureId, retryNonce]);

  async function handleRetry() {
    setRetrying(true);
    setRetryError(null);
    const result = await retryLecture(lectureId);
    if (!mountedRef.current) return;
    setRetrying(false);
    if (result.error || !result.data) {
      setRetryError(result.error ?? "Couldn't retry this lecture.");
      return;
    }
    setSnapshot({
      id: result.data.id,
      status: "pending",
      progress_message: "",
      error_message: "",
      notice: "",
    });
    setRetryNonce((current) => current + 1);
  }

  const status = snapshot?.status ?? "pending";
  const progressMessage = snapshot?.progress_message ?? "";
  const stage = snapshot ? stageForLecture(status, progressMessage) : "transcribing";
  const message = snapshot
    ? pipelineMessage({
        stage,
        status,
        progressMessage,
        errorMessage: snapshot.error_message,
      })
    : "Checking status…";
  const percent = snapshot
    ? stageBarPercent({ stage, status, progressMessage })
    : null;
  const notice = snapshot?.status === "ready" ? snapshot.notice?.trim() ?? "" : "";

  return (
    <LecturePipelineView
      framed={framed}
      title={title}
      stage={stage}
      message={message}
      percent={percent}
      notice={notice}
      reviewHref={
        stage === "ready" && showReviewLink ? lectureReviewPath(classId, lectureId) : null
      }
      onRetry={stage === "failed" ? () => void handleRetry() : undefined}
      retrying={retrying}
      retryError={retryError}
      pollError={pollError}
    />
  );
}

export function LectureProcessingPage() {
  const { classId, lectureId } = useParams();
  const id = Number(lectureId);
  const valid = Boolean(classId) && Number.isInteger(id) && id > 0;
  const [title, setTitle] = useState("Lecture");

  useEffect(() => {
    if (!classId || !valid) return;
    let active = true;
    void getProfessorClassLectures(classId).then((result) => {
      if (!active) return;
      const match = result.data?.find((lecture) => lecture.id === id);
      if (match) setTitle(match.title);
    });
    return () => {
      active = false;
    };
  }, [classId, id, valid]);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <ProfessorNav />
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-8">
        <Link
          to={classId ? `/professor/class/${classId}` : "/professor"}
          className="text-sm text-sky-400 hover:text-sky-300"
        >
          ← Back to class
        </Link>
        {valid && classId ? (
          <div className="mt-6">
            <LectureProcessing lectureId={id} classId={classId} title={title} />
          </div>
        ) : (
          <p role="alert" className="mt-8 text-red-400">
            Invalid lecture.
          </p>
        )}
      </div>
    </div>
  );
}
