import { describe, expect, it } from "vitest";
import { displayUsername } from "./displayUsername";

describe("displayUsername", () => {
  it("returns the chosen username", () => {
    expect(displayUsername({ username: "torres11" })).toBe("torres11");
  });

  it("turns a legacy email username into the part before @", () => {
    expect(displayUsername("torres11@gmail.com")).toBe("torres11");
    expect(displayUsername("first.last+tag@school.edu")).toBe("firstlasttag");
    expect(displayUsername("@@@")).toBe("user");
  });

  it("does not fall back to an email address", () => {
    expect(
      displayUsername({
        username: "",
        name: "",
        display_name: "",
      }),
    ).toBe("");
  });

  it("prefers username, then name, then display_name", () => {
    expect(
      displayUsername({
        username: "ada",
        name: "Ada Lovelace",
        display_name: "Ada L.",
      }),
    ).toBe("ada");
    expect(displayUsername({ name: "ada", display_name: "Ada L." })).toBe("ada");
    expect(displayUsername({ display_name: "sam" })).toBe("sam");
  });
});
