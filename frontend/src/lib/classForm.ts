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
 * Formats a create-class error. Only the name field's blank or required
 * errors become "Class name is required." Other fields keep their own text.
 */
export function formatCreateClassErrorMessage(
  error: string | null | undefined,
  fields?: Record<string, string[]> | null,
): string {
  const nameErrors = fields?.name ?? [];
  if (nameErrors.length > 0) {
    const text = nameErrors.join(" ");
    if (/blank|required/i.test(text)) {
      return "Class name is required.";
    }
    return text;
  }

  if (!error) {
    return "Could not create class. Please try again.";
  }

  const namesTheClassName =
    /^name\b/i.test(error.trim()) || /\bclass name\b/i.test(error);
  if (namesTheClassName && /blank|required/i.test(error)) {
    return "Class name is required.";
  }

  return error;
}
