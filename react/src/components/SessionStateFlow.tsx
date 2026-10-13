import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react";

export type FlowNodeState = "done" | "active" | "upcoming";

export type FlowTone = "warning" | "accent" | "success";

export type LoopSource = "review" | "lint" | null;

export type LoopState = "pending" | "active" | "passed";

const LOOP_LANE_HEIGHT = 24;
const LOOP_AREA_HEIGHT = 54;
const LOOP_DROP = 4;
const LOOP_HEAD = 8;
const LOOP_HEAD_HALF = 5.5;
const LOOP_RADIUS = 7;
const LOOP_ENTRY_OFFSET = 12;

export interface FlowNode {
  key: string;
  label: string;
  steps: string[];
  tone: FlowTone;
  terminal?: boolean;
  finalSteps?: string[];
}

export interface FlowFeedback {
  key: Exclude<LoopSource, null>;
  label: string;
  from: string;
  to: string;
  lane: number;
}

export const RESEARCH_FLOW: FlowNode[] = [
  { key: "linear", label: "Linear", steps: ["initial"], tone: "warning" },
  { key: "research", label: "Research", steps: ["research"], tone: "warning" },
  { key: "in-review", label: "In Review", steps: ["researched"], tone: "success", terminal: true },
];

export const BUILD_FLOW: FlowNode[] = [
  { key: "linear", label: "Linear", steps: ["initial"], tone: "warning" },
  { key: "plan", label: "Plan", steps: ["plan", "awaiting_input"], tone: "warning" },
  { key: "build", label: "Build", steps: ["build"], tone: "accent" },
  { key: "validate", label: "Validate", steps: ["validate"], tone: "accent" },
  { key: "review", label: "Review", steps: ["review"], tone: "accent" },
  { key: "lint", label: "Lint", steps: ["lint"], tone: "accent" },
  { key: "test", label: "Test", steps: ["test"], tone: "accent" },
  { key: "github", label: "GitHub", steps: ["wiki", "push", "completed"], tone: "success", finalSteps: ["completed"] },
];

export const BUILD_FEEDBACK: FlowFeedback[] = [
  { key: "review", label: "Feedback from review", from: "review", to: "build", lane: 1 },
  { key: "lint", label: "Feedback from lint and test", from: "test", to: "build", lane: 2 },
];

export function endsFlow(node: FlowNode, step: string): boolean {
  return node.terminal === true || (node.finalSteps?.includes(step) ?? false);
}

export function resolveNodeStates(flow: FlowNode[], step?: string | null): FlowNodeState[] {
  const activeIndex = step ? flow.findIndex((node) => node.steps.includes(step)) : -1;
  if (activeIndex === -1) return flow.map(() => "upcoming");
  // A step that ends the flow completes it, so it and everything before it read as done.
  if (step && endsFlow(flow[activeIndex], step)) return flow.map(() => "done");
  return flow.map((_, index) => {
    if (index === activeIndex) return "active";
    return index < activeIndex ? "done" : "upcoming";
  });
}

export function loopTrigger(previous: string | null, step: string | null): LoopSource {
  if (step !== "build") return null;
  if (previous === "review") return "review";
  if (previous === "lint" || previous === "test") return "lint";
  return null;
}

export function resolveLoopState(
  flow: FlowNode[],
  feedback: FlowFeedback,
  taken: boolean,
  step?: string | null,
): LoopState {
  // Without a loop back there is nothing to report, so the arrow stays dashed.
  if (!taken) return "pending";
  const sourceIndex = flow.findIndex((node) => node.key === feedback.from);
  const currentIndex = step ? flow.findIndex((node) => node.steps.includes(step)) : -1;
  if (currentIndex === -1 || sourceIndex === -1) return "passed";
  // The loop is behind us once the flow moved past the node that produced it.
  return currentIndex > sourceIndex ? "passed" : "active";
}

export function loopPath(fromX: number, toX: number, lane: number): { bracket: string; head: string } {
  const depth = lane * LOOP_LANE_HEIGHT;
  const direction = toX >= fromX ? 1 : -1;
  const radius = Math.min(LOOP_RADIUS, Math.abs(toX - fromX) / 2);
  const bracket = [
    `M ${fromX} ${LOOP_DROP}`,
    `V ${depth - radius}`,
    `Q ${fromX} ${depth} ${fromX + direction * radius} ${depth}`,
    `H ${toX - direction * radius}`,
    `Q ${toX} ${depth} ${toX} ${depth - radius}`,
    `V ${LOOP_HEAD}`,
  ].join(" ");
  const head = `M ${toX - LOOP_HEAD_HALF} ${LOOP_HEAD} L ${toX} 0 L ${toX + LOOP_HEAD_HALF} ${LOOP_HEAD}`;
  return { bracket, head };
}

