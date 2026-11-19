import { describe, expect, it } from "vitest";
import {
  lectureCanBeReviewed,
  lectureReviewPath,
  questionInputFromDraft,
  validateQuestionDraft,
  type QuestionDraft,
} from "./lectureReview";

function draft(overrides: Partial<QuestionDraft> = {}): QuestionDraft {
  return {
    prompt: "What is a sprint?",
    choices: ["A time box", "A bug", "A branch", "A test"],
    correctIndex: 0,
    difficulty: "easy",
    ...overrides,
  };
}

describe("lecture review links", () => {
  it("links ready and published lectures to the review page", () => {
    expect(lectureCanBeReviewed("ready")).toBe(true);
    expect(lectureCanBeReviewed("published")).toBe(true);
    expect(lectureCanBeReviewed("pending")).toBe(false);
    expect(lectureCanBeReviewed("processing")).toBe(false);
    expect(lectureCanBeReviewed("failed")).toBe(false);
    expect(lectureReviewPath(4, 9)).toBe("/professor/class/4/lectures/9");
  });
});

describe("validateQuestionDraft", () => {
  it("accepts four unique choices", () => {
    expect(validateQuestionDraft(draft())).toBeNull();
  });

  it("rejects a blank prompt, a blank choice, and duplicate choices", () => {
    expect(validateQuestionDraft(draft({ prompt: "  " }))).toBe("Enter a question.");
    expect(validateQuestionDraft(draft({ choices: ["A", "B", " ", "D"] }))).toBe(
      "Choices cannot be blank."
    );
    expect(validateQuestionDraft(draft({ choices: ["Yes", " yes ", "No", "Maybe"] }))).toBe(
      "Choices must be unique."
    );
    expect(validateQuestionDraft(draft({ choices: ["A", "B", "C"] }))).toBe(
      "Provide exactly four choices."
    );
  });

  it("trims choices in the request body", () => {
    expect(
      questionInputFromDraft(draft({ choices: ["  A  ", "B", "C", "D"] })).choices
    ).toEqual(["A", "B", "C", "D"]);
  });
});
