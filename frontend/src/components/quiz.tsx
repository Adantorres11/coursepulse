import { useState } from "react";

interface QuizQuestion {
  question: string;
  answers: string[];
  correctAnswer: number;
}

export default function MathQuiz() {
  const [score, setScore] = useState<number>(0);
  const [questionIndex, setQuestionIndex] = useState<number>(0);

// QUIZ questions, can be easily adjusted later. Will need to connect to question database / AI creating questions.
  const questions: QuizQuestion[] = [
    {
      question: "What's 2 + 2?",
      answers: ["3", "4", "5"],
      correctAnswer: 1
    },
    {
      question: "What's 4 + 3?",
      answers: ["3", "6", "7"],
      correctAnswer: 2
    },
    {
      question: "What's 10 + 10?",
      answers: ["20", "13", "19"],
      correctAnswer: 0
    }
  ];

  const [selectedAnswers, setSelectedAnswers] = useState<(number | null)[]>(
    Array(questions.length).fill(null)
  );

  // sets color of buttons based on user input
  function getAnswerColor(answerIndex: number) {
    if (selectedAnswers[questionIndex] !== null && answerIndex === questions[questionIndex].correctAnswer) {
      return "green";
    }
    else if(selectedAnswers[questionIndex] === answerIndex) {
      return "red";
    }
    return "white";
  }

// adjusts score based on which quiz answer selected
  function handleAnswer(answerIndex: number) {
    setSelectedAnswers((prev) => {
      const updated = [...prev];
      updated[questionIndex] = answerIndex;
      return updated;
    });

    if (answerIndex === questions[questionIndex].correctAnswer) {
      setScore(score + 1);
    }

    setQuestionIndex(questionIndex + 1);
  }

// returns the maximum possible score for the results screen
  function getMaxScore(): number {
    let maxScore = 0;
    for (let i = 0; i < questions.length; i++) {
      maxScore += 1;
    }
    return maxScore;
  }

  if (questionIndex < questions.length) {
    // QUIZ in progress
    return (
      <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
        <h1>{questions[questionIndex].question}</h1>
        <p>Score: {score}</p>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className = "quiz-button" onClick={() => handleAnswer(0)} style = {{backgroundColor: getAnswerColor(0)}}>
            {questions[questionIndex].answers[0]}
          </button>
          <button className = "quiz-button" onClick={() => handleAnswer(1)} style = {{backgroundColor: getAnswerColor(1)}}>
            {questions[questionIndex].answers[1]}
          </button>
          <button className = "quiz-button" onClick={() => handleAnswer(2)} style = {{backgroundColor: getAnswerColor(2)}}>
            {questions[questionIndex].answers[2]}
          </button>
        </div>
      </div>
    );
  }
  // QUIZ results
  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>Quiz Complete!</h1>
      <p>Score: {score}/{getMaxScore()}</p>
    </div>
  );
}
