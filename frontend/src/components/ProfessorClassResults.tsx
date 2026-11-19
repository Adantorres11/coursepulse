import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getClassResults } from "../lib/apiClient";
import {
  formatClassAverage,
  formatLectureScore,
  formatPercent,
  formatPlayedCount,
  formatStudentAccuracy,
} from "../lib/lectureSummary";
import { personLabel } from "../lib/person";
import type {
  ClassResultLecture,
  ClassResultLectureScore,
  ClassResultStudent,
  ClassResults,
} from "../types/api";
import { ProfessorNav } from "./ProfessorNav";

function playFor(
  student: ClassResultStudent,
  lectureId: number
): ClassResultLectureScore {
  return (
    student.lectures.find((row) => row.lecture_id === lectureId) ?? {
      lecture_id: lectureId,
      played: false,
      score: null,
      correct_count: null,
    }
  );
}

function ranksFor(students: ClassResultStudent[]): number[] {
  let rank = 0;
  let previous: number | null = null;
  return students.map((student, index) => {
    if (student.total_points !== previous) rank = index + 1;
    previous = student.total_points;
    return rank;
  });
}

export function ProfessorClassResults() {
  const { classId } = useParams<{ classId: string }>();
  const location = useLocation();
  const onProfessorRoute = location.pathname.startsWith("/professor/");

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

  const backTo = onProfessorRoute
    ? `/professor/class/${classId}`
    : `/class/${classId}`;
  const students = results?.students ?? [];
  const lectures = results?.lectures ?? [];
  const ranks = ranksFor(students);
  const anyonePlayed = students.some((student) =>
    student.lectures.some((lecture) => lecture.played)
  );

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <ProfessorNav
        currentClass={
          results
            ? { id: results.classroom_id, name: results.classroom }
            : classId
              ? { id: classId, name: "Results" }
              : null
        }
      />

      <main className="max-w-6xl mx-auto px-4 sm:px-8 py-8">
        <Link
          to={backTo}
          className="text-sky-400 hover:text-sky-300 text-sm"
        >
          ← Back to class
        </Link>

        <h1 className="text-3xl font-bold mt-6">
          {results?.classroom ? `${results.classroom} results` : "Class results"}
        </h1>
        <p className="text-slate-400 mt-2 max-w-2xl">
          Best completed play for each published lecture. Total points follow
          the class ranking and count the first play only.
        </p>

        {loading && (
          <p className="mt-8 text-slate-400" role="status">
            Loading results...
          </p>
        )}

        {!loading && error && (
          <div
            role="alert"
            className="mt-8 rounded-xl bg-slate-900 border border-slate-800 p-8 text-center"
          >
            <h2 className="text-xl font-bold mb-2">Couldn&apos;t load results</h2>
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

        {!loading && !error && results && students.length === 0 && lectures.length === 0 && (
          <div className="mt-8 border border-dashed border-slate-700 rounded-xl p-10 text-center">
            <h2 className="text-xl font-bold mb-2">No results yet</h2>
            <p className="text-slate-400">
              Results show up here after you publish a lecture and students join.
            </p>
          </div>
        )}

        {!loading && !error && results && (students.length > 0 || lectures.length > 0) && (
          <div className="mt-8 space-y-8">
            {!anyonePlayed && (
              <p className="text-slate-400">
                No one has finished a published lecture yet.
              </p>
            )}

            <section className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-xl font-bold mb-5">Total points</h2>
              {students.length === 0 ? (
                <p className="text-slate-400">No students enrolled yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="py-3 pr-4 font-medium">Rank</th>
                        <th className="py-3 pr-4 font-medium">Student</th>
                        <th className="py-3 pr-4 font-medium">Total points</th>
                        <th className="py-3 font-medium">Lectures played</th>
                      </tr>
                    </thead>
                    <tbody>
                      {students.map((student, index) => (
                        <tr key={student.student_id} className="border-b border-slate-800/80">
                          <td className="py-4 pr-4 text-sky-300 font-semibold">
                            {ranks[index]}
                          </td>
                          <td className="py-4 pr-4 font-medium">
                            {personLabel(student)}
                          </td>
                          <td className="py-4 pr-4">{student.total_points}</td>
                          <td className="py-4">{student.quizzes_played}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {lectures.length === 0 ? (
              <p className="text-slate-400">No published lectures yet.</p>
            ) : (
              lectures.map((lecture) => (
                <LectureResult
                  key={lecture.lecture_id}
                  lecture={lecture}
                  students={students}
                />
              ))
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function LectureResult({
  lecture,
  students,
}: {
  lecture: ClassResultLecture;
  students: ClassResultStudent[];
}) {
  const plays = students.map((student) => playFor(student, lecture.lecture_id));
  const scores = plays
    .filter((play) => play.played && play.score !== null)
    .map((play) => play.score as number);
  const average = scores.length
    ? scores.reduce((sum, score) => sum + score, 0) / scores.length
    : null;
  const answered = lecture.questions.filter(
    (question) => question.accuracy_percent !== null
  );
  const percents = answered.map((question) => question.accuracy_percent as number);
  const lowest = percents.length ? Math.min(...percents) : null;
  const highest = percents.length ? Math.max(...percents) : null;

  return (
    <section className="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <h2 className="text-xl font-bold">{lecture.title}</h2>
        <p className="text-sm text-slate-400">
          {formatPlayedCount(scores.length)} · {formatClassAverage(average)}
        </p>
      </div>

      {students.length === 0 ? (
        <p className="text-slate-400 mb-6">No students enrolled yet.</p>
      ) : (
        <div className="overflow-x-auto mb-6">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3 pr-4 font-medium">Student</th>
                <th className="py-3 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {students.map((student) => {
                const play = playFor(student, lecture.lecture_id);
                const label = formatLectureScore(play);
                return (
                  <tr key={student.student_id} className="border-b border-slate-800/80">
                    <td className="py-4 pr-4 font-medium">{personLabel(student)}</td>
                    <td className={`py-4 ${play.played ? "text-white" : "text-slate-500"}`}>
                      {label}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-3">
        Questions
      </h3>
      {lecture.questions.length === 0 ? (
        <p className="text-slate-400">No questions on this lecture.</p>
      ) : (
        <div className="space-y-3">
          {lecture.questions.map((question, index) => {
            const hardest = lowest !== null
              && highest !== null
              && lowest < highest
              && question.accuracy_percent === lowest;
            return (
              <div
                key={question.question_id}
                className={`rounded-xl border p-4 ${
                  hardest
                    ? "border-amber-500/50 bg-amber-500/10"
                    : "border-slate-800 bg-slate-950"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-medium">
                    {index + 1}. {question.prompt}
                  </p>
                  {hardest && (
                    <span className="text-xs font-bold text-amber-300">
                      Hardest question
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-400 mt-2">
                  {formatStudentAccuracy(question)}
                </p>
                {question.accuracy_percent !== null && (
                  <div className="flex items-center gap-3 mt-3">
                    <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${hardest ? "bg-amber-400" : "bg-sky-400"}`}
                        style={{ width: `${question.accuracy_percent}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold">
                      {formatPercent(question.accuracy_percent)}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
