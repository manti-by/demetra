import { useState, useCallback, useEffect, useMemo } from "react";
import {
  ProjectEnvironmentEntry,
  getProjectEnvironment,
  upsertProjectEnvironment,
  deleteProjectEnvironment,
} from "../services/api";
import { EnvFileUploadButton } from "./EnvFileUploadButton";
import { Loader } from "./Loader";
import { isSensitiveKey, validateEnvKey, type EnvFileEntry } from "../utils/envFile";

interface EnvSettingsProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  projectName: string;
}

const CloseIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const TrashIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <polyline points="3,6 5,6 21,6" />
    <path d="M19,6v14a2,2 0 0,1-2,2H7a2,2 0 0,1-2-2V6m3,0V4a2,2 0 0,1,2-2h4a2,2 0 0,1,2 2v2" />
  </svg>
);

const PencilIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <path d="M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
  </svg>
);

function formatValue(entry: ProjectEnvironmentEntry): string {
  if (!entry.value) {
    return "(empty)";
  }
  if (entry.type === "encrypted") {
    return "••••••••";
  }
  return entry.value;
}

function sortByKey<T extends { key: string }>(entries: T[]): T[] {
  return [...entries].sort((a, b) => a.key.localeCompare(b.key));
}

export function EnvSettings({
  isOpen,
  onClose,
  projectId,
  projectName,
}: EnvSettingsProps) {
  const [entries, setEntries] = useState<ProjectEnvironmentEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [draftKey, setDraftKey] = useState("");
  const [draftValue, setDraftValue] = useState("");
  const [draftEncrypted, setDraftEncrypted] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);

  const sortedEntries = useMemo(() => sortByKey(entries), [entries]);

  const fetchEnvironment = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getProjectEnvironment(projectId);
      setEntries(sortByKey(data));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load environment");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (isOpen) {
      fetchEnvironment();
      setDraftKey("");
      setDraftValue("");
      setDraftEncrypted(false);
      setEditingKey(null);
    }
  }, [isOpen, fetchEnvironment]);

  const beginEdit = useCallback((entry: ProjectEnvironmentEntry) => {
    setEditingKey(entry.key);
    setDraftKey(entry.key);
    setDraftValue(entry.type === "encrypted" ? "" : entry.value);
    setDraftEncrypted(entry.type === "encrypted");
    setError(null);
  }, []);

  const cancelEdit = useCallback(() => {
    setEditingKey(null);
    setDraftKey("");
    setDraftValue("");
    setDraftEncrypted(false);
    setError(null);
  }, []);

  const handleAddEntry = useCallback(async () => {
    const key = draftKey.trim();
    const validationError = validateEnvKey(key);
    if (validationError) {
      setError(validationError);
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
        draftEncrypted ? "encrypted" : "text",
      );
      setEntries((prev) => sortByKey([...prev, entry]));
      setDraftKey("");
      setDraftValue("");
      setDraftEncrypted(false);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to add environment variable",
      );
    } finally {
      setSaving(false);
    }
  }, [draftKey, draftValue, draftEncrypted, entries, projectId]);

  const handleSaveEdit = useCallback(async () => {
    if (editingKey === null) return;
    const key = draftKey.trim();
    const validationError = validateEnvKey(key);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (entries.some((entry) => entry.key === key && entry.key !== editingKey)) {
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
        draftEncrypted ? "encrypted" : "text",
      );
      if (key !== editingKey) {
        await deleteProjectEnvironment(projectId, editingKey);
        setEntries((prev) =>
          sortByKey([...prev.filter((e) => e.key !== editingKey), entry]),
        );
      } else {
        setEntries((prev) =>
          sortByKey(prev.map((e) => (e.key === editingKey ? entry : e))),
        );
      }
      setEditingKey(null);
      setDraftKey("");
      setDraftValue("");
      setDraftEncrypted(false);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to save environment variable",
      );
    } finally {
      setSaving(false);
    }
  }, [draftKey, draftValue, draftEncrypted, editingKey, entries, projectId]);

  const handleUpload = useCallback(
    async (fileEntries: EnvFileEntry[]) => {
      setSaving(true);
      setError(null);
      let upsertedCount = 0;
      try {
        for (const fileEntry of fileEntries) {
          try {
            // Sensitive keys default to encrypted so plaintext secrets are
            // never stored in the database.
            const type = isSensitiveKey(fileEntry.key) ? "encrypted" : "text";
            const entry = await upsertProjectEnvironment(
              projectId,
              fileEntry.key,
              fileEntry.value,
              type,
            );
            // Apply each successful entry immediately so local state stays in
            // sync with the server even when a later entry in the import fails.
            setEntries((prev) => {
              const next = [...prev];
              const index = next.findIndex((e) => e.key === entry.key);
              if (index >= 0) {
                next[index] = entry;
              } else {
                next.push(entry);
              }
              return sortByKey(next);
            });
            upsertedCount += 1;
          } catch (e) {
            const message =
              e instanceof Error
                ? e.message
                : "Failed to import environment variables";
            if (upsertedCount > 0) {
              setError(`Import partially completed: ${message}`);
            } else {
              setError(message);
            }
            break;
          }
        }
      } finally {
        setSaving(false);
      }
    },
    [projectId],
  );

  const handleDeleteEntry = useCallback(
    async (key: string) => {
      setSaving(true);
      setError(null);
      try {
        await deleteProjectEnvironment(projectId, key);
        setEntries((prev) => prev.filter((entry) => entry.key !== key));
        if (editingKey === key) {
          cancelEdit();
        }
      } catch (e) {
        setError(
          e instanceof Error
            ? e.message
            : "Failed to delete environment variable",
        );
      } finally {
        setSaving(false);
      }
    },
    [projectId, editingKey, cancelEdit],
  );

  if (!isOpen) return null;

  const isEditing = editingKey !== null;
  const valuePlaceholder =
    isEditing && draftEncrypted ? "leave blank to keep current value" : "Value";

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
          <p className="env-help-text">
            User-shared env is applied to all your projects. Project env
            overrides user-shared on key conflict.
          </p>
          {error && <div className="settings-error">{error}</div>}

          {loading ? (
            <Loader size={36} />
          ) : (
            <>
              <div className="env-list">
                {sortedEntries.length === 0 ? (
                  <p className="empty-message">
                    No environment variables yet. Add your first one!
                  </p>
                ) : (
                  sortedEntries.map((entry) => (
                    <div key={entry.key} className="env-row">
                      <span className="env-key">{entry.key}</span>
                      <span className="env-value">{formatValue(entry)}</span>
                      <span className={`env-type env-type-${entry.type}`}>
                        {entry.type}
                      </span>
                      <button
                        className="btn-icon edit-env"
                        onClick={() => beginEdit(entry)}
                        aria-label={`Edit ${entry.key}`}
                        disabled={saving}
                      >
                        <PencilIcon />
                      </button>
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
                   type={draftEncrypted ? "password" : "text"}
                   placeholder={valuePlaceholder}
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
                {isEditing ? (
                  <>
                    <button
                      className="btn-primary"
                      onClick={handleSaveEdit}
                      disabled={saving || !draftKey.trim()}
                    >
                      {saving ? <Loader size={18} /> : "Save"}
                    </button>
                    <button
                      className="btn-secondary"
                      onClick={cancelEdit}
                      disabled={saving}
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    className="btn-primary"
                    onClick={handleAddEntry}
                    disabled={saving || !draftKey.trim()}
                  >
                    {saving ? <Loader size={18} /> : "Add"}
                  </button>
                )}
              </div>

              <div className="env-upload-row">
                <EnvFileUploadButton onParsed={handleUpload} onError={setError} />
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
