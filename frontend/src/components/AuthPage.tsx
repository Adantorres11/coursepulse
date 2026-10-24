import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { API_BASE_URL } from "../lib/apiClient";

type AuthTab = "login" | "signup";
type UserRole = "student" | "professor";

interface AuthPageProps {
  initialTab?: AuthTab;
}

export function AuthPage({ initialTab = "login" }: AuthPageProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Determine active tab from URL param (e.g. ?tab=signup) or prop
  const urlTab = searchParams.get("tab") as AuthTab | null;
  const [activeTab, setActiveTab] = useState<AuthTab>(
    urlTab === "signup" || urlTab === "login" ? urlTab : initialTab
  );

  // Form states
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("student");
  const [showPassword, setShowPassword] = useState(false);
  const [hasLoginError, setHasLoginError] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<{ title: string; subtitle: string }>({
    title: "Incorrect email or password.",
    subtitle: "Check your details and try again.",
  });

  const handleTabSwitch = (tab: AuthTab) => {
    setActiveTab(tab);
    setHasLoginError(false);
    setSearchParams({ tab });
  };
const submitAuth = async (mode: AuthTab) => {
  if (isSubmitting) return;

  setHasLoginError(false);
  setIsSubmitting(true);

  try {
    const endpoint = mode === "login" ? "login" : "register";

    const response = await fetch(`${API_BASE_URL}/auth/${endpoint}/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email.trim(),
        password,
        ...(mode === "signup" ? { role } : {}),
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      const message = Object.entries(data)
        .map(([field, value]) => {
          const text = Array.isArray(value)
            ? value.join(" ")
            : String(value);

          return field === "detail" ? text : `${field}: ${text}`;
        })
        .join(" ");

      setErrorMessage({
        title: mode === "login" ? "Login failed." : "Signup failed.",
        subtitle: message || "Please check your details and try again.",
      });
      setHasLoginError(true);
      return;
    }

    if (typeof data.token !== "string" || !data.token) {
      throw new Error("Missing authentication token");
    }

    sessionStorage.setItem("coursepulse_token", data.token);
    navigate("/hub");
  } catch {
    setErrorMessage({
      title: "Unable to complete your request.",
      subtitle: "Check that the backend is running and try again.",
    });
    setHasLoginError(true);
  } finally {
    setIsSubmitting(false);
  }
};

  const handleLoginSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  void submitAuth("login");
};

  const handleSignupSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  void submitAuth("signup");
};

  return (
    <div className="min-h-screen bg-[#0B1220] text-white flex flex-col justify-between selection:bg-sky-500/30">
      {/* Top Bar with Brand Logo */}
      <header className="px-6 sm:px-10 py-6 w-full">
        <Link
          to="/"
          className="inline-flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity"
        >
          {/* Logo Mark */}
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center overflow-hidden shadow-sm">
            <img
              src="/assets/coursePulseLogo.png"
              alt="CoursePulse"
              className="w-full h-full object-cover"
              onError={(e) => {
                // Fallback SVG icon if image not available
                e.currentTarget.style.display = "none";
                const fallback = e.currentTarget.parentElement?.querySelector(".fallback-icon");
                if (fallback) fallback.classList.remove("hidden");
              }}
            />
            <svg
              className="fallback-icon hidden w-5 h-5 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M2 12a10 10 0 0 1 18-6" />
              <path d="M5 14a6 6 0 0 1 10-3" />
              <path d="M8 16a2 2 0 0 1 2-1" />
            </svg>
          </div>
          <span className="text-xl font-bold tracking-tight text-white">CoursePulse</span>
        </Link>

        </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-8 sm:py-12 w-full">
        <div className="w-full max-w-[420px] mx-auto">
          {/* Title & Subtitle */}
          <div className="text-center mb-8">
            <h1 className="text-3xl sm:text-[34px] font-extrabold tracking-tight text-white mb-2">
              {activeTab === "login" ? "Welcome back" : "Create your account"}
            </h1>
            <p className="text-slate-400 text-sm leading-relaxed max-w-sm mx-auto">
              {activeTab === "login"
                ? "Log in to see your classes and keep your points climbing."
                : "Join your classes and start earning points."}
            </p>
          </div>

          {/* Auth Card */}
          <div className="bg-[#10192E] border border-slate-800/90 rounded-2xl p-6 sm:p-7 shadow-2xl shadow-black/50">
            {/* Tabs (Log in / Sign up) */}
            <div className="grid grid-cols-2 p-1 bg-[#090F1E] border border-slate-800/80 rounded-xl mb-6">
              <button
                type="button"
                onClick={() => handleTabSwitch("login")}
                className={`py-2 px-3 text-sm font-semibold rounded-lg transition-all cursor-pointer ${
                  activeTab === "login"
                    ? "bg-[#38BDF8] text-[#0A101D] shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Log in
              </button>
              <button
                type="button"
                onClick={() => handleTabSwitch("signup")}
                className={`py-2 px-3 text-sm font-semibold rounded-lg transition-all cursor-pointer ${
                  activeTab === "signup"
                    ? "bg-[#38BDF8] text-[#0A101D] shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Sign up
              </button>
            </div>

            {/* Red Error Banner (Acceptance Criteria) */}
            {hasLoginError && (
              <div className="flex items-start gap-2.5 bg-[#2B131C] border border-rose-500/80 rounded-xl p-3 text-xs text-rose-200 mb-5">
                {/* Exclamation Circle Icon */}
                <svg
                  className="w-4 h-4 text-rose-400 shrink-0 mt-0.5"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                    clipRule="evenodd"
                  />
                </svg>
                <div className="leading-snug">
                  <strong className="font-semibold text-white">{errorMessage.title}</strong>{" "}
                  {errorMessage.subtitle}
                </div>
              </div>
            )}

            {/* Form */}
            <form onSubmit={activeTab === "login" ? handleLoginSubmit : handleSignupSubmit}>
              {/* Email Field */}
              <div className="mb-4">
                <label
                  htmlFor="email-input"
                  className="block text-xs font-semibold text-slate-300 mb-1.5"
                >
                  Email
                </label>
                <input
                  id="email-input"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (hasLoginError) setHasLoginError(false);
                  }}
                  placeholder="you@school.edu"
                  className={`w-full bg-[#0A101F] text-white rounded-xl px-3.5 py-2.5 text-sm placeholder:text-slate-500 focus:outline-none transition ${
                    hasLoginError
                      ? "border border-rose-500 ring-1 ring-rose-500/50"
                      : "border border-slate-800 focus:border-[#38BDF8] focus:ring-1 focus:ring-[#38BDF8]"
                  }`}
                />
              </div>

              {/* Password Field */}
              <div className="mb-5">
                <label
                  htmlFor="password-input"
                  className="block text-xs font-semibold text-slate-300 mb-1.5"
                >
                  Password
                </label>
                <div className="relative flex items-center">
                  <input
                    id="password-input"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (hasLoginError) setHasLoginError(false);
                    }}
                    placeholder={
                      activeTab === "login" ? "Your password" : "At least 8 characters"
                    }
                    className={`w-full bg-[#0A101F] text-white rounded-xl pl-3.5 pr-10 py-2.5 text-sm placeholder:text-slate-500 focus:outline-none transition ${
                      hasLoginError
                        ? "border border-rose-500 ring-1 ring-rose-500/50"
                        : "border border-slate-800 focus:border-[#38BDF8] focus:ring-1 focus:ring-[#38BDF8]"
                    }`}
                  />
                  {/* Show/Hide Password Toggle Button */}
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-3 text-slate-500 hover:text-slate-300 transition-colors p-1 cursor-pointer"
                  >
                    {showPassword ? (
                      /* Eye-off icon */
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"
                        />
                      </svg>
                    ) : (
                      /* Eye icon */
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Role Selection (Sign Up only - Acceptance Criteria) */}
              {activeTab === "signup" && (
                <div className="mb-5">
                  <span className="block text-xs font-semibold text-slate-300 mb-2">I am a</span>
                  <div className="grid grid-cols-2 gap-3">
                    {/* Student Choice */}
                    <div
                      onClick={() => setRole("student")}
                      className={`rounded-xl p-3 text-left transition-all relative cursor-pointer ${
                        role === "student"
                          ? "bg-[#0F1D38] border-2 border-[#38BDF8]"
                          : "bg-[#0A101F] border border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        {/* Graduation Cap Icon */}
                        <svg
                          className={`w-4 h-4 ${
                            role === "student" ? "text-[#38BDF8]" : "text-slate-400"
                          }`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <path d="M12 14l9-5-9-5-9 5 9 5z" />
                          <path d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z" />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M12 14l9-5-9-5-9 5 9 5zm0 0v6"
                          />
                        </svg>

                        {/* Checkmark Indicator */}
                        {role === "student" && (
                          <div className="w-4 h-4 rounded-full bg-[#38BDF8] flex items-center justify-center">
                            <svg
                              className="w-2.5 h-2.5 text-[#0A101D]"
                              viewBox="0 0 20 20"
                              fill="currentColor"
                            >
                              <path
                                fillRule="evenodd"
                                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                clipRule="evenodd"
                              />
                            </svg>
                          </div>
                        )}
                      </div>
                      <div className="text-sm font-bold text-white mb-0.5">Student</div>
                      <p className="text-[11px] text-slate-400 leading-snug">
                        Take quizzes and climb the leaderboard
                      </p>
                    </div>

                    {/* Professor Choice */}
                    <div
                      onClick={() => setRole("professor")}
                      className={`rounded-xl p-3 text-left transition-all relative cursor-pointer ${
                        role === "professor"
                          ? "bg-[#0F1D38] border-2 border-[#38BDF8]"
                          : "bg-[#0A101F] border border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        {/* Monitor / Screen Icon */}
                        <svg
                          className={`w-4 h-4 ${
                            role === "professor" ? "text-[#38BDF8]" : "text-slate-400"
                          }`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                          <line x1="8" y1="21" x2="16" y2="21" />
                          <line x1="12" y1="17" x2="12" y2="21" />
                        </svg>

                        {/* Checkmark Indicator */}
                        {role === "professor" && (
                          <div className="w-4 h-4 rounded-full bg-[#38BDF8] flex items-center justify-center">
                            <svg
                              className="w-2.5 h-2.5 text-[#0A101D]"
                              viewBox="0 0 20 20"
                              fill="currentColor"
                            >
                              <path
                                fillRule="evenodd"
                                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                clipRule="evenodd"
                              />
                            </svg>
                          </div>
                        )}
                      </div>
                      <div className="text-sm font-bold text-white mb-0.5">Professor</div>
                      <p className="text-[11px] text-slate-400 leading-snug">
                        Upload lectures and publish quizzes
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold py-3 px-4 rounded-xl text-sm flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg shadow-sky-500/10 mt-2"
              >
                <span>{activeTab === "login" ? "Log in" : "Create account"}</span>
                <span>→</span>
              </button>
            </form>
          </div>

          {/* Quick Demo Helper Hint */}
          <div className="text-center mt-6">
            <button
              type="button"
              onClick={() => {
                setEmail("student@school.edu");
                setPassword("wrongpassword");
                setHasLoginError(true);
              }}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors underline cursor-pointer"
            >
              Test simulated failed login (acceptance criteria)
            </button>
          </div>
        </div>
      </main>

      {/* Footer spacer */}
      <footer className="py-4 text-center text-xs text-slate-600">
        CoursePulse © {new Date().getFullYear()} — Study Companion
      </footer>
    </div>
  );
}

export default AuthPage;
