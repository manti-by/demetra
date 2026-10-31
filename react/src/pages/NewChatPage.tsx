import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Header } from "../components/Header";
import { Loader } from "../components/Loader";
import { useAuth } from "../contexts/AuthContext";
import { createChat, getProjects, type Project } from "../services/api";

export function NewChatPage() {
  const navigate = useNavigate();
  const { user, loading, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [projectId, setProjectId] = useState("");
  const [tags, setTags] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getProjects()
      .then((data) => {
        if (cancelled) return;
        const active = data.filter((project) => project.state === "active");
        setProjects(active);
        if (active.length > 0) setProjectId(active[0].id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load projects"));
    return () => {
      cancelled = true;
    };
  }, [user]);

  const handleLogout = useCallback(async () => {
    await logout();
    window.location.reload();
  }, [logout]);

  const handleSubmit = useCallback(async () => {
    if (!title.trim() || !description.trim() || !projectId) {
      setError("Title, description and project are required");
      return;
    }
    setSubmitting(true);
    try {
      const chat = await createChat({
        title: title.trim(),
        description: description.trim(),
        project_id: projectId,
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
      });
      navigate(`/chats/${chat.session_task_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create chat");
    } finally {
      setSubmitting(false);
    }
  }, [title, description, projectId, tags, navigate]);

  if (loading) {
    return <Loader fullScreen size={56} />;
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

        <div className="chat-form">
          <h1 className="chat-title">New chat</h1>
          {error && <div className="chat-error">{error}</div>}

          <label className="chat-field" htmlFor="chat-title">
            <span>Title</span>
            <input
              id="chat-title"
              className="form-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Add user authentication"
            />
          </label>

          <label className="chat-field" htmlFor="chat-description">
            <span>Description</span>
            <textarea
              id="chat-description"
              className="form-input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              placeholder="What should the agent build?"
            />
          </label>

          <label className="chat-field" htmlFor="chat-project">
            <span>Project</span>
            <select
              id="chat-project"
              className="form-input"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            >
              {projects.length === 0 && <option value="">No active projects</option>}
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <label className="chat-field" htmlFor="chat-tags">
            <span>Tags</span>
            <input
              id="chat-tags"
              className="form-input"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="Research, Backend"
            />
          </label>

          <div className="form-actions">
            <button className="btn-primary" onClick={handleSubmit} disabled={submitting || projects.length === 0}>
              {submitting ? "Starting..." : "Start chat"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default NewChatPage;
