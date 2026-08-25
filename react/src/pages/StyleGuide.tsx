import { useState } from "react";
import { Link } from "react-router-dom";
import { Loader } from "../components/Loader";
import { GitHubLoginButton } from "../components/GitHubLoginButton";
import { SessionHistory } from "../components/SessionHistory";
import "./StyleGuide.css";

const MOCK_HISTORY_ENTRIES = [
  {
    id: "1",
    session_id: "sess-abc",
    step: "plan",
    created_at: new Date(Date.now() - 3600000).toISOString(),
    length: 1200,
    input_tokens: 600,
    output_tokens: 400,
    reasoning_tokens: 120,
    cache_read_tokens: 40,
    cache_write_tokens: 40,
    context_tokens: 200,
    model: "openrouter/anthropic",
  },
  {
    id: "2",
    session_id: "sess-abc",
    step: "build",
    created_at: new Date(Date.now() - 1800000).toISOString(),
    length: 2400,
    input_tokens: 1100,
    output_tokens: 900,
    reasoning_tokens: 300,
    cache_read_tokens: 80,
    cache_write_tokens: 80,
    context_tokens: 340,
    model: "openrouter/anthropic",
  },
];

const MOCK_TOTAL = {
  length: 3600,
  input_tokens: 1700,
  output_tokens: 1300,
  reasoning_tokens: 420,
  cache_read_tokens: 120,
  cache_write_tokens: 120,
};

