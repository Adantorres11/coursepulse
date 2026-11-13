import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  createClass,
  getProfessorClasses,
  type ProfessorClass,
} from "../lib/apiClient";
import { useAuth } from "../context/AuthContext";

interface ProfessorDashboardProps {
  onSelectClass?: (classId: number) => void;
}

export function ProfessorDashboard({ onSelectClass }: ProfessorDashboardProps = {}) {
  const navigate = useNavigate();
  const { logout } = useAuth();

  // Dashboard class list state
  const [classes, setClasses] = useState<ProfessorClass[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Copy code feedback state
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  // Create class modal state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [newClassName, setNewClassName] = useState<string>("");
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccessMsg, setCreateSuccessMsg] = useState<string | null>(null);

  const fetchClasses = async () => {
    setLoading(true);
    setError(null);

    const token = sessionStorage.getItem("coursepulse_token");
    if (!token) {
      setClasses([]);
      setError("Please log in to view your classes.");
      setLoading(false);
      return;
    }

    const result = await getProfessorClasses();

    if (result.error || !result.data) {
      setClasses([]);
      setError(result.error || "Unable to load your classes.");
      setLoading(false);
      return;
    }

    setClasses(result.data);
    setLoading(false);
  };

  useEffect(() => {
    void fetchClasses();
  }, []);

  const handleClassClick = (classId: number) => {
    if (onSelectClass) {
      onSelectClass(classId);
    } else {
      navigate(`/class/${classId}`);
    }
  };

  const handleCopyCode = (e: React.MouseEvent, code: string) => {
    e.stopPropagation();
    void navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => {
      setCopiedCode((current) => (current === code ? null : current));
    }, 2000);
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newClassName.trim();
    if (!trimmed) {
      setCreateError("Class name is required.");
      return;
    }

    setIsCreating(true);
    setCreateError(null);
    setCreateSuccessMsg(null);

    const result = await createClass(trimmed);

    if (result.error || !result.data) {
      setCreateError(result.error || "Could not create class. Please try again.");
      setIsCreating(false);
      return;
    }

    const created = result.data;
    setCreateSuccessMsg(`Created "${created.name}"! Access code: ${created.access_code}`);

    // Prepend newly created class into the local state
    const newEntry: ProfessorClass = {
      id: created.id,
      name: created.name,
      access_code: created.access_code,
      student_count: 0,
      lecture_count: 0,
    };
    setClasses((prev) => [newEntry, ...prev.filter((c) => c.id !== created.id)]);

    setTimeout(() => {
      setIsCreating(false);
      setNewClassName("");
      setCreateSuccessMsg(null);
      setIsCreateModalOpen(false);
    }, 1200);
  };

  return (
    <div className="min-h-screen bg-[#0B1220] text-white flex flex-col justify-between selection:bg-sky-500/30">
      {/* Top Header Bar */}
      <header className="px-4 sm:px-10 py-5 w-full max-w-6xl mx-auto flex items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity"
        >
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center overflow-hidden shadow-sm">
            <img
              src="/assets/coursePulseLogo.png"
              alt="CoursePulse"
              className="w-full h-full object-cover"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                const fallback = e.currentTarget.parentElement?.querySelector(".prof-fallback-icon");
                if (fallback) fallback.classList.remove("hidden");
              }}
            />
            <svg
              className="prof-fallback-icon hidden w-5 h-5 text-white"
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
          <span className="hidden sm:inline-block ml-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">
            Professor
          </span>
        </Link>

        {/* Right actions: Create class button + Logout */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              setCreateError(null);
              setCreateSuccessMsg(null);
              setIsCreateModalOpen(true);
            }}
            className="inline-flex items-center gap-1.5 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-xs sm:text-sm px-3.5 sm:px-4 py-2 rounded-xl transition cursor-pointer shadow-md shadow-sky-500/20"
          >
            <span className="text-base leading-none font-extrabold">+</span>
            <span>Create class</span>
          </button>

          <button
            type="button"
            onClick={handleLogout}
            className="text-xs sm:text-sm font-semibold text-slate-300 hover:text-white px-2 py-1.5 rounded-lg transition-colors cursor-pointer"
          >
            Log out
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Title & Subtitle */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 mb-2 sm:hidden">
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">
                Professor Portal
              </span>
            </div>
            <h1 className="text-3xl sm:text-4xl md:text-[42px] font-extrabold tracking-tight text-white mb-2">
              Your Classes
            </h1>
            <p className="text-slate-400 text-sm sm:text-base max-w-xl">
              Manage your courses, share join codes with your students, and view lecture quizzes.
            </p>
          </div>

          {classes.length > 0 && !loading && !error && (
            <div className="text-xs text-slate-400 font-medium">
              Showing <span className="text-white font-bold">{classes.length}</span>{" "}
              {classes.length === 1 ? "class" : "classes"}
            </div>
          )}
        </div>

        {/* ======================================================== */}
        {/* 1. LOADING SKELETON STATE                                */}
        {/* ======================================================== */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 animate-pulse">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-56 bg-[#111A30]/60 border border-slate-800/80 rounded-2xl p-6 flex flex-col justify-between"
              >
                <div>
                  <div className="h-6 bg-slate-700/50 rounded-md w-3/4 mb-4" />
                  <div className="h-4 bg-slate-800 rounded-md w-1/2 mb-6" />
                  <div className="flex gap-2">
                    <div className="h-6 bg-slate-800/80 rounded-lg w-24" />
                    <div className="h-6 bg-slate-800/80 rounded-lg w-24" />
                  </div>
                </div>
                <div className="h-4 bg-slate-800/60 rounded w-1/3" />
              </div>
            ))}
          </div>
        )}

        {/* ======================================================== */}
        {/* 2. ERROR STATE WITH RETRY                                */}
        {/* ======================================================== */}
        {!loading && error && (
          <div className="bg-[#10192E] border border-slate-800 rounded-3xl p-8 sm:p-12 text-center max-w-xl mx-auto shadow-2xl flex flex-col items-center">
            {/* Warning Icon Badge */}
            <div className="w-14 h-14 rounded-full bg-[#2A1520] border border-rose-500/30 flex items-center justify-center mb-5 text-rose-400 text-2xl shadow-inner">
              !
            </div>

            <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
              Failed to load classes
            </h2>
            <p className="text-slate-400 text-sm max-w-md mx-auto mb-6 leading-relaxed">
              {error}
            </p>

            <button
              type="button"
              onClick={fetchClasses}
              className="inline-flex items-center gap-2 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm px-6 py-2.5 rounded-xl transition cursor-pointer shadow-md shadow-sky-500/20 active:scale-95"
            >
              <span>↻</span>
              <span>Retry</span>
            </button>
          </div>
        )}

        {/* ======================================================== */}
        {/* 3. "NO CLASSES YET" EMPTY STATE                          */}
        {/* ======================================================== */}
        {!loading && !error && classes.length === 0 && (
          <div className="border-2 border-dashed border-slate-700/80 rounded-3xl p-10 sm:p-16 text-center max-w-3xl mx-auto flex flex-col items-center justify-center bg-[#10192E]/30">
            {/* Presentation / Class icon */}
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
              Create your first class to generate a join code and start publishing lecture quizzes.
            </p>

            <button
              type="button"
              onClick={() => {
                setCreateError(null);
                setCreateSuccessMsg(null);
                setIsCreateModalOpen(true);
              }}
              className="inline-flex items-center gap-2 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm px-6 py-3 rounded-xl transition-all shadow-lg shadow-sky-500/20 hover:scale-[1.02] cursor-pointer"
            >
              <span>+ Create class</span>
              <span>→</span>
            </button>
          </div>
        )}

        {/* ======================================================== */}
        {/* 4. POPULATED STATE: CLASS CARDS GRID                     */}
        {/* ======================================================== */}
        {!loading && !error && classes.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {classes.map((cls) => (
              <div
                key={cls.id}
                onClick={() => handleClassClick(cls.id)}
                className="group bg-[#111A30] hover:bg-[#14203D] border border-slate-800/90 hover:border-slate-700 rounded-2xl p-5 sm:p-6 flex flex-col justify-between transition-all duration-150 shadow-lg cursor-pointer"
              >
                <div>
                  {/* Top row: Name & Arrow button */}
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <h3 className="text-lg sm:text-xl font-bold text-white group-hover:text-sky-300 transition-colors line-clamp-2">
                      {cls.name}
                    </h3>
                    <div className="w-8 h-8 rounded-xl bg-[#182647] group-hover:bg-[#233560] flex items-center justify-center text-[#38BDF8] shrink-0 group-hover:translate-x-0.5 transition-all">
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

                  {/* Join Code Chip */}
                  <div className="mb-5">
                    <div className="inline-flex items-center gap-2 bg-[#0A101F] border border-slate-800 rounded-xl px-3 py-1.5 shadow-inner">
                      <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                        Join Code:
                      </span>
                      <span className="font-mono font-bold text-sm tracking-wider text-[#38BDF8]">
                        {cls.access_code}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => handleCopyCode(e, cls.access_code)}
                        title="Copy join code to clipboard"
                        aria-label={`Copy join code ${cls.access_code}`}
                        className="ml-1 text-slate-400 hover:text-white transition p-1 rounded hover:bg-slate-800 cursor-pointer"
                      >
                        {copiedCode === cls.access_code ? (
                          <span className="text-[10px] font-bold text-emerald-400">
                            Copied!
                          </span>
                        ) : (
                          <svg
                            className="w-3.5 h-3.5"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Bottom stats: Student count & Lecture count */}
                <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                  <div className="flex items-center gap-1.5">
                    {/* Users Icon */}
                    <svg
                      className="w-4 h-4 text-sky-400/80"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                      <circle cx="9" cy="7" r="4" />
                      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                    </svg>
                    <span className="font-semibold text-slate-300">
                      {cls.student_count}
                    </span>
                    <span>{cls.student_count === 1 ? "student" : "students"}</span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {/* Document / Lecture Icon */}
                    <svg
                      className="w-4 h-4 text-sky-400/80"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                    </svg>
                    <span className="font-semibold text-slate-300">
                      {cls.lecture_count}
                    </span>
                    <span>{cls.lecture_count === 1 ? "lecture" : "lectures"}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* ======================================================== */}
      {/* 5. CREATE CLASS MODAL                                    */}
      {/* ======================================================== */}
      {isCreateModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-class-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
        >
          <div className="bg-[#10192E] border border-slate-800 rounded-2xl p-6 sm:p-7 max-w-md w-full shadow-2xl relative">
            <h3 id="create-class-title" className="text-xl font-bold text-white mb-2">
              Create a Class
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 mb-5">
              Enter your class name. A unique 6-character access code will be generated for your students to join.
            </p>

            {createError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-950/60 border border-rose-500/60 text-rose-300 text-xs font-semibold">
                {createError}
              </div>
            )}

            {createSuccessMsg && (
              <div className="mb-4 p-3 rounded-xl bg-emerald-950/60 border border-emerald-500/60 text-emerald-300 text-xs font-semibold">
                {createSuccessMsg}
              </div>
            )}

            <form onSubmit={handleCreateSubmit}>
              <div className="mb-5">
                <label
                  htmlFor="class-name-input"
                  className="block text-xs font-semibold text-slate-300 mb-1.5"
                >
                  Class Name
                </label>
                <input
                  id="class-name-input"
                  type="text"
                  value={newClassName}
                  onChange={(e) => {
                    setNewClassName(e.target.value);
                    if (createError) setCreateError(null);
                  }}
                  placeholder="e.g. CS 3398 Software Engineering"
                  autoFocus
                  disabled={isCreating}
                  className="w-full bg-[#0A101F] border border-slate-800 focus:border-[#38BDF8] text-white rounded-xl px-3.5 py-2.5 text-sm placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-[#38BDF8] transition disabled:opacity-50"
                />
              </div>

              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  disabled={isCreating}
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white transition cursor-pointer disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-xs sm:text-sm px-5 py-2.5 rounded-xl transition cursor-pointer shadow-md disabled:opacity-60"
                >
                  {isCreating ? "Creating…" : "Create class →"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="text-center text-xs text-slate-600 max-w-6xl mx-auto w-full py-6">
        CoursePulse © {new Date().getFullYear()} — Study Companion
      </footer>
    </div>
  );
}

export default ProfessorDashboard;

