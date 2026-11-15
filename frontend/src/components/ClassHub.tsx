import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  getClasses,
  getClassesRoute,
  getClassStats,
  getProfessorClasses,
  isProfessor,
  type ClassStats,
  type ClassSummary,
  type ProfessorClass,
} from "../lib/apiClient";
import { LeaderboardModal } from "./LeaderboardModal";

type HubState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; classInfo: ClassSummary; stats: ClassStats }
  | { status: "professor"; classInfo: ProfessorClass };

export function ClassHub() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();

  const [state, setState] = useState<HubState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [isLeaderboardOpen, setIsLeaderboardOpen] = useState(false);

  const reload = () => setReloadKey((k) => k + 1);

  // Load class data based on role (professor vs student)
  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    if (isProfessor()) {
      getProfessorClasses().then((result) => {
        if (cancelled) return;
        if (result.error || !result.data) {
          setState({
            status: "error",
            message: result.error || "Unable to load this class.",
          });
          return;
        }

        const profClass = result.data.find(
          (c) => String(c.id) === String(classId)
        );
        if (!profClass) {
          setState({
            status: "error",
            message: "We could not find this class in your dashboard.",
          });
          return;
        }

        setState({ status: "professor", classInfo: profClass });
      });

      return () => {
        cancelled = true;
      };
    }

    Promise.all([getClassStats(classId ?? ""), getClasses()]).then(
      ([statsResult, classesResult]) => {
        // A newer load started (class changed or Retry), so drop this answer.
        if (cancelled) return;

        if (statsResult.error || !statsResult.data) {
          setState({ status: "error", message: statsResult.error || "Unable to load this class." });
          return;
        }
        if (classesResult.error || !classesResult.data) {
          setState({ status: "error", message: classesResult.error || "Unable to load this class." });
          return;
        }

        const stats = statsResult.data;
        const classInfo = classesResult.data.find((c) => c.id === stats.classroom_id);
        if (!classInfo) {
          setState({ status: "error", message: "We could not find this class." });
          return;
        }
        setState({ status: "ready", classInfo, stats });
      }
    );

    return () => {
      cancelled = true;
    };
  }, [classId, reloadKey]);

  const classInfo = state.status === "ready" ? state.classInfo : null;
  const stats = state.status === "ready" ? state.stats : null;
  const moreLectures = stats ? stats.lectures.filter((l) => l.id !== stats.up_next?.id) : [];

  const handleStartQuiz = (lectureId: number) => {
    // Remember where the student came from so the quiz can link back here.
    navigate(`/quiz/${lectureId}`, { state: { from: `/class/${classId}` } });
  };

  const backRoute = getClassesRoute();
  const backLabel = isProfessor() ? "Created classes" : "All classes";

  return (
    <div className="min-h-screen bg-[#0B1220] text-white flex flex-col justify-between selection:bg-sky-500/30">
      {/* Top Bar with Brand Logo */}
      <header className="px-4 sm:px-10 py-5 w-full max-w-5xl mx-auto flex items-center justify-between">
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
                const fallback = e.currentTarget.parentElement?.querySelector(".class-fallback-icon");
                if (fallback) fallback.classList.remove("hidden");
              }}
            />
            <svg
              className="class-fallback-icon hidden w-5 h-5 text-white"
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

        {/* Back Link to All Classes (Student Hub) or Created Classes (Professor Dashboard) */}
        <Link
          to={backRoute}
          className="text-xs sm:text-sm font-semibold text-slate-400 hover:text-white transition-colors cursor-pointer"
        >
          {backLabel}
        </Link>
      </header>

      {/* Main Container */}
      <main className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Navigation Breadcrumb */}
        <div className="mb-4">
          <Link
            to={backRoute}
            className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-semibold text-slate-400 hover:text-white transition-colors cursor-pointer group"
          >
            <span className="transition-transform group-hover:-translate-x-1 font-bold">←</span>
            <span>{backLabel}</span>
          </Link>
        </div>

        {/* Class Header Title & Subtitle */}
        <div className="mb-8">
          <h1 className="text-3xl sm:text-4xl md:text-[42px] font-extrabold tracking-tight text-white mb-1.5">
            {state.status === "professor"
              ? state.classInfo.name
              : classInfo
              ? classInfo.name
              : "Class"}
          </h1>
          <p className="text-slate-400 text-sm sm:text-base">
            {state.status === "loading"
              ? "Loading class details..."
              : state.status === "professor"
              ? `Join code: ${state.classInfo.access_code} · ${state.classInfo.student_count} students · ${state.classInfo.lecture_count} lectures`
              : classInfo
              ? `${classInfo.course_code} · ${classInfo.professor?.name ?? "Professor not assigned"}`
              : ""}
          </p>
        </div>

        {/* ======================================================== */}
        {/* STATE 1: LOADING SKELETON (Matching Mockup 3)            */}
        {/* ======================================================== */}
        {state.status === "loading" && (
          <div className="space-y-4 animate-pulse">
            <div className="h-24 bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 flex items-center justify-between">
              <div className="space-y-2.5 w-1/2">
                <div className="h-4 bg-slate-700/60 rounded-md w-3/4"></div>
                <div className="h-3 bg-slate-800/80 rounded-md w-1/2"></div>
              </div>
              <div className="w-10 h-10 bg-slate-700/50 rounded-xl"></div>
            </div>

            <div className="h-24 bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 flex items-center justify-between">
              <div className="space-y-2.5 w-2/5">
                <div className="h-4 bg-slate-700/60 rounded-md w-4/5"></div>
                <div className="h-3 bg-slate-800/80 rounded-md w-2/3"></div>
              </div>
              <div className="w-10 h-10 bg-slate-700/50 rounded-xl"></div>
            </div>

            <div className="h-24 bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 flex items-center justify-between">
              <div className="space-y-2.5 w-1/2">
                <div className="h-4 bg-slate-700/60 rounded-md w-3/4"></div>
                <div className="h-3 bg-slate-800/80 rounded-md w-1/3"></div>
              </div>
              <div className="w-10 h-10 bg-slate-700/50 rounded-xl"></div>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STATE 2: ERROR STATE (Matching Mockup 1)                 */}
        {/* ======================================================== */}
        {state.status === "error" && (
          <div className="bg-[#10192E] border border-slate-800 rounded-3xl p-8 sm:p-12 text-center max-w-2xl mx-auto shadow-2xl flex flex-col items-center">
            {/* Red Warning Icon */}
            <div className="w-14 h-14 rounded-full bg-[#2A1520] border border-rose-500/30 flex items-center justify-center mb-5 text-rose-400 text-2xl shadow-inner">
              !
            </div>

            <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
              Couldn't load class details
            </h2>
            <p className="text-slate-400 text-sm max-w-sm mx-auto mb-6 leading-relaxed">
              {state.message}
            </p>

            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={reload}
                className="inline-flex items-center gap-2 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm px-6 py-2.5 rounded-xl transition cursor-pointer shadow-md shadow-sky-500/20 active:scale-95"
              >
                <span>↻</span>
                <span>Retry</span>
              </button>
              {isProfessor() && (
                <Link
                  to="/professor"
                  className="inline-flex items-center gap-2 bg-[#141C33] hover:bg-[#1A2645] border border-slate-700 text-white font-semibold text-sm px-5 py-2.5 rounded-xl transition cursor-pointer"
                >
                  ← Back to created classes
                </Link>
              )}
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STATE 2.5: PROFESSOR CLASS VIEW                          */}
        {/* ======================================================== */}
        {state.status === "professor" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 sm:gap-4">
              {/* Card 1: Join Code */}
              <div className="bg-[#111A30] border border-slate-800/90 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    <svg className="w-3.5 h-3.5 text-sky-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                    <span>Join Code</span>
                  </div>
                  <div className="text-3xl sm:text-4xl font-mono font-extrabold text-[#38BDF8] tracking-tight">
                    {state.classInfo.access_code}
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-3">Share with students to enroll</p>
              </div>

              {/* Card 2: Students Enrolled */}
              <div className="bg-[#111A30] border border-slate-800/90 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    <svg className="w-3.5 h-3.5 text-sky-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                      <circle cx="9" cy="7" r="4" />
                      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                    </svg>
                    <span>Enrolled Students</span>
                  </div>
                  <div className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                    {state.classInfo.student_count}
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-3">Active learners in this class</p>
              </div>

              {/* Card 3: Lectures */}
              <div className="bg-[#111A30] border border-slate-800/90 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    <svg className="w-3.5 h-3.5 text-sky-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span>Lectures</span>
                  </div>
                  <div className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                    {state.classInfo.lecture_count}
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-3">Quizzes created for this class</p>
              </div>
            </div>

            <div className="pt-2">
              <Link
                to="/professor"
                className="inline-flex items-center gap-2 bg-[#111A30] hover:bg-[#162547] border border-slate-700 hover:border-slate-500 text-white font-semibold text-sm px-5 py-3 rounded-xl transition cursor-pointer shadow-md"
              >
                <span>←</span>
                <span>Back to created classes</span>
              </Link>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STATE 3: EMPTY STATE (Matching Mockup 2)                 */}
        {/* ======================================================== */}
        {stats && stats.lectures.length === 0 && (
          <div className="border-2 border-dashed border-slate-700/80 rounded-3xl p-10 sm:p-16 text-center max-w-3xl mx-auto flex flex-col items-center justify-center bg-[#10192E]/30">
            {/* Document Icon Badge */}
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
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </div>

            <h2 className="text-2xl sm:text-3xl font-bold text-white mb-2">
              No quizzes yet
            </h2>
            <p className="text-slate-400 text-sm max-w-md mx-auto leading-relaxed">
              When your professor publishes a lecture quiz, it will show up here.
            </p>
          </div>
        )}

        {/* ======================================================== */}
        {/* STATE 4: POPULATED STATE (Matching Mockup 4)             */}
        {/* ======================================================== */}
        {stats && stats.lectures.length > 0 && (
          <div className="space-y-8">
            {/* 1. Stat Cards (Acceptance Criterion 1) */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 sm:gap-4">
              {/* Card 1: Total Points */}
              <div className="bg-[#111A30] border border-slate-800/90 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    <svg className="w-3.5 h-3.5 text-sky-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                    </svg>
                    <span>Total Points</span>
                  </div>
                  <div className="text-3xl sm:text-4xl font-extrabold text-[#38BDF8] tracking-tight">
                    {stats.total_points.toLocaleString()}
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-3">Across all lectures</p>
              </div>

              {/* Card 2: Class Rank (Acceptance Criterion 5: opens leaderboard modal) */}
              <button
                type="button"
                onClick={() => setIsLeaderboardOpen(true)}
                aria-haspopup="dialog"
                className="bg-[#111A30] hover:bg-[#142240] border border-slate-800/90 hover:border-slate-700 rounded-2xl p-5 shadow-lg flex flex-col justify-between text-left w-full cursor-pointer transition group focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
                title="Click to view class leaderboard"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400 uppercase tracking-wider">
                      <svg className="w-3.5 h-3.5 text-sky-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="20" x2="18" y2="10" />
                        <line x1="12" y1="20" x2="12" y2="4" />
                        <line x1="6" y1="20" x2="6" y2="14" />
                      </svg>
                      <span>Class Rank</span>
                    </div>
                    <div className="w-7 h-7 rounded-lg bg-[#182647] group-hover:bg-[#1D305A] flex items-center justify-center text-slate-400 group-hover:text-white transition text-xs font-bold shadow-sm">
                      →
                    </div>
                  </div>
                  <div className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                    #{stats.rank}
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-3">
                  {stats.rank > 1 && stats.points_to_next_rank > 0 ? (
                    <>
                      <span className="text-[#38BDF8] font-semibold">{stats.points_to_next_rank} pts</span> to reach #{stats.rank - 1}
                    </>
                  ) : stats.rank === 1 ? (
                    <span>You are in first place</span>
                  ) : (
                    <span>Play a quiz to rank up</span>
                  )}
                </p>
              </button>

              {/* Card 3: Quizzes Played */}
              <div className="bg-[#111A30] border border-slate-800/90 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    <svg className="w-3.5 h-3.5 text-sky-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                      <polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                    <span>Quizzes Played</span>
                  </div>
                  <div className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                    {stats.quizzes_played}
                    <span className="text-slate-500 font-semibold text-xl sm:text-2xl">
                      {" "}/ {stats.quizzes_total}
                    </span>
                  </div>
                </div>

                {/* Progress bar matching mockup */}
                <div className="w-full bg-[#18233C] h-2 rounded-full overflow-hidden mt-3">
                  <div
                    className="bg-[#38BDF8] h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${
                        stats.quizzes_total > 0 ? (stats.quizzes_played / stats.quizzes_total) * 100 : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* 2. Up Next Section (Acceptance Criterion 2) */}
            {stats.up_next && (
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                  Up Next
                </h3>

                <div className="bg-[#101B33] border border-sky-500/40 rounded-2xl p-5 sm:p-6 shadow-xl relative overflow-hidden flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  {/* Background ripple design */}
                  <div className="absolute right-0 top-0 bottom-0 w-64 pointer-events-none opacity-20">
                    <svg
                      viewBox="0 0 200 200"
                      className="w-full h-full"
                      fill="none"
                      stroke="#38BDF8"
                      strokeWidth="1.5"
                    >
                      <circle cx="160" cy="100" r="40" />
                      <circle cx="160" cy="100" r="70" />
                      <circle cx="160" cy="100" r="100" />
                    </svg>
                  </div>

                  {/* Left content */}
                  <div className="relative z-10">
                    <h4 className="text-xl sm:text-2xl font-bold text-white mb-2.5">
                      {stats.up_next.title}
                    </h4>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="bg-[#18294D] border border-slate-700/80 text-slate-300 px-3 py-1 rounded-full font-medium">
                        {stats.up_next.question_count} questions
                      </span>
                    </div>
                  </div>

                  {/* Right Action Button */}
                  <button
                    type="button"
                    onClick={() => handleStartQuiz(stats.up_next!.id)}
                    className="relative z-10 inline-flex items-center justify-center gap-2 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm px-6 py-3 rounded-xl transition cursor-pointer shadow-lg shadow-sky-500/20 active:scale-95 shrink-0 self-start sm:self-auto"
                  >
                    <span>Start quiz</span>
                    <span>→</span>
                  </button>
                </div>
              </div>
            )}

            {/* 3. More Lectures List (Acceptance Criterion 3). The Up Next quiz is shown above, so skip it here. */}
            {moreLectures.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                More Lectures
              </h3>

              <div className="space-y-3">
                {moreLectures.map((lecture) => (
                  <div
                    key={lecture.id}
                    onClick={() => handleStartQuiz(lecture.id)}
                    className="group bg-[#111A30] hover:bg-[#14203D] border border-slate-800/90 hover:border-slate-700 rounded-2xl p-4 sm:p-5 flex items-center justify-between transition-all duration-150 shadow-md cursor-pointer"
                  >
                    {/* Left: Check / Play Icon + Title + Progress */}
                    <div className="flex items-center gap-3.5 sm:gap-4 min-w-0">
                      {!lecture.is_new ? (
                        <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl bg-[#162547] flex items-center justify-center text-[#38BDF8] shrink-0 shadow-sm font-bold">
                          ✓
                        </div>
                      ) : (
                        <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl bg-[#16223D] flex items-center justify-center text-slate-400 group-hover:text-white shrink-0 shadow-sm text-sm">
                          ▶
                        </div>
                      )}

                      <div className="min-w-0">
                        <h4 className="text-sm sm:text-base font-bold text-white group-hover:text-sky-300 transition-colors truncate">
                          {lecture.title}
                        </h4>

                        {!lecture.is_new ? (
                          /* Score Dots Indicator matching Mockup */
                          <div className="flex items-center gap-1.5 mt-1">
                            <div className="flex items-center gap-1">
                              {Array.from({ length: lecture.question_count }).map((_, i) => (
                                <span
                                  key={i}
                                  className={`w-1.5 h-1.5 rounded-full ${
                                    i < lecture.correct_count
                                      ? "bg-[#38BDF8]"
                                      : "bg-slate-700"
                                  }`}
                                />
                              ))}
                            </div>
                            <span className="text-xs text-slate-400 font-medium ml-1">
                              {lecture.correct_count} of {lecture.question_count} correct
                            </span>
                          </div>
                        ) : (
                          <p className="text-xs text-slate-400 mt-0.5">
                            {lecture.question_count} questions
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Right: Best Points / New Badge + Arrow Button */}
                    <div className="flex items-center gap-3 sm:gap-4 shrink-0">
                      {!lecture.is_new ? (
                        <div className="text-right">
                          <span className="block text-[10px] uppercase font-bold text-slate-400">
                            Best
                          </span>
                          <span className="text-xs sm:text-sm font-bold text-[#38BDF8]">
                            {lecture.best_score} pts
                          </span>
                        </div>
                      ) : (
                        <span className="bg-[#162547] border border-sky-500/30 text-sky-400 text-xs font-bold px-2.5 py-0.5 rounded-full shadow-sm">
                          New
                        </span>
                      )}

                      <div className="w-8 h-8 rounded-xl bg-[#18233C] group-hover:bg-[#1D305A] flex items-center justify-center text-slate-400 group-hover:text-white transition text-xs font-bold shadow-sm">
                        →
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            )}
          </div>
        )}
      </main>

      {/* Leaderboard modal (Acceptance Criterion 5) */}
      {isLeaderboardOpen && stats && (
        <LeaderboardModal
          classroomId={stats.classroom_id}
          onClose={() => setIsLeaderboardOpen(false)}
        />
      )}

      {/* Footer */}
      <footer className="text-center text-xs text-slate-600 max-w-5xl mx-auto w-full py-6">
        CoursePulse © {new Date().getFullYear()} — Study Companion
      </footer>
    </div>
  );
}

export default ClassHub;
