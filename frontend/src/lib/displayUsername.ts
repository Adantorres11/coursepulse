/**
 * The name to show for a person. It is their username, never an email.
 * Prefer this over reading email, name, or display_name directly.
 *
 * Mirrors backend accounts.usernames.display_username.
 */
const UNSAFE = /[^A-Za-z0-9_-]/g;

export function displayUsername(
  person:
    | string
    | {
        username?: string | null;
        name?: string | null;
        display_name?: string | null;
      }
    | null
    | undefined,
): string {
  const raw =
    typeof person === "string"
      ? person
      : person?.username || person?.name || person?.display_name || "";
  return usernameForDisplay(raw);
}

export function usernameForDisplay(username: string): string {
  const trimmed = username.trim();
  if (!trimmed.includes("@")) {
    return trimmed;
  }
  const local = trimmed
    .split("@")[0]
    .replace(UNSAFE, "")
    .replace(/^[-_]+|[-_]+$/g, "");
  return local || "user";
}
