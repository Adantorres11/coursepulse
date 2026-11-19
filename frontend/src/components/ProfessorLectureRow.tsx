import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { lectureCanBeReviewed, lectureReviewPath } from "../lib/lectureReview";
import { formatLectureMeta } from "../lib/lectureSummary";
import type { ProfessorLecture } from "../types/api";

export function ProfessorLectureRow({
  lecture,
  classId,
  children,
}: {
  lecture: ProfessorLecture;
  classId: string;
  children?: ReactNode;
}) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="font-medium truncate">{lecture.title}</p>
          <p className="mt-1 text-xs text-slate-400">{formatLectureMeta(lecture)}</p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-xs font-semibold capitalize px-3 py-1 rounded-full bg-slate-800 text-sky-300">
            {lecture.status}
          </span>
          {lectureCanBeReviewed(lecture.status) && (
            <Link
              to={lectureReviewPath(classId, lecture.id)}
              className="text-sm font-semibold text-sky-400 hover:text-sky-300"
            >
              Review
            </Link>
          )}
        </div>
      </div>
      {children ? <div className="mt-4 border-t border-slate-800 pt-4">{children}</div> : null}
    </div>
  );
}