interface LoopBracketProps {
  feedback: FlowFeedback;
  fromX: number;
  toX: number;
  width: number;
  state: LoopState;
}

function LoopBracket({ feedback, fromX, toX, width, state }: LoopBracketProps) {
  const depth = feedback.lane * LOOP_LANE_HEIGHT;
  // Nested brackets enter the target node side by side instead of stacking on one arrowhead.
  const entryX = toX - (feedback.lane - 1) * LOOP_ENTRY_OFFSET + 10;
  const { bracket, head } = loopPath(fromX, entryX, feedback.lane);
  return (
    <svg
      className={`session-flow-loop ${state}`}
      data-state={state}
      role="img"
      aria-label={feedback.label}
      width={Math.max(width, 1)}
      height={LOOP_AREA_HEIGHT}
      viewBox={`0 0 ${Math.max(width, 1)} ${LOOP_AREA_HEIGHT}`}
    >
      <path d={bracket} />
      <path d={head} />
      {state !== "pending" && (
        <text x={(fromX + entryX) / 2} y={depth - 5} textAnchor="middle">
          {feedback.label}
        </text>
      )}
    </svg>
  );
}

interface SessionStateFlowProps {
  step?: string | null;
  isResearch?: boolean;
}

export function SessionStateFlow({ step, isResearch = false }: SessionStateFlowProps) {
  const flow = isResearch ? RESEARCH_FLOW : BUILD_FLOW;
  const states = resolveNodeStates(flow, step);
  const trackRef = useRef<HTMLDivElement>(null);
  const previousStepRef = useRef<string | null>(null);
  const [takenLoops, setTakenLoops] = useState<Record<Exclude<LoopSource, null>, boolean>>({
    review: false,
    lint: false,
  });
  const [anchors, setAnchors] = useState<Record<string, number>>({});
  const [trackWidth, setTrackWidth] = useState(0);

  useEffect(() => {
    const trigger = loopTrigger(previousStepRef.current, step ?? null);
    previousStepRef.current = step ?? null;
    if (!trigger) return;
    setTakenLoops((previous) => (previous[trigger] ? previous : { ...previous, [trigger]: true }));
  }, [step]);

  useLayoutEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const measure = () => {
      const box = track.getBoundingClientRect();
      const centers: Record<string, number> = {};
      track.querySelectorAll<HTMLElement>("[data-node]").forEach((node) => {
        const rect = node.getBoundingClientRect();
        centers[node.dataset.node ?? ""] = rect.left - box.left + rect.width / 2;
      });
      setAnchors(centers);
      setTrackWidth(box.width);
    };
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    if (observer) {
      observer.observe(track);
    } else {
      window.addEventListener("resize", measure);
    }
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [flow]);

  const currentNode = step ? flow.find((node) => node.steps.includes(step)) : undefined;

  return (
    <div className="session-flow">
      <span className="session-flow-status" role="status" aria-live="polite">
        {currentNode ? `Current step: ${currentNode.label}` : ""}
      </span>
      <div className={`session-flow-track-wrap${isResearch ? " no-loops" : ""}`} ref={trackRef}>
        <div className="session-flow-track">
          {flow.map((node, index) => (
            <Fragment key={node.key}>
              {index > 0 && <span className="session-flow-separator" aria-hidden="true" />}
              <span
                className={`session-flow-node tone-${node.tone} ${states[index]}`}
                data-state={states[index]}
                data-node={node.key}
              >
                {node.label}
              </span>
            </Fragment>
          ))}
        </div>
        {!isResearch && (
          <div className="session-flow-loops">
            {BUILD_FEEDBACK.map((feedback) => {
              const fromX = anchors[feedback.from];
              const toX = anchors[feedback.to];
              if (fromX === undefined || toX === undefined) return null;
              return (
                <LoopBracket
                  key={feedback.key}
                  feedback={feedback}
                  fromX={fromX}
                  toX={toX}
                  width={trackWidth}
                  state={resolveLoopState(flow, feedback, takenLoops[feedback.key], step)}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default SessionStateFlow;
