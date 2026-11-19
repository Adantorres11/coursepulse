import { describe, expect, it } from "vitest";
import { formatCreateClassErrorMessage, validateClassName } from "./classForm";

describe("validateClassName", () => {
  it("rejects empty strings", () => {
    const result = validateClassName("");
    expect(result.isValid).toBe(false);
    expect(result.error).toBe("Class name is required.");
  });

  it("rejects strings containing only whitespace", () => {
    const result = validateClassName("   \t  \n  ");
    expect(result.isValid).toBe(false);
    expect(result.error).toBe("Class name is required.");
  });

  it("accepts valid class names", () => {
    const result = validateClassName("CS 3398 Software Engineering");
    expect(result.isValid).toBe(true);
    expect(result.error).toBeNull();
  });

  it("accepts class names with leading or trailing whitespace as long as content exists", () => {
    const result = validateClassName("   Data Structures   ");
    expect(result.isValid).toBe(true);
    expect(result.error).toBeNull();
  });

  it("rejects class names exceeding 255 characters", () => {
    const longName = "A".repeat(256);
    const result = validateClassName(longName);
    expect(result.isValid).toBe(false);
    expect(result.error).toBe("Class name cannot exceed 255 characters.");
  });
});

describe("formatCreateClassErrorMessage", () => {
  it("returns default message when error is empty or null", () => {
    expect(formatCreateClassErrorMessage(null)).toBe("Could not create class. Please try again.");
    expect(formatCreateClassErrorMessage("")).toBe("Could not create class. Please try again.");
  });

  it("normalizes blank or required field errors", () => {
    expect(formatCreateClassErrorMessage("This field may not be blank.")).toBe("Class name is required.");
    expect(formatCreateClassErrorMessage("name field is required")).toBe("Class name is required.");
  });

  it("passes through readable permission errors", () => {
    expect(formatCreateClassErrorMessage("Only professors can create classes.")).toBe(
      "Only professors can create classes."
    );
  });
});
