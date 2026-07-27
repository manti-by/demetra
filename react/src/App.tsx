import { lazy, Suspense, useCallback, useMemo, useRef, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import { GitHubLoginButton } from "./components/GitHubLoginButton";
import { Header } from "./components/Header";
import { PasswordAuthForm } from "./components/PasswordAuthForm";
import { SessionArtifacts } from "./components/SessionArtifacts";
import { UserSettings } from "./components/UserSettings";
import { SessionSidebar } from "./components/SessionSidebar";
import { CommandPalette, type CommandPaletteHandle } from "./components/CommandPalette";
import { deleteSession, type Session } from "./services/api";
import "./App.css";

const GitHubCallback = lazy(() =>
  import("./pages/GitHubCallback").then((m) => ({ default: m.GitHubCallback })),
);
const LogConsole = lazy(() =>
  import("./components/LogConsole").then((m) => ({ default: m.LogConsole })),
);

const LOGIN_TITLE = "Demetra";
const LOGIN_SUBTITLE =
  "AI-powered workflow orchestration for developers. Automate your development workflow with intelligent agents.";

function LoadingSpinner() {
  return (
    <div className="loading-container">
      <div className="loading-spinner" />
    </div>
  );
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
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
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

  const handleSelectSession = useCallback((taskId: string) => {
    setSelectedTaskId(taskId);
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
      />
      {user ? (
        <main className="main-content">
          <div className="main-content-body">
            <SessionSidebar
              onSelectSession={handleSelectSession}
              selectedTaskId={selectedTaskId}
              refreshTrigger={sessionRefreshTrigger}
              sessions={sessions}
              setSessions={setSessions}
            />
            <div className="console-container">
              <Suspense
                fallback={
                  <div className="loading-container">
                    <div className="loading-spinner" />
                  </div>
                }
              >
                <LogConsole taskId={selectedTaskId} sessionName={sessions.find((s) => s.task_id === selectedTaskId)?.name ?? null} onDeleteSession={handleDeleteSession} onSessionStatus={updateSessionStatus} />
              </Suspense>
              <SessionArtifacts taskId={selectedTaskId} sessions={sessions} />
            </div>
          </div>
        </main>
      ) : (
        <LoginView />
      )}
      <UserSettings isOpen={settingsOpen} onClose={handleCloseSettings} />
      {user && <CommandPalette ref={paletteRef} commands={commands} />}
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
            <Route path="/github/callback" element={<GitHubCallback />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
