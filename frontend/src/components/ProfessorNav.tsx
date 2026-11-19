import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { displayUsername } from "../lib/displayUsername";

export interface CurrentClassInfo {
  id: number | string;
  name: string;
}

interface ProfessorNavProps {
  currentClass?: CurrentClassInfo | null;
  onCreateClass?: () => void;
}

export function ProfessorNav({ currentClass, onCreateClass }: ProfessorNavProps = {}) {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, user } = useAuth();
  const username = displayUsername(user);

  const isDashboardActive =
    location.pathname === "/professor" ||
    location.pathname === "/professor/classes" ||
    location.pathname === "/professor/dashboard";

  const isCurrentClassActive = Boolean(currentClass && !isDashboardActive);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <header className="border-b border-slate-800/80 bg-[#0B1220]/90 backdrop-blur-md sticky top-0 z-40 px-4 sm:px-8 py-3.5 w-full">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
        {/* Top row / Left side: Brand + Role Badge */}
        <div className="flex items-center justify-between sm:justify-start gap-4">
          <Link
            to="/professor"
            className="inline-flex items-center gap-2.5 text-white hover:opacity-90 transition-opacity shrink-0"
          >
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center overflow-hidden shadow-sm">
              <img
                src="/assets/coursePulseLogo.png"
                alt="CoursePulse"
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  const fallback = e.currentTarget.parentElement?.querySelector(".prof-nav-fallback");
                  if (fallback) fallback.classList.remove("hidden");
                }}
              />
              <svg
                className="prof-nav-fallback hidden w-5 h-5 text-white"
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
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Professor
            </span>
            {username && (
              <span className="text-sm font-semibold text-slate-300 truncate max-w-[8rem] sm:max-w-[12rem]">
                {username}
              </span>
            )}
          </Link>

          {/* Mobile-only Logout button on the right */}
          <div className="sm:hidden flex items-center gap-2">
            {onCreateClass && (
              <button
                type="button"
                onClick={onCreateClass}
                className="inline-flex items-center gap-1 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-xs px-2.5 py-1.5 rounded-lg transition cursor-pointer"
              >
                <span>+ Create</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleLogout}
              className="text-xs font-semibold text-slate-300 hover:text-white px-2.5 py-1.5 rounded-lg border border-slate-800 bg-[#0F172A] transition-colors cursor-pointer"
            >
              Log out
            </button>
          </div>
        </div>

        {/* Center / Nav Links: Dashboard and Current Class */}
        <nav
          aria-label="Professor Navigation"
          className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm overflow-x-auto py-0.5 sm:py-0"
        >
          {/* Link to Dashboard */}
          <Link
            to="/professor"
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-semibold transition shrink-0 cursor-pointer ${
              isDashboardActive
                ? "bg-[#162547] text-[#38BDF8] border border-sky-500/30 shadow-sm"
                : "text-slate-400 hover:text-white hover:bg-slate-800/50"
            }`}
          >
            {/* Grid / Dashboard icon */}
            <svg
              className="w-3.5 h-3.5 sm:w-4 sm:h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
            </svg>
            <span>Dashboard</span>
          </Link>

          {/* Current Class Link (when viewing a class) */}
          {currentClass && (
            <>
              <span className="text-slate-600 font-bold px-0.5">/</span>

              <Link
                to={`/class/${currentClass.id}`}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-semibold transition shrink-0 max-w-[200px] sm:max-w-xs truncate cursor-pointer ${
                  isCurrentClassActive
                    ? "bg-[#162547] text-[#38BDF8] border border-sky-500/30 shadow-sm"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                }`}
                title={currentClass.name}
              >
                {/* Book / Classroom icon */}
                <svg
                  className="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0 text-sky-400"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                </svg>
                <span className="truncate">{currentClass.name}</span>
              </Link>
            </>
          )}
        </nav>

        {/* Right side: Action Button + Desktop Logout */}
        <div className="hidden sm:flex items-center gap-3 shrink-0">
          {onCreateClass && (
            <button
              type="button"
              onClick={onCreateClass}
              className="inline-flex items-center gap-1.5 bg-[#38BDF8] hover:bg-[#0EA5E9] text-[#0A101D] font-bold text-xs sm:text-sm px-3.5 py-2 rounded-xl transition cursor-pointer shadow-md shadow-sky-500/20 active:scale-95"
            >
              <span className="text-base leading-none font-extrabold">+</span>
              <span>Create class</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleLogout}
            className="text-xs sm:text-sm font-semibold text-slate-300 hover:text-white px-3 py-2 rounded-xl hover:bg-slate-800/60 transition-colors cursor-pointer flex items-center gap-1.5 border border-transparent hover:border-slate-800"
          >
            {/* Logout icon */}
            <svg
              className="w-4 h-4 text-slate-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Log out</span>
          </button>
        </div>
      </div>
    </header>
  );
}

export default ProfessorNav;
