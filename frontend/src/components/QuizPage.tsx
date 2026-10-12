import { useEffect, useState } from "react";
import { getQuiz, type Quiz } from "../lib/apiClient";

interface QuizPageProps {
  lectureId: string | number;
  onBackToHub: () => void;
}

export function QuizPage({ lectureId, onBackToHub }: QuizPageProps) {
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

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

  return (
    <div className="w-full max-w-3xl mx-auto px-4 py-8">
      {/* Back button */}
      <button
        onClick={onBackToHub}
        className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors mb-6 cursor-pointer"
      >
        <span>←</span>
        <span>Back to Student Hub</span>
      </button>

      {loading ? (
        <div className="bg-slate-800/40 border border-slate-700/60 rounded-2xl p-8 text-center animate-pulse">
          <p className="text-slate-400">Loading quiz questions...</p>
        </div>
      ) : error || !quiz ? (
        /* Not-Found Message (Acceptance Criteria) */
        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-10 text-center max-w-lg mx-auto">
          <div className="text-4xl mb-3">🔍</div>
          <h2 className="text-xl font-bold text-white mb-2">Quiz Not Found</h2>
          <p className="text-slate-400 text-sm mb-6 leading-relaxed">
            {error || `We couldn't find any quiz questions for lecture #${lectureId}.`}
          </p>
          <button
            onClick={onBackToHub}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition cursor-pointer"
          >
            Return to Hub
          </button>
        </div>
      ) : (
        /* Quiz Loaded State */
        <div className="bg-slate-800/80 border border-slate-700 rounded-2xl p-8 shadow-xl">
          <div className="border-b border-slate-700/70 pb-4 mb-6">
            <span className="text-xs uppercase font-semibold text-indigo-400 tracking-wider">
              Lecture Quiz
            </span>
            <h2 className="text-2xl font-bold text-white mt-1">{quiz.title}</h2>
            <p className="text-slate-400 text-sm mt-1">
              {quiz.questions.length} questions loaded and ready to play.
            </p>
          </div>

          {/* Placeholder for the gameplay component (Arena / SCRUM-17) */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 text-center">
            <p className="text-slate-300 text-sm font-medium mb-4">
              Questions loaded successfully:
            </p>
            <ul className="text-left text-xs text-slate-400 space-y-2 max-w-md mx-auto">
              {quiz.questions.map((q, idx) => (
                <li key={q.id ?? idx} className="flex gap-2">
                  <span className="text-indigo-400 font-bold">{idx + 1}.</span>
                  <span>{q.prompt}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

export default QuizPage;
