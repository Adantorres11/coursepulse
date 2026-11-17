
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getProfessorClasses,
  getClassRoster,
  getProfessorClassLectures,
} from "../lib/apiClient";
import type {
  ProfessorClass,
  ProfessorLecture,
  ClassRosterStudent,
} from "../types/api";
import { ProfessorNav } from "./ProfessorNav";

export function ProfessorClassDetail() {
  const { classId } = useParams();

  const [classInfo, setClassInfo] = useState<ProfessorClass | null>(null);
  const [lectures, setLectures] = useState<ProfessorLecture[]>([]);
  const [students, setStudents] = useState<ClassRosterStudent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!classId) {
      setError("Invalid class ID.");
      setLoading(false);
      return;
    }

    let active = true;

    async function loadClass() {
      setLoading(true);
      setError(null);

      const [classesResult, lecturesResult, rosterResult] =
        await Promise.all([
          getProfessorClasses(),
          getProfessorClassLectures(classId!),
          getClassRoster(classId!),
        ]);

      if (!active) return;

      const selectedClass = classesResult.data?.find(
        (item) => String(item.id) === classId
      );

      if (
        classesResult.error ||
        lecturesResult.error ||
        rosterResult.error ||
        !selectedClass
      ) {
        setError(
          classesResult.error ||
          lecturesResult.error ||
          rosterResult.error ||
          "Class not found."
        );
      } else {
        setClassInfo(selectedClass);
        setLectures(lecturesResult.data ?? []);
        setStudents(rosterResult.data ?? []);
      }

      setLoading(false);
    }

    void loadClass();

    return () => {
      active = false;
    };
  }, [classId]);

  async function copyCode() {
    if (!classInfo) return;

    try {
      await navigator.clipboard.writeText(classInfo.access_code);
      setCopied(true);
    } catch {
      setError("Could not copy the class code.");
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <ProfessorNav
        currentClass={
          classInfo
            ? { id: classInfo.id, name: classInfo.name }
            : null
        }
      />

      <div className="max-w-6xl mx-auto px-4 sm:px-8 py-8">
        <Link
          to="/professor"
          className="text-sky-400 hover:text-sky-300 text-sm"
        >
          ← Back to Dashboard
        </Link>

        {loading ? (
          <p className="mt-8 text-slate-400">Loading class...</p>
        ) : error ? (
          <p role="alert" className="mt-8 text-red-400">
            {error}
          </p>
        ) : classInfo ? (
          <>
            <section className="mt-6 bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h1 className="text-3xl font-bold">
                {classInfo.name}
              </h1>

              <div className="flex flex-wrap items-center gap-3 mt-4">
                <span className="text-slate-400">
                  Join code:
                </span>
                <span className="font-mono font-bold text-sky-400">
                  {classInfo.access_code}
                </span>
                <button
                  type="button"
                  onClick={() => void copyCode()}
                  className="px-3 py-1 rounded-lg bg-sky-600 hover:bg-sky-500 text-sm"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
              </div>

              <p className="text-slate-400 mt-4">
                {students.length} students · {lectures.length} lectures
              </p>
            </section>

            <section className="mt-8">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-xl font-bold">Lectures</h2>
                <button
                  type="button"
                  disabled
                  title="Lecture upload screen is being developed."
                  className="px-4 py-2 rounded-lg bg-slate-700 text-slate-300 cursor-not-allowed"
                >
                  + Upload Lecture
                </button>
              </div>

              {lectures.length === 0 ? (
                <p className="text-slate-400 mt-4">
                  No lectures uploaded yet.
                </p>
              ) : (
                <div className="mt-4 space-y-3">
                  {lectures.map((lecture) => (
                    <div
                      key={lecture.id}
                      className="flex items-center justify-between gap-3 bg-slate-900 border border-slate-800 rounded-xl p-4"
                    >
                      <p className="font-medium">{lecture.title}</p>
                      <span className="text-xs font-semibold capitalize px-3 py-1 rounded-full bg-slate-800 text-sky-300">
                        {lecture.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="mt-8">
              <h2 className="text-xl font-bold">Student Roster</h2>

              {students.length === 0 ? (
                <p className="text-slate-400 mt-4">
                  No students yet.
                </p>
              ) : (
                <div className="mt-4 bg-slate-900 border border-slate-800 rounded-xl divide-y divide-slate-800">
                  {students.map((student, index) => (
                    <div
                      key={`${student.name}-${index}`}
                      className="flex justify-between gap-4 p-4"
                    >
                      <span>{student.name}</span>
                      <span className="text-sm text-slate-400">
                        Joined{" "}
                        {new Date(student.joined_at).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        ) : null}
      </div>
    </div>
  );
}
