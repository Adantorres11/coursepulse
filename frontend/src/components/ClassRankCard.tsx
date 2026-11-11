import { useEffect, useState } from "react";
import { API_BASE_URL } from "../lib/apiClient";

interface RankEntry {
  rank: number;
  points: number;
  is_current_user: boolean;
}

interface ClassRankCardProps {
  classroomId: number;
  onOpen: (classroomId: number) => void;
}

export function ClassRankCard({
  classroomId,
  onOpen,
}: ClassRankCardProps) {
  
    const [myRank, setMyRank] = useState<number | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
  let active = true;
  const controller = new AbortController();

  setMyRank(null);
  setLoading(true);
  setError("");

  const loadRank = async () => {
    const token = sessionStorage.getItem("coursepulse_token");

    if (!token) {
      setError("Log in to see your rank.");
      setLoading(false);
      return;
    }

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
        setError(data.detail || "Unable to load your rank.");
        return;
      }

      const entries: RankEntry[] = data;
      const currentUser = entries.find((entry) => entry.is_current_user);

      setMyRank(currentUser?.rank ?? null);
    } catch {
      if (active) setError("Unable to load your rank.");
    } finally {
      if (active) setLoading(false);
    }
  };

  void loadRank();

  return () => {
    active = false;
    controller.abort();
  };
}, [classroomId]);

    return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onOpen(classroomId);
      }}
      className="w-full rounded-2xl border border-sky-400/40 bg-[#142342] p-4 text-left hover:border-sky-400 focus-visible:outline-2 focus-visible:outline-sky-400"
    >
      <span className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
        Your rank
      </span>
      <span className="mt-2 block text-2xl font-bold text-white">
        {loading
            ? "Loading..."
            : error
            ? "Unavailable"
            : myRank !== null
                ? `#${myRank}`
                : "Not ranked yet"}
        </span>

        {error && (
        <span className="mt-1 block text-sm text-red-400">
            {error}
        </span>
        )}
      <span className="mt-2 block text-sm font-semibold text-sky-300">
        View leaderboard &rarr;
      </span>
    </button>
  );
}