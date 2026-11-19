// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import { writeClipboard } from "../lib/clipboard";
import { ProfessorDashboard } from "./ProfessorDashboard";

vi.mock("../lib/clipboard", () => ({
  COPY_FAILED_MESSAGE: "Could not copy the class code.",
  writeClipboard: vi.fn(),
}));

vi.mock("../lib/apiClient", async () => {
  const actual = await vi.importActual<typeof import("../lib/apiClient")>("../lib/apiClient");
  return {
    ...actual,
    isProfessor: () => true,
    getStoredToken: () => "token",
    getStoredUser: () => ({ id: 1, email: "p@example.com", role: "professor" as const }),
    getCurrentUser: vi.fn(async () => ({
      data: { id: 1, email: "p@example.com", role: "professor" },
      error: null,
    })),
    clearSession: vi.fn(),
    getProfessorClasses: vi.fn(async () => ({
      data: [
        {
          id: 1,
          name: "Software Engineering",
          access_code: "ABC123",
          student_count: 2,
          lecture_count: 1,
        },
      ],
      error: null,
    })),
    createClass: vi.fn(async () => ({
      data: { id: 9, name: "Algorithms", access_code: "NEW123" },
      error: null,
    })),
  };
});

function renderDashboard() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <ProfessorDashboard />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("ProfessorDashboard copy", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(writeClipboard).mockReset();
  });

  it("shows Copied only when the class-card copy succeeds", async () => {
    const user = userEvent.setup();
    vi.mocked(writeClipboard).mockResolvedValue(false);
    renderDashboard();

    await screen.findByText("Software Engineering");
    await user.click(screen.getByRole("button", { name: /copy join code abc123/i }));

    expect(screen.queryByText("Copied!")).toBeNull();
    expect(screen.getByRole("alert").textContent).toBe("Could not copy the class code.");

    vi.mocked(writeClipboard).mockResolvedValue(true);
    await user.click(screen.getByRole("button", { name: /copy join code abc123/i }));
    expect(await screen.findByText("Copied!")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows Copied on the new-class dialog only when the copy succeeds", async () => {
    const user = userEvent.setup();
    vi.mocked(writeClipboard).mockResolvedValue(false);
    renderDashboard();

    await screen.findByText("Software Engineering");
    await user.click(screen.getByRole("button", { name: /create class/i }));
    await user.type(screen.getByLabelText("Class Name"), "Algorithms");
    await user.click(screen.getByRole("button", { name: /create class →/i }));
    expect(await screen.findByText("Class Created!")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Copy Code" }));
    expect(screen.queryByText("Copied!")).toBeNull();
    expect(screen.getByRole("alert").textContent).toBe("Could not copy the class code.");

    vi.mocked(writeClipboard).mockResolvedValue(true);
    await user.click(screen.getByRole("button", { name: "Copy Code" }));
    expect(await screen.findByText("Copied!")).toBeTruthy();
  });
});
