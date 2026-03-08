import { useState, useCallback, useMemo } from 'react';

interface HeaderProps {
  user: { github_username: string; email: string } | null;
  onLogout: () => void | Promise<void>;
}

const LOGOUT_ICON = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16,17 21,12 16,7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

const BurgerIcon = () => (
  <span className="burger-icon">
    <span></span>
    <span></span>
    <span></span>
  </span>
);

export function Header({ user, onLogout }: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = useCallback(async () => {
    await onLogout();
  }, [onLogout]);

  const toggleMenu = useCallback(() => {
    setMenuOpen((prev) => !prev);
  }, []);

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
