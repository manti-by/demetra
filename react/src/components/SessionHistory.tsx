import { memo, useState } from "react";
import { Loader } from "./Loader";
import type { SessionHistoryEntry, SessionTokenTotals, SessionToolUsage } from "../services/api";

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

const ChevronIcon = () => (
  <svg
    className="session-history-chevron"
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

interface HistoryDisplayItem {
  /** The row carrying the tokens when merged, otherwise the row itself. */
  entry: SessionHistoryEntry;
  /** Marker row time, present when this item absorbs a step marker. */
  start: string | null;
  /** ok: marker paired with its invocation; pending: marker awaits its agent; failed: agent never completed. */
  status: "ok" | "pending" | "failed";
}

/**
 * Fold step markers into their agent invocation rows.
 *
 * The workflow records a `kind='step'` marker before an agent runs and the
 * `kind='invocation'` row with tokens only after it finishes, so both belong
 * to one visual block: the marker supplies the start time, the invocation the
 * end time and usage. A marker pairs with the next same-step invocation before
 * the next same-step marker. Only steps that start a marker before an agent
 * count as agent markers — today that is `build`; steps that never produce
 * invocations (lint, test, wiki, ...) keep their plain marker card. A marker
 * without an invocation is still running when it is the newest row and failed
 * otherwise.
 */
const AGENT_MARKER_STEPS = new Set(["build"]);

export function mergeHistoryEntries(entries: SessionHistoryEntry[]): HistoryDisplayItem[] {
  const invokedSteps = new Set(
    entries.filter((entry) => entry.kind === "invocation").map((entry) => entry.step),
  );

  const items: HistoryDisplayItem[] = [];
  let index = 0;
  while (index < entries.length) {
    const marker = entries[index];
    const isAgentMarker = marker.kind === "step" && (AGENT_MARKER_STEPS.has(marker.step) || invokedSteps.has(marker.step));
    if (!isAgentMarker) {
      items.push({ entry: marker, start: null, status: "ok" });
      index += 1;
      continue;
    }

    let match = -1;
    for (let scan = index + 1; scan < entries.length; scan += 1) {
      const candidate = entries[scan];
      if (candidate.kind === "step" && candidate.step === marker.step) break;
      if (candidate.kind === "invocation" && candidate.step === marker.step) {
        match = scan;
        break;
      }
    }

    if (match === -1) {
      const isLatest = index === entries.length - 1;
      items.push({ entry: marker, start: marker.created_at, status: isLatest ? "pending" : "failed" });
      index += 1;
      continue;
    }

    items.push({ entry: entries[match], start: marker.created_at, status: "ok" });
    index = match + 1;
  }
  return items;
}

interface SessionHistoryCardProps {
  item: HistoryDisplayItem;
}

/**
 * One history block, collapsible and collapsed by default.
 *
 * The header carries the step name on the left and the cost and time on the
 * right. The cost is only worth a spot while the block is collapsed: an open
 * block repeats it in the token breakdown, so the header drops it then.
 */
function SessionHistoryCard({ item }: SessionHistoryCardProps) {
  const { entry, start, status } = item;
  const [isOpen, setIsOpen] = useState(false);
  const hasTokens = entry.kind === "invocation" || entry.kind === "llm_call";
  const toolUsage = entry.tool_usage ?? [];
  const isError = status === "failed" || entry.step === "failed";
  const isPending = status === "pending" && !isError;
  // Within a marker item the entry is either the paired invocation or the
  // marker itself, so only an invocation entry supplies a real end time.
  const end = entry.kind === "invocation" ? entry.created_at : null;
  const durationMs =
    start !== null && end !== null
      ? new Date(end).getTime() - new Date(start).getTime()
      : isPending && start !== null
        ? Date.now() - new Date(start).getTime()
        : null;

  const cardClass = [
    "session-history-card",
    isError && "session-history-card-error",
    isPending && "session-history-card-pending",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <li
      className={cardClass}
      data-step={entry.step}
      data-kind={entry.kind}
      data-status={status}
      data-open={isOpen}
    >
      <button
        type="button"
        className="session-history-card-header"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
      >
        <span className="session-history-step">
          <ChevronIcon />
          {entry.step}
        </span>
        <span className="session-history-header-meta">
          {!isOpen && entry.cost != null && (
            <span className="session-history-cost">${entry.cost.toFixed(4)}</span>
          )}
          <time
            className="session-history-time"
            dateTime={entry.created_at}
            title={new Date(entry.created_at).toLocaleString()}
          >
            {formatTime(entry.created_at)}
          </time>
        </span>
      </button>
      {isOpen && (
        <>
          {entry.message != null && (
            <p className="session-history-failure" title="Failure reason">
              {entry.message}
            </p>
          )}
          {isError && entry.message == null && (
            <p className="session-history-status session-history-status-error">
              Agent did not complete, no usage was recorded for this run.
            </p>
          )}
          {isPending && (
            <p className="session-history-status session-history-status-pending">
              Agent is still running, tokens appear when it finishes.
            </p>
          )}
          {start != null && (
            <dl className="session-history-timing">
              <div>
                <dt>Start</dt>
                <dd title={new Date(start).toLocaleString()}>{formatTime(start)}</dd>
              </div>
              <div>
                <dt>End</dt>
                <dd>{end != null ? formatTime(end) : "—"}</dd>
              </div>
              <div>
                <dt>Duration</dt>
                <dd>{durationMs != null ? formatDuration(durationMs) : "—"}</dd>
              </div>
            </dl>
          )}
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
          {entry.agent != null && (
            <div>
              <dt>Agent</dt>
              <dd>{entry.agent}</dd>
            </div>
          )}
          {entry.cost != null && (
            <div>
              <dt>Cost</dt>
              <dd>${entry.cost.toFixed(4)}</dd>
            </div>
          )}
          {entry.price != null && (
            <div>
              <dt>Price / 1M</dt>
              <dd>
                in ${entry.price.input.toFixed(2)} · out ${entry.price.output.toFixed(2)}
              </dd>
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
          {hasTokens && toolUsage.length > 0 && (
            <div className="session-history-tools">
              <span className="session-history-tools-label">Tools</span>
              <ul className="session-history-tools-list">
                {toolUsage.map((tool) => (
                  <li
                    key={tool.name}
                    title={`${tool.succeeded} succeeded, ${tool.failed} failed, ${tool.duration_ms.toLocaleString()} ms`}
                  >
                    <span className="session-history-tool-name">{tool.name}</span>
                    <span className="session-history-tool-calls">×{tool.calls.toLocaleString()}</span>
                    {tool.failed > 0 && (
                      <span className="session-history-tool-failed"> ({tool.failed} failed)</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </li>
  );
}

interface SessionHistoryProps {
  entries: SessionHistoryEntry[];
  total: SessionTokenTotals;
  toolUsage: SessionToolUsage[];
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
        <div className="session-history-totals-grand">
          <dt>Total Cost</dt>
          <dd>${total.cost.toFixed(4)}</dd>
        </div>
      </dl>
    </div>
  );
}

function ToolUsageBlock({ usage }: { usage: SessionToolUsage[] }) {
  if (usage.length === 0) return null;

  return (
    <div className="session-history-totals">
      <h3 className="session-history-totals-header">Tool Usage</h3>
      <dl className="session-history-tool-grid">
        {usage.map((tool) => (
          <div key={tool.name}>
            <dt>{tool.name}</dt>
            <dd
              title={`${tool.succeeded} succeeded, ${tool.failed} failed, ${tool.duration_ms.toLocaleString()} ms`}
            >
              {tool.calls.toLocaleString()}
              {tool.failed > 0 && (
                <span className="session-history-tool-failed"> ({tool.failed} failed)</span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function SessionHistoryInner({
  entries,
  total,
  toolUsage,
  isOpen,
  onClose,
  isLoading,
  error,
}: SessionHistoryProps) {
  if (!isOpen) return null;

  const items = mergeHistoryEntries(entries);

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
          {isLoading && <Loader size={36} />}
          {!isLoading && error && (
            <div className="session-history-error">{error}</div>
          )}
          {!isLoading && !error && entries.length === 0 && (
            <div className="session-history-empty">No history yet</div>
          )}
          {!isLoading && !error && entries.length > 0 && (
            <>
              <ol className="session-history-timeline">
                {items.map((item) => (
                  <SessionHistoryCard key={item.entry.id} item={item} />
                ))}
              </ol>
              <TotalTokensBlock total={total} />
              <ToolUsageBlock usage={toolUsage} />
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
