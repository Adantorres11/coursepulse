import { useState } from "react";
import type { Quiz, DifficultyLevel } from "../types/api";

type QuizQuestion = Quiz["questions"][number];

interface QuizGameProps {
  questions: QuizQuestion[];
}

export default function QuizGame({ questions }: QuizGameProps) {
  const [score, setScore] = useState<number>(0);
  const [questionIndex, setQuestionIndex] = useState<number>(0);

  const [selectedAnswers, setSelectedAnswers] = useState<(number | null)[]>(
    Array(questions.length).fill(null)
  );

  // keeps track of which questions have been answered
  const [answeredQuestions, setAnsweredQuestions] = useState<boolean[]>(
    questions.map(() => false)
  );

  // sets color of buttons based on user input
  function getAnswerColor(answerIndex: number) {
    if (selectedAnswers[questionIndex] !== null && answerIndex === questions[questionIndex].correct_index) {
      return "bg-emerald-500 text-white";
    }
    else if (selectedAnswers[questionIndex] === answerIndex) {
      return "bg-red-500 text-white";
    }
    return "bg-slate-100 text-black";
  }

// adjusts score based on which quiz answer selected
  function handleAnswer(answerIndex: number) {
    if(answeredQuestions[questionIndex]) {
      return;
    }

    setSelectedAnswers((prev) => {
      const updated = [...prev];
      updated[questionIndex] = answerIndex;
      return updated;
    });

    if (answerIndex === questions[questionIndex].correct_index) {
      setScore(score + 100 * getDifficultyPoints(questions[questionIndex].difficulty));
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
  if (questionIndex < questions.length - 1) {
    setQuestionIndex((prev) => prev + 1);
  } else {
    setQuestionIndex(questions.length);
  }
}

  function previousQuestion() {
    if (questionIndex > 0) {
      setQuestionIndex(questionIndex - 1);
    }
  }

// returns the maximum possible score for the results screen
  function getMaxScore(): number {
    return questions.reduce((total, question) => {
      return total + 100 * getDifficultyPoints(question?.difficulty);
    }, 0);
  }

  // quiz is empty
  if (questions.length === 0) {
    return <p>No questions available for this quiz.</p>;
  }
  if (questionIndex < questions.length) {
    // QUIZ in progress
    return (
      <div className="p-20 font-sans">
        <div>
          Question {questionIndex + 1} / {questions.length}
          <p>Score: {score}</p>
        </div>
        <h1>{questions[questionIndex].prompt}</h1>
        <div className="flex justify-center gap-2.5 m-5">
          {questions[questionIndex].choices.map((choice, index) => (
            <button
              key={index}
              className={`border border-black px-5 py-2 rounded-lg cursor-pointer transition-colors ${getAnswerColor(index)}`}
              onClick={() => handleAnswer(index)}
            >
              {choice}
            </button>
          ))}
        </div>
        <div className="flex justify-center gap-2.5">
          <button className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-5 py-2.5 rounded-lg transition-colors shadow-sm" onClick={() => previousQuestion()}>
            Prev Question
          </button>
          <button className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-5 py-2.5 rounded-lg transition-colors shadow-sm" onClick={() => nextQuestion()}>
            {questionIndex === questions.length - 1
              ? "Submit"
              : "Next Question"}
          </button>
        </div>
      </div>
    );
  }
  // QUIZ results
  return (
    <div className="p-20 font-sans">
      <h1>Quiz Complete!</h1>
      <p>Score: {(score / getMaxScore() * 100).toFixed(2)}%</p>
    </div>
  );
}

