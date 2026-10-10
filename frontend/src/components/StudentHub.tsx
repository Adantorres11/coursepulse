import { useEffect, useState } from "react";
import { getLectures, type Lecture } from "../lib/apiClient";

interface StudentHubProps {
  onSelectQuiz: (lectureId: number | string) => void;
}

export function StudentHub({ onSelectQuiz }: StudentHubProps) {
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLectures = async () => {
    setLoading(true);
    setError(null);

    const result = await getLectures();

    if (result.error) {
      setError(result.error);
      setLectures([]);
    } else {
      setLectures(result.data ?? []);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchLectures();
  }, []);

  const formatDate = (dateString?: string): string => {
    if (!dateString) return "Recently published";
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return dateString;
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-8">
      {/* Header */}
      <header className="mb-8 border-b border-slate-800 pb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse"></span>
            <h1 className="text-3xl font-bold tracking-tight text-white">Student Hub</h1>
          </div>
          <p className="text-slate-400 text-sm">
            Keep the pulse on your lectures — practice and test your knowledge.
          </p>
        </div>
      </header>

      {/* Loading Skeleton */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 animate-pulse h-52 flex flex-col justify-between"
            >
              <div>
                <div className="h-5 bg-slate-700 rounded-md w-1/3 mb-4"></div>
                <div className="h-6 bg-slate-700 rounded-md w-3/4 mb-2"></div>
                <div className="h-4 bg-slate-700 rounded-md w-1/2"></div>
              </div>
              <div className="h-9 bg-slate-700 rounded-xl w-full"></div>
            </div>
          ))}
        </div>
      ) : error ? (
        /* Error State */
        <div className="bg-red-950/40 border border-red-800/60 rounded-2xl p-8 text-center max-w-md mx-auto">
          <h2 className="text-xl font-semibold text-white mb-2">Failed to load lectures</h2>
          <p className="text-red-300 text-sm mb-4">{error}</p>
          <button
            onClick={fetchLectures}
            className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition"
          >
            Retry
          </button>
        </div>
      ) : lectures.length === 0 ? (
        /* Empty State (Acceptance Criteria) */
        <div className="bg-slate-800/40 border border-slate-800 rounded-2xl p-12 text-center max-w-md mx-auto">
          <div className="text-4xl mb-3">📚</div>
          <h2 className="text-xl font-semibold text-white mb-2">No quizzes available yet</h2>
          <p className="text-slate-400 text-sm leading-relaxed mb-6">
            There are no lecture quizzes published right now. Check back once your professor publishes one!
          </p>
          <button
            onClick={fetchLectures}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded-lg text-xs font-medium transition"
          >
            Refresh
          </button>
        </div>
      ) : (
        /* Card Grid (Acceptance Criteria) */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {lectures.map((lecture) => {
            const questionCount = lecture.question_count ?? 5;

            return (
              <div
                key={lecture.id}
                onClick={() => onSelectQuiz(lecture.id)}
                className="group bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 hover:border-indigo-500 rounded-2xl p-6 transition-all duration-200 shadow-lg hover:shadow-indigo-500/10 hover:-translate-y-1 flex flex-col justify-between cursor-pointer"
              >
                <div>
                  {/* "New Quiz" badge & question count */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-800/60">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                      New Quiz
                    </span>
                    <span className="text-xs font-medium text-slate-400 bg-slate-900/60 px-2.5 py-1 rounded-md border border-slate-700/50">
                      {questionCount} Questions
                    </span>
                  </div>

                  {/* Title */}
                  <h3 className="text-lg font-bold text-white group-hover:text-indigo-300 transition-colors mb-2">
                    {lecture.title}
                  </h3>

                  {/* Class */}
                  <p className="text-sm font-medium text-indigo-400/90 mb-1">
                    {lecture.classroom || "CS 3398 Software Engineering"}
                  </p>

                  {/* Date */}
                  <p className="text-xs text-slate-400">
                    Published {formatDate(lecture.published_at || lecture.publishedAt)}
                  </p>
                </div>

                {/* Footer button */}
                <div className="mt-6 pt-4 border-t border-slate-700/50 flex justify-between items-center">
                  <span className="text-xs text-slate-500 group-hover:text-slate-400 transition-colors">
                    Click card to play
                  </span>
                  <span className="text-indigo-400 group-hover:translate-x-1 transition-transform font-bold">
                    →
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default StudentHub;
