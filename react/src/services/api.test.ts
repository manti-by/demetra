import { describe, expect, it, vi, beforeEach } from "vitest";

import { getCurrentUser, getSessionHistory, signup, WaitlistedError } from "./api";

describe("getCurrentUser", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the user on 200", async () => {
    const user = { id: "u1", email: "a@b.c" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(user), { status: 200 })
    );

    await expect(getCurrentUser()).resolves.toEqual(user);
  });

  it("returns null on 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 })
    );

    await expect(getCurrentUser()).resolves.toBeNull();
  });

  it("returns transient on 5xx", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "boom" }), { status: 500 })
    );

    await expect(getCurrentUser()).resolves.toBe("transient");
  });

  it("returns transient on network failure", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(getCurrentUser()).resolves.toBe("transient");
  });
});

describe("signup", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("throws WaitlistedError on 202 waitlisted response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "waitlisted",
          message: "Your waitlist request has been recorded.",
        }),
        { status: 202 }
      )
    );

    await expect(signup("blocked@example.com", "hunter2hunter2")).rejects.toThrow(WaitlistedError);
  });
});

describe("getSessionHistory", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns empty history and tool usage on 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Session not found" }), { status: 404 })
    );

    await expect(getSessionHistory("TASK-1")).resolves.toEqual({
      total: {
        length: 0,
        input_tokens: 0,
        output_tokens: 0,
        reasoning_tokens: 0,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost: 0,
      },
      tool_usage: [],
      history: [],
    });
  });

  it("returns llm call rows alongside invocation rows", async () => {
    const payload = {
      total: {
        length: 700,
        input_tokens: 500,
        output_tokens: 200,
        reasoning_tokens: 0,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost: 0,
      },
      tool_usage: [],
      history: [
        {
          id: "h1",
          session_id: null,
          task_id: "TASK-1",
          agent_session_id: null,
          kind: "llm_call",
          step: "summarize_plan",
          created_at: "2026-01-01T00:00:00Z",
          length: 400,
          input_tokens: 300,
          output_tokens: 100,
          reasoning_tokens: null,
          cache_read_tokens: null,
          cache_write_tokens: null,
          context_tokens: null,
          cost: null,
          model: "openai/gpt-oss-120b",
          agent: "openrouter",
          message: null,
        },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200 })
    );

    const result = await getSessionHistory("TASK-1");

    expect(result.history).toHaveLength(1);
    expect(result.history[0].kind).toBe("llm_call");
    expect(result.history[0].agent).toBe("openrouter");
    expect(result.history[0].model).toBe("openai/gpt-oss-120b");
  });
});
