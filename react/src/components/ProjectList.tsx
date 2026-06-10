import { useState, useCallback, useEffect } from 'react';
import { Project, getProjects, createProject, deleteProject } from '../services/api';
import { EnvSettings } from './EnvSettings';

interface ProjectListProps {
  onClose?: () => void;
  inline?: boolean;
}

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const TrashIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="3,6 5,6 21,6" />
    <path d="M19,6v14a2,2 0 0,1-2,2H7a2,2 0 0,1-2-2V6m3,0V4a2,2 0 0,1,2-2h4a2,2 0 0,1,2 2v2" />
  </svg>
);

const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const EnvIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M20 7h-3V4H7v3H4v13h16V7zM10 12h4M10 16h4" />
  </svg>
);

export function ProjectList({ onClose, inline = false }: ProjectListProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [newProject, setNewProject] = useState({
    name: '',
    repository_url: '',
    linear_project_id: '',
  });
  const [saving, setSaving] = useState(false);
  const [envProject, setEnvProject] = useState<Project | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getProjects();
      setProjects(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleCreateProject = useCallback(async () => {
    if (!newProject.name.trim() || !newProject.repository_url.trim()) {
      setError('Name and repository URL are required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await createProject({
        name: newProject.name.trim(),
        repository_url: newProject.repository_url.trim(),
        linear_project_id: newProject.linear_project_id.trim() || undefined,
      });
      setNewProject({ name: '', repository_url: '', linear_project_id: '' });
      setShowForm(false);
      await fetchProjects();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create project');
    } finally {
      setSaving(false);
    }
  }, [newProject, fetchProjects]);

  const handleDeleteProject = useCallback(
    async (projectId: string) => {
      if (!confirm('Are you sure you want to delete this project?')) {
        return;
      }

      try {
        await deleteProject(projectId);
        await fetchProjects();
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to delete project');
      }
    },
    [fetchProjects]
  );

  const content = (
    <>
      {error && <div className="settings-error">{error}</div>}

      {loading ? (
        <div className="loading-container">
          <div className="loading-spinner" />
        </div>
      ) : (
        <>
          <div className="projects-list">
            {projects.length === 0 ? (
              <p className="empty-message">No projects yet. Add your first project!</p>
            ) : (
              projects.map((project) => (
                <div key={project.id} className="project-item">
                  <div className="project-info">
                    <h3>{project.name}</h3>
                    <p className="project-url">{project.repository_url}</p>
                    {project.linear_project_id && (
                      <p className="project-linear">Linear ID: {project.linear_project_id}</p>
                    )}
                  </div>
                  <div className="project-actions">
                    <button
                      className="btn-icon env-project"
                      onClick={() => setEnvProject(project)}
                      aria-label={`Environment for ${project.name}`}
                    >
                      <EnvIcon />
                    </button>
                    {project.user_id && (
                      <button
                        className="btn-icon delete-project"
                        onClick={() => handleDeleteProject(project.id)}
                        aria-label="Delete project"
                      >
                        <TrashIcon />
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {showForm && (
            <div className="project-form">
              <input
                type="text"
                placeholder="Project Name"
                value={newProject.name}
                onChange={(e) => setNewProject((prev) => ({ ...prev, name: e.target.value }))}
                className="form-input"
              />
              <input
                type="text"
                placeholder="Repository URL (e.g., https://github.com/user/repo)"
                value={newProject.repository_url}
                onChange={(e) =>
                  setNewProject((prev) => ({ ...prev, repository_url: e.target.value }))
                }
                className="form-input"
              />
              <input
                type="text"
                placeholder="Linear Project ID (optional)"
                value={newProject.linear_project_id}
                onChange={(e) =>
                  setNewProject((prev) => ({ ...prev, linear_project_id: e.target.value }))
                }
                className="form-input"
              />
              <div className="form-actions">
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setShowForm(false);
                    setNewProject({ name: '', repository_url: '', linear_project_id: '' });
                  }}
                >
                  Cancel
                </button>
                <button className="btn-primary" onClick={handleCreateProject} disabled={saving}>
                  {saving ? 'Creating...' : 'Create'}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );

  if (inline) {
    return (
      <div className="projects-inline">
        <div className="projects-header">
          <h3>Projects</h3>
          {!showForm && (
            <button className="btn-secondary" onClick={() => setShowForm(true)}>
              <PlusIcon /> Add Project
            </button>
          )}
        </div>
        {content}
        {envProject && (
          <EnvSettings
            isOpen={true}
            onClose={() => setEnvProject(null)}
            projectId={envProject.id}
            projectName={envProject.name}
          />
        )}
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Projects</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">{content}</div>
        <div className="modal-footer">
          {!showForm && (
            <button className="btn-secondary" onClick={() => setShowForm(true)}>
              <PlusIcon /> Add Project
            </button>
          )}
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
      {envProject && (
        <EnvSettings
          isOpen={true}
          onClose={() => setEnvProject(null)}
          projectId={envProject.id}
          projectName={envProject.name}
        />
      )}
    </div>
  );
}
