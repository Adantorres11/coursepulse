import { useState, useEffect, useRef } from "react";
import confetti from "canvas-confetti";
import type {
  Quiz,
  DifficultyLevel,
  AnswerRequest,
  AnswerResult,
  AnsweredQuestion,
} from "../types/api";
import { postAnswer, startQuestion } from "../lib/apiClient";
import { LeaderboardModal } from "./LeaderboardModal";

type QuizQuestion = Quiz["questions"][number];

// Matches quizzes.grading.QUESTION_TIME_LIMIT_SECONDS. Scoring uses that value.
export const QUESTION_TIME_LIMIT_SECONDS = 35;
const READY_SECONDS = 3;

interface QuizGameProps {
  questions: QuizQuestion[];
  lectureId?: string | number;
  initialAnsweredIds?: number[];
  initialAnswers?: AnsweredQuestion[];
  initialScore?: number;
  classroomId?: number;
}

interface FailedRequest {
  body: AnswerRequest;
  answerIndex: number | null;
  index: number;
}

interface PointsPop {
  id: number;
  points: number;
  animate: boolean;
}

function prefersReducedMotion() {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function difficultyLabel(difficulty: DifficultyLevel | undefined) {
  if (!difficulty) return "Question";
  return difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
}

function formatTime(seconds: number) {
  const safe = Math.max(0, seconds);
  return `0:${String(safe).padStart(2, "0")}`;
}

function burstCorrect() {
  if (prefersReducedMotion()) return;
  void confetti({
    particleCount: 42,
    spread: 58,
    startVelocity: 26,
    ticks: 70,
    gravity: 1.15,
    scalar: 0.7,
    origin: { y: 0.62 },
    disableForReducedMotion: true,
    colors: ["#7DD3FC", "#34D399", "#FDE68A", "#F9A8D4"],
  });
}

export default function QuizGame({
  questions,
  lectureId = "",
  initialAnsweredIds = [],
  initialAnswers = [],
  initialScore = 0,
  classroomId,
}: QuizGameProps) {
  const [isLeaderboardOpen, setIsLeaderboardOpen] = useState(false);

  // ids answered in an earlier visit; cleared on replay
  const [resumeIds, setResumeIds] = useState<string[]>(initialAnsweredIds.map(String));
  const [priorAnswers, setPriorAnswers] = useState<AnsweredQuestion[]>(initialAnswers);
  const allAnsweredAtLoad =
    questions.length > 0 && questions.every((q) => resumeIds.includes(String(q.id)));

  const [score, setScore] = useState<number>(initialScore);
  const [questionIndex, setQuestionIndex] = useState<number>(
    allAnsweredAtLoad ? questions.length : -1
  );

  const [selectedAnswers, setSelectedAnswers] = useState<(number | null)[]>(
    Array(questions.length).fill(null)
  );

  const [streak, setStreak] = useState<number>(0);
  const [maxStreak, setMaxStreak] = useState<number>(0);

  const [results, setResults] = useState<(AnswerResult | null)[]>(
    Array(questions.length).fill(null)
  );
  const currentResult = results[questionIndex] ?? null;

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [failedRequest, setFailedRequest] = useState<FailedRequest | null>(null);

  const [startedIndex, setStartedIndex] = useState<number | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [startAttempt, setStartAttempt] = useState<number>(0);
  const questionStarted = startedIndex === questionIndex;

  const [timeLeft, setTimeLeft] = useState<number>(READY_SECONDS);
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);
  const [pointsPop, setPointsPop] = useState<PointsPop | null>(null);
  const [shake, setShake] = useState(false);

  const timeoutSentRef = useRef(false);
  const deadlineRef = useRef<number | null>(null);
  const submittingRef = useRef(false);
  const failedRef = useRef<FailedRequest | null>(null);
  const resultRef = useRef<AnswerResult | null>(currentResult);
  resultRef.current = currentResult;
  failedRef.current = failedRequest;

  const handleAnswerRef = useRef<(answerIndex: number | null) => void>(() => {});

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReducedMotion(media.matches);
    media.addEventListener?.("change", onChange);
    return () => media.removeEventListener?.("change", onChange);
  }, []);

  useEffect(() => {
    timeoutSentRef.current = false;
    deadlineRef.current = null;
    setShake(false);
    setPointsPop(null);
  }, [questionIndex]);

  const activeQuestionId =
    questionIndex >= 0 && questionIndex < questions.length
      ? questions[questionIndex]?.id
      : null;

  useEffect(() => {
    if (questionIndex < 0 || questionIndex >= questions.length || currentResult) {
      return;
    }

    let cancelled = false;
    setStartError(null);
    startQuestion(lectureId, Number(activeQuestionId)).then((result) => {
      if (cancelled) return;
      if (result.error || !result.data) {
        setStartError(result.error ?? "Could not start this question.");
        return;
      }
      setStartedIndex(questionIndex);
    });

    return () => {
      cancelled = true;
    };
  }, [questionIndex, startAttempt, currentResult, lectureId, questions.length, activeQuestionId]);

  useEffect(() => {
    if (questionIndex !== -1) return;
    setTimeLeft(READY_SECONDS);
    const deadline = Date.now() + READY_SECONDS * 1000;
    const timer = window.setInterval(() => {
      const remaining = deadline - Date.now();
      if (remaining <= 0) {
        window.clearInterval(timer);
        const next = questions.findIndex((question) => !resumeIds.includes(String(question.id)));
        setTimeLeft(QUESTION_TIME_LIMIT_SECONDS);
        setQuestionIndex(next === -1 ? questions.length : next);
        return;
      }
      setTimeLeft(Math.ceil(remaining / 1000));
    }, 200);
    return () => window.clearInterval(timer);
  }, [questionIndex, questions, resumeIds]);

  useEffect(() => {
    if (
      questionIndex < 0 ||
      questionIndex >= questions.length ||
      !questionStarted ||
      currentResult
    ) {
      return;
    }
    if (deadlineRef.current == null) {
      deadlineRef.current = Date.now() + QUESTION_TIME_LIMIT_SECONDS * 1000;
    }
    const deadline = deadlineRef.current;
    const timer = window.setInterval(() => {
      const remaining = deadline - Date.now();
      setTimeLeft(Math.max(0, Math.ceil(remaining / 1000)));
      if (
        remaining <= 0 &&
        !timeoutSentRef.current &&
        !submittingRef.current &&
        !failedRef.current &&
        !resultRef.current
      ) {
        timeoutSentRef.current = true;
        handleAnswerRef.current(null);
      }
    }, 200);
    return () => window.clearInterval(timer);
  }, [questionIndex, questionStarted, currentResult, questions.length]);

  function getAnswerColor(answerIndex: number) {
    if (!currentResult) {
      return "border border-slate-600 bg-slate-800 hover:border-slate-400";
    }

    if (answerIndex === currentResult.correct_index) {
      if (selectedAnswers[questionIndex] === answerIndex) {
        return "border border-emerald-400 bg-emerald-600";
      }
      return "border border-emerald-400 bg-emerald-900";
    }

    if (selectedAnswers[questionIndex] === answerIndex) {
      return "border border-red-300 bg-red-500";
    }

    return "border border-slate-600 bg-slate-800";
  }

  async function submitAnswer(body: AnswerRequest, answerIndex: number | null, index: number) {
    submittingRef.current = true;
    setSubmitting(true);
    setError(null);
    const result = await postAnswer(lectureId, body);
    setSubmitting(false);
    submittingRef.current = false;

    if (result.error || !result.data) {
      const failure = { body, answerIndex, index };
      failedRef.current = failure;
      setError(result.error ?? "Could not save your answer.");
      setFailedRequest(failure);
      return;
    }

    const answer = result.data;
    failedRef.current = null;
    resultRef.current = answer;
    setFailedRequest(null);
    setSelectedAnswers((prev) => {
      const updated = [...prev];
      updated[index] = answerIndex;
      return updated;
    });
    setResults((prev) => {
      const updated = [...prev];
      updated[index] = answer;
      return updated;
    });

    const motionOk = !prefersReducedMotion();
    if (answer.is_correct) {
      const nextStreak = streak + 1;
      setStreak(nextStreak);
      if (maxStreak < nextStreak) {
        setMaxStreak(nextStreak);
      }
      setPointsPop({ id: index, points: answer.points_awarded, animate: motionOk });
      if (motionOk) burstCorrect();
    } else if (streak !== 0) {
      setStreak(-1);
    }
    if (!answer.is_correct && motionOk) {
      setShake(true);
    }

    setScore(answer.total_points);
  }

  async function handleAnswer(answerIndex: number | null) {
    if (resultRef.current || submittingRef.current || failedRef.current) {
      return;
    }
    if (questionIndex < 0 || questionIndex >= questions.length) return;

    const body: AnswerRequest = {
      question_id: Number(questions[questionIndex].id),
      chosen_index: answerIndex,
    };
    await submitAnswer(body, answerIndex, questionIndex);
  }

  handleAnswerRef.current = (answerIndex) => {
    void handleAnswer(answerIndex);
  };

  function retryAnswer() {
    if (!failedRequest || submittingRef.current) return;
    failedRef.current = null;
    void submitAnswer(failedRequest.body, failedRequest.answerIndex, failedRequest.index);
  }

  function getStreakBonus(currentStreak: number) {
    return currentStreak >= 3 ? 50 : 0;
  }

  function getDifficultyPoints(difficulty: DifficultyLevel | undefined): number {
    switch (difficulty) {
      case "easy":
        return 100;
      case "medium":
        return 200;
      case "hard":
        return 300;
      default:
        return 100;
    }
  }

  function nextOpenIndex(from: number): number {
    for (let i = from + 1; i < questions.length; i++) {
      if (!resumeIds.includes(String(questions[i].id))) return i;
    }
    return questions.length;
  }

  function nextQuestion() {
    setTimeLeft(QUESTION_TIME_LIMIT_SECONDS);
    setQuestionIndex(nextOpenIndex(questionIndex));
    if (streak === -1) setStreak(0);
  }

  function getNumberQuestionsCorrect(): number {
    return results.filter((result) => result?.is_correct).length;
  }

  const readyFraction = Math.min(1, Math.max(0, timeLeft / READY_SECONDS));
  const radius = 44;
  const strokeWidth = 3.5;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - readyFraction * circumference;

  function restartQuiz() {
    setScore(0);
    setQuestionIndex(-1);
    setTimeLeft(READY_SECONDS);
    setSelectedAnswers(Array(questions.length).fill(null));
    setResults(Array(questions.length).fill(null));
    setResumeIds([]);
    setPriorAnswers([]);
    setError(null);
    setFailedRequest(null);
    failedRef.current = null;
    setStartedIndex(null);
    setStartError(null);
    setStreak(0);
    setMaxStreak(0);
    setShake(false);
    setPointsPop(null);
  }

  if (questions.length === 0) {
    return <p>No questions available for this quiz.</p>;
  }

  if (questionIndex === -1) {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center overflow-hidden font-sans">
        <h1 className="pb-3 text-2xl font-bold text-white">Get ready</h1>
        <div className="relative flex h-36 w-36 items-center justify-center sm:h-40 sm:w-40">
          <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full -rotate-90">
            <circle
              cx="50"
              cy="50"
              r={radius}
              className="text-slate-800/60"
              strokeWidth={strokeWidth}
              stroke="currentColor"
              fill="transparent"
            />
            <circle
              cx="50"
              cy="50"
              r={radius}
              className="text-sky-400 transition-[stroke-dashoffset] duration-1000 ease-linear"
              strokeWidth={strokeWidth}
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              stroke="currentColor"
              fill="transparent"
            />
          </svg>
          <div className="text-6xl font-black tabular-nums tracking-tighter text-white select-none">
            {timeLeft}
          </div>
        </div>
        <div className="mt-4 flex flex-row items-center justify-center gap-2">
          <div className="rounded-lg bg-slate-700 px-2.5 py-1 text-sm text-white shadow-sm">
            {questions.length} questions
          </div>
          <div className="rounded-lg bg-slate-700 px-2.5 py-1 text-sm text-white shadow-sm">
            {QUESTION_TIME_LIMIT_SECONDS} sec each
          </div>
          <div className="rounded-lg bg-slate-700 px-2.5 py-1 text-sm text-white shadow-sm">
            100 to 300 pts
          </div>
        </div>
        <span className="mt-3 text-sm font-medium text-slate-400">
          Question {questions.findIndex((question) => !resumeIds.includes(String(question.id))) + 1} starts in a moment.
        </span>
      </div>
    );
  }

  if (questionIndex < questions.length) {
    const question = questions[questionIndex];
    return (
      <div
        data-testid="quiz-play"
        className="relative flex h-full min-h-0 flex-col overflow-hidden font-sans"
      >
        {pointsPop && (
          <div className="pointer-events-none absolute inset-x-0 top-8 z-10 text-center">
            <span
              data-testid="points-pop"
              className={`inline-block text-lg font-bold text-emerald-300 ${pointsPop.animate ? "quiz-points-pop" : ""}`}
            >
              +{pointsPop.points} points
            </span>
          </div>
        )}

        <div className="flex shrink-0 items-center justify-between gap-3">
          <h1 className="text-base font-bold tracking-tight text-white">
            Question {questionIndex + 1} of {questions.length}
          </h1>
          <div className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800 px-3 py-1 text-white shadow-sm">
            <span className="text-xs text-slate-400">Score</span>
            <span className="text-lg font-bold text-blue-400 tabular-nums">{score}</span>
          </div>
        </div>

        <div className="flex w-full shrink-0 gap-1.5 py-1.5">
          {questions.map((item, index) => (
            <div
              key={item.id}
              className={`h-1.5 flex-1 rounded-full ${
                index < questionIndex ? "bg-sky-400" : index === questionIndex ? "bg-white" : "bg-slate-800"
              }`}
            />
          ))}
        </div>

        <div className="flex shrink-0 items-center gap-2 py-1">
          <div className="flex items-center gap-1.5">
            <span className="text-lg text-blue-300" aria-hidden="true">◷</span>
            <span className="text-base font-bold tabular-nums text-slate-200" role="timer">
              {formatTime(timeLeft)}
            </span>
          </div>
          <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-800">
            {questionStarted && !reducedMotion ? (
              <div
                data-testid="question-timer-bar"
                className={`quiz-timer-bar h-full w-full bg-sky-400${currentResult ? " is-paused" : ""}`}
                style={{ animationDuration: `${QUESTION_TIME_LIMIT_SECONDS}s` }}
              />
            ) : (
              <div
                className="h-full bg-sky-400"
                style={{
                  width: questionStarted
                    ? `${(Math.max(0, timeLeft) / QUESTION_TIME_LIMIT_SECONDS) * 100}%`
                    : "100%",
                }}
              />
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center justify-between py-1">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-slate-700 px-2 py-0.5 text-xs text-white shadow-sm">
              {difficultyLabel(question.difficulty)}
            </div>
            <span className="text-xs font-medium text-slate-400">
              {getDifficultyPoints(question.difficulty)} pts
            </span>
          </div>
          {streak > 1 && (
            <div className="rounded-lg bg-yellow-900 px-2 py-0.5 text-xs text-yellow-300 shadow-sm">
              🔥 {streak} in a row
            </div>
          )}
          {streak === -1 && (
            <div className="rounded-lg bg-slate-800 px-2 py-0.5 text-xs text-slate-400 shadow-sm">
              Streak ended
            </div>
          )}
        </div>

        <h2 className="shrink-0 text-base font-semibold leading-snug text-white">{question.prompt}</h2>
        {!questionStarted && !startError && !currentResult && (
          <p className="shrink-0 text-xs text-slate-400">Loading question...</p>
        )}

        <div
          data-testid="choices"
          className={`mt-2 flex min-h-0 flex-1 flex-col justify-center gap-1.5 ${shake ? "quiz-shake" : ""}`}
        >
          {question.choices.map((choice, index) => (
            <button
              key={index}
              type="button"
              className={`flex w-full shrink-0 items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left text-sm leading-snug transition-colors ${getAnswerColor(index)}`}
              disabled={!questionStarted || Boolean(currentResult) || submitting}
              onClick={() => void handleAnswer(index)}
            >
              <span className="flex min-w-0 items-center gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-600/40 text-xs font-bold">
                  {String.fromCharCode(65 + index)}
                </span>
                <span className="min-w-0">{choice}</span>
              </span>
              <span className="pr-1 text-white font-bold">
                {currentResult && index === currentResult.correct_index && "✓"}
                {currentResult &&
                  selectedAnswers[questionIndex] === index &&
                  index !== currentResult.correct_index &&
                  "✕"}
              </span>
            </button>
          ))}
        </div>

        <div className="mt-1 flex min-h-10 shrink-0 items-center justify-between gap-3">
          {!currentResult && startError && (
            <>
              <span className="text-sm font-bold text-red-400">{startError}</span>
              <button
                type="button"
                className="rounded-lg bg-blue-300 px-4 py-2 text-sm font-medium text-black shadow-sm"
                onClick={() => setStartAttempt((n) => n + 1)}
              >
                Try again
              </button>
            </>
          )}
          {!currentResult && error && (
            <>
              <span className="text-sm font-bold text-red-400">{error}</span>
              <button
                type="button"
                className="rounded-lg bg-blue-300 px-4 py-2 text-sm font-medium text-black shadow-sm"
                onClick={() => retryAnswer()}
              >
                Try again
              </button>
            </>
          )}
          {currentResult && (
            <>
              <div className="min-w-0 text-sm font-bold">
                {currentResult.is_correct ? (
                  <span className="text-emerald-400">
                    ✓ Correct! +{currentResult.points_awarded} points
                    {getStreakBonus(streak) > 0 && ` (+${getStreakBonus(streak)} streak bonus)`}
                  </span>
                ) : (
                  <span className="text-red-400">✕ Not quite. +{currentResult.points_awarded} points</span>
                )}
              </div>
              <button
                type="button"
                className="shrink-0 rounded-lg bg-blue-300 px-4 py-2 text-sm font-medium text-black shadow-sm"
                onClick={() => nextQuestion()}
              >
                {questionIndex === questions.length - 1 ? "Submit" : "Next Question →"}
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  const priorById = new Map(priorAnswers.map((row) => [String(row.question_id), row]));

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden font-sans">
      <div className="flex shrink-0 flex-col items-center">
        <h1 className="text-2xl font-bold text-white">Quiz Complete</h1>
        <h2 className="mt-1 text-xs font-bold text-slate-500">FINAL SCORE</h2>
        <span className="text-5xl font-bold tabular-nums text-blue-300">{score}</span>
        {results.every((result) => result !== null) && (
          <span className="text-sm text-slate-200">
            {getNumberQuestionsCorrect()} of {questions.length} correct
          </span>
        )}
        {maxStreak > 1 && (
          <div className="mt-1 rounded-lg bg-yellow-900 px-2 py-0.5 text-sm text-yellow-300">
            🔥 Max Streak: {maxStreak}
          </div>
        )}
      </div>

      <ul className="mt-3 flex min-h-0 w-full flex-1 flex-col gap-2 overflow-x-hidden overflow-y-auto">
        {questions.map((question, index) => {
          const session = results[index];
          const prior = priorById.get(String(question.id));
          const earlier = !session && (prior != null || resumeIds.includes(String(question.id)));
          const points = session ? session.points_awarded : prior?.points_awarded;
          const correct = session ? session.is_correct : prior?.is_correct;
          return (
            <li
              key={question.id}
              className="flex w-full items-center gap-3 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-2 text-sm"
            >
              <span className="w-6 shrink-0 font-semibold text-slate-200">{index + 1}</span>
              <span className="w-16 shrink-0 text-slate-300">{difficultyLabel(question.difficulty)}</span>
              <span className="min-w-0 flex-1 text-slate-200">
                {earlier ? "Answered earlier" : correct ? "Correct" : "Incorrect"}
              </span>
              <span className={`shrink-0 font-semibold ${correct ? "text-emerald-400" : "text-red-400"}`}>
                {points == null ? (
                  "—"
                ) : (
                  <>
                    <span aria-hidden="true">{correct ? "✓" : "✕"}</span>
                    <span className="ml-1">+{points}</span>
                  </>
                )}
              </span>
            </li>
          );
        })}
      </ul>

      <div className="mt-3 flex shrink-0 flex-row items-center justify-center gap-2">
        <button
          type="button"
          className="flex items-center gap-2 rounded-lg bg-blue-300 px-3 py-2 text-left leading-none text-black"
          onClick={() => restartQuiz()}
        >
          <span className="flex items-center justify-center font-bold">⟳</span>
          <span className="font-medium">Replay</span>
        </button>
        <button
          type="button"
          onClick={() => setIsLeaderboardOpen(true)}
          disabled={classroomId == null}
          className="rounded-lg bg-sky-400 px-3 py-2 font-medium text-slate-950 hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-40"
        >
          View leaderboard
        </button>
        {isLeaderboardOpen && classroomId != null && (
          <LeaderboardModal classroomId={classroomId} onClose={() => setIsLeaderboardOpen(false)} />
        )}
      </div>
    </div>
  );
}
