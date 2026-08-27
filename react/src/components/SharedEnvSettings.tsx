import { useState, useCallback, useEffect } from "react";
import {
  UserEnvironmentEntry,
  getUserEnvironment,
  upsertUserEnvironment,
  deleteUserEnvironment,
} from "../services/api";
import { EnvFileUploadButton } from "./EnvFileUploadButton";
import { Loader } from "./Loader";
import { isSensitiveKey, type EnvFileEntry } from "../utils/envFile";

interface SharedEnvSettingsProps {
  isOpen: boolean;
  onClose: () => void;
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

function formatValue(entry: UserEnvironmentEntry): string {
  if (!entry.value) {
    return "(empty)";
  }
  if (entry.type === "encrypted") {
    return "••••••••";
  }
  return entry.value;
}

export function SharedEnvSettings({ isOpen, onClose }: SharedEnvSettingsProps) {
  const [entries, setEntries] = useState<UserEnvironmentEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [draftKey, setDraftKey] = useState("");
  const [draftValue, setDraftValue] = useState("");
  const [draftEncrypted, setDraftEncrypted] = useState(false);

  const fetchEnvironment = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getUserEnvironment();
      setEntries(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load shared environment");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchEnvironment();
      setDraftKey("");
      setDraftValue("");
      setDraftEncrypted(false);
    }
  }, [isOpen, fetchEnvironment]);

  const handleAddEntry = useCallback(
    async (key: string, value: string, encrypted: boolean) => {
      const entry = await upsertUserEnvironment(key, value, encrypted ? "encrypted" : "text");
      setEntries((prev) => {
        const existing = prev.findIndex((e) => e.key === key);
        if (existing >= 0) {
          const next = [...prev];
          next[existing] = entry;
          return next;
        }
        return [...prev, entry];
      });
    },
    [],
  );

  const handleAddDraft = useCallback(async () => {
    const key = draftKey.trim();
    if (!key) {
      setError("Environment key is required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await handleAddEntry(key, draftValue, draftEncrypted);
      setDraftKey("");
      setDraftValue("");
      setDraftEncrypted(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add environment variable");
    } finally {
      setSaving(false);
    }
  }, [draftKey, draftValue, draftEncrypted, handleAddEntry]);

  const handleUpload = useCallback(
    async (fileEntries: EnvFileEntry[]) => {
      setSaving(true);
      setError(null);
      try {
        for (const fileEntry of fileEntries) {
          // Sensitive keys default to encrypted so plaintext secrets are never
          // stored in the database.
          await handleAddEntry(fileEntry.key, fileEntry.value, isSensitiveKey(fileEntry.key));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to import environment variables");
      } finally {
        setSaving(false);
      }
    },
    [handleAddEntry],
  );

  const handleDeleteEntry = useCallback(
    async (key: string) => {
      setSaving(true);
      setError(null);
      try {
        await deleteUserEnvironment(key);
        setEntries((prev) => prev.filter((entry) => entry.key !== key));
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
    [],
  );

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Shared Environment</h2>
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
                {entries.length === 0 ? (
                  <p className="empty-message">
                    No shared environment variables yet. Add your first one!
                  </p>
                ) : (
                  entries.map((entry) => (
                    <div key={entry.key} className="env-row">
                      <span className="env-key">{entry.key}</span>
                      <span className="env-value">{formatValue(entry)}</span>
                      <span className={`env-type env-type-${entry.type}`}>
                        {entry.type}
                      </span>
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
                  onClick={handleAddDraft}
                  disabled={saving || !draftKey.trim()}
                >
                  {saving ? <Loader size={18} /> : "Add"}
                </button>
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
