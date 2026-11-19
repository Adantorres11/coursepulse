import { useEffect, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { getClassesRoute, getPartReview, isProfessor } from "../lib/apiClient";
import type { PartReview } from "../types/api";

export function PartReviewPage() {
  const { lectureId = "" } = useParams<{ lectureId: string }>();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const backTo = from ?? getClassesRoute();
  const backLabel = from ? "Class Hub" : isProfessor() ? "Created classes" : "Student Hub";
  const part = Number(searchParams.get("part"));

  const [review, setReview] = useState<PartReview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    if (!lectureId || !Number.isInteger(part) || part < 1) {
      setError("This review needs a part number.");
      setLoading(false);
      return;
    }
    getPartReview(lectureId, part).then((result) => {
      if (!active) return;
      if (result.error || !result.data) {
        setReview(null);
        setError(result.error ?? "This part has no completed attempt yet.");
      } else {
        setReview(result.data);
      }
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [lectureId, part]);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
      <Link
        to={backTo}
        className="mb-6 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"
      >
        <span aria-hidden="true">←</span>
        <span>Back to {backLabel}</span>
      </Link>

      {loading ? (
        <p className="text-slate-400">Loading your last attempt...</p>
      ) : error || !review ? (
        <div className="rounded-2xl border border-slate-700 bg-slate-800/50 p-8 text-center">
          <h1 className="text-xl font-bold text-white">No review yet</h1>
          <p className="mt-2 text-sm text-slate-400">{error}</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-700 bg-slate-800/80 p-6 shadow-xl sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-wider text-sky-300">
            Part {review.part} of {review.part_count}
          </p>
          <h1 className="mt-1 text-2xl font-bold text-white">{review.title}</h1>
          <p className="mt-2 text-lg font-bold text-sky-300">Score {review.total_points} pts</p>
          <ol className="mt-6 space-y-4">
            {review.questions.map((question, index) => (
              <li key={question.id} className="rounded-xl border border-slate-700 bg-[#0D1528] p-4">
                <p className="text-xs font-semibold uppercase text-slate-500">Question {index + 1}</p>
                <p className="mt-1 font-semibold text-white">{question.prompt}</p>
                <p className="mt-3 text-sm text-slate-300">
                  Your answer:{" "}
                  <span className="text-white">{question.your_answer ?? "No answer"}</span>
                </p>
                <p className="mt-1 text-sm text-slate-300">
                  Correct answer: <span className="text-emerald-300">{question.correct_answer}</span>
                </p>
                <p className="mt-2 text-sm font-bold text-sky-300">{question.points_awarded} pts</p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
