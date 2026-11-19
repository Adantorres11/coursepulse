import { useEffect, useState } from "react";
import { getLeaderboard } from "../lib/apiClient";

interface ClassRankCardProps {
  classroomId: number;
  onOpen: (classroomId: number) => void;
}

export function ClassRankCard({ classroomId, onOpen }: ClassRankCardProps) {
  const [myRank, setMyRank] = useState<number | null>(null);
  const [points, setPoints] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setMyRank(null);
    setPoints(null);

    const loadRank = async () => {
      if (!sessionStorage.getItem("coursepulse_token")) return;
      const result = await getLeaderboard(classroomId, controller.signal);
      if (!active || result.error || !result.data) return;
      const currentUser = result.data.find((entry) => entry.is_current_user);
      setMyRank(currentUser?.rank ?? null);
      setPoints(currentUser?.points ?? null);
    };

    void loadRank();
    return () => {
      active = false;
      controller.abort();
    };
  }, [classroomId]);

  if (myRank === null && points === null) return null;

  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onOpen(classroomId);
      }}
      className="inline-flex items-center gap-2 rounded-lg px-1 py-1 text-sm hover:text-white"
      aria-label={
        myRank !== null
          ? `Rank ${myRank}${points !== null ? `, ${points} points` : ""}. View leaderboard`
          : "View leaderboard"
      }
    >
      {points !== null && (
        <span className="font-semibold text-sky-300">{points.toLocaleString()} pts</span>
      )}
      {myRank !== null && <span className="font-bold text-white">#{myRank}</span>}
    </button>
  );
}
