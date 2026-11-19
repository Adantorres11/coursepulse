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

  it("rewrites blank and required errors that belong to the name field", () => {
    expect(
      formatCreateClassErrorMessage("This field may not be blank.", {
        name: ["This field may not be blank."],
      })
    ).toBe("Class name is required.");
    expect(
      formatCreateClassErrorMessage("ignored", {
        name: ["This field is required."],
      })
    ).toBe("Class name is required.");
    expect(formatCreateClassErrorMessage("name: This field may not be blank.")).toBe(
      "Class name is required."
    );
    expect(formatCreateClassErrorMessage("Class name is required.")).toBe(
      "Class name is required."
    );
  });

  it("leaves blank or required errors for other fields unchanged", () => {
    expect(formatCreateClassErrorMessage("This field may not be blank.")).toBe(
      "This field may not be blank."
    );
    expect(formatCreateClassErrorMessage("Password is required.")).toBe(
      "Password is required."
    );
    expect(formatCreateClassErrorMessage("Recording file may not be blank.")).toBe(
      "Recording file may not be blank."
    );
    expect(
      formatCreateClassErrorMessage("This field is required.", {
        recording: ["This field is required."],
      })
    ).toBe("This field is required.");
  });

  it("keeps a name-field error that is not a blank or required error", () => {
    expect(
      formatCreateClassErrorMessage("too long", {
        name: ["Ensure this field has no more than 255 characters."],
      })
    ).toBe("Ensure this field has no more than 255 characters.");
  });

  it("passes through readable permission errors", () => {
    expect(formatCreateClassErrorMessage("Only professors can create classes.")).toBe(
      "Only professors can create classes."
    );
  });
});
