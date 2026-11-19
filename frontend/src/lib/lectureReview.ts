import type { DifficultyLevel, ProfessorLecture, ProfessorQuestionInput } from "../types/api";

export interface QuestionDraft {
  prompt: string;
  choices: string[];
  correctIndex: number;
  difficulty: DifficultyLevel;
}

export function lectureReviewPath(
  classId: string | number,
  lectureId: string | number
): string {
  return `/professor/class/${classId}/lectures/${lectureId}`;
}

export function professorResultsPath(classId: string | number): string {
  return `/professor/class/${classId}/results`;
}

/** Ready and published lectures have questions a professor can review. */
export function lectureCanBeReviewed(status: ProfessorLecture["status"]): boolean {
  return status === "ready" || status === "published";
}

/** Edit, add, and delete are only for an unpublished lecture whose status is ready. */
export function canEditLectureQuestions(status: ProfessorLecture["status"]): boolean {
  return status === "ready";
}

export function validateQuestionDraft(draft: QuestionDraft): string | null {
  if (!draft.prompt.trim()) {
    return "Enter a question.";
  }
  if (draft.choices.length !== 4) {
    return "Provide exactly four choices.";
  }
  const trimmed = draft.choices.map((choice) => choice.trim());
  if (trimmed.some((choice) => choice === "")) {
    return "Choices cannot be blank.";
  }
  const folded = new Set(trimmed.map((choice) => choice.toLocaleLowerCase()));
  if (folded.size !== 4) {
    return "Choices must be unique.";
  }
  if (![0, 1, 2, 3].includes(draft.correctIndex)) {
    return "Choose the correct answer.";
  }
  if (!["easy", "medium", "hard"].includes(draft.difficulty)) {
    return "Choose a difficulty.";
  }
  return null;
}

export function questionInputFromDraft(draft: QuestionDraft): ProfessorQuestionInput {
  return {
    prompt: draft.prompt.trim(),
    choices: draft.choices.map((choice) => choice.trim()),
    correct_index: draft.correctIndex,
    difficulty: draft.difficulty,
  };
}
