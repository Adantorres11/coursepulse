import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  createLectureQuestion,
  deleteLectureQuestion,
  getLectureQuestions,
  getProfessorClasses,
  getProfessorClassLectures,
  publishLecture,
  unpublishLecture,
  updateLectureQuestion,
} from "../lib/apiClient";
import {
  questionInputFromDraft,
  validateQuestionDraft,
  type QuestionDraft,
} from "../lib/lectureReview";
import type {
  DifficultyLevel,
  ProfessorClass,
  ProfessorLecture,
  ProfessorQuestion,
} from "../types/api";
import { ProfessorNav } from "./ProfessorNav";

const DIFFICULTIES: DifficultyLevel[] = ["easy", "medium", "hard"];

function blankDraft(): QuestionDraft {
  return {
    prompt: "",
    choices: ["", "", "", ""],
    correctIndex: 0,
    difficulty: "easy",
  };
}

function draftFromQuestion(question: ProfessorQuestion): QuestionDraft {
  return {
    prompt: question.prompt,
    choices: [...question.choices],
    correctIndex: question.correct_index,
    difficulty: question.difficulty,
  };
}

export function LectureReview() {
  const { classId, lectureId } = useParams();
  const [classInfo, setClassInfo] = useState<ProfessorClass | null>(null);
  const [lecture, setLecture] = useState<ProfessorLecture | null>(null);
  const [questions, setQuestions] = useState<ProfessorQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<QuestionDraft>(blankDraft);
  const [addDraft, setAddDraft] = useState<QuestionDraft>(blankDraft);

  useEffect(() => {
    let active = true;

    async function load() {
      if (!classId || !lectureId) {
        setError("Invalid lecture.");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);

      const [classesResult, lecturesResult, questionsResult] = await Promise.all([
        getProfessorClasses(),
        getProfessorClassLectures(classId),
        getLectureQuestions(lectureId),
      ]);

      if (!active) return;

      const selectedClass = classesResult.data?.find(
        (item) => String(item.id) === classId
      );
      const selectedLecture = lecturesResult.data?.find(
        (item) => String(item.id) === lectureId
      );

      if (
        classesResult.error ||
        lecturesResult.error ||
        questionsResult.error ||
        !selectedClass ||
        !selectedLecture ||
        !questionsResult.data
      ) {
        setError(
          classesResult.error ||
            lecturesResult.error ||
            questionsResult.error ||
            "Lecture not found."
        );
        setLoading(false);
        return;
      }

      const ordered = [...questionsResult.data].sort(
        (a, b) => a.position - b.position || a.id - b.id
      );
      setClassInfo(selectedClass);
      setLecture(selectedLecture);
      setQuestions(ordered);
      setLoading(false);
    }

    void load();
    return () => {
      active = false;
    };
  }, [classId, lectureId, reloadKey]);

  const published = lecture?.status === "published" || Boolean(lecture?.published_at);
  const canEdit = Boolean(lecture) && !published;
  const canPublish = lecture?.status === "ready" && !published;

  async function runAction(action: () => Promise<string | null>) {
    setBusy(true);
    setActionError(null);
    const message = await action();
    setBusy(false);
    if (message) {
      setActionError(message);
      return;
    }
    setEditingId(null);
    setAddDraft(blankDraft());
    setReloadKey((key) => key + 1);
  }

  function saveEdit(event: FormEvent) {
    event.preventDefault();
    if (!lectureId || editingId == null) return;
    const problem = validateQuestionDraft(editDraft);
    if (problem) {
      setActionError(problem);
      return;
    }
    void runAction(async () => {
      const result = await updateLectureQuestion(
        lectureId,
        editingId,
        questionInputFromDraft(editDraft)
      );
      return result.error;
    });
  }

  function saveNew(event: FormEvent) {
    event.preventDefault();
    if (!lectureId) return;
    const problem = validateQuestionDraft(addDraft);
    if (problem) {
      setActionError(problem);
      return;
    }
    void runAction(async () => {
      const result = await createLectureQuestion(
        lectureId,
        questionInputFromDraft(addDraft)
      );
      return result.error;
    });
  }

  function removeQuestion(question: ProfessorQuestion) {
    if (!lectureId) return;
    if (!window.confirm("Delete this question?")) return;
    void runAction(async () => {
      const result = await deleteLectureQuestion(lectureId, question.id);
      return result.error;
    });
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <ProfessorNav
        currentClass={classInfo ? { id: classInfo.id, name: classInfo.name } : null}
      />

      <div className="max-w-3xl mx-auto px-4 sm:px-8 py-8">
        <Link
          to={`/professor/class/${classId ?? ""}`}
          className="text-sky-400 hover:text-sky-300 text-sm"
        >
          ← Back to class
        </Link>

        {loading ? (
          <p className="mt-8 text-slate-400">Loading questions...</p>
        ) : error ? (
          <p role="alert" className="mt-8 text-red-400">
            {error}
          </p>
        ) : lecture ? (
          <>
            <header className="mt-6">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Review questions
              </p>
              <h1 className="text-3xl font-bold mt-1">{lecture.title}</h1>
              <p className="text-slate-400 mt-2 capitalize">
                Status: {lecture.status}
                {published ? " · Students can take this quiz" : " · Hidden from students"}
              </p>
            </header>

            <div className="mt-4 flex flex-wrap gap-3">
              {canPublish && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(async () => (await publishLecture(lecture.id)).error)
                  }
                  className="px-4 py-2 rounded-xl bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm disabled:opacity-60"
                >
                  Publish quiz
                </button>
              )}
              {published && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(async () => (await unpublishLecture(lecture.id)).error)
                  }
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-sm disabled:opacity-60"
                >
                  Unpublish
                </button>
              )}
            </div>

            {!published && lecture.status !== "ready" && (
              <p className="mt-4 text-sm text-slate-400">
                This lecture is {lecture.status}. You can publish it once it is ready.
              </p>
            )}

            {published && (
              <p className="mt-4 text-sm text-slate-400">
                Unpublish the quiz to edit, add, or delete questions.
              </p>
            )}

            {actionError && (
              <p role="alert" className="mt-4 text-sm text-rose-300">
                {actionError}
              </p>
            )}

            <ol className="mt-6 space-y-4">
              {questions.map((question, index) => (
                <li
                  key={question.id}
                  className="bg-slate-900 border border-slate-800 rounded-xl p-5"
                >
                  {editingId === question.id ? (
                    <QuestionForm
                      draft={editDraft}
                      onChange={setEditDraft}
                      onSubmit={saveEdit}
                      submitLabel="Save question"
                      disabled={busy}
                      onCancel={() => setEditingId(null)}
                    />
                  ) : (
                    <>
                      <div className="flex items-start justify-between gap-3">
                        <h2 className="font-semibold">
                          {index + 1}. {question.prompt}
                        </h2>
                        <span className="text-xs font-semibold capitalize px-2 py-1 rounded-full bg-slate-800 text-sky-300 shrink-0">
                          {question.difficulty}
                        </span>
                      </div>
                      <ul className="mt-3 space-y-2">
                        {question.choices.map((choice, choiceIndex) => (
                          <li
                            key={`${question.id}-${choiceIndex}`}
                            className={`rounded-lg px-3 py-2 text-sm ${
                              choiceIndex === question.correct_index
                                ? "bg-sky-500/15 text-sky-200 border border-sky-500/40"
                                : "bg-slate-950 text-slate-300 border border-slate-800"
                            }`}
                          >
                            {choice}
                            {choiceIndex === question.correct_index ? " · Correct" : ""}
                          </li>
                        ))}
                      </ul>
                      {canEdit && (
                        <div className="mt-4 flex gap-3">
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => {
                              setEditingId(question.id);
                              setEditDraft(draftFromQuestion(question));
                              setActionError(null);
                            }}
                            className="text-sm font-semibold text-sky-400 hover:text-sky-300"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => removeQuestion(question)}
                            className="text-sm font-semibold text-rose-300 hover:text-rose-200"
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </li>
              ))}
            </ol>

            {questions.length === 0 && (
              <p className="mt-6 text-slate-400">No questions yet.</p>
            )}

            {canEdit && (
              <section className="mt-8 bg-slate-900 border border-slate-800 rounded-xl p-5">
                <h2 className="text-lg font-bold mb-4">Add a question</h2>
                <QuestionForm
                  draft={addDraft}
                  onChange={setAddDraft}
                  onSubmit={saveNew}
                  submitLabel="Add question"
                  disabled={busy}
                />
              </section>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}

function QuestionForm({
  draft,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
  onCancel,
}: {
  draft: QuestionDraft;
  onChange: (draft: QuestionDraft) => void;
  onSubmit: (event: FormEvent) => void;
  submitLabel: string;
  disabled: boolean;
  onCancel?: () => void;
}) {
  const promptId = `${submitLabel}-prompt`;

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div>
        <label htmlFor={promptId} className="block text-xs font-semibold text-slate-300 mb-1">
          Prompt
        </label>
        <textarea
          id={promptId}
          value={draft.prompt}
          disabled={disabled}
          onChange={(event) => onChange({ ...draft, prompt: event.target.value })}
          rows={3}
          className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white"
        />
      </div>

      <fieldset className="space-y-2">
        <legend className="text-xs font-semibold text-slate-300">Choices</legend>
        {draft.choices.map((choice, index) => (
          <div key={index} className="flex items-center gap-2">
            <input
              type="radio"
              name={`${submitLabel}-correct`}
              checked={draft.correctIndex === index}
              disabled={disabled}
              onChange={() => onChange({ ...draft, correctIndex: index })}
              aria-label={`Mark choice ${index + 1} correct`}
            />
            <input
              value={choice}
              disabled={disabled}
              aria-label={`Choice ${index + 1}`}
              onChange={(event) => {
                const choices = [...draft.choices];
                choices[index] = event.target.value;
                onChange({ ...draft, choices });
              }}
              className="flex-1 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white"
            />
          </div>
        ))}
      </fieldset>

      <div>
        <label className="block text-xs font-semibold text-slate-300 mb-1" htmlFor={`${submitLabel}-difficulty`}>
          Difficulty
        </label>
        <select
          id={`${submitLabel}-difficulty`}
          value={draft.difficulty}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...draft, difficulty: event.target.value as DifficultyLevel })
          }
          className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-white"
        >
          {DIFFICULTIES.map((level) => (
            <option key={level} value={level}>
              {level}
            </option>
          ))}
        </select>
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={disabled}
          className="px-4 py-2 rounded-xl bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-sm disabled:opacity-60"
        >
          {submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            disabled={disabled}
            onClick={onCancel}
            className="px-4 py-2 rounded-xl text-sm text-slate-300"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
