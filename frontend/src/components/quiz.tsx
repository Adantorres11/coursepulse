import { useState, useEffect, useRef } from "react";
import type { Quiz, DifficultyLevel, AnswerRequest, AnswerResult } from "../types/api";
import { postAnswer } from "../lib/apiClient";

type QuizQuestion = Quiz["questions"][number];

interface QuizGameProps {
  questions: QuizQuestion[];
  lectureId?: string | number;
  initialAnsweredIds?: number[];
  initialScore?: number;
}

export default function QuizGame({
  questions,
  lectureId = "",
  initialAnsweredIds = [],
  initialScore = 0,
}: QuizGameProps) {
  // ids answered in an earlier visit; cleared on replay
  const [resumeIds, setResumeIds] = useState<string[]>(initialAnsweredIds.map(String));
  const allAnsweredAtLoad =
    questions.length > 0 && questions.every((q) => resumeIds.includes(String(q.id)));

  const [score, setScore] = useState<number>(initialScore);
  const [questionIndex, setQuestionIndex] = useState<number>(
    allAnsweredAtLoad ? questions.length : -1
  );

  const [selectedAnswers, setSelectedAnswers] = useState<(number | null)[]>(
    Array(questions.length).fill(null)
  );

  // server grading result per question; null until answered in this session
  const [results, setResults] = useState<(AnswerResult | null)[]>(
    Array(questions.length).fill(null)
  );
  const currentResult = results[questionIndex] ?? null;

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  // the request that failed, so "Try again" repeats the same call
  const [failedRequest, setFailedRequest] = useState<
    { body: AnswerRequest; answerIndex: number | null; index: number } | null
  >(null);

  const questionStartRef = useRef<number>(Date.now());
  const timeoutSentRef = useRef<boolean>(false);

  useEffect(() => {
    questionStartRef.current = Date.now();
    timeoutSentRef.current = false;
  }, [questionIndex]);

  // sets color of buttons based on user input
  function getAnswerColor(answerIndex: number) {
    if (!currentResult) {
      return "border border-slate-600 bg-slate-800 hover:border-slate-400";
    }

    if (answerIndex === currentResult.correct_index) {
      if(selectedAnswers[questionIndex] === answerIndex)
        return "border border-emerald-400 bg-emerald-600";
      else
        return "border border-emerald-400 bg-emerald-900";
    }

    if (selectedAnswers[questionIndex] === answerIndex) {
      return "border border-red-300 bg-red-500";
    }

    return "border border-slate-600 bg-slate-800";
  }

// sends the answer to the server, which grades it
  async function handleAnswer(answerIndex: number | null) {
    if (currentResult || submitting || failedRequest) {
      return;
    }

    const elapsed = Date.now() - questionStartRef.current;
    const body: AnswerRequest = {
      question_id: Number(questions[questionIndex].id),
      chosen_index: answerIndex ?? 0,
      // over the 15000 ms server limit when time ran out
      time_taken_ms: answerIndex === null ? Math.max(elapsed, 15001) : elapsed,
    };
    await submitAnswer(body, answerIndex, questionIndex);
  }

  async function submitAnswer(body: AnswerRequest, answerIndex: number | null, index: number) {
    setSubmitting(true);
    setError(null);
    const result = await postAnswer(lectureId, body);
    setSubmitting(false);

    if (result.error || !result.data) {
      setError(result.error ?? "Could not save your answer.");
      setFailedRequest({ body, answerIndex, index });
      return;
    }

    const answer = result.data;
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
    setScore(answer.total_points);
  }

  function retryAnswer() {
    if (!failedRequest || submitting) {
      return;
    }
    submitAnswer(failedRequest.body, failedRequest.answerIndex, failedRequest.index);
  }

  // display only; the server decides the points
  function getDifficultyPoints(difficulty: DifficultyLevel | undefined): number {
    switch (difficulty) {
      case "easy":
        return 1;
      case "medium":
        return 2;
      case "hard":
        return 3;
      default:
        return 1;
    }
  }

  // first question after `from` not answered in an earlier visit
  function nextOpenIndex(from: number): number {
    for (let i = from + 1; i < questions.length; i++) {
      if (!resumeIds.includes(String(questions[i].id))) {
        return i;
      }
    }
    return questions.length;
  }

  function nextQuestion() {
    setTimeLeft(15);
    setQuestionIndex(nextOpenIndex(questionIndex));
  }

// returns number of questions user got correct.
  function getNumberQuestionsCorrect(): number {
    return results.filter((result) => result?.is_correct).length;
  }

  // Timer workings.
  const [timeLeft, setTimeLeft] = useState<number>(3);

  useEffect(() => {
    if (questionIndex >= questions.length || currentResult || submitting || failedRequest){
      return;
    }

    // question out of time
    if(questionIndex != -1 && timeLeft <= 0) {
      if (!timeoutSentRef.current) {
        timeoutSentRef.current = true;
        handleAnswer(null);
      }
      return;
    }
    // countdown out of time
    else if(timeLeft < 0) {
      nextQuestion();
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft, questionIndex, currentResult, submitting, failedRequest, questions.length]);

  // timer ring config
  const radius = 44;
  const strokeWidth = 3.5;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (timeLeft / 3) * circumference;


  function restartQuiz() {
    setScore(0);
    setQuestionIndex(-1);
    setTimeLeft(3);
    setSelectedAnswers(Array(questions.length).fill(null));
    setResults(Array(questions.length).fill(null));
    setResumeIds([]);
    setError(null);
    setFailedRequest(null);
  }

  // QUIZ is empty
  if (questions.length === 0) {
    return <p>No questions available for this quiz.</p>;
  }
  // countdown screen
  if (questionIndex === -1) {
    return (
      <div className="p-5 font-sans">
        <div className="flex items-center justify-center flex-col">
          <h1 className="text-3xl font-bold p-6 text-white">Get ready</h1>

          {/* Countdown Circle */}
          <div className="relative flex items-center justify-center w-72 h-72 sm:w-80 sm:h-80">
            <svg viewBox="0 0 100 100" className="w-full h-full transform -rotate-90 absolute top-0 left-0">
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
                className="text-sky-400 transition-all duration-980 ease-linear"
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
              />
            </svg>
            <div className="absolute text-8xl sm:text-9xl font-black text-white tabular-nums tracking-tighter select-none">
              {timeLeft}
            </div>
          </div>

          <div className="flex items-center justify-center flex-row p-8 gap-2">
            <div className="bg-slate-700 text-sm text-white px-2.5 py-1 rounded-lg transition-colors shadow-sm">
              {questions.length} questions
            </div>
            <div className="bg-slate-700 text-sm text-white px-2.5 py-1 rounded-lg transition-colors shadow-sm">
              15 sec each
            </div>
            <div className="bg-slate-700 text-sm text-white px-2.5 py-1 rounded-lg transition-colors shadow-sm">
              100 to 300 pts
            </div>
          </div>
          <span className="text-slate-400 text-sm font-medium">Question {nextOpenIndex(-1) + 1} starts in a moment.</span>
        </div>
      </div>
    )
  }
  // QUIZ in progress
  if (questionIndex < questions.length) {
    return (
      <div className="p-5 font-sans">
        {/* question number and quiz point counter */}
        <div className="flex items-center justify-between w-full">
          <div className="flex flex-col gap-1">
            <h1 className="text-white text-xl font-bold tracking-tight">Question {questionIndex + 1} of {questions.length}</h1>
          </div>

          <div className="inline-flex items-center gap-2 border border-slate-600 bg-slate-800 text-white font-medium px-5 py-2.5 rounded-lg transition-colors shadow-sm">
            <span className="text-slate-400 text-sm">Score</span>
            <span className="text-blue-400 font-bold text-xl">{score}</span>
          </div>
        </div>

        {/* quizprogress bar */}
        <div className="flex w-full gap-2 py-3">
          {questions.map((_, index) => (
            <div
              key={index}
              className={`h-2 flex-1 rounded-full ${
                index < questionIndex ? 'bg-sky-400' : index === questionIndex ? 'bg-white' : 'bg-slate-800'
              }`}
            />
          ))}
        </div>

        {/* timer bar */}
        <div className="flex items-center justify-between w-full gap-2 py-2">
          <div className="flex justify-between items-center mb-1 gap-2">
            <span className="text-blue-300 text-2xl">◷</span>
            <span className={"text-l font-bold text-slate-200"}>
              0:{Math.max(0, timeLeft) < 10 ? `0${Math.max(0, timeLeft)}` : Math.max(0, timeLeft)}
            </span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden relative">
            <div 
              className={"h-full transition-all duration-1000 linear rounded-full bg-sky-400"}
              style={{ width: `${(timeLeft / 15) * 100}%` }}
            />
          </div>
        </div>

        {/* difficulty and point chip */}
        <div className="flex items-center justify-between w-full px-2 pt-3 pb-2">
          <div className="flex flex-row inline-flex items-center gap-1">
            <div className="bg-slate-700 text-sm text-white px-2.5 py-1 rounded-lg transition-colors shadow-sm">
              {questions[questionIndex]?.difficulty 
                ? questions[questionIndex].difficulty.charAt(0).toUpperCase() + questions[questionIndex].difficulty.slice(1)
                : "Loading..."}
            </div>
            <span className="text-slate-400 text-sm font-medium">{getDifficultyPoints(questions[questionIndex].difficulty) * 100} pts</span>
          </div>
        </div>

        {/* question */}
        <h2 className="text-white text-xl font-bold tracking-tight">{questions[questionIndex].prompt}</h2>

        {/* choices buttons */}
        <div className="flex flex-col items-stretch gap-2.5 mx-0 my-5 w-full mr-auto">
          {questions[questionIndex].choices.map((choice, index) => (
            <button
              key={index}
              className={`flex w-full items-center justify-between gap-4 px-2 py-2 rounded-lg cursor-pointer transition-colors text-left ${getAnswerColor(index)}`}
              onClick={() => handleAnswer(index)}
            >
              <div className="flex items-center gap-4">
                <span className="flex items-center justify-center w-8 h-8 bg-slate-600/40 rounded-lg font-bold text-sm">
                  {String.fromCharCode(65 + index)}
                </span>
                {choice}
              </div>
                
              <div className="pr-1">
                {currentResult && index == currentResult.correct_index && <span className="text-white font-bold">✓</span>}
                {currentResult && selectedAnswers[questionIndex] == index && index != currentResult.correct_index && <span className="text-white font-bold">✕</span>}
              </div>

            </button>
          ))}
        </div>
        {!currentResult && error &&
          <div className="flex items-center justify-between w-full">
            <span className="text-red-400 font-bold">{error}</span>
            <button className="bg-blue-300 text-black font-medium px-5 py-2.5 rounded-lg transition-colors shadow-sm" onClick={() => retryAnswer()}>
              Try again
            </button>
          </div>
        }
        {currentResult &&
          <div className="flex items-center justify-between w-full">
            <div>
              {currentResult.is_correct && <span className="text-emerald-400 font-bold">✓ Correct! +{currentResult.points_awarded} points</span>}
              {!currentResult.is_correct && <span className="text-red-400 font-bold">✕ Not quite. +{currentResult.points_awarded} points</span>}
            </div>
            <button className="bg-blue-300 text-black font-medium px-5 py-2.5 rounded-lg transition-colors shadow-sm" onClick={() => nextQuestion()}>
              {questionIndex === questions.length - 1
                ? "Submit"
                : "Next Question →"}
            </button>
          </div>
        }
      </div>
    );
  }
  // QUIZ results
  return (
    <div className="p-5 font-sans">
      <div className="flex items-center justify-center flex-col">
        <h1 className="text-3xl font-bold p-6">Quiz Complete</h1>
        <h2 className="text-xs font-bold text-slate-500 p-1">FINAL SCORE</h2>
        <span className="text-9xl font-bold text-blue-300">{score}</span>
        {results.every((result) => result !== null) &&
          <span className="text-m text-slate-200 p-1">{getNumberQuestionsCorrect()} of {questions.length} correct</span>
        }
      </div>

      {/* TODO leaderboard info */}

      <div className="flex items-center justify-center flex-row p-6 gap-2">
        {questions.map((_, index) => (
            <div key={index} className="flex flex-col items-center justify-between px-2 py-2 rounded-lg transition-colors text-left border border-slate-600 bg-slate-800">
              <div>
                <span className="text-slate-400 text-xs font-medium">Q{index + 1} - {questions[index]?.difficulty 
                  ? questions[index].difficulty.charAt(0).toUpperCase() + questions[index].difficulty.slice(1)
                  : "Loading..."}</span>
              </div>
              <div>
                {!results[index] && <span className="text-slate-400 text-xs font-medium">Answered earlier</span>}
                {results[index]?.is_correct && <span className="text-emerald-400 font-bold">✓ +{results[index]?.points_awarded}</span>}
                {results[index] && !results[index]?.is_correct && <span className="text-red-400 font-bold">✕ 0</span>}
              </div>
            </div>
          ))}
      </div>

      <div className="flex items-center justify-center flex-row p-6 gap-2">
          <button className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors text-left bg-blue-300 text-black leading-none" onClick={() => restartQuiz()}>
            <span className="font-bold flex items-center justify-center">⟳</span>
            <span className="font-medium">Replay</span>
          </button>

          {/* TODO view leaderboard button*/}
      </div>

    </div>
  );
}