export function StyleGuide() {
  const [showHistory, setShowHistory] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

  const toggleHistoryLoading = () => {
    setShowHistory(true);
    setHistoryLoading(true);
    setTimeout(() => setHistoryLoading(false), 1500);
  };

  return (
    <div className="styleguide-page">
      <div className="styleguide-header">
        <div>
          <h1 className="styleguide-title">Style Guide</h1>
          <p className="styleguide-subtitle">
            Living catalog of Demetra UI — colors, typography, buttons, forms, loaders and composite components.
          </p>
        </div>
        <Link to="/" className="btn-secondary">← Back to app</Link>
      </div>

      {/* ── Loader ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Loader</h2>
        <p className="sg-section-desc">Replaces all BE-waiting spinners. Uses <code>/loader.svg</code> (#788860).</p>
        <div className="sg-card">
          <div className="sg-loader-grid">
            <div className="sg-loader-item">
              <Loader size={18} />
              <span>18 — button inline</span>
            </div>
            <div className="sg-loader-item">
              <Loader size={28} />
              <span>28 — small</span>
            </div>
            <div className="sg-loader-item">
              <Loader size={40} />
              <span>40 — default</span>
            </div>
            <div className="sg-loader-item">
              <Loader size={56} />
              <span>56 — fullscreen</span>
            </div>
          </div>
          <div className="sg-row" style={{ marginTop: 16 }}>
            <button className="btn-primary" disabled><Loader size={18} /></button>
            <button className="btn-primary"><Loader size={18} /></button>
            <span className="sg-muted">Inline in <code>.btn-primary</code> / <code>.auth-submit</code> — container padding is collapsed via CSS.</span>
          </div>
          <div className="sg-inline-loader-demo">
            <span>Fullscreen variant:</span>
            <div className="sg-fullscreen-mock"><Loader size={48} /></div>
          </div>
        </div>
      </section>

      {/* ── Colors ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Design Tokens</h2>
        <div className="sg-card">
          <h3 className="sg-h3">Surfaces</h3>
          <div className="sg-swatches">
            <div className="sg-swatch" style={{ background: "var(--color-canvas)", border: "1px solid var(--color-border)" }}><span>--color-canvas</span><code>#0c0e0d</code></div>
            <div className="sg-swatch" style={{ background: "var(--color-surface-1)" }}><span>--color-surface-1</span><code>#0f110f</code></div>
            <div className="sg-swatch" style={{ background: "var(--color-surface-2)" }}><span>--color-surface-2</span><code>#141614</code></div>
            <div className="sg-swatch" style={{ background: "var(--color-surface-3)" }}><span>--color-surface-3</span><code>#181a18</code></div>
          </div>
          <h3 className="sg-h3">Accent & semantic</h3>
          <div className="sg-swatches">
            <div className="sg-swatch" style={{ background: "var(--color-accent)" }}><span style={{ color: "#fff" }}>--color-accent</span><code style={{ color: "#fff" }}>#788860</code></div>
            <div className="sg-swatch" style={{ background: "var(--color-success)" }}><span style={{ color: "#fff" }}>--color-success</span></div>
            <div className="sg-swatch" style={{ background: "var(--color-error)" }}><span style={{ color: "#fff" }}>--color-error</span></div>
            <div className="sg-swatch" style={{ background: "var(--color-warning)" }}><span>--color-warning</span></div>
          </div>
          <h3 className="sg-h3">Text</h3>
          <div className="sg-text-row">
            <span style={{ color: "var(--color-text-primary)" }}>--color-text-primary</span>
            <span style={{ color: "var(--color-text-secondary)" }}>--color-text-secondary</span>
            <span style={{ color: "var(--color-text-tertiary)" }}>--color-text-tertiary</span>
          </div>
        </div>
      </section>

      {/* ── Typography ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Typography</h2>
        <div className="sg-card sg-typography">
          <h1>H1 — Demetra title 1.75rem / 600 / -0.035em</h1>
          <h2>H2 — Section 1.5rem / 600</h2>
          <h3>H3 — Card 1.25rem / 500</h3>
          <h4>H4 — 1rem / 500</h4>
          <h5>H5 — 0.875rem</h5>
          <h6>H6 — 0.75rem uppercase / secondary</h6>
          <p>Paragraph — 0.875rem / 1.5. The quick brown fox jumps over the lazy dog. <a href="#">Inline link</a> with accent hover.</p>
          <small>Small — 0.75rem / secondary. Used for hints and meta.</small>
          <div className="sg-row"><code>inline code</code> <kbd>Cmd</kbd> + <kbd>K</kbd> <em>emphasis</em> <strong>strong</strong></div>
          <blockquote>Blockquote — secondary italic with left border.</blockquote>
          <pre>pre — mono 0.8125rem / 1.618{`
const hello = "world";`}</pre>
        </div>
      </section>

      {/* ── Buttons ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Buttons</h2>
        <div className="sg-card">
          <div className="sg-row sg-wrap">
            <button className="btn-primary">Primary</button>
            <button className="btn-primary" disabled>Primary disabled</button>
            <button className="btn-primary"><Loader size={16} /></button>
            <button className="btn-secondary">Secondary</button>
            <button className="btn-secondary" disabled>Secondary disabled</button>
            <GitHubLoginButton />
          </div>
          <div className="sg-row sg-wrap">
            <button className="btn-icon" aria-label="icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3" /></svg></button>
            <button className="btn-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3,6 5,6 21,6" /><path d="M19,6v14a2,2 0 0,1-2,2H7a2,2 0 0,1-2-2V6m3,0V4a2,2 0 0,1,2-2h4a2,2 0 0,1,2 2v2" /></svg></button>
            <button className="theme-toggle" aria-label="theme"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5" /></svg></button>
            <button className="palette-trigger"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg> <kbd>Cmd+K</kbd></button>
            <button className="modal-btn">Modal btn</button>
          </div>
          <div className="sg-row">
            <button className="github-login-button" type="button"><svg height="20" viewBox="0 0 16 16" width="20" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" /></svg> Sign in with GitHub</button>
          </div>
        </div>
      </section>

      {/* ── Forms ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Forms</h2>
        <div className="sg-card">
          <div className="sg-form-grid">
            <input className="form-input" placeholder="form-input placeholder" defaultValue="typed value" />
            <input className="form-input" placeholder="disabled" disabled value="disabled" />
            <div className="env-form" style={{ gridColumn: "1 / -1" }}>
              <input className="form-input env-key-input" placeholder="Key" defaultValue="OPENROUTER_API_KEY" />
              <input className="form-input env-value-input" placeholder="Value" defaultValue="sk-••••••••" />
              <label className="env-encrypted-label"><input type="checkbox" defaultChecked /> Encrypted</label>
              <button className="btn-primary">Add</button>
            </div>
            <div className="settings-error" style={{ gridColumn: "1 / -1" }}>settings-error — Failed to load projects</div>
          </div>
        </div>
      </section>

      {/* ── Session items ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Sessions & Projects</h2>
        <div className="sg-card">
          <div className="sg-stack">
            <div className="session-item selected">
              <div className="session-item-header"><span className="session-title">my-feature-branch</span><span className="session-step build">build</span></div>
              <div className="session-item-meta"><span className="session-time">2h ago</span><span className="session-plan">Build plan available</span></div>
            </div>
            <div className="session-item">
              <div className="session-item-header"><span className="session-title">fix/auth-flow</span><span className="session-step completed">completed</span></div>
              <div className="session-item-meta"><span className="session-time">1d ago</span><span className="session-plan">PR #42</span></div>
            </div>
            <div className="session-item">
              <div className="session-item-header"><span className="session-title">init</span><span className="session-step failed">failed</span></div>
              <div className="session-item-meta"><span className="session-time">Just now</span></div>
            </div>
            <div className="session-item">
              <div className="session-item-header"><span className="session-title">initial session</span><span className="session-step initial">initial</span></div>
              <div className="session-item-meta"><span className="session-time">5m ago</span></div>
            </div>
          </div>
          <div className="sg-row sg-wrap" style={{ marginTop: 12 }}>
            <span className="session-step initial">initial</span>
            <span className="session-step plan">plan</span>
            <span className="session-step build">build</span>
            <span className="session-step review">review</span>
            <span className="session-step completed">completed</span>
            <span className="session-step failed">failed</span>
          </div>
          <hr />
          <div className="projects-list">
            <div className="project-item">
              <div className="project-info"><h3>demetra</h3><p className="project-url">Repository: https://github.com/org/demetra</p><p className="project-linear">Linear ID: abc123</p></div>
              <div className="project-actions"><button className="btn-icon env-project"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 7h-3V4H7v3H4v13h16V7zM10 12h4M10 16h4" /></svg></button><button className="btn-icon delete-project"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3,6 5,6 21,6" /><path d="M19,6v14a2,2 0 0,1-2,2H7a2,2 0 0,1-2-2V6m3,0V4a2,2 0 0,1,2-2h4a2,2 0 0,1,2 2v2" /></svg></button></div>
            </div>
            <div className="project-item">
              <div className="project-info"><h3>empty-project</h3><p className="project-url">Repository: https://github.com/org/empty</p></div>
              <div className="project-actions"><button className="btn-icon env-project"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 7h-3V4H7v3H4v13h16V7zM10 12h4M10 16h4" /></svg></button></div>
            </div>
          </div>
          <hr />
          <div className="env-list">
            <div className="env-row"><span className="env-key">DATABASE_URL</span><span className="env-value">postgres://••••</span><span className="env-type env-type-encrypted">encrypted</span></div>
            <div className="env-row"><span className="env-key">NODE_ENV</span><span className="env-value">production</span><span className="env-type">text</span></div>
            <div className="env-row"><span className="env-key">EMPTY_VAR</span><span className="env-value">(empty)</span><span className="env-type">text</span></div>
          </div>
          <p className="empty-message">No environment variables yet. Add your first one!</p>
        </div>
      </section>

      {/* ── Log console ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Log Console</h2>
        <div className="sg-card" style={{ padding: 0, overflow: "hidden" }}>
          <div className="log-console" style={{ minHeight: 220 }}>
            <div className="log-header">
              <span className="log-title"><span className="log-indicator connected" /> Session: abc12345</span>
              <div className="log-actions"><button className="log-btn log-btn-delete">Delete</button><button className="log-btn">Clear</button></div>
            </div>
            <div className="log-content">
              <div className="log-line"><span className="log-message">[12:00:01] Starting build…</span></div>
              <div className="log-line"><span className="log-message">[12:00:03] Installing dependencies</span></div>
              <div className="log-line error"><span className="log-message">[12:00:04] ERR! peer dep missing</span></div>
              <div className="log-line success"><span className="log-message">[12:00:05] Build complete</span></div>
            </div>
          </div>
          <div style={{ padding: 12, borderTop: "1px solid var(--color-border)" }}>
            <div className="log-empty">Waiting for log events...</div>
            <div className="log-empty" style={{ marginTop: 8 }}>Select a session</div>
          </div>
        </div>
      </section>

      {/* ── Session History inline ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Session History</h2>
        <div className="sg-card">
          <div className="sg-row sg-wrap">
            <button className="btn-secondary" onClick={() => setShowHistory(true)}>Open populated</button>
            <button className="btn-secondary" onClick={toggleHistoryLoading}>Open loading (1.5s)</button>
            <button className="btn-secondary" onClick={() => setShowHistory(false)}>Close</button>
          </div>
          <div className="sg-muted" style={{ marginTop: 8 }}>Modal overlay demo — same component used in SessionArtifacts.</div>
          <div className="sg-history-inline">
            <ol className="session-history-timeline">
              <li className="session-history-card"><div className="session-history-card-header"><span className="session-history-step">plan</span><time className="session-history-time">1h ago</time></div><dl className="session-history-tokens"><div><dt>Input</dt><dd>600</dd></div><div><dt>Output</dt><dd>400</dd></div><div><dt>Total</dt><dd>1,200</dd></div></dl></li>
              <li className="session-history-card"><div className="session-history-card-header"><span className="session-history-step">build</span><time className="session-history-time">30m ago</time></div><dl className="session-history-tokens"><div><dt>Input</dt><dd>1,100</dd></div><div><dt>Output</dt><dd>900</dd></div><div><dt>Total</dt><dd>2,400</dd></div></dl></li>
            </ol>
            <div className="session-history-totals">
              <h3 className="session-history-totals-header">Total Tokens</h3>
              <dl className="session-history-totals-grid"><div><dt>Input</dt><dd>1,700</dd></div><div><dt>Output</dt><dd>1,300</dd></div><div><dt>Total</dt><dd>3,600</dd></div></dl>
            </div>
          </div>
          <div className="session-history-empty">No history yet</div>
          <div className="session-history-error">Failed to load session history</div>
          <div style={{ display: "flex", justifyContent: "center", padding: 12 }}><Loader size={32} /></div>
        </div>

        <SessionHistory entries={MOCK_HISTORY_ENTRIES} total={MOCK_TOTAL} isOpen={showHistory} onClose={() => setShowHistory(false)} isLoading={historyLoading} error={null} />
      </section>

      {/* ── Modals ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Modals</h2>
        <div className="sg-card">
          <button className="btn-primary" onClick={() => setShowModal(true)}>Open demo modal</button>
          <div className="sg-muted" style={{ marginTop: 8 }}>Uses <code>.modal-overlay</code> / <code>.modal-content</code> / <code>.modal-header</code> / <code>.modal-body</code> / <code>.modal-footer</code></div>
          <div className="sg-modal-inline">
            <div className="modal-content" style={{ position: "relative", maxHeight: "none" }}>
              <div className="modal-header"><h2>Build Plan</h2><button className="modal-close" aria-label="Close"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg></button></div>
              <div className="modal-body"><pre className="build-plan-text"># Build plan — example{"\n"}- Parse Linear issue{"\n"}- Generate diff{"\n"}- Open PR</pre></div>
              <div className="modal-footer"><button className="modal-btn">Show Markdown</button><button className="btn-secondary">Close</button></div>
            </div>
          </div>
        </div>
        {showModal && (
          <div className="modal-overlay" onClick={() => setShowModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header"><h2>Demo modal</h2><button className="modal-close" onClick={() => setShowModal(false)} aria-label="Close"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg></button></div>
              <div className="modal-body"><p>This is a live modal overlay. Click outside to close.</p></div>
              <div className="modal-footer"><button className="btn-secondary" onClick={() => setShowModal(false)}>Close</button></div>
            </div>
          </div>
        )}
      </section>

      {/* ── Auth ── */}
      <section className="sg-section">
        <h2 className="sg-section-title">Auth & misc</h2>
        <div className="sg-card">
          <div style={{ maxWidth: 320, margin: "0 auto" }}>
            <GitHubLoginButton />
            <div className="auth-divider"><span>or</span></div>
            <div className="auth-field"><input placeholder="Email" defaultValue="demo@example.com" /></div>
            <div className="auth-field" style={{ marginTop: 8 }}><input placeholder="Password" type="password" defaultValue="password123" /></div>
            <button className="auth-submit" style={{ marginTop: 8, width: "100%" }}>Sign in</button>
            <button className="auth-submit" style={{ marginTop: 8, width: "100%" }} disabled><Loader size={18} /></button>
          </div>
          <hr />
          <div className="session-artifacts"><a className="session-artifacts-link" href="#"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></svg> View Linear Issue</a><a className="session-artifacts-link" href="#"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg> View Pull Request</a><a className="session-artifacts-link" href="#"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg> View Build Plan</a></div>
          <hr />
          <div className="sg-row">
            <div className="user-info"><div className="user-avatar">D</div><span className="user-name">demo@example.com</span></div>
            <span className="sg-muted">user-info / avatar / burger-icon</span>
          </div>
        </div>
      </section>

      <footer className="sg-footer">
        <span>Demetra Style Guide — generated from live <code>App.css</code> + <code>index.css</code> tokens.</span>
        <Link to="/" className="btn-secondary">Back to app</Link>
      </footer>
    </div>
  );
}

export default StyleGuide;
