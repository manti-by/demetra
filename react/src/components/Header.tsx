import { useState, useCallback, useMemo } from "react";
import { useTheme } from "../contexts/ThemeContext";

interface HeaderProps {
  user: { github_username: string; email: string } | null;
  onLogout: () => void | Promise<void>;
  onOpenSettings?: () => void;
  onOpenPalette?: () => void;
}

const LOGOUT_ICON = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16,17 21,12 16,7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

const SETTINGS_ICON = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const MOON_ICON = (
  <svg
    width="15"
    height="15"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  </svg>
);

const SUN_ICON = (
  <svg
    width="15"
    height="15"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <circle cx="12" cy="12" r="5" />
    <line x1="12" y1="1" x2="12" y2="3" />
    <line x1="12" y1="21" x2="12" y2="23" />
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
    <line x1="1" y1="12" x2="3" y2="12" />
    <line x1="21" y1="12" x2="23" y2="12" />
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
  </svg>
);

const BurgerIcon = () => (
  <span className="burger-icon">
    <span />
    <span />
    <span />
  </span>
);

export function Header({
  user,
  onLogout,
  onOpenSettings,
  onOpenPalette,
}: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();

  const handleLogout = useCallback(async () => {
    await onLogout();
  }, [onLogout]);

  const toggleMenu = useCallback(() => {
    setMenuOpen((prev) => !prev);
  }, []);

  const handleOpenSettings = useCallback(() => {
    setMenuOpen(false);
    onOpenSettings?.();
  }, [onOpenSettings]);

  const initial = useMemo(
    () => (user ? user.github_username.charAt(0).toUpperCase() : ""),
    [user],
  );

  return (
    <header className="header">
      <div className="header-left">{user && <h1>Demetra</h1>}</div>
      <div className="header-right">
        {user && (
          <>
            <button
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? SUN_ICON : MOON_ICON}
            </button>
            {onOpenPalette && (
              <button
                className="palette-trigger"
                onClick={onOpenPalette}
                aria-label="Open command palette"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <kbd>Cmd+K</kbd>
              </button>
            )}
            <div className="user-info">
              <div className="user-avatar">{initial}</div>
              <span className="user-name">{user.github_username}</span>
            </div>
            <button
              className="burger-button"
              onClick={toggleMenu}
              aria-label="Menu"
            >
              <BurgerIcon />
            </button>
            {menuOpen && (
              <div className="burger-menu">
                {onOpenSettings && (
                  <button onClick={handleOpenSettings}>
                    {SETTINGS_ICON}
                    Settings
                  </button>
                )}
                <a
                  href="/rq/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="danger"
                >
                  <span className="empty-icon"></span>
                  RQ Dashboard
                </a>
                <button className="danger" onClick={handleLogout}>
                  {LOGOUT_ICON}
                  Logout
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </header>
  );
}
