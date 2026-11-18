/**
 * Utilities and validation helpers for the professor class creation form.
 * Conforms to API contract specification: POST /api/classes/
 */

export interface ClassNameValidation {
  isValid: boolean;
  error: string | null;
}

/**
 * Validates a class name input.
 * Class names cannot be blank or contain only whitespace.
 */
export function validateClassName(name: string): ClassNameValidation {
  const trimmed = name.trim();
  if (!trimmed) {
    return {
      isValid: false,
      error: "Class name is required.",
    };
  }

  if (trimmed.length > 255) {
    return {
      isValid: false,
      error: "Class name cannot exceed 255 characters.",
    };
  }

  return {
    isValid: true,
    error: null,
  };
}

/**
 * Formats a server error response into a human-readable message.
 */
export function formatCreateClassErrorMessage(error: string | null | undefined): string {
  if (!error) {
    return "Could not create class. Please try again.";
  }

  // Handle common server detail strings or fallback gracefully
  if (error.includes("blank") || error.includes("required")) {
    return "Class name is required.";
  }

  return error;
}
