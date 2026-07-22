import { useState, useEffect, useCallback, memo } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { getSessions, type Session } from '../services/api';
interface SessionArtifactsProps {
  taskId: string | null;
}

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

function SessionArtifactsInner({ taskId }: SessionArtifactsProps) {
  const [session, setSession] = useState<Session | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [isRendered, setIsRendered] = useState(true);

  useEffect(() => {
    if (!taskId) {
      setSession(null);
      return;
    }

    let cancelled = false;

    const fetchSession = async () => {
      try {
        const sessions = await getSessions();
        if (!cancelled) {
          const found = sessions.find((s) => s.task_id === taskId) ?? null;
          setSession(found);
        }
      } catch {
        if (!cancelled) {
          setSession(null);
        }
      }
    };

    fetchSession();

    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const openModal = useCallback(() => {
    setIsRendered(true);
    setModalOpen(true);
  }, []);
  const closeModal = useCallback(() => setModalOpen(false), []);

  if (!session) {
    return <div className="session-artifacts" />;
  }

  const hasPrLink = !!session.pr_link;
  const hasBuildPlan = !!session.build_plan;
  const hasLinearLink = !!session.linear_link;

  if (!hasPrLink && !hasBuildPlan && !hasLinearLink) {
    return <div className="session-artifacts" />;
  }

  return (
    <div className="session-artifacts">
      {hasLinearLink && (
        <a
          className="session-artifacts-link"
          href={session.linear_link!}
          target="_blank"
          rel="noopener noreferrer"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
            <line x1="8" y1="21" x2="16" y2="21" />
            <line x1="12" y1="17" x2="12" y2="21" />
          </svg>
          View Linear Issue
        </a>
      )}
      {hasPrLink && (
        <a
          className="session-artifacts-link"
          href={session.pr_link!}
          target="_blank"
          rel="noopener noreferrer"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          View Pull Request
        </a>
      )}
      {hasBuildPlan && (
        <a className="session-artifacts-link" href="#" onClick={(e) => { e.preventDefault(); openModal(); }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          View Build Plan
        </a>
      )}
      {modalOpen && hasBuildPlan && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content build-plan-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Build Plan</h2>
              <button className="modal-close" onClick={closeModal} aria-label="Close">
                <CloseIcon />
              </button>
            </div>
            <div className="modal-body">
              {!isRendered ? (
                <pre className="build-plan-text">{session.build_plan}</pre>
              ) : (
                <div className="rendered-content" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(session.build_plan!, { async: false }) as string) }} />
              )}
            </div>
            <div className="modal-footer">
              <button className="modal-btn" onClick={() => setIsRendered(!isRendered)}>
                {isRendered ? 'Show Markdown' : 'Show Rendered'}
              </button>
            </div>
        </div>
        </div>
      )}
    </div>
  );
}

export const SessionArtifacts = memo(SessionArtifactsInner);
export default SessionArtifacts;
