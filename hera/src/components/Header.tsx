import { useState, useCallback, useMemo } from 'react';

interface HeaderProps {
  user: { github_username: string; email: string } | null;
  onLogout: () => void | Promise<void>;
  onOpenSettings?: () => void;
}

const LOGOUT_ICON = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16,17 21,12 16,7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

const SETTINGS_ICON = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const BurgerIcon = () => (
  <span className="burger-icon">
    <span></span>
    <span></span>
    <span></span>
  </span>
);

export function Header({ user, onLogout, onOpenSettings }: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);

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
    () => (user ? user.github_username.charAt(0).toUpperCase() : ''),
    [user]
  );

  return (
    <header className="header">
      <div className="header-left">
        <h1>Demetra</h1>
      </div>
      <div className="header-right">
        {user && (
          <>
            <div className="user-info">
              <div className="user-avatar">{initial}</div>
              <span className="user-name">{user.github_username}</span>
            </div>
            <button className="burger-button" onClick={toggleMenu} aria-label="Menu">
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
                <button className="logout" onClick={handleLogout}>
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
