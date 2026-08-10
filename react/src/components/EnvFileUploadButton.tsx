import { useCallback, useRef } from 'react';
import { parseEnvFile, type EnvFileEntry } from '../utils/envFile';

interface EnvFileUploadButtonProps {
  onParsed: (entries: EnvFileEntry[]) => void;
  onError?: (message: string) => void;
}

const UploadIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
  >
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17,8 12,3 7,8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

export function EnvFileUploadButton({
  onParsed,
  onError,
}: EnvFileUploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const text = typeof reader.result === 'string' ? reader.result : '';
          const entries = parseEnvFile(text);
          if (entries.length === 0) {
            onError?.('No KEY=VALUE entries found in the selected file');
            return;
          }
          onParsed(entries);
        } catch (e) {
          onError?.(e instanceof Error ? e.message : 'Failed to parse the .env file');
        } finally {
          if (inputRef.current) {
            inputRef.current.value = '';
          }
        }
      };
      reader.onerror = () => {
        onError?.('Failed to read the selected file');
        if (inputRef.current) {
          inputRef.current.value = '';
        }
      };
      reader.readAsText(file);
    },
    [onParsed, onError],
  );

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".env"
        className="env-file-input"
        onChange={handleFileChange}
        aria-label="Upload .env file"
      />
      <button
        className="btn-secondary env-upload-button"
        onClick={() => inputRef.current?.click()}
        type="button"
      >
        <UploadIcon />
        Upload .env
      </button>
    </>
  );
}
