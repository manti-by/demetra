import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ChatPanel } from "../components/ChatPanel";
import { Header } from "../components/Header";
import { Loader } from "../components/Loader";
import { useAuth } from "../contexts/AuthContext";

export { MessageBubble, splitFailureBody } from "../components/ChatPanel";

export function ChatPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { user, loading, logout } = useAuth();
  const [showLogs, setShowLogs] = useState(false);

  const handleLogout = useCallback(async () => {
    await logout();
    window.location.reload();
  }, [logout]);

  const handleToggleLogs = useCallback(() => {
    setShowLogs((value) => !value);
  }, []);

  if (loading) {
    return <Loader fullScreen size={56} />;
  }

  if (!user) {
    return (
      <div className="chat-page">
        <Header user={null} onLogout={handleLogout} />
        <div className="chat-empty">
          Please <Link to="/">sign in</Link> to view this chat.
        </div>
      </div>
    );
  }

  return (
    <div className="chat-page">
      <Header user={user} onLogout={handleLogout} />
      <main className="chat-main">
        <div className="chat-topbar">
          <button className="btn-secondary" onClick={() => navigate("/")}>
            Back to sessions
          </button>
        </div>
        {taskId ? (
          <ChatPanel
            taskId={taskId}
            showLogs={showLogs}
            onShowLogsToggle={handleToggleLogs}
            onDeleteSession={() => navigate("/")}
          />
        ) : (
          <Loader size={48} />
        )}
      </main>
    </div>
  );
}

export default ChatPage;
