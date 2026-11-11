import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "../lib/apiClient";

interface LeaderboardEntry {
  rank: number;
  display_name: string;
  points: number;
  is_current_user: boolean;
}

interface LeaderboardModalProps {
  classroomId: number;
  onClose: () => void;
}

export function LeaderboardModal({
  classroomId,
  onClose,
}: LeaderboardModalProps) {
  
const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState("");
const dialogRef = useRef<HTMLElement>(null);

useEffect(() => {
  let active = true;
  let timer: number | undefined;
  const controller = new AbortController();

  setEntries([]);
  setLoading(true);
  setError("");

  const loadLeaderboard = async () => {
    const token = sessionStorage.getItem("coursepulse_token");

    if (!token) {
      setError("Please log in to view the leaderboard.");
      setLoading(false);
      return;
    }

    let shouldRefresh = true;

    try {
      const response = await fetch(
        `${API_BASE_URL}/classes/${classroomId}/leaderboard/`,
        {
          headers: { Authorization: `Token ${token}` },
          signal: controller.signal,
        }
      );

      const data = await response.json();

      if (!active) return;

      if (!response.ok) {
        setError(data.detail || "Unable to load the leaderboard.");

        if ([401, 403, 404].includes(response.status)) {
          setEntries([]);
          shouldRefresh = false;
        }
      } else {
        setEntries(data);
        setError("");
      }
    } catch {
      if (active) {
        setError("Could not refresh the leaderboard. Retrying shortly.");
      }
    } finally {
      if (active) {
        setLoading(false);

        if (shouldRefresh) {
          timer = window.setTimeout(loadLeaderboard, 10000);
        }
      }
    }
  };

  void loadLeaderboard();

  return () => {
    active = false;
    window.clearTimeout(timer);
    controller.abort();
  };
}, [classroomId]);

useEffect(() => {
  const previouslyFocused = document.activeElement as HTMLElement | null;
  const previousOverflow = document.body.style.overflow;
  const closeButton = dialogRef.current?.querySelector<HTMLButtonElement>(
    'button[aria-label="Close leaderboard"]'
  );

  document.body.style.overflow = "hidden";
  closeButton?.focus();

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }

    if (event.key === "Tab") {
      event.preventDefault();
      closeButton?.focus();
    }
  };

  document.addEventListener("keydown", handleKeyDown);

  return () => {
    document.removeEventListener("keydown", handleKeyDown);
    document.body.style.overflow = previousOverflow;
    previouslyFocused?.focus();
  };
}, [onClose]);

    return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="leaderboard-title"
        aria-describedby="leaderboard-subtitle"
        className="max-h-[90dvh] w-full max-w-lg overflow-y-auto rounded-3xl border border-slate-700 bg-[#191e32] p-5 text-white sm:p-7"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="leaderboard-title" className="text-2xl font-bold">
              Leaderboard
            </h2>
            <p
              id="leaderboard-subtitle"
              className="mt-1 text-sm text-slate-400"
            >
              Total points across all lectures
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close leaderboard"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-700 text-2xl hover:bg-slate-600"
          >
            &times;
          </button>
        </div>

        <div className="mt-6">
  {loading && (
    <p role="status" className="text-sm text-slate-400">
      Loading leaderboard...
    </p>
  )}

  {error && (
    <p role="alert" className="mb-4 text-sm text-red-400">
      {error}
    </p>
  )}

  {!loading && !error && entries.length === 0 && (
    <p className="text-sm text-slate-400">
      No students on the leaderboard yet.
    </p>
  )}

  <ol className="space-y-2">
    {entries.map((entry, index) => (
      <li
        key={index}
        className={`flex items-center gap-3 rounded-2xl border p-3 sm:p-4 ${
          entry.is_current_user
            ? "border-sky-400 bg-[#223850]"
            : "border-slate-700 bg-[#1e253b]"
        }`}
      >
        <span
          className={`flex h-9 min-w-9 shrink-0 items-center justify-center rounded-full px-2 font-bold ${
            entry.is_current_user
              ? "bg-sky-400 text-slate-950"
              : "bg-slate-700 text-slate-200"
          }`}
        >
          {entry.rank}
        </span>

        <span className="min-w-0 flex-1 break-words font-semibold">
          {entry.is_current_user ? "You" : entry.display_name}
        </span>

        <span
          className={`shrink-0 font-bold ${
            entry.is_current_user ? "text-sky-400" : "text-white"
          }`}
        >
          {entry.points.toLocaleString()}{" "}
          <span className="text-xs font-normal text-slate-400">pts</span>
        </span>
      </li>
    ))}
  </ol>
</div>
      </section>
    </div>
  );
}