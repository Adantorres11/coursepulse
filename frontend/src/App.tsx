import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import { StudentHub } from "./components/StudentHub";
import { QuizPage } from "./components/QuizPage";

export default function App() {
  return (
    <BrowserRouter>
      <main className="min-h-screen bg-slate-950 text-white flex flex-col">
        {/* Top Navbar */}
        <nav className="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur px-4 sm:px-6 py-4">
          <div className="max-w-5xl mx-auto flex items-center justify-between">
            <Link
              to="/"
              className="text-xl font-bold tracking-tight text-white hover:text-indigo-300 transition-colors flex items-center gap-2 cursor-pointer"
            >
              <span>CoursePulse</span>
            </Link>
          </div>
        </nav>

        {/* Screen Router */}
        <div className="flex-1 w-full">
          <Routes>
            <Route path="/" element={<StudentHub />} />
            <Route path="/quiz/:lectureId" element={<QuizPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </BrowserRouter>
  );
}

