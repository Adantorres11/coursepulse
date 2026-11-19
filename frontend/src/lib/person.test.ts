import { describe, expect, it } from "vitest";
import { personLabel } from "./person";

describe("personLabel", () => {
  it("uses the full name when there is no username", () => {
    expect(personLabel({ name: "Ada Lovelace", username: null })).toBe("Ada Lovelace");
  });

  it("prefers a username when one is present", () => {
    expect(personLabel({ name: "Ada Lovelace", username: "ada" })).toBe("ada");
  });

  it("ignores a blank username", () => {
    expect(personLabel({ name: "Ada Lovelace", username: "  " })).toBe("Ada Lovelace");
  });
});
