import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getLectures, type Lecture } from "../lib/apiClient";

interface EnrolledClass {
  id: string | number;
  name: string;
  code: string;
  instructor: string;
  quizCount: number;
  newQuizCount?: number;
  lectureId?: string | number;
}

interface StudentHubProps {
  onSelectQuiz?: (lectureId: number | string) => void;
}

export function StudentHub({ onSelectQuiz }: StudentHubProps = {}) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Class enrollment state
  const [classes, setClasses] = useState<EnrolledClass[]>([
    {
      id: "cs-201",
      name: "Data Structures",
      code: "CS 201",
      instructor: "Prof. Lin",
      quizCount: 4,
      newQuizCount: 2,
      lectureId: 1,
    },
    {
      id: "math-210",
      name: "Discrete Math",
      code: "MATH 210",
      instructor: "Prof. Okafor",
      quizCount: 6,
      newQuizCount: 1,
      lectureId: 2,
    },
    {
      id: "stat-301",
      name: "Probability and Statistics",
      code: "STAT 301",
      instructor: "Prof. Rivera",
      quizCount: 3,
      lectureId: 3,
    },
  ]);

  // Modal for joining a class with access code
  const [isJoinModalOpen, setIsJoinModalOpen] = useState(false);
  const [accessCode, setAccessCode] = useState("");
  const [joinSuccessMsg, setJoinSuccessMsg] = useState<string | null>(null);

  // Fetch real backend / sample lectures
  const fetchLectures = async () => {
    setLoading(true);
    setError(null);

    const result = await getLectures();

    if (result.error) {
      setError(result.error);
    } else if (result.data && result.data.length > 0) {
      // Sync classes with real lectures if available
      const mapped = result.data.map((lecture: Lecture, idx: number) => ({
        id: lecture.id,
        name: lecture.title,
        code: lecture.classroom || `CS ${300 + idx}`,
        instructor: "Course Faculty",
        quizCount: lecture.question_count ?? 5,
        newQuizCount: idx === 0 ? 2 : idx === 1 ? 1 : undefined,
        lectureId: lecture.id,
      }));
      setClasses(mapped);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchLectures();
  }, []);

  const handleClassClick = (targetLectureId?: string | number) => {
    const selectedId = targetLectureId || 1;
    if (onSelectQuiz) {
      onSelectQuiz(selectedId);
    } else {
      navigate(`/quiz/${selectedId}`);
    }
  };

  const handleJoinClassSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessCode.trim()) return;

    const newClass: EnrolledClass = {
      id: `class-${Date.now()}`,
      name: `Joined Class (${accessCode.toUpperCase()})`,
      code: accessCode.toUpperCase(),
      instructor: "Assigned Professor",
      quizCount: 5,
      newQuizCount: 1,
      lectureId: 1,
    };

    setClasses((prev) => [newClass, ...prev]);
    setAccessCode("");
    setJoinSuccessMsg(`Successfully joined ${newClass.code}!`);
    setTimeout(() => {
      setJoinSuccessMsg(null);
      setIsJoinModalOpen(false);
    }, 1200);
  };

  return (
    <div className="min-h-screen bg-[#0B1220] text-white flex flex-col justify-between selection:bg-sky-500/30">
      {/* Top Bar matching Mockups (CoursePulse Logo on left, Log out on right) */}
      <header className="px-4 sm:px-10 py-5 w-full max-w-5xl mx-auto flex items-center justify-between">
        <Link to="/" className="inline-flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center overflow-hidden shadow-sm">
            <img
              src="/assets/coursePulseLogo.png"
              alt="CoursePulse"
              className="w-full h-full object-cover"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                const fallback = e.currentTarget.parentElement?.querySelector(".hub-fallback-icon");
                if (fallback) fallback.classList.remove("hidden");
              }}
            />
            <svg
              className="hub-fallback-icon hidden w-5 h-5 text-white"
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

        {/* Log out link matching mockups */}
        <Link
          to="/login"
          className="text-sm font-semibold text-slate-300 hover:text-white transition-colors cursor-pointer"
        >
          Log out
        </Link>
      </header>

      {/* Main Container */}
      <main className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Title & Subtitle */}
        <div className="mb-8">
          <h1 className="text-3xl sm:text-4xl md:text-[42px] font-extrabold tracking-tight text-white mb-2">
            Your Classes
          </h1>
          {classes.length > 0 && (
            <p className="text-slate-400 text-sm">
              Choose a class to see its quizzes.
            </p>
          )}
        </div>

        {/* Loading Skeleton */}
        {loading ? (
          <div className="space-y-4 animate-pulse">
            <div className="h-44 bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6"></div>
            <div className="h-20 bg-slate-800/40 border border-slate-700/50 rounded-2xl"></div>
            <div className="h-20 bg-slate-800/40 border border-slate-700/50 rounded-2xl"></div>
          </div>
        ) : error ? (
          /* Error State */
          <div className="bg-red-950/40 border border-red-800/60 rounded-2xl p-8 text-center max-w-md mx-auto">
            <h2 className="text-xl font-semibold text-white mb-2">Failed to load classes</h2>
            <p className="text-red-300 text-sm mb-4">{error}</p>
            <button
              onClick={fetchLectures}
              className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : classes.length === 0 ? (
          /* Empty State — Matches Mockup 1 (No classes yet) */
          <div className="border-2 border-dashed border-slate-700/80 rounded-3xl p-10 sm:p-16 text-center max-w-3xl mx-auto flex flex-col items-center justify-center bg-[#10192E]/30">
            {/* Book Icon Badge */}
            <div className="w-14 h-14 rounded-2xl bg-[#142342] flex items-center justify-center mb-5 text-[#38BDF8] shadow-md">
              <svg
                className="w-7 h-7"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            </div>

            <h2 className="text-2xl sm:text-3xl font-bold text-white mb-2">
              No classes yet
            </h2>
            <p className="text-slate-400 text-sm max-w-md mx-auto mb-8 leading-relaxed">
              Join a class with the access code from your professor to see its quizzes.
            </p>

            <button
              type="button"
              onClick={() => setIsJoinModalOpen(true)}
              className="inline-flex items-center gap-2 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm px-6 py-3 rounded-xl transition-all shadow-lg shadow-sky-500/20 hover:scale-[1.02] cursor-pointer"
            >
              <span>Join a class</span>
              <span>→</span>
            </button>
          </div>
        ) : (
          /* Populated State — Matches Mockup 2 */
          <div className="space-y-4">
            {/* 1. Daily Streak Banner Card */}
            <div className="bg-[#141525] border border-amber-500/40 rounded-2xl p-5 sm:p-6 shadow-xl mb-6">
              {/* Header: Fire icon, streak title, and 'Best 9' badge */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3.5">
                  <div className="w-11 h-11 rounded-full bg-[#35251C] flex items-center justify-center text-amber-500 shrink-0 text-xl shadow-inner">
                    🔥
                  </div>
                  <div>
                    <h3 className="text-lg sm:text-xl font-bold text-white leading-tight">
                      4 day streak
                    </h3>
                    <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                      Play a quiz today to make it 5.
                    </p>
                  </div>
                </div>

                <div className="bg-[#2D211A] text-amber-400 border border-amber-600/40 text-xs font-bold px-3 py-1 rounded-full">
                  Best 9
                </div>
              </div>

              {/* Weekly Streak Dots (M, T, W, T, F, S, S) */}
              <div className="flex justify-between items-center max-w-md mx-auto mt-6 px-2 sm:px-4">
                {/* Monday - missed */}
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-400">M</span>
                  <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#18233C] border border-slate-800"></div>
                </div>

                {/* Tuesday - completed */}
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-400">T</span>
                  <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#F59E0B] flex items-center justify-center text-slate-950 font-bold text-sm shadow-sm">
                    ✓
                  </div>
                </div>

                {/* Wednesday - completed */}
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-400">W</span>
                  <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#F59E0B] flex items-center justify-center text-slate-950 font-bold text-sm shadow-sm">
                    ✓
                  </div>
                </div>

                {/* Thursday - completed */}
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-400">T</span>
                  <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#F59E0B] flex items-center justify-center text-slate-950 font-bold text-sm shadow-sm">
                    ✓
                  </div>
                </div>

                {/* Friday - completed */}
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-400">F</span>
                  <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#F59E0B] flex items-center justify-center text-slate-950 font-bold text-sm shadow-sm">
                    ✓
                  </div>
                </div>

                {/* Saturday (Today) - active streak target */}
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[11px] font-bold text-amber-400">S</span>
                  <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full border-2 border-dashed border-amber-400 flex items-center justify-center text-amber-400 bg-amber-400/10 text-xs shadow-sm animate-pulse">
                    🔥
                  </div>
                </div>

                {/* Sunday - upcoming */}
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-500">S</span>
                  <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#18233C] border border-slate-800"></div>
                </div>
              </div>
            </div>

            {/* 2. Class List Cards */}
            <div className="space-y-3.5">
              {classes.map((cls) => (
                <div
                  key={cls.id}
                  onClick={() => handleClassClick(cls.lectureId)}
                  className="group bg-[#111A30] hover:bg-[#14203D] border border-slate-800/90 hover:border-slate-700 rounded-2xl p-4 sm:p-5 flex items-center justify-between transition-all duration-150 shadow-lg cursor-pointer"
                >
                  {/* Left info with Book icon */}
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="w-11 h-11 sm:w-12 sm:h-12 rounded-xl bg-[#162547] flex items-center justify-center text-[#38BDF8] shrink-0 shadow-sm">
                      <svg
                        className="w-5 h-5 sm:w-6 sm:h-6"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                      </svg>
                    </div>

                    <div className="min-w-0">
                      <h3 className="text-base sm:text-lg font-bold text-white group-hover:text-sky-300 transition-colors truncate">
                        {cls.name}
                      </h3>
                      <p className="text-xs sm:text-sm text-slate-400 mt-0.5 truncate">
                        {cls.code} · {cls.instructor} · {cls.quizCount} quizzes
                      </p>
                    </div>
                  </div>

                  {/* Right actions (New badge + arrow button) */}
                  <div className="flex items-center gap-2.5 shrink-0 ml-4">
                    {cls.newQuizCount && (
                      <span className="bg-[#182645] border border-sky-500/40 text-sky-300 text-xs font-semibold px-3 py-1 rounded-full">
                        {cls.newQuizCount} new
                      </span>
                    )}
                    <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-[#1B294B] group-hover:bg-[#233560] flex items-center justify-center text-[#38BDF8] group-hover:translate-x-0.5 transition-all">
                      <svg
                        className="w-4 h-4"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <line x1="5" y1="12" x2="19" y2="12" />
                        <polyline points="12 5 19 12 12 19" />
                      </svg>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* 3. Bottom Banner — 'Have a class code?' */}
            <div className="border border-dashed border-slate-700/80 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#10192E]/60 shadow-lg mt-6">
              <div className="flex items-center gap-3.5">
                <div className="w-10 h-10 rounded-xl bg-[#162342] flex items-center justify-center text-[#38BDF8] shrink-0">
                  {/* Key Icon */}
                  <svg
                    className="w-5 h-5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle cx="7.5" cy="15.5" r="5.5" />
                    <path d="M21 2l-9.6 9.6" />
                    <path d="M15.5 7.5l3 3" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-sm sm:text-base font-bold text-white">
                    Have a class code?
                  </h4>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Enter the code from your professor to join.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setIsJoinModalOpen(true)}
                className="inline-flex items-center justify-center gap-2 bg-[#141C33] hover:bg-[#1A2645] border border-slate-700 hover:border-slate-500 text-white font-semibold text-xs sm:text-sm py-2.5 px-4 rounded-xl transition cursor-pointer self-start sm:self-auto"
              >
                <span>Join a class</span>
                <span>→</span>
              </button>
            </div>
          </div>
        )}

        {/* Demo Helper: Toggle between empty and populated states */}
        <div className="text-center mt-8">
          <button
            type="button"
            onClick={() => {
              if (classes.length > 0) {
                setClasses([]);
              } else {
                fetchLectures();
              }
            }}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors underline cursor-pointer"
          >
            {classes.length > 0
              ? "Preview Mockup 1 (Empty State: No classes yet)"
              : "Preview Mockup 2 (Populated State with Streak & Classes)"}
          </button>
        </div>
      </main>

      {/* Modal: Join a Class with Access Code */}
      {isJoinModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#10192E] border border-slate-800 rounded-2xl p-6 sm:p-7 max-w-md w-full shadow-2xl relative">
            <h3 className="text-xl font-bold text-white mb-2">Join a Class</h3>
            <p className="text-xs sm:text-sm text-slate-400 mb-5">
              Enter the unique 6-character access code provided by your instructor.
            </p>

            {joinSuccessMsg && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-950/60 border border-emerald-500/60 text-emerald-300 text-xs font-semibold">
                {joinSuccessMsg}
              </div>
            )}

            <form onSubmit={handleJoinClassSubmit}>
              <div className="mb-5">
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Class Access Code
                </label>
                <input
                  type="text"
                  value={accessCode}
                  onChange={(e) => setAccessCode(e.target.value)}
                  placeholder="e.g. CS3398"
                  autoFocus
                  className="w-full bg-[#0A101F] border border-slate-800 focus:border-[#38BDF8] text-white rounded-xl px-3.5 py-2.5 text-sm uppercase tracking-wider font-mono placeholder:normal-case placeholder:tracking-normal placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-[#38BDF8] transition"
                />
              </div>

              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsJoinModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-xs sm:text-sm px-5 py-2.5 rounded-xl transition cursor-pointer shadow-md"
                >
                  Join Class →
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="text-center text-xs text-slate-600 max-w-5xl mx-auto w-full py-6">
        CoursePulse © {new Date().getFullYear()} — Study Companion
      </footer>
    </div>
  );
}

export default StudentHub;
