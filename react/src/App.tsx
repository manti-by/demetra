import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import { GitHubLoginButton } from "./components/GitHubLoginButton";
import { Header } from "./components/Header";
import { Loader } from "./components/Loader";
import { PasswordAuthForm } from "./components/PasswordAuthForm";
import { SessionArtifacts } from "./components/SessionArtifacts";
import { UserSettings } from "./components/UserSettings";
import { SharedEnvSettings } from "./components/SharedEnvSettings";
import { SessionSidebar } from "./components/SessionSidebar";
import { CommandPalette, type CommandPaletteHandle } from "./components/CommandPalette";
import { deleteSession, type Session } from "./services/api";
import "./App.css";

const GitHubCallback = lazy(() =>
  import("./pages/GitHubCallback").then((m) => ({ default: m.GitHubCallback })),
);
const StyleGuide = lazy(() =>
  import("./pages/StyleGuide").then((m) => ({ default: m.StyleGuide })),
);
const LogConsole = lazy(() =>
  import("./components/LogConsole").then((m) => ({ default: m.LogConsole })),
);

const LOGIN_TITLE = "Demetra";
const LOGIN_SUBTITLE =
  "AI-powered workflow orchestration for developers. Automate your development workflow with intelligent agents.";

function LoadingSpinner() {
  return <Loader fullScreen size={56} />;
}

function LoginView() {
  return (
    <div className="login-container">
      <h1 className="login-title">{LOGIN_TITLE}</h1>
      <p className="login-subtitle">{LOGIN_SUBTITLE}</p>
      <GitHubLoginButton />
      <PasswordAuthForm />
    </div>
  );
}

function AppContent() {
  const { user, loading, logout } = useAuth();
  const { toggleTheme, theme } = useTheme();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sharedEnvOpen, setSharedEnvOpen] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessionRefreshTrigger, setSessionRefreshTrigger] = useState(0);
  const [sessions, setSessions] = useState<Session[]>([]);
  const paletteRef = useRef<CommandPaletteHandle>(null);
  const handleOpenPalette = useCallback(() => paletteRef.current?.open(), []);

  const updateSessionStatus = useCallback((taskId: string, data: { step: string; name?: string }) => {
    setSessions((prev) =>
      prev.map((s) =>
        s.task_id === taskId
          ? { ...s, step: data.step, ...(data.name !== undefined ? { name: data.name } : {}) }
          : s,
      ),
    );
  }, []);

  const handleLogout = useCallback(async () => {
    await logout();
    window.location.reload();
  }, [logout]);

  const handleOpenSettings = useCallback(() => {
    setSettingsOpen(true);
  }, []);

  const handleCloseSettings = useCallback(() => {
    setSettingsOpen(false);
  }, []);

  const handleOpenSharedEnv = useCallback(() => {
    setSharedEnvOpen(true);
  }, []);

  const handleCloseSharedEnv = useCallback(() => {
    setSharedEnvOpen(false);
  }, []);

  const handleOpenSidebar = useCallback(() => {
    setSidebarOpen(true);
  }, []);

  const handleCloseSidebar = useCallback(() => {
    setSidebarOpen(false);
  }, []);

  useEffect(() => {
    if (!sidebarOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sidebarOpen]);

  const handleSelectSession = useCallback((taskId: string) => {
    setSelectedTaskId(taskId);
    setSidebarOpen(false);
  }, []);

  const handleDeleteSession = useCallback(async (taskId: string) => {
    try {
      await deleteSession(taskId);
      setSelectedTaskId(null);
      setSessionRefreshTrigger((t) => t + 1);
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  }, []);

  const commands = useMemo(
    () => [
      { id: "toggle-theme", label: `Switch to ${theme === "dark" ? "light" : "dark"} mode`, shortcut: "T", action: toggleTheme },
      { id: "open-settings", label: "Open settings", shortcut: "S", action: handleOpenSettings },
      { id: "logout", label: "Logout", action: handleLogout },
    ],
    [theme, toggleTheme, handleOpenSettings, handleLogout],
  );

  const consoleInert = sidebarOpen ? { inert: "" } : {};

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="app">
      <Header
        user={user}
        onLogout={handleLogout}
        onOpenSettings={handleOpenSettings}
        onOpenPalette={handleOpenPalette}
        onOpenSharedEnv={handleOpenSharedEnv}
        inert={sidebarOpen}
      />
      {user ? (
        <main className="main-content">
          {sidebarOpen && <div className="sidebar-overlay" onClick={handleCloseSidebar} />}
          <div className="main-content-body">
            <div className={`sidebar-slot${sidebarOpen ? " open" : ""}`}>
              <SessionSidebar
                onSelectSession={handleSelectSession}
                selectedTaskId={selectedTaskId}
                refreshTrigger={sessionRefreshTrigger}
                sessions={sessions}
                setSessions={setSessions}
              />
            </div>
            <div className="console-container" {...consoleInert}>
              {sessions.length > 0 && (
                <div className="console-tabs">
                  {sessions.map((session) => (
                    <button
                      key={session.task_id}
                      className={`console-tab${session.task_id === selectedTaskId ? " active" : ""}`}
                      onClick={() => handleSelectSession(session.task_id)}
                    >
                      {session.name || session.task_id.slice(0, 8)}
                    </button>
                  ))}
                </div>
              )}
              <Suspense fallback={<Loader size={48} />}>

                <LogConsole taskId={selectedTaskId} sessionName={sessions.find((s) => s.task_id === selectedTaskId)?.name ?? null} onDeleteSession={handleDeleteSession} onSessionStatus={updateSessionStatus} />
              </Suspense>
              <SessionArtifacts taskId={selectedTaskId} sessions={sessions} />
              <div className="console-toolbar">
                <button className="console-toolbar-btn" onClick={handleOpenSidebar}>
                  Sessions
                  <span className="console-toolbar-count">{sessions.length}</span>
                </button>
              </div>
            </div>
          </div>
        </main>
      ) : (
        <LoginView />
      )}
      <UserSettings isOpen={settingsOpen} onClose={handleCloseSettings} />
      <SharedEnvSettings isOpen={sharedEnvOpen} onClose={handleCloseSharedEnv} />
      {user && <CommandPalette ref={paletteRef} commands={commands} />}
    </div>
  );
}

function StyleGuideLayout() {
  const { user, loading, logout } = useAuth();
  const handleLogout = useCallback(async () => {
    await logout();
    window.location.reload();
  }, [logout]);

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="app">
      <Header user={user} onLogout={handleLogout} />
      <main className="main-content">
        <Suspense fallback={<Loader size={48} />}>
          <StyleGuide />
        </Suspense>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<AppContent />} />
            <Route path="/styleguide" element={<StyleGuideLayout />} />
            <Route path="/github/callback" element={<GitHubCallback />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
