import { useState } from "react";
import MathQuiz from "./components/quiz"
// Placeholder screen. The Student Hub and the quiz Arena replace this in Sprint 1.
export default function App() {
const [view, setView] = useState<"home" | "quiz">("home");
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-3 bg-slate-900 text-white">
      {view === "home" ? (
        // HOME PAGE VIEW
        <>
          <h1 className="text-4xl font-bold">CoursePulse</h1>
          <p className="text-slate-300">Keep the pulse on what you learned in lecture.</p>
          <p className="text-sm text-slate-500 mb-6">Walking skeleton: frontend is running.</p>
          
          <button 
            onClick={() => setView("quiz")}
            style={{ padding: "10px 20px", cursor: "pointer", backgroundColor: "#38bdf8", color: "#0f172a", border: "none", borderRadius: "6px", fontWeight: "bold" }}
          >
            Take Quiz →
          </button>
        </>
      ) : (
        // QUIZ PAGE VIEW
        <div className="flex flex-col items-center">
          <button 
            onClick={() => setView("home")}
            style={{ marginBottom: "20px", background: "none", border: "none", color: "#94a3b8", cursor: "pointer", textDecoration: "underline" }}
          >
            ← Back to Home
          </button>
          
          <MathQuiz />
        </div>
      )}
    </main>
  );
}
