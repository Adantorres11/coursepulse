import { useEffect, useState } from "react";
import { StudentHub } from "./components/StudentHub";
import { QuizPage } from "./components/QuizPage";

export default function App() {
  const [currentPath, setCurrentPath] = useState<string>(
    typeof window !== "undefined" ? window.location.pathname : "/"
  );

  // Sync route when the user clicks the Browser Back or Forward buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigateTo = (path: string) => {
    window.history.pushState({}, "", path);
    setCurrentPath(path);
  };

  // Match /quiz/:lectureId
  const quizMatch = currentPath.match(/^\/quiz\/([^/]+)$/);
  const selectedLectureId = quizMatch ? quizMatch[1] : null;

  return (
    <main className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* Top Navbar */}
      <nav className="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <button
            onClick={() => navigateTo("/")}
            className="text-xl font-bold tracking-tight text-white hover:text-indigo-300 transition-colors flex items-center gap-2 cursor-pointer"
          >
            <span>CoursePulse</span>
          </button>
        </div>
      </nav>

      {/* Screen Router */}
      <div className="flex-1">
        {selectedLectureId ? (
          <QuizPage
            lectureId={selectedLectureId}
            onBackToHub={() => navigateTo("/")}
          />
        ) : (
          <StudentHub
            onSelectQuiz={(lectureId) => navigateTo(`/quiz/${lectureId}`)}
          />
        )}
      </div>
    </main>
  );
}
