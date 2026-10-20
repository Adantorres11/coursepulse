import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getQuiz, type Quiz } from "../lib/apiClient";
import QuizGame from "./quiz";

interface QuizPageProps {
  lectureId?: string | number;
  onBackToHub?: () => void;
}

export function QuizPage({ lectureId: propLectureId, onBackToHub }: QuizPageProps = {}) {
  const { lectureId: routeLectureId } = useParams<{ lectureId: string }>();
  const lectureId = propLectureId ?? routeLectureId ?? "";

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    if (!lectureId) {
      setError("No lecture ID provided.");
      setLoading(false);
      return;
    }

    getQuiz(lectureId).then((result) => {
      if (!isMounted) return;
      if (result.error || !result.data) {
        setError(result.error || `Quiz for lecture "${lectureId}" was not found.`);
        setQuiz(null);
      } else {
        setQuiz(result.data);
      }
      setLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [lectureId]);

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
        to="/hub"
        onClick={handleBackClick}
        className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors mb-6 cursor-pointer"
      >
        <span>←</span>
        <span>Back to Student Hub</span>
      </Link>

      {loading ? (
        <div className="bg-slate-800/40 border border-slate-700/60 rounded-2xl p-6 sm:p-8 text-center animate-pulse">
          <p className="text-slate-400">Loading quiz questions...</p>
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
            to="/hub"
            onClick={handleBackClick}
            className="inline-block px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition cursor-pointer"
          >
            Return to Hub
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

          {<QuizGame questions={quiz.questions} />}
        </div>
      )}
    </div>
  );
}

export default QuizPage;
