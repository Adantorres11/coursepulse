import { BrowserRouter, Routes, Route, Link, Navigate, useLocation } from "react-router-dom";
import { StudentHub } from "./components/StudentHub";
import { QuizPage } from "./components/QuizPage";
import { AuthPage } from "./components/AuthPage";
import { LandingPage } from "./components/LandingPage";

function AppContent() {
  const location = useLocation();
  const isAuthOrLandingPage =
    location.pathname === "/" ||
    location.pathname === "/landing" ||
    location.pathname === "/login" ||
    location.pathname === "/signup";

  return (
    <main className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* Top Navbar (hidden on dedicated landing and auth screens) */}
      {!isAuthOrLandingPage && (
        <nav className="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur px-4 sm:px-6 py-4">
          <div className="max-w-5xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link
                to="/"
                className="text-xl font-bold tracking-tight text-white hover:text-sky-300 transition-colors flex items-center gap-2 cursor-pointer"
              >
                <span>CoursePulse</span>
              </Link>
              <Link
                to="/hub"
                className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
              >
                Student Hub
              </Link>
            </div>
            <div className="flex items-center gap-3">
              <Link
                to="/login"
                className="text-sm font-semibold text-slate-300 hover:text-white px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
              >
                Log in
              </Link>
              <Link
                to="/signup"
                className="text-sm font-semibold bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] px-3.5 py-1.5 rounded-lg transition-all shadow-sm cursor-pointer"
              >
                Sign up
              </Link>
            </div>
          </div>
        </nav>
      )}

      {/* Screen Router */}
      <div className="flex-1 w-full">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/landing" element={<LandingPage />} />
          <Route path="/hub" element={<StudentHub />} />
          <Route path="/quiz/:lectureId" element={<QuizPage />} />
          <Route path="/login" element={<AuthPage initialTab="login" />} />
          <Route path="/signup" element={<AuthPage initialTab="signup" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}


