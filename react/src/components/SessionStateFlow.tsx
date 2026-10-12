import { Fragment, useEffect, useRef, useState } from "react";

export type FlowNodeState = "done" | "active" | "upcoming";

export type FlowTone = "warning" | "accent" | "success";

export type LoopSource = "review" | "lint" | null;

export interface FlowNode {
  key: string;
  label: string;
  steps: string[];
  tone: FlowTone;
}

export interface FlowFeedback {
  key: Exclude<LoopSource, null>;
  label: string;
}

export const RESEARCH_FLOW: FlowNode[] = [
  { key: "linear", label: "Linear", steps: ["initial"], tone: "warning" },
  { key: "research", label: "Research", steps: ["research"], tone: "warning" },
  { key: "linear-report", label: "Linear", steps: ["awaiting_input"], tone: "warning" },
  { key: "done", label: "Done", steps: ["completed"], tone: "success" },
];

export const BUILD_FLOW: FlowNode[] = [
  { key: "linear", label: "Linear", steps: ["initial"], tone: "warning" },
  { key: "plan", label: "Plan", steps: ["plan", "awaiting_input"], tone: "warning" },
  { key: "build", label: "Build", steps: ["build"], tone: "accent" },
  { key: "validate", label: "Validate", steps: ["validate"], tone: "accent" },
  { key: "review", label: "Review", steps: ["review"], tone: "accent" },
  { key: "lint", label: "Lint", steps: ["lint"], tone: "accent" },
  { key: "test", label: "Test", steps: ["test"], tone: "accent" },
  { key: "github", label: "GitHub", steps: ["wiki", "push", "completed"], tone: "success" },
];

export const BUILD_FEEDBACK: FlowFeedback[] = [
  { key: "review", label: "Feedback from review" },
  { key: "lint", label: "Feedback from lint and test" },
];

export function resolveNodeStates(flow: FlowNode[], step?: string | null): FlowNodeState[] {
  const activeIndex = step ? flow.findIndex((node) => node.steps.includes(step)) : -1;
  return flow.map((_, index) => {
    if (activeIndex === -1 || index > activeIndex) return "upcoming";
    return index === activeIndex ? "active" : "done";
  });
}

export function activeFeedback(step?: string | null, previous?: string | null): LoopSource {
  if (step !== "build") return null;
  if (previous === "review") return "review";
  if (previous === "lint" || previous === "test") return "lint";
  return null;
}

const LoopArrow = () => (
  <svg
    className="session-flow-loop-arrow"
    viewBox="0 0 90 18"
    width="90"
    height="18"
    aria-hidden="true"
    focusable="false"
  >
    <path d="M2 2 C 24 18, 66 18, 88 2" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M81 2 L88 2 L86 9" fill="none" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

interface SessionStateFlowProps {
  step?: string | null;
  isResearch?: boolean;
}

export function SessionStateFlow({ step, isResearch = false }: SessionStateFlowProps) {
  const flow = isResearch ? RESEARCH_FLOW : BUILD_FLOW;
  const states = resolveNodeStates(flow, step);
  const previousStepRef = useRef<string | null>(null);
  const [activeLoop, setActiveLoop] = useState<LoopSource>(null);

  useEffect(() => {
    setActiveLoop(activeFeedback(step, previousStepRef.current));
    previousStepRef.current = step ?? null;
  }, [step]);

  const loop = step === "build" ? activeLoop : null;

  return (
    <div className="session-flow">
      <div className="session-flow-track" aria-label="Session state">
        {flow.map((node, index) => (
          <Fragment key={node.key}>
            {index > 0 && <span className="session-flow-separator" aria-hidden="true" />}
            <span
              className={`session-flow-node tone-${node.tone} ${states[index]}`}
              data-state={states[index]}
            >
              {node.label}
            </span>
          </Fragment>
        ))}
      </div>
      {!isResearch && (
        <div className="session-flow-loops">
          {BUILD_FEEDBACK.map((feedback) => (
            <span
              key={feedback.key}
              className={`session-flow-loop${loop === feedback.key ? " active" : ""}`}
              aria-label={feedback.label}
              data-active={loop === feedback.key ? "true" : "false"}
            >
              <LoopArrow />
              <span className="session-flow-loop-label">{feedback.label}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default SessionStateFlow;
