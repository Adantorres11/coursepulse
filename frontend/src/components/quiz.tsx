import { useState } from "react";

interface QuizQuestion {
  prompt: string;
  choices: string[];
  correct_index: number;
  difficulty: number;
}

export default function MathQuiz() {
  const [score, setScore] = useState<number>(0);
  const [questionIndex, setQuestionIndex] = useState<number>(0);


// QUIZ questions, can be easily adjusted later. Will need to connect to question database / AI creating questions.
  const questions: QuizQuestion[] = [
    {
      prompt: "What's 2 + 2?",
      choices: ["3", "4", "5", "8"],
      correct_index: 1,
      difficulty: 1
    },
    {
      prompt: "What's 2 + 2?",
      choices: ["3", "4", "5"],
      correct_index: 1,
      difficulty: 1
    }
  ];

  const [selectedAnswers, setSelectedAnswers] = useState<(number | null)[]>(
    Array(questions.length).fill(null)
  );

  // sets color of buttons based on user input
  function getAnswerColor(answerIndex: number) {
    if (selectedAnswers[questionIndex] !== null && answerIndex === questions[questionIndex].correct_index) {
      return "#50C878";
    }
    else if(selectedAnswers[questionIndex] === answerIndex) {
      return "#F54927";
    }
    return "#708090";
  }

  // keeps track of which questions have been answered
  const [answeredQuestions, setAnsweredQuestions] = useState<boolean[]>(
    questions.map(() => false)
  );

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
      setScore(score + questions[questionIndex].difficulty);
    }

    setAnsweredQuestions((previous) => {
      const updated = [...previous];
      updated[questionIndex] = true;
      return updated;
    });
  }

  function nextQuestion() {
    if(questionIndex < questions.length - 1) {
      setQuestionIndex(questionIndex + 1);
    }
    else {
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
    let maxScore = 0;
    for (let i = 0; i < questions.length; i++) {
      maxScore += questions[i].difficulty;
    }
    return maxScore;
  }

  if (questionIndex < questions.length) {
    // QUIZ in progress
    return (
      <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
        <h1>{questions[questionIndex].prompt}</h1>
        <p>Score: {score}</p>
        <div style={{ display: "flex", gap: "10px" }}>
          {questions[questionIndex].choices.map((choice, index) => (
            <button
              key={index}
              className="text-black border border-black px-5 py-2 rounded-lg cursor-pointer"
              onClick={() => handleAnswer(index)}
              style={{ backgroundColor: getAnswerColor(index) }}
            >
              {choice}
            </button>
          ))}
        </div>
        <div>
          Question {questionIndex + 1} / {questions.length}
        </div>
        <div>
          <button className="bg-white text-black border border-black px-5 py-2 rounded-lg cursor-pointer" onClick={() => previousQuestion()}>
            Prev Question
          </button>
          <button className="bg-white text-black border border-black px-5 py-2 rounded-lg cursor-pointer" onClick={() => nextQuestion()}>
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
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>Quiz Complete!</h1>
      <p>Score: {score}/{getMaxScore()}</p>
    </div>
  );
}

