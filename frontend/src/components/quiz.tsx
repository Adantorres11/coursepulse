import { useState, useEffect } from "react";
import type { Quiz, DifficultyLevel } from "../types/api";

type QuizQuestion = Quiz["questions"][number];

interface QuizGameProps {
  questions: QuizQuestion[];
}

export default function QuizGame({ questions }: QuizGameProps) {
  const [score, setScore] = useState<number>(0);
  const [questionIndex, setQuestionIndex] = useState<number>(-1);

  const [selectedAnswers, setSelectedAnswers] = useState<(number | null)[]>(
    Array(questions.length).fill(null)
  );

  // keeps track of which questions have been answered
  const [answeredQuestions, setAnsweredQuestions] = useState<boolean[]>(
    questions.map(() => false)
  );

  // sets color of buttons based on user input
  function getAnswerColor(answerIndex: number) {
    if (!answeredQuestions[questionIndex]) {
      return "border border-slate-600 bg-slate-800 hover:border-slate-400";
    }

    if (answerIndex === questions[questionIndex].correct_index) {
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

// adjusts score based on which quiz answer selected
  function handleAnswer(answerIndex: number | null) {
    if(answeredQuestions[questionIndex]) {
      return;
    }

    setSelectedAnswers((prev) => {
      const updated = [...prev];
      updated[questionIndex] = answerIndex;
      return updated;
    });

    if (answerIndex !== null && answerIndex === questions[questionIndex].correct_index) {
      setScore((prev) => prev + 100 * getDifficultyPoints(questions[questionIndex].difficulty));
    }

    setAnsweredQuestions((previous) => {
      const updated = [...previous];
      updated[questionIndex] = true;
      return updated;
    });
  }

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

  function nextQuestion() {
    setTimeLeft(20);

    if (questionIndex < questions.length - 1) {
      setQuestionIndex((prev) => prev + 1);
    } else {
      setQuestionIndex(questions.length);
    }
  }

// returns number of questions user got correct.
  function getNumberQuestionsCorrect(): number {
    var count = 0;
    for(var i = 0; i < questions.length; i++){
      if(selectedAnswers[i] === questions[i].correct_index)
        count += 1;
    }
    return count;
  }

  // Timer workings.
  const [timeLeft, setTimeLeft] = useState<number>(5);

  useEffect(() => {
    if (questionIndex >= questions.length || answeredQuestions[questionIndex]){
      return;
    }

    if (timeLeft < 0) {
      // question out of time
      if(questionIndex != -1) {
        handleAnswer(null);
        return;
      }
      // countdown out of time
      else {
        nextQuestion();
      }
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft, questionIndex, answeredQuestions, questions.length]);

  // timer ring config
  const radius = 44;
  const strokeWidth = 3.5;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (timeLeft / 5) * circumference;


  function restartQuiz() {
    setScore(0);
    setQuestionIndex(-1);
    setTimeLeft(5);
    setSelectedAnswers(Array(questions.length).fill(null));
    setAnsweredQuestions(questions.map(() => false));
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
              20 sec each
            </div>
            <div className="bg-slate-700 text-sm text-white px-2.5 py-1 rounded-lg transition-colors shadow-sm">
              100 to 300 pts
            </div>
          </div>
          <span className="text-slate-400 text-sm font-medium">Question 1 starts in a moment.</span>
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
              style={{ width: `${(timeLeft / 20) * 100}%` }}
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
                {answeredQuestions[questionIndex] && index == questions[questionIndex].correct_index && <span className="text-white font-bold">✓</span>}
                {selectedAnswers[questionIndex] == index && index != questions[questionIndex].correct_index && <span className="text-white font-bold">✕</span>}
              </div>

            </button>
          ))}
        </div>
        {answeredQuestions[questionIndex] &&
          <div className="flex items-center justify-between w-full">
            <div>
              {selectedAnswers[questionIndex] == questions[questionIndex].correct_index && <span className="text-emerald-400 font-bold">✓ Correct! +{getDifficultyPoints(questions[questionIndex].difficulty) * 100} points</span>}
              {selectedAnswers[questionIndex] != questions[questionIndex].correct_index && <span className="text-red-400 font-bold">✕ Not quite. +0 points</span>}
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
        <span className="text-m text-slate-200 p-1">{getNumberQuestionsCorrect()} of {questions.length} correct</span>
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
                {selectedAnswers[index] == questions[index].correct_index && <span className="text-emerald-400 font-bold">✓ +{getDifficultyPoints(questions[index].difficulty) * 100}</span>}
                {selectedAnswers[index] != questions[index].correct_index && <span className="text-red-400 font-bold">✕ 0</span>}
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

