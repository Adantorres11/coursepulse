import { useEffect, useState } from "react";
import { useParams, useLocation, Link } from "react-router-dom";
import { getClassesRoute, getQuiz, isProfessor, request, type Quiz, type Lecture } from "../lib/apiClient";
import QuizGame from "./quiz";

interface QuizPageProps {
  lectureId?: string | number;
  onBackToHub?: () => void;
}

export function QuizPage({ lectureId: propLectureId, onBackToHub }: QuizPageProps = {}) {
  const { lectureId: routeLectureId } = useParams<{ lectureId: string }>();
  const lectureId = propLectureId ?? routeLectureId ?? "";

  // The Class Hub passes the page it came from; otherwise go to the Student Hub.
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const backTo = from ?? getClassesRoute();
  const backLabel = from
    ? "Class Hub"
    : isProfessor()
    ? "Created classes"
    : "Student Hub";

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [classroomId, setClassroomId] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | undefined>(undefined);
  const [reloadKey, setReloadKey] = useState<number>(0);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    setClassroomId(undefined);

    if (lectureId) {
      request<Lecture[]>("/lectures/", {
        signal: controller.signal,
      })
        .then((result) => {
          if (!active) return;

          // request() never throws. On error the quiz still plays and the
          // leaderboard button stays disabled because classroomId is undefined.
          const lecture = result.data?.find(
            (item) => String(item.id) === String(lectureId)
          );

          setClassroomId(lecture?.classroom_id);
        });
    }

    return () => {
      active = false;
      controller.abort();
    };
  }, [lectureId, reloadKey]);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);
    setErrorStatus(undefined);

    if (!lectureId) {
      setError("No lecture ID provided.");
      setLoading(false);
      return;
    }

    getQuiz(lectureId).then((result) => {
      if (!isMounted) return;
      if (result.error || !result.data) {
        // A 404 normally has server text; only an empty 200 body has none, and the Not Found card then shows its own message.
        setError(result.error ?? null);
        setErrorStatus(result.status);
        setQuiz(null);
      } else {
        setQuiz(result.data);
      }
      setLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [lectureId, reloadKey]);

  // Any failure except 404 can be retried. No lecture ID and empty data keep the Not Found card.
  const loadFailed = Boolean(lectureId) && Boolean(error) && errorStatus !== 404;

  const handleBackClick = (e: React.MouseEvent) => {
    if (onBackToHub) {
      e.preventDefault();
      onBackToHub();
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      {/* Back link to Hub */}
      <Link
        to={backTo}
        onClick={handleBackClick}
        className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors mb-6 cursor-pointer"
      >
        <span>←</span>
        <span>Back to {backLabel}</span>
      </Link>

      {loading ? (
        <div className="bg-slate-800/40 border border-slate-700/60 rounded-2xl p-6 sm:p-8 text-center animate-pulse">
          <p className="text-slate-400">Loading quiz questions...</p>
        </div>
      ) : loadFailed ? (
        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 sm:p-10 text-center max-w-lg mx-auto">
          <div className="text-4xl mb-3">⚠️</div>
          <h2 className="text-xl font-bold text-white mb-2">Could not load the quiz</h2>
          <p className="text-slate-400 text-sm mb-6 leading-relaxed">{error}</p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              type="button"
              onClick={() => setReloadKey((n) => n + 1)}
              className="inline-block px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition cursor-pointer"
            >
              Try again
            </button>
            <Link
              to={backTo}
              onClick={handleBackClick}
              className="inline-block px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition cursor-pointer"
            >
              Return to {backLabel}
            </Link>
          </div>
        </div>
      ) : error || !quiz ? (
        /* Not-Found / Error Placeholder Screen */
        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 sm:p-10 text-center max-w-lg mx-auto">
          <div className="text-4xl mb-3">🔍</div>
          <h2 className="text-xl font-bold text-white mb-2">Quiz Not Found</h2>
          <p className="text-slate-400 text-sm mb-6 leading-relaxed">
            {error || `We couldn't find any quiz questions for lecture #${lectureId}.`}
          </p>
          <Link
            to={backTo}
            onClick={handleBackClick}
            className="inline-block px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition cursor-pointer"
          >
            Return to {backLabel}
          </Link>
        </div>
      ) : (
        /* Quiz Placeholder Screen */
        <div className="bg-slate-800/80 border border-slate-700 rounded-2xl p-6 sm:p-8 shadow-xl">
          <div className="border-b border-slate-700/70 pb-4 mb-6">
            <span className="text-xs uppercase font-semibold text-indigo-400 tracking-wider">
              Lecture Quiz
            </span>
            <h2 className="text-xl sm:text-2xl font-bold text-white mt-1">{quiz.title}</h2>
            <p className="text-slate-400 text-sm mt-1">
              {quiz.questions.length} questions loaded and ready to play.
            </p>
          </div>

          {/* Interactive Gameplay Component */}
          <QuizGame
            questions={quiz.questions}
            lectureId={lectureId}
            initialAnsweredIds={quiz.answered_question_ids ?? []}
            initialScore={quiz.total_points ?? 0}
            classroomId={classroomId}
          />
        </div>
      )}
    </div>
  );
}

export default QuizPage;
