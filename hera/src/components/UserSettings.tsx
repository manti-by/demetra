import { useState, useCallback } from 'react';
import { updateUserKeys } from '../services/api';

interface KeyValue {
  id: string;
  key: string;
  value: string;
}

interface UserSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const RemoveIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export function UserSettings({ isOpen, onClose }: UserSettingsProps) {
  const [keys, setKeys] = useState<KeyValue[]>([{ id: '1', key: '', value: '' }]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleAddKey = useCallback(() => {
    setKeys((prev) => [...prev, { id: crypto.randomUUID(), key: '', value: '' }]);
  }, []);

  const handleRemoveKey = useCallback((id: string) => {
    setKeys((prev) => prev.filter((k) => k.id !== id));
  }, []);

  const handleKeyChange = useCallback((id: string, field: 'key' | 'value', value: string) => {
    setKeys((prev) => prev.map((k) => (k.id === id ? { ...k, [field]: value } : k)));
    setError(null);
    setSuccess(false);
  }, []);

  const validate = useCallback((): string | null => {
    const keysList = keys.filter((k) => k.key.trim() !== '');
    const duplicates = keysList.filter((k, i) => keysList.findIndex((x) => x.key === k.key) !== i);
    if (duplicates.length > 0) {
      return 'Duplicate keys are not allowed';
    }
    const emptyKeys = keysList.filter((k) => k.key.trim() === '');
    if (emptyKeys.length > 0) {
      return 'Keys cannot be empty';
    }
    return null;
  }, [keys]);

  const handleSave = useCallback(async () => {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    const keysObject: Record<string, string> = {};
    keys.forEach((k) => {
      if (k.key.trim() !== '') {
        keysObject[k.key.trim()] = k.value;
      }
    });

    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      await updateUserKeys(keysObject);
      setSuccess(true);
      setKeys([{ id: '1', key: '', value: '' }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save keys');
    } finally {
      setLoading(false);
    }
  }, [keys, validate]);

  const handleClose = useCallback(() => {
    setKeys([{ id: '1', key: '', value: '' }]);
    setError(null);
    setSuccess(false);
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>User Settings</h2>
          <button className="modal-close" onClick={handleClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          <div className="settings-section">
            <h3>Keys</h3>
            <p className="settings-description">Add key-value pairs for your user configuration.</p>
            <div className="key-value-list">
              {keys.map((kv) => (
                <div key={kv.id} className="key-value-row">
                  <input
                    type="text"
                    placeholder="Key"
                    value={kv.key}
                    onChange={(e) => handleKeyChange(kv.id, 'key', e.target.value)}
                    className="key-input"
                  />
                  <input
                    type="password"
                    placeholder="Value"
                    value={kv.value}
                    onChange={(e) => handleKeyChange(kv.id, 'value', e.target.value)}
                    className="value-input"
                  />
                  <button
                    className="btn-icon remove-key"
                    onClick={() => handleRemoveKey(kv.id)}
                    aria-label="Remove key"
                    disabled={keys.length === 1}
                  >
                    <RemoveIcon />
                  </button>
                </div>
              ))}
            </div>
            <button className="btn-secondary add-key-btn" onClick={handleAddKey}>
              + Add Key
            </button>
          </div>
          {error && <div className="settings-error">{error}</div>}
          {success && <div className="settings-success">Keys saved successfully</div>}
        </div>
        <div className="modal-footer">
          <button className="btn-secondary" onClick={handleClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleSave} disabled={loading}>
            {loading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
