import {
  forwardRef,
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
  useImperativeHandle,
} from "react";

interface Command {
  id: string;
  label: string;
  shortcut?: string;
  action: () => void;
  category?: string;
}

interface CommandPaletteProps {
  commands: Command[];
}

export interface CommandPaletteHandle {
  open: () => void;
}

export const CommandPalette = forwardRef<
  CommandPaletteHandle,
  CommandPaletteProps
>(function CommandPalette({ commands }, ref) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(
    ref,
    () => ({
      open: () => {
        setOpen(true);
        setQuery("");
        setSelectedIndex(0);
      },
    }),
    [],
  );

  const filtered = useMemo(
    () =>
      query.trim() === ""
        ? commands
        : commands.filter(
            (cmd) =>
              cmd.label.toLowerCase().includes(query.toLowerCase()) ||
              (cmd.category?.toLowerCase().includes(query.toLowerCase()) ??
                false),
          ),
    [commands, query],
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
        setQuery("");
        setSelectedIndex(0);
      }
      if (e.key === "Escape") {
        setOpen(false);
        setQuery("");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % Math.max(filtered.length, 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev <= 0 ? Math.max(filtered.length - 1, 0) : prev - 1,
        );
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        filtered[selectedIndex].action();
        setOpen(false);
        setQuery("");
      }
    },
    [filtered, selectedIndex],
  );

  const handleGlobalKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!open) return;
      if (document.activeElement === inputRef.current) return;
      const cmd = commands.find((c) => c.shortcut && c.shortcut === e.key.toUpperCase());
      if (cmd) {
        e.preventDefault();
        cmd.action();
        setOpen(false);
        setQuery("");
      }
    },
    [open, commands],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [handleGlobalKeyDown]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);

  if (!open) return null;

  return (
    <div className="palette-overlay" onClick={close}>
      <div
        className="palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="palette-input-wrapper">
          <svg
            className="palette-search-icon"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            className="palette-input"
            type="text"
            placeholder="Type a command..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <kbd className="palette-esc-hint">esc</kbd>
        </div>
        {filtered.length > 0 && (
          <div className="palette-results">
            {filtered.map((cmd, i) => (
              <button
                key={cmd.id}
                className={`palette-item ${i === selectedIndex ? "palette-item-selected" : ""}`}
                onClick={() => {
                  cmd.action();
                  close();
                }}
                onMouseEnter={() => setSelectedIndex(i)}
              >
                <span className="palette-item-label">
                  {cmd.category && (
                    <span className="palette-item-category">
                      {cmd.category}
                    </span>
                  )}
                  {cmd.label}
                </span>
                {cmd.shortcut && (
                  <kbd className="palette-item-shortcut">{cmd.shortcut}</kbd>
                )}
              </button>
            ))}
          </div>
        )}
        {filtered.length === 0 && query.trim() !== "" && (
          <div className="palette-empty">No results for "{query}"</div>
        )}
      </div>
    </div>
  );
});

export default CommandPalette;
