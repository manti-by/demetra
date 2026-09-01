import { describe, expect, it, vi, beforeEach } from "vitest";

import { getCurrentUser, signup, WaitlistedError } from "./api";

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