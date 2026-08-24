import { memo } from "react";
import type { SessionHistoryEntry, SessionTokenTotals } from "../services/api";

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

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffSec = Math.round((now - then) / 1000);

  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

interface SessionHistoryCardProps {
  entry: SessionHistoryEntry;
}

function SessionHistoryCard({ entry }: SessionHistoryCardProps) {
  const hasTokens =
    entry.input_tokens != null ||
    entry.output_tokens != null ||
    entry.reasoning_tokens != null ||
    entry.cache_read_tokens != null ||
    entry.cache_write_tokens != null ||
    entry.context_tokens != null ||
    entry.model != null ||
    entry.length != null;

  return (
    <li className="session-history-card" data-step={entry.step}>
      <div className="session-history-card-header">
        <span className="session-history-step">{entry.step}</span>
        <time
          className="session-history-time"
          dateTime={entry.created_at}
          title={entry.created_at}
        >
          {formatRelativeTime(entry.created_at)}
        </time>
      </div>
      {hasTokens && (
        <dl className="session-history-tokens">
          {entry.input_tokens != null && (
            <div>
              <dt>Input</dt>
              <dd>{entry.input_tokens.toLocaleString()}</dd>
            </div>
          )}
          {entry.output_tokens != null && (
            <div>
              <dt>Output</dt>
              <dd>{entry.output_tokens.toLocaleString()}</dd>
            </div>
          )}
          {entry.reasoning_tokens != null && (
            <div>
              <dt>Reasoning</dt>
              <dd>{entry.reasoning_tokens.toLocaleString()}</dd>
            </div>
          )}
          {entry.cache_read_tokens != null && (
            <div>
              <dt>Cache read</dt>
              <dd>{entry.cache_read_tokens.toLocaleString()}</dd>
            </div>
          )}
          {entry.cache_write_tokens != null && (
            <div>
              <dt>Cache write</dt>
              <dd>{entry.cache_write_tokens.toLocaleString()}</dd>
            </div>
          )}
          {entry.context_tokens != null && (
            <div>
              <dt>Context</dt>
              <dd>{entry.context_tokens.toLocaleString()}</dd>
            </div>
          )}
          {entry.model != null && (
            <div>
              <dt>Model</dt>
              <dd>{entry.model}</dd>
            </div>
          )}
          {entry.length != null && (
            <div>
              <dt>Total</dt>
              <dd>{entry.length.toLocaleString()}</dd>
            </div>
          )}
        </dl>
      )}
    </li>
  );
}

interface SessionHistoryProps {
  entries: SessionHistoryEntry[];
  total: SessionTokenTotals;
  isOpen: boolean;
  onClose: () => void;
  isLoading: boolean;
  error: string | null;
}

function TotalTokensBlock({ total }: { total: SessionTokenTotals }) {
  return (
    <div className="session-history-totals">
      <h3 className="session-history-totals-header">Total Tokens</h3>
      <dl className="session-history-totals-grid">
        <div>
          <dt>Input</dt>
          <dd>{total.input_tokens.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Output</dt>
          <dd>{total.output_tokens.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Reasoning</dt>
          <dd>{total.reasoning_tokens.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Cache read</dt>
          <dd>{total.cache_read_tokens.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Cache write</dt>
          <dd>{total.cache_write_tokens.toLocaleString()}</dd>
        </div>
        <div className="session-history-totals-grand">
          <dt>Total</dt>
          <dd>{total.length.toLocaleString()}</dd>
        </div>
      </dl>
    </div>
  );
}

function SessionHistoryInner({
  entries,
  total,
  isOpen,
  onClose,
  isLoading,
  error,
}: SessionHistoryProps) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content session-history-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>Session History [BETA]</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>
        <div className="modal-body">
          {isLoading && <div className="loading-spinner" />}
          {!isLoading && error && (
            <div className="session-history-error">{error}</div>
          )}
          {!isLoading && !error && entries.length === 0 && (
            <div className="session-history-empty">No history yet</div>
          )}
          {!isLoading && !error && entries.length > 0 && (
            <>
              <ol className="session-history-timeline">
                {entries.map((entry) => (
                  <SessionHistoryCard key={entry.id} entry={entry} />
                ))}
              </ol>
              <TotalTokensBlock total={total} />
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="modal-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export const SessionHistory = memo(SessionHistoryInner);
export default SessionHistory;
