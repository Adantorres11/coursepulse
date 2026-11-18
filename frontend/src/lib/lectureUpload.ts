/**
 * Upload rules shared by the lecture upload screen.
 * Keep this list in sync with LectureUploadSerializer.validate_recording
 * in backend/classrooms/serializers.py.
 */
export const ALLOWED_RECORDING_EXTENSIONS = [
  ".mp3",
  ".mp4",
  ".m4a",
  ".wav",
  ".mov",
  ".mkv",
  ".webm",
  ".avi",
  ".ogg",
  ".flac",
  ".aac",
];

/** Value for the file input's accept attribute. */
export const RECORDING_ACCEPT = ALLOWED_RECORDING_EXTENSIONS.join(",");

/** True when the file name ends in an extension the backend accepts. */
export function isAllowedRecording(fileName: string): boolean {
  const lowerName = fileName.toLowerCase();
  return ALLOWED_RECORDING_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
}

function firstMessage(value: unknown): string | null {
  if (typeof value === "string" && value) return value;
  if (Array.isArray(value) && typeof value[0] === "string" && value[0]) return value[0];
  return null;
}

/** Turns a failed upload response into a readable message. */
export function uploadErrorMessage(status: number, responseText: string): string {
  const fallback = `Upload failed (HTTP ${status}). Please try again.`;
  try {
    const body = JSON.parse(responseText) as Record<string, unknown>;
    for (const key of ["recording", "title", "detail", "error", "non_field_errors", "file"]) {
      const message = firstMessage(body?.[key]);
      if (message) return message;
    }
  } catch {
    // Not JSON; keep the fallback message.
  }
  return fallback;
}
