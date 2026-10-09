// Placeholder screen. The Student Hub and the quiz Arena replace this in Sprint 1.

import { useEffect } from "react";
import { getLectures } from "./lib/apiClient";

export default function App() {
  useEffect(() => {
    getLectures().then(console.log);
  }, []);
    
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-3 bg-slate-900 text-white">
      <h1 className="text-4xl font-bold">CoursePulse</h1>
      <p className="text-slate-300">Keep the pulse on what you learned in lecture.</p>
      <p className="text-sm text-slate-500">Walking skeleton: frontend is running.</p>
    </main>
  );
}
