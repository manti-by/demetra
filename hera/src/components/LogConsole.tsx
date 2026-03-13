import { useEffect, useRef, useState, useCallback, useMemo, memo } from "react";

const API_URL = import.meta.env.VITE_API_URL || "";
const MAX_LOGS = 200;

interface LogMessage {
  id: string;
  timestamp: string;
  message: string;
  type: "info" | "error" | "success";
}

const formatTimestamp = (ts: string): string => {
  const date = new Date(ts);
  const h = String(date.getHours()).padStart(2, "0");
  const m = String(date.getMinutes()).padStart(2, "0");
  const s = String(date.getSeconds()).padStart(2, "0");
  return `${h}:${m}:${s}`;
};

const LogLine = memo(({ log }: { log: LogMessage }) => (
  <div className={`log-line ${log.type}`}>
    <span className="log-timestamp">[{formatTimestamp(log.timestamp)}]</span>
    <span className="log-message">{log.message}</span>
  </div>
));

const EmptyLog = () => (
  <div className="log-empty">Waiting for log events...</div>
);

const SelectSession = () => <div className="log-empty">Select a session</div>;

interface LogConsoleProps {
  taskId?: string | null;
}

export function LogConsole({ taskId }: LogConsoleProps) {
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const cachedToken = localStorage.getItem("auth_token");
    tokenRef.current = cachedToken;
    if (!cachedToken) return;

    setLogs([]);
    const wsUrl = `${API_URL.replace(/^http/, "ws")}/ws/v1/watcher/logs?task_id=${taskId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      const addLog = (log: LogMessage) => {
        setLogs((prev) => [...prev.slice(-MAX_LOGS), log]);
      };

      try {
        const data = JSON.parse(event.data);
        addLog({ 
          ...data, 
          id: crypto.randomUUID(),
          type: data.type || "info" 
        });
      } catch {
        addLog({
          id: crypto.randomUUID(),
          message: event.data,
          type: "info",
          timestamp: new Date().toISOString(),
        });
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [taskId]);

  useEffect(() => {
    if (logsEndRef.current && typeof logsEndRef.current.scrollIntoView === 'function') {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs.length]);

  const clearLogs = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setLogs([]);
  }, []);

  const logElements = useMemo(
    () => logs.map((log) => <LogLine key={log.id} log={log} />),
    [logs],
  );

  const indicatorClass = connected
    ? "log-indicator connected"
    : "log-indicator";

  const logTitle = taskId ? `Session: ${taskId.slice(0, 8)}` : "Session Logs";

  return (
    <div className="log-console">
      <div className="log-header">
        <span className="log-title">
          <span className={indicatorClass} />
          {logTitle}
        </span>
        <div className="log-actions">
          <button className="log-btn" onClick={clearLogs}>
            Clear
          </button>
        </div>
      </div>
      <div className="log-content">
        {!taskId ? (
          <SelectSession />
        ) : logs.length === 0 ? (
          <EmptyLog />
        ) : (
          logElements
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}

export default LogConsole;
