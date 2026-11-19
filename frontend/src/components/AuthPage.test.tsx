// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import { register } from "../lib/apiClient";
import { AuthPage } from "./AuthPage";

vi.mock("../lib/apiClient", async () => {
  const actual = await vi.importActual<typeof import("../lib/apiClient")>("../lib/apiClient");
  return {
    ...actual,
    getStoredToken: () => null,
    getStoredUser: () => null,
    getCurrentUser: vi.fn(async () => ({
      data: null,
      error: "Authentication credentials were not provided.",
    })),
    register: vi.fn(),
    login: vi.fn(),
  };
});

function renderAuth(path: "/signup" | "/login") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/signup" element={<AuthPage initialTab="signup" />} />
          <Route path="/login" element={<AuthPage initialTab="login" />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("AuthPage usernames", () => {
  beforeEach(() => {
    vi.mocked(register).mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("asks for a username on sign-up and not on log in", () => {
    renderAuth("/signup");
    expect(screen.getByLabelText("Username")).toBeTruthy();

    cleanup();
    renderAuth("/login");
    expect(screen.queryByLabelText("Username")).toBeNull();
    expect(screen.getByLabelText("Email")).toBeTruthy();
  });

  it("rejects a blank username before creating an account", async () => {
    const user = userEvent.setup();
    renderAuth("/signup");

    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(screen.getByText(/enter a username/i)).toBeTruthy();
    expect(register).not.toHaveBeenCalled();
  });

  it("rejects an email used as a username", async () => {
    const user = userEvent.setup();
    renderAuth("/signup");

    await user.type(screen.getByLabelText("Username"), "torres11@gmail.com");
    await user.type(screen.getByLabelText("Email"), "ada@school.edu");
    await user.type(screen.getByLabelText("Password"), "Maple!River82");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(screen.getByText(/cannot be an email address/i)).toBeTruthy();
    expect(register).not.toHaveBeenCalled();
  });

  it("shows the server message when the username is taken", async () => {
    const user = userEvent.setup();
    vi.mocked(register).mockResolvedValue({
      data: null,
      error: "That username is already taken.",
      status: 400,
      fields: { username: ["That username is already taken."] },
    });
    renderAuth("/signup");

    await user.type(screen.getByLabelText("Username"), "torres11");
    await user.type(screen.getByLabelText("Email"), "ada@school.edu");
    await user.type(screen.getByLabelText("Password"), "Maple!River82");
    await user.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText(/already taken/i)).toBeTruthy();
    expect(register).toHaveBeenCalledWith({
      email: "ada@school.edu",
      username: "torres11",
      password: "Maple!River82",
      role: "student",
    });
  });
});
