import { useState, useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getLectures } from "../lib/apiClient";

export type ViewState = "populated" | "loading" | "empty" | "error";

interface ClassStat {
  totalPoints: number;
  classRank: number;
  pointsToNextRank: number;
  quizzesPlayed: number;
  totalQuizzes: number;
}

interface LectureItem {
  id: string | number;
  title: string;
  questionCount: number;
  difficultyRange?: string;
  isUpNext?: boolean;
  isCompleted?: boolean;
  score?: number;
  correctCount?: number;
  bestPoints?: number;
  isNew?: boolean;
}

interface LeaderboardEntry {
  rank: number;
  name: string;
  points: number;
  isCurrentUser?: boolean;
}

export function ClassHub() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();

  // State management
  const [viewState, setViewState] = useState<ViewState>("populated");
  const [isLeaderboardOpen, setIsLeaderboardOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Class directory matching Student Hub mockups
  const CLASS_DIRECTORY: Record<
    string,
    { name: string; code: string; totalQuizzes: number; upNext: LectureItem; lectures: LectureItem[] }
  > = {
    "cs-201": {
      name: "Data Structures",
      code: "CS 201 · Prof. Lin",
      totalQuizzes: 4,
      upNext: {
        id: 3,
        title: "Lecture 3: Sorting Algorithms",
        questionCount: 10,
        difficultyRange: "100–300 pts each",
        isUpNext: true,
      },
      lectures: [
        { id: 1, title: "Lecture 1: Data Structures", questionCount: 5, isCompleted: false, isNew: true },
        { id: 2, title: "Lecture 2: Hash Tables", questionCount: 8, isCompleted: false, isNew: true },
        { id: 4, title: "Lecture 4: Graph Algorithms", questionCount: 6, isCompleted: false, isNew: true },
      ],
    },
    "math-210": {
      name: "Discrete Math",
      code: "MATH 210 · Prof. Okafor",
      totalQuizzes: 6,
      upNext: {
        id: 11,
        title: "Lecture 1: Propositional Logic",
        questionCount: 8,
        difficultyRange: "100–300 pts each",
        isUpNext: true,
      },
      lectures: [
        { id: 12, title: "Lecture 2: Set Theory & Relations", questionCount: 6, isCompleted: false, isNew: true },
        { id: 13, title: "Lecture 3: Combinatorics & Permutations", questionCount: 7, isCompleted: false, isNew: true },
      ],
    },
    "stat-301": {
      name: "Probability and Statistics",
      code: "STAT 301 · Prof. Rivera",
      totalQuizzes: 3,
      upNext: {
        id: 21,
        title: "Lecture 1: Random Variables & Distributions",
        questionCount: 8,
        difficultyRange: "100–300 pts each",
        isUpNext: true,
      },
      lectures: [
        { id: 22, title: "Lecture 2: Central Limit Theorem", questionCount: 5, isCompleted: false, isNew: true },
      ],
    },
  };

  const selectedClass = (classId && CLASS_DIRECTORY[classId]) || CLASS_DIRECTORY["cs-201"];

  // Class metadata
  const className = selectedClass.name;
  const classCode = selectedClass.code;

  // Stats - 0 points and 0/X quizzes played until points/tracking are implemented
  const [stats] = useState<ClassStat>({
    totalPoints: 0,
    classRank: 1,
    pointsToNextRank: 0,
    quizzesPlayed: 0,
    totalQuizzes: selectedClass.totalQuizzes,
  });

  // Up Next featured quiz
  const [upNextLecture, setUpNextLecture] = useState<LectureItem | null>(selectedClass.upNext);

  // List of lectures
  const [lectures, setLectures] = useState<LectureItem[]>(selectedClass.lectures);

  // Leaderboard data for modal - only Student with 0 points
  const leaderboardData: LeaderboardEntry[] = [
    { rank: 1, name: "Student", points: 0, isCurrentUser: true },
  ];

  // Fetch real lecture data on mount
  const loadClassData = async () => {
    setLoading(true);
    setErrorMessage(null);

    const result = await getLectures();
    if (!result.error && result.data && result.data.length > 0) {
      // If real backend returns lectures matching this class name, use them
      const matching = result.data.filter(
        (l) => l.classroom && l.classroom.toLowerCase().includes(className.toLowerCase())
      );
      if (matching.length > 0) {
        setUpNextLecture({
          id: matching[0].id,
          title: matching[0].title,
          questionCount: matching[0].question_count || 5,
          difficultyRange: "100–300 pts each",
          isUpNext: true,
        });

        if (matching.length > 1) {
          setLectures(
            matching.slice(1).map((lec) => ({
              id: lec.id,
              title: lec.title,
              questionCount: lec.question_count || 5,
              isCompleted: false,
              isNew: true,
            }))
          );
        }
      }
    }
    setLoading(false);
  };

  useEffect(() => {
    loadClassData();
  }, [classId]);

  const handleStartQuiz = (lectureId?: string | number) => {
    const targetId = lectureId || upNextLecture?.id || 1;
    navigate(`/quiz/${targetId}`);
  };

  const handleRetry = () => {
    setViewState("loading");
    setTimeout(() => {
      setViewState("populated");
      loadClassData();
    }, 600);
  };

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

        {/* Back Link to All Classes (Student Hub) */}
        <Link
          to="/hub"
          className="text-xs sm:text-sm font-semibold text-slate-400 hover:text-white transition-colors cursor-pointer"
        >
          All classes
        </Link>
      </header>

      {/* Main Container */}
      <main className="flex-1 w-full max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Navigation Breadcrumb matching Mockups */}
        <div className="mb-4">
          <Link
            to="/hub"
            className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-semibold text-slate-400 hover:text-white transition-colors cursor-pointer group"
          >
            <span className="transition-transform group-hover:-translate-x-1 font-bold">←</span>
            <span>All classes</span>
          </Link>
        </div>

        {/* Class Header Title & Subtitle */}
        <div className="mb-8">
          <h1 className="text-3xl sm:text-4xl md:text-[42px] font-extrabold tracking-tight text-white mb-1.5">
            {className}
          </h1>
          <p className="text-slate-400 text-sm sm:text-base">
            {viewState === "loading" || loading ? "Loading your quizzes..." : classCode}
          </p>
        </div>

        {/* ======================================================== */}
        {/* STATE 1: LOADING SKELETON (Matching Mockup 3)            */}
        {/* ======================================================== */}
        {(viewState === "loading" || loading) && (
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
        {viewState === "error" && !loading && (
          <div className="bg-[#10192E] border border-slate-800 rounded-3xl p-8 sm:p-12 text-center max-w-2xl mx-auto shadow-2xl flex flex-col items-center">
            {/* Red Warning Icon */}
            <div className="w-14 h-14 rounded-full bg-[#2A1520] border border-rose-500/30 flex items-center justify-center mb-5 text-rose-400 text-2xl shadow-inner">
              !
            </div>

            <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
              Couldn't load your quizzes
            </h2>
            <p className="text-slate-400 text-sm max-w-sm mx-auto mb-6 leading-relaxed">
              {errorMessage || "Something went wrong on our end. Check your connection and try again."}
            </p>

            <button
              type="button"
              onClick={handleRetry}
              className="inline-flex items-center gap-2 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm px-6 py-2.5 rounded-xl transition cursor-pointer shadow-md shadow-sky-500/20 active:scale-95"
            >
              <span>↻</span>
              <span>Retry</span>
            </button>
          </div>
        )}

        {/* ======================================================== */}
        {/* STATE 3: EMPTY STATE (Matching Mockup 2)                 */}
        {/* ======================================================== */}
        {viewState === "empty" && !loading && (
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
        {viewState === "populated" && !loading && (
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
                    {stats.totalPoints.toLocaleString()}
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-3">Across all lectures</p>
              </div>

              {/* Card 2: Class Rank (Acceptance Criterion 5: opens leaderboard modal) */}
              <div
                onClick={() => setIsLeaderboardOpen(true)}
                className="bg-[#111A30] hover:bg-[#142240] border border-slate-800/90 hover:border-slate-700 rounded-2xl p-5 shadow-lg flex flex-col justify-between cursor-pointer transition group"
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
                    #{stats.classRank}
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-3">
                  {stats.totalPoints > 0 && stats.pointsToNextRank > 0 ? (
                    <>
                      <span className="text-[#38BDF8] font-semibold">{stats.pointsToNextRank} pts</span> to reach #{stats.classRank - 1}
                    </>
                  ) : (
                    <span>Play a quiz to rank up</span>
                  )}
                </p>
              </div>

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
                    {stats.quizzesPlayed}
                    <span className="text-slate-500 font-semibold text-xl sm:text-2xl">
                      {" "}/ {stats.totalQuizzes}
                    </span>
                  </div>
                </div>

                {/* Progress bar matching mockup */}
                <div className="w-full bg-[#18233C] h-2 rounded-full overflow-hidden mt-3">
                  <div
                    className="bg-[#38BDF8] h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${(stats.quizzesPlayed / stats.totalQuizzes) * 100}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* 2. Up Next Section (Acceptance Criterion 2) */}
            {upNextLecture && (
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
                      {upNextLecture.title}
                    </h4>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="bg-[#18294D] border border-slate-700/80 text-slate-300 px-3 py-1 rounded-full font-medium">
                        {upNextLecture.questionCount} questions
                      </span>
                      <span className="bg-[#18294D] border border-slate-700/80 text-slate-300 px-3 py-1 rounded-full font-medium">
                        {upNextLecture.difficultyRange || "100–300 pts each"}
                      </span>
                    </div>
                  </div>

                  {/* Right Action Button */}
                  <button
                    type="button"
                    onClick={() => handleStartQuiz(upNextLecture.id)}
                    className="relative z-10 inline-flex items-center justify-center gap-2 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm px-6 py-3 rounded-xl transition cursor-pointer shadow-lg shadow-sky-500/20 active:scale-95 shrink-0 self-start sm:self-auto"
                  >
                    <span>Start quiz</span>
                    <span>→</span>
                  </button>
                </div>
              </div>
            )}

            {/* 3. More Lectures List (Acceptance Criterion 3) */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                More Lectures
              </h3>

              <div className="space-y-3">
                {lectures.map((lecture) => (
                  <div
                    key={lecture.id}
                    onClick={() => handleStartQuiz(lecture.id)}
                    className="group bg-[#111A30] hover:bg-[#14203D] border border-slate-800/90 hover:border-slate-700 rounded-2xl p-4 sm:p-5 flex items-center justify-between transition-all duration-150 shadow-md cursor-pointer"
                  >
                    {/* Left: Check / Play Icon + Title + Progress */}
                    <div className="flex items-center gap-3.5 sm:gap-4 min-w-0">
                      {lecture.isCompleted ? (
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

                        {lecture.isCompleted && lecture.correctCount !== undefined ? (
                          /* Score Dots Indicator matching Mockup */
                          <div className="flex items-center gap-1.5 mt-1">
                            <div className="flex items-center gap-1">
                              {Array.from({ length: lecture.questionCount }).map((_, i) => (
                                <span
                                  key={i}
                                  className={`w-1.5 h-1.5 rounded-full ${
                                    i < (lecture.correctCount || 0)
                                      ? "bg-[#38BDF8]"
                                      : "bg-slate-700"
                                  }`}
                                />
                              ))}
                            </div>
                            <span className="text-xs text-slate-400 font-medium ml-1">
                              {lecture.correctCount} of {lecture.questionCount} correct
                            </span>
                          </div>
                        ) : (
                          <p className="text-xs text-slate-400 mt-0.5">
                            {lecture.questionCount} questions
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Right: Best Points / New Badge + Arrow Button */}
                    <div className="flex items-center gap-3 sm:gap-4 shrink-0">
                      {lecture.bestPoints ? (
                        <div className="text-right">
                          <span className="block text-[10px] uppercase font-bold text-slate-400">
                            Best
                          </span>
                          <span className="text-xs sm:text-sm font-bold text-[#38BDF8]">
                            {lecture.bestPoints} pts
                          </span>
                        </div>
                      ) : lecture.isNew ? (
                        <span className="bg-[#162547] border border-sky-500/30 text-sky-400 text-xs font-bold px-2.5 py-0.5 rounded-full shadow-sm">
                          New
                        </span>
                      ) : null}

                      <div className="w-8 h-8 rounded-xl bg-[#18233C] group-hover:bg-[#1D305A] flex items-center justify-center text-slate-400 group-hover:text-white transition text-xs font-bold shadow-sm">
                        →
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* DEV HELPER: STATE TOGGLE SWITCHER (Acceptance Crit 4)     */}
        {/* ======================================================== */}
        <div className="mt-12 pt-6 border-t border-slate-800/80 text-center">
          <p className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-2">
            Reviewer Demo Switcher (Simulate Acceptance Criteria States)
          </p>
          <div className="inline-flex flex-wrap items-center justify-center gap-2 p-1 bg-[#090F1E] border border-slate-800 rounded-xl">
            {(["populated", "loading", "empty", "error"] as ViewState[]).map((state) => (
              <button
                key={state}
                type="button"
                onClick={() => setViewState(state)}
                className={`px-3 py-1 text-xs font-semibold rounded-lg transition-colors capitalize cursor-pointer ${
                  viewState === state
                    ? "bg-[#38BDF8] text-[#0A101D] shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {state}
              </button>
            ))}
          </div>
        </div>
      </main>

      {/* ======================================================== */}
      {/* LEADERBOARD MODAL (Acceptance Criterion 5)                */}
      {/* ======================================================== */}
      {isLeaderboardOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
          <div className="bg-[#10192E] border border-slate-800 rounded-2xl p-6 sm:p-7 max-w-md w-full shadow-2xl relative">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
              <div>
                <h3 className="text-xl font-bold text-white">Class Leaderboard</h3>
                <p className="text-xs text-slate-400 mt-0.5">{className} · {classCode}</p>
              </div>
              <button
                type="button"
                onClick={() => setIsLeaderboardOpen(false)}
                className="w-8 h-8 rounded-lg bg-[#18233C] hover:bg-[#203055] text-slate-400 hover:text-white flex items-center justify-center transition cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Leaderboard Ranks List */}
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {leaderboardData.map((user) => (
                <div
                  key={user.rank}
                  className={`flex items-center justify-between p-3 rounded-xl transition ${
                    user.isCurrentUser
                      ? "bg-[#18294D] border border-sky-500/50 text-white font-bold"
                      : "bg-[#0B1220] border border-slate-800 text-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-6 text-center text-xs font-extrabold ${
                        user.rank === 1
                          ? "text-amber-400"
                          : user.rank === 2
                          ? "text-slate-300"
                          : user.rank === 3
                          ? "text-amber-600"
                          : "text-slate-500"
                      }`}
                    >
                      #{user.rank}
                    </span>
                    <span className="text-xs sm:text-sm font-medium truncate max-w-[170px]">
                      {user.name}
                    </span>
                  </div>
                  <span className="text-xs sm:text-sm font-bold text-sky-400">
                    {user.points.toLocaleString()} pts
                  </span>
                </div>
              ))}
            </div>

            {/* Footer Close Button */}
            <div className="mt-5 pt-3 border-t border-slate-800 flex justify-end">
              <button
                type="button"
                onClick={() => setIsLeaderboardOpen(false)}
                className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold rounded-xl transition cursor-pointer"
              >
                Close
              </button>
            </div>
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

export default ClassHub;
