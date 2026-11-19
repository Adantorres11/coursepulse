// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProfessorNav } from "./ProfessorNav";
import { StudentNav } from "./StudentNav";

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: "torres11@gmail.com",
      username: "torres11",
      role: "student",
    },
    logout: vi.fn(),
  }),
}));

describe("person headers", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows the username in the student and professor headers", () => {
    render(
      <MemoryRouter>
        <StudentNav />
      </MemoryRouter>
    );
    expect(screen.getByText("torres11")).toBeTruthy();
    expect(screen.queryByText("torres11@gmail.com")).toBeNull();

    cleanup();
    render(
      <MemoryRouter>
        <ProfessorNav />
      </MemoryRouter>
    );
    expect(screen.getByText("torres11")).toBeTruthy();
    expect(screen.queryByText("torres11@gmail.com")).toBeNull();
  });
});
