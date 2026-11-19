import { useState } from "react";
import type { ClassLectureStat } from "../types/api";
import {
  lectureScoreText,
  lectureSizeText,
  nextPlayablePart,
  partAction,
  partScoreText,
  partsOf,
} from "../lib/lectureParts";

function PartCircle({ filled }: { filled: boolean }) {
  return (
    <span
      className={`inline-block h-3.5 w-3.5 rounded-full border-2 ${
        filled ? "border-sky-400 bg-sky-400" : "border-slate-500 bg-transparent"
      }`}
      aria-hidden="true"
    />
  );
}

interface LecturePartsProps {
  lecture: ClassLectureStat;
  variant?: "next" | "list";
  onStart: (lectureId: number, part: number) => void;
  onReview: (lectureId: number, part: number) => void;
}

export function LectureParts({
  lecture,
  variant = "list",
  onStart,
  onReview,
}: LecturePartsProps) {
  const [open, setOpen] = useState(false);
  const parts = partsOf(lecture);
  const score = lectureScoreText(lecture);
  const next = nextPlayablePart(parts);
  const panelId = `lecture-${lecture.id}-parts`;
  const highlighted = variant === "next";

  return (
    <div
      className={
        highlighted
          ? "bg-[#101B33] border border-sky-500/40 rounded-2xl p-5 sm:p-6 shadow-xl"
          : "bg-[#111A30] border border-slate-800/90 rounded-2xl shadow-md"
      }
      data-testid={`lecture-${lecture.id}`}
    >
      <div className={`flex items-center justify-between gap-3 ${highlighted ? "" : "p-4 sm:p-5"}`}>
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <span
                className={`font-bold text-white ${
                  highlighted ? "text-xl sm:text-2xl" : "text-sm sm:text-base"
                }`}
              >
                {lecture.title}
              </span>
              <span className="inline-flex items-center gap-1.5">
                {parts.map((part) => (
                  <PartCircle key={part.part} filled={part.completed} />
                ))}
                <span className="sr-only">
                  {parts.filter((part) => part.completed).length} of {parts.length} parts completed
                </span>
              </span>
            </span>
            <span className="mt-1 block text-xs text-slate-400">{lectureSizeText(lecture)}</span>
          </span>
        </button>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {score ? (
            <span className="text-right text-xs font-bold text-sky-300 sm:text-sm">{score}</span>
          ) : lecture.is_new ? (
            <span className="rounded-full border border-sky-500/30 bg-[#162547] px-2.5 py-0.5 text-xs font-bold text-sky-400">
              New
            </span>
          ) : null}
          {highlighted && next && (
            <button
              type="button"
              onClick={() => onStart(lecture.id, next.part)}
              className="inline-flex items-center gap-2 rounded-xl bg-[#38BDF8] px-4 py-2.5 text-sm font-bold text-[#0A101D] shadow-lg shadow-sky-500/20 hover:bg-[#0EA5E9]"
            >
              {partAction(next) === "resume" ? "Resume" : "Start quiz"}
              <span aria-hidden="true">→</span>
            </button>
          )}
          <button
            type="button"
            aria-label={open ? `Hide parts of ${lecture.title}` : `Show parts of ${lecture.title}`}
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((value) => !value)}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#18233C] text-xs font-bold text-slate-300"
          >
            <span className={`inline-block transition ${open ? "rotate-90" : ""}`} aria-hidden="true">
              →
            </span>
          </button>
        </div>
      </div>

      {open && (
        <ul id={panelId} className={`space-y-2 ${highlighted ? "mt-4" : "px-4 pb-4 sm:px-5 sm:pb-5"}`}>
          {parts.map((part) => {
            const action = partAction(part);
            return (
              <li
                key={part.part}
                data-testid={`part-${lecture.id}-${part.part}`}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-[#0D1528] px-3 py-2.5"
              >
                <span className="flex items-center gap-2 text-sm text-white">
                  <PartCircle filled={part.completed} />
                  <span className="font-semibold">Part {part.part}</span>
                  <span className="text-xs text-slate-400">{partScoreText(part)}</span>
                </span>
                <span className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onStart(lecture.id, part.part)}
                    className="rounded-lg bg-[#38BDF8] px-3 py-1.5 text-xs font-bold text-[#0A101D] hover:bg-[#0EA5E9]"
                  >
                    {action === "resume" ? "Resume" : action === "replay" ? "Replay" : "Start"}
                  </button>
                  {part.completed && (
                    <button
                      type="button"
                      onClick={() => onReview(lecture.id, part.part)}
                      className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:border-slate-400"
                    >
                      Review
                    </button>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
