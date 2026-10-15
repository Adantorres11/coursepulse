import { Link } from "react-router-dom";

interface LandingPageProps {
  onTakeQuiz?: () => void;
}

export function LandingPage({ onTakeQuiz }: LandingPageProps = {}) {
  return (
    <div className="min-h-screen bg-[#0B1220] bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:28px_28px] text-white flex flex-col justify-between px-4 sm:px-6 py-8 sm:py-12 selection:bg-sky-500/30 overflow-x-hidden">
      {/* Top Navbar / Spacer */}
      <header className="max-w-5xl mx-auto w-full flex items-center justify-between">
        <Link to="/" className="inline-flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center overflow-hidden shadow-sm">
            <img
              src="/assets/coursePulseLogo.png"
              alt="CoursePulse"
              className="w-full h-full object-cover"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                const fallback = e.currentTarget.parentElement?.querySelector(".fallback-icon");
                if (fallback) fallback.classList.remove("hidden");
              }}
            />
            <svg
              className="fallback-icon hidden w-5 h-5 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M2 12a10 10 0 0 1 18-6" />
              <path d="M5 14a6 6 0 0 1 10-3" />
              <path d="M8 16a2 2 0 0 1 2-1" />
            </svg>
          </div>
          <span className="text-xl font-bold tracking-tight text-white">CoursePulse</span>
        </Link>

        {/* Auth shortcut links */}
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="text-sm font-semibold text-slate-300 hover:text-white px-3 py-1.5 rounded-lg transition-colors"
          >
            Log in
          </Link>
          <Link
            to="/signup"
            className="text-sm font-semibold bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] px-3.5 py-1.5 rounded-lg transition-all shadow-sm"
          >
            Sign up
          </Link>
        </div>
      </header>

      {/* Main Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center text-center my-12 sm:my-16 max-w-4xl mx-auto w-full">
        {/* Central Logo Container with Floating Difficulty Chips */}
        <div className="relative inline-flex items-center justify-center mb-6">
          {/* Chip 1: Easy +100 (Upper Left) */}
          <div className="absolute -top-6 -left-16 sm:-left-28 bg-[#10192E]/95 border border-slate-700/80 rounded-full px-3.5 py-1.5 shadow-xl shadow-black/40 backdrop-blur-md flex items-center gap-1.5 -rotate-6 select-none animate-pulse">
            <span className="text-xs font-medium text-slate-300">Easy</span>
            <span className="text-xs font-bold text-[#38BDF8]">+100</span>
          </div>

          {/* Chip 2: Medium +200 (Upper Right) */}
          <div className="absolute -top-8 -right-20 sm:-right-32 bg-[#10192E]/95 border border-slate-700/80 rounded-full px-3.5 py-1.5 shadow-xl shadow-black/40 backdrop-blur-md flex items-center gap-1.5 -rotate-3 select-none">
            <span className="text-xs font-medium text-slate-300">Medium</span>
            <span className="text-xs font-bold text-[#38BDF8]">+200</span>
          </div>

          {/* Chip 3: Hard +300 (Mid/Lower Right) */}
          <div className="absolute top-10 -right-24 sm:-right-36 bg-[#10192E]/95 border border-slate-700/80 rounded-full px-3.5 py-1.5 shadow-xl shadow-black/40 backdrop-blur-md flex items-center gap-1.5 rotate-3 select-none">
            <span className="text-xs font-medium text-slate-300">Hard</span>
            <span className="text-xs font-bold text-[#38BDF8]">+300</span>
          </div>

          {/* Large Center Circle Logo */}
          <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-full bg-white flex items-center justify-center p-3.5 shadow-2xl shadow-sky-500/15 ring-4 ring-slate-800/60">
            <img
              src="/assets/coursePulseLogo.png"
              alt="CoursePulse"
              className="w-full h-full object-contain"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                const fallback = e.currentTarget.parentElement?.querySelector(".fallback-hero-icon");
                if (fallback) fallback.classList.remove("hidden");
              }}
            />
            <svg
              className="fallback-hero-icon hidden w-16 h-16 text-blue-600"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M2 12a10 10 0 0 1 18-6" />
              <path d="M5 14a6 6 0 0 1 10-3" />
              <path d="M8 16a2 2 0 0 1 2-1" />
            </svg>
          </div>
        </div>

        {/* Brand Name */}
        <h1 className="text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white mb-3">
          CoursePulse
        </h1>

        {/* Tagline */}
        <p className="text-slate-400 text-base sm:text-lg leading-relaxed max-w-sm sm:max-w-md mx-auto mb-8 font-normal">
          Keep the pulse on what
          <br />
          you learned in lecture.
        </p>

        {/* "Take Quiz" Button */}
        {onTakeQuiz ? (
          <button
            type="button"
            onClick={onTakeQuiz}
            className="inline-flex items-center gap-2.5 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-base px-8 py-3.5 rounded-xl transition-all shadow-lg shadow-sky-500/25 hover:shadow-sky-500/40 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <span>Take Quiz</span>
            <span>→</span>
          </button>
        ) : (
          <Link
            to="/hub"
            className="inline-flex items-center gap-2.5 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-base px-8 py-3.5 rounded-xl transition-all shadow-lg shadow-sky-500/25 hover:shadow-sky-500/40 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <span>Take Quiz</span>
            <span>→</span>
          </Link>
        )}

        {/* Three Info Cards (Acceptance Criteria) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-5 w-full max-w-4xl mx-auto mt-16 sm:mt-24 text-left">
          {/* Card 1: Professor uploads */}
          <div className="bg-[#10192E]/90 border border-slate-800/90 rounded-2xl p-5 flex items-start gap-3.5 shadow-xl shadow-black/30 hover:border-slate-700 transition-colors">
            <div className="w-10 h-10 rounded-xl bg-[#090F1E] border border-slate-800/80 flex items-center justify-center shrink-0 text-[#38BDF8]">
              {/* Upload Icon */}
              <svg
                className="w-5 h-5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-bold text-white mb-1">Professor uploads</h3>
              <p className="text-xs text-slate-400 leading-snug">Lecture audio or slides.</p>
            </div>
          </div>

          {/* Card 2: AI writes the questions */}
          <div className="bg-[#10192E]/90 border border-slate-800/90 rounded-2xl p-5 flex items-start gap-3.5 shadow-xl shadow-black/30 hover:border-slate-700 transition-colors">
            <div className="w-10 h-10 rounded-xl bg-[#090F1E] border border-slate-800/80 flex items-center justify-center shrink-0 text-[#38BDF8]">
              {/* Sparkle Icon */}
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0L14.59 9.41L24 12L14.59 14.59L12 24L9.41 14.59L0 12L9.41 9.41L12 0Z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-bold text-white mb-1">AI writes the questions</h3>
              <p className="text-xs text-slate-400 leading-snug">Reviewed before they go live.</p>
            </div>
          </div>

          {/* Card 3: You play and climb */}
          <div className="bg-[#10192E]/90 border border-slate-800/90 rounded-2xl p-5 flex items-start gap-3.5 shadow-xl shadow-black/30 hover:border-slate-700 transition-colors">
            <div className="w-10 h-10 rounded-xl bg-[#090F1E] border border-slate-800/80 flex items-center justify-center shrink-0 text-[#38BDF8]">
              {/* Leaderboard / Bar Chart Icon */}
              <svg
                className="w-5 h-5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="18" y1="20" x2="18" y2="10" />
                <line x1="12" y1="20" x2="12" y2="4" />
                <line x1="6" y1="20" x2="6" y2="14" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-bold text-white mb-1">You play and climb</h3>
              <p className="text-xs text-slate-400 leading-snug">Earn points, move up the leaderboard.</p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-slate-600 max-w-5xl mx-auto w-full pt-6">
        CoursePulse © {new Date().getFullYear()} — Study Companion
      </footer>
    </div>
  );
}

export default LandingPage;
