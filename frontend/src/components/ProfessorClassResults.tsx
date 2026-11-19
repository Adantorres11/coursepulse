
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getClassResults } from "../lib/apiClient";
import { displayUsername } from "../lib/displayUsername";
import type { ClassResults } from "../types/api";

export function ProfessorClassResults() {
  const { classId } = useParams<{ classId: string }>();

  const [results, setResults] = useState<ClassResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    setLoading(true);
    setError(null);
    setResults(null);

    getClassResults(classId ?? "", controller.signal).then((result) => {
      if (controller.signal.aborted) return;

      if (result.error || !result.data) {
        setError(result.error || "Unable to load class results.");
      } else {
        setResults(result.data);
      }

      setLoading(false);
    });

    return () => controller.abort();
  }, [classId, reloadKey]);

  const students = [...(results?.students ?? [])].sort(
    (a, b) => b.total_points - a.total_points
  );

  const hasResults =
    students.some((student) => student.quizzes_played > 0) ||
    (results?.lectures ?? []).some((lecture) =>
      lecture.questions.some((question) => question.answer_count > 0)
    );

  return (
    <div className="min-h-screen bg-[#0B1220] text-white">
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <Link
          to={`/class/${classId}`}
          className="text-sky-400 hover:text-sky-300 text-sm font-semibold"
        >
          &larr; Back to class
        </Link>

        <h1 className="text-3xl font-extrabold mt-6 mb-2">
          Class Results
        </h1>

        <p className="text-slate-400 mb-8">
          Monitor student performance and quiz accuracy.
        </p>

        {/* Loading state */}
        {loading && (
          <div
            className="space-y-4 animate-pulse"
            role="status"
            aria-label="Loading class results"
          >
            {[1, 2, 3].map((item) => (
              <div
                key={item}
                className="h-24 rounded-2xl bg-slate-800"
              />
            ))}
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div role="alert" className="rounded-2xl bg-[#111A30] border border-slate-800 p-8 text-center">
            <h2 className="text-xl font-bold mb-2">
              Failed to load results
            </h2>

            <p className="text-slate-400 mb-5">{error}</p>

            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className="bg-sky-400 hover:bg-sky-500 text-slate-950 font-bold px-6 py-2 rounded-xl"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && results && (
          <>
            {/* Empty state */}
            {!hasResults && (
              <div className="border-2 border-dashed border-slate-700 rounded-2xl p-10 text-center mb-8">
                <h2 className="text-xl font-bold mb-2">
                  No results yet
                </h2>

                <p className="text-slate-400">
                  Results will appear once students complete quizzes.
                </p>
              </div>
            )}

            {/* Student leaderboard */}
            <section className="bg-[#111A30] border border-slate-800 rounded-2xl p-6 mb-8">
              <h2 className="text-xl font-bold mb-5">
                Student Leaderboard
              </h2>

              {students.length === 0 ? (
                <p className="text-slate-400">
                  No students enrolled yet.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-slate-400 border-b border-slate-700">
                      <tr>
                        <th className="py-3 px-2">Rank</th>
                        <th className="py-3 px-2">Student</th>
                        <th className="py-3 px-2">Total Points</th>
                        <th className="py-3 px-2">Quizzes Played</th>
                      </tr>
                    </thead>

                    <tbody>
                      {students.map((student) => (
                        <tr
                          key={student.student_id}
                          className="border-b border-slate-800"
                        >
                          <td className="py-4 px-2 text-sky-400 font-bold">
                            #{students.findIndex(
                              (entry) =>
                                entry.total_points === student.total_points
                            ) + 1}
                          </td>

                          <td className="py-4 px-2 font-semibold">
                            {displayUsername(student)}
                          </td>

                          <td className="py-4 px-2">
                            {student.total_points}
                          </td>

                          <td className="py-4 px-2">
                            {student.quizzes_played}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Question accuracy */}
            <section className="space-y-5">
              <h2 className="text-xl font-bold">
                Lecture Question Accuracy
              </h2>

              {results.lectures.length === 0 && (
                <p className="text-slate-400">
                  No lectures available yet.
                </p>
              )}

              {results.lectures.map((lecture) => {
                const answeredQuestions = lecture.questions.filter(
                  (question) =>
                    question.accuracy_percent !== null
                );

                const lowestAccuracy = answeredQuestions.length
                  ? Math.min(
                      ...answeredQuestions.map(
                        (question) =>
                          question.accuracy_percent!
                      )
                    )
                  : null;

                return (
                  <div
                    key={lecture.lecture_id}
                    className="bg-[#111A30] border border-slate-800 rounded-2xl p-6"
                  >
                    <h3 className="text-lg font-bold mb-5">
                      {lecture.title}
                    </h3>

                    {lecture.questions.length === 0 && (
                      <p className="text-slate-400">
                        No questions available.
                      </p>
                    )}

                    <div className="space-y-4">
                      {lecture.questions.map((question, index) => {
                        const isHardest =
                          lowestAccuracy !== null &&
                          question.accuracy_percent === lowestAccuracy;

                        return (
                          <div
                            key={question.question_id}
                            className={`rounded-xl border p-4 ${
                              isHardest
                                ? "border-amber-500/60 bg-amber-500/10"
                                : "border-slate-800 bg-[#0B1220]"
                            }`}
                          >
                            <div className="flex flex-wrap justify-between items-center gap-2 mb-3">
                              <p className="font-medium">
                                Q{index + 1}. {question.prompt}
                              </p>

                              {isHardest && (
                                <span className="text-xs font-bold text-amber-400">
                                  Hardest question
                                </span>
                              )}
                            </div>

                            <p className="text-sm text-slate-400 mb-3">
                              {question.answer_count === 0
                                ? "No answers yet"
                                : `${question.correct_count} of ${question.answer_count} answers correct`}
                            </p>

                            {question.accuracy_percent !== null && (
                              <div className="flex items-center gap-3">
                                <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      isHardest
                                        ? "bg-amber-400"
                                        : "bg-sky-400"
                                    }`}
                                    style={{
                                      width: `${question.accuracy_percent}%`,
                                    }}
                                  />
                                </div>

                                <span className="text-sm font-semibold">
                                  {question.accuracy_percent}%
                                </span>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
