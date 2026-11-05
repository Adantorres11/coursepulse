import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE_URL } from "../lib/apiClient";

interface Classroom {
  id: number;
  name: string;
  course_code: string;
  professor: {
    id: number;
    name: string;
  } | null;
  quiz_count: number;
  new_quiz_count: number;
}

export function JoinClassPage() {
  const [code, setCode] = useState("");
  
  const [foundClass, setFoundClass] = useState<Classroom | null>(null);
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [isJoining, setIsJoining] = useState(false);
  const [joinError, setJoinError] = useState("");
  const [joinSuccess, setJoinSuccess] = useState(false);

useEffect(() => {
  setFoundClass(null);
  setLookupError("");

  if (code.length !== 6) {
    setIsLookingUp(false);
    return;
  }

  const token = sessionStorage.getItem("coursepulse_token");

  if (!token) {
    setLookupError("Please log in before joining a class.");
    setIsLookingUp(false);
    return;
  }

  const controller = new AbortController();
  let active = true;
  setIsLookingUp(true);

  const timer = window.setTimeout(async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/classes/lookup/?code=${encodeURIComponent(code)}`,
        {
          headers: { Authorization: `Token ${token}` },
          signal: controller.signal,
        }
      );

      const data = await response.json();

      if (!active) return;

      if (response.ok) {
        setFoundClass(data);
      } else {
        setLookupError(
          response.status === 404
            ? "We couldn't find a class with that code"
            : data.detail || "Unable to check this code. Please try again."
        );
      }
    } catch {
      if (active) {
        setLookupError("Could not reach the server. Please try again.");
      }
    } finally {
      if (active) setIsLookingUp(false);
    }
  }, 300);

  return () => {
    active = false;
    window.clearTimeout(timer);
    controller.abort();
  };
}, [code]);

const handleJoin = async () => {
  if (!foundClass || isLookingUp || isJoining || joinSuccess) return;

  const token = sessionStorage.getItem("coursepulse_token");

  if (!token) {
    setJoinError("Please log in before joining a class.");
    return;
  }

  setIsJoining(true);
  setJoinError("");

  try {
    const response = await fetch(`${API_BASE_URL}/classes/join/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Token ${token}`,
      },
      body: JSON.stringify({ code }),
    });

    const data = await response.json();

    if (!response.ok) {
      setJoinError(data.detail || "Unable to join this class. Please try again.");
      return;
    }

    setJoinSuccess(true);
  } catch {
    setJoinError("Could not reach the server. Please try again.");
  } finally {
    setIsJoining(false);
  }
};

  return (
    <div className="min-h-screen bg-[#141625] text-white px-4 py-6">
      <header className="max-w-5xl mx-auto">
        <Link to="/hub" className="inline-flex items-center gap-2 font-bold">
          <img
            src="/assets/coursePulseLogo.png"
            alt=""
            className="w-8 h-8 rounded-full"
          />
          CoursePulse
        </Link>
      </header>

      <section className="max-w-md mx-auto mt-12 sm:mt-16">
        <Link to="/hub" className="text-sm text-sky-300 hover:underline">
          &larr; All classes
        </Link>

        <h1 className="mt-8 text-center text-3xl font-bold">
          Join a class
        </h1>

        <p className="mt-2 text-center text-sm text-slate-400">
          Enter the access code your professor gave you.
        </p>

        <div className="mt-8 rounded-2xl border border-slate-700/60 bg-[#191e30] p-6">
          <label
            htmlFor="class-code"
            className="block text-sm font-medium text-slate-200"
          >
            Class access code
          </label>

          <input
            id="class-code"
            disabled={isJoining}
            value={code}
            onChange={(e) => {
              const nextCode = e.target.value
                .toUpperCase()
                .replace(/[^A-Z0-9]/g, "")
                .slice(0, 6);

              if (nextCode === code) return;

              setCode(nextCode);
              setFoundClass(null);
              setLookupError("");
              setJoinError("");
              setJoinSuccess(false);
            }}
            type="text"
            maxLength={6}
            placeholder="ABC123"
            autoComplete="off"
            spellCheck={false}
            className="mt-2 w-full rounded-xl border border-slate-600 bg-[#20253a] px-4 py-4 text-center font-mono text-3xl uppercase tracking-[0.25em] text-white placeholder:text-slate-500 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
          />
          <div aria-live="polite" className="mt-4">
  {isLookingUp && (
    <p className="text-sm text-slate-400">Checking code...</p>
  )}

  {lookupError && (
    <p role="alert" className="text-sm text-red-400">
      {lookupError}
    </p>
  )}

  {foundClass && !isLookingUp && (
    <div className="rounded-xl border border-sky-400 bg-[#202d46] p-4">
      <p className="text-xs font-semibold uppercase tracking-widest text-sky-300">
        Class found
      </p>
      <h2 className="mt-1 font-bold">{foundClass.name}</h2>
      <p className="mt-1 text-sm text-slate-300">
        {[
          foundClass.course_code,
          foundClass.professor?.name,
          `${foundClass.quiz_count} ${
            foundClass.quiz_count === 1 ? "quiz" : "quizzes"
          }`,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
    </div>
  )}
</div>
          <button
            type="button"
            onClick={handleJoin}
            disabled={
              code.length !== 6 ||
              isLookingUp ||
              !foundClass ||
              isJoining ||
              joinSuccess
            }
            className="mt-5 w-full rounded-xl bg-sky-400 px-4 py-3 font-bold text-slate-950 hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isJoining
              ? "Joining..."
              : joinSuccess
                ? "Joined!"
                : "Join class →"}
          </button>
          <div aria-live="polite" className="mt-3">
            {joinError && (
              <p role="alert" className="text-sm text-red-400">
                {joinError}
              </p>
            )}

            {joinSuccess && (
              <p className="text-sm text-emerald-400">
                You successfully joined this class.{" "}
                <Link to="/hub" className="underline">
                  All classes
                </Link>
              </p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}