/** Label for a person. A username replaces the name when the API sends one. */
export function personLabel(person: {
  name: string;
  username?: string | null;
}): string {
  const username = person.username?.trim();
  if (username) return username;
  return person.name;
}
