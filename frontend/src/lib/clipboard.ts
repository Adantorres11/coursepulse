export const COPY_FAILED_MESSAGE = "Could not copy the class code.";

/** Copies text. Returns true only when the clipboard write succeeds. */
export async function writeClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
