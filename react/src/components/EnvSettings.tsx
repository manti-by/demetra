import { useState, useCallback, useEffect } from 'react';
import {
  ProjectEnvironmentEntry,
  getProjectEnvironment,
  upsertProjectEnvironment,
  deleteProjectEnvironment,
} from '../services/api';

interface EnvSettingsProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  projectName: string;
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

function formatValue(entry: ProjectEnvironmentEntry): string {
  if (!entry.value) {
    return '(empty)';
  }
  if (entry.type === 'encrypted') {
    return '••••••••';
  }
  return entry.value;
}

export function EnvSettings({ isOpen, onClose, projectId, projectName }: EnvSettingsProps) {
  const [entries, setEntries] = useState<ProjectEnvironmentEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [draftKey, setDraftKey] = useState('');
  const [draftValue, setDraftValue] = useState('');
  const [draftEncrypted, setDraftEncrypted] = useState(false);

  const fetchEnvironment = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getProjectEnvironment(projectId);
      setEntries(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load environment');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (isOpen) {
      fetchEnvironment();
      setDraftKey('');
      setDraftValue('');
      setDraftEncrypted(false);
    }
  }, [isOpen, fetchEnvironment]);

  const handleAddEntry = useCallback(async () => {
    const key = draftKey.trim();
    if (!key) {
      setError('Environment key is required');
      return;
    }
    if (entries.some((entry) => entry.key === key)) {
      setError(`Environment key "${key}" already exists`);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const entry = await upsertProjectEnvironment(
        projectId,
        key,
        draftValue,
        draftEncrypted ? 'encrypted' : 'text'
      );
      setEntries((prev) => [...prev, entry]);
      setDraftKey('');
      setDraftValue('');
      setDraftEncrypted(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add environment variable');
    } finally {
      setSaving(false);
    }
  }, [draftKey, draftValue, draftEncrypted, entries, projectId]);

  const handleDeleteEntry = useCallback(
    async (key: string) => {
      setSaving(true);
      setError(null);
      try {
        await deleteProjectEnvironment(projectId, key);
        setEntries((prev) => prev.filter((entry) => entry.key !== key));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to delete environment variable');
      } finally {
        setSaving(false);
      }
    },
    [projectId]
  );

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Environment - {projectName}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          {error && <div className="settings-error">{error}</div>}

          {loading ? (
            <div className="loading-container">
              <div className="loading-spinner" />
            </div>
          ) : (
            <>
              <div className="env-list">
                {entries.length === 0 ? (
                  <p className="empty-message">No environment variables yet. Add your first one!</p>
                ) : (
                  entries.map((entry) => (
                    <div key={entry.key} className="env-row">
                      <span className="env-key">{entry.key}</span>
                      <span className="env-value">{formatValue(entry)}</span>
                      <span className={`env-type env-type-${entry.type}`}>{entry.type}</span>
                      <button
                        className="btn-icon delete-env"
                        onClick={() => handleDeleteEntry(entry.key)}
                        aria-label={`Delete ${entry.key}`}
                        disabled={saving}
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  ))
                )}
              </div>

              <div className="env-form">
                <input
                  type="text"
                  placeholder="Key"
                  value={draftKey}
                  onChange={(e) => setDraftKey(e.target.value)}
                  className="form-input env-key-input"
                />
                <input
                  type="password"
                  placeholder="Value"
                  value={draftValue}
                  onChange={(e) => setDraftValue(e.target.value)}
                  className="form-input env-value-input"
                />
                <label className="env-encrypted-label">
                  <input
                    type="checkbox"
                    checked={draftEncrypted}
                    onChange={(e) => setDraftEncrypted(e.target.checked)}
                  />
                  Encrypted
                </label>
                <button
                  className="btn-primary"
                  onClick={handleAddEntry}
                  disabled={saving || !draftKey.trim()}
                >
                  {saving ? 'Saving...' : 'Add'}
                </button>
              </div>
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
