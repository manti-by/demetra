import { describe, expect, it } from "vitest";
import { isSensitiveKey, parseEnvFile } from "../utils/envFile";

describe("parseEnvFile", () => {
  it("parses simple KEY=VALUE pairs", () => {
    const entries = parseEnvFile("FOO=bar\nBAZ=qux\n");
    expect(entries).toEqual([
      { key: "FOO", value: "bar" },
      { key: "BAZ", value: "qux" },
    ]);
  });

  it("ignores blank lines and comments", () => {
    const entries = parseEnvFile("# comment\n\nFOO=bar\n# another\n");
    expect(entries).toEqual([{ key: "FOO", value: "bar" }]);
  });

  it("handles export prefix", () => {
    const entries = parseEnvFile("export FOO=bar\n");
    expect(entries).toEqual([{ key: "FOO", value: "bar" }]);
  });

  it("strips surrounding quotes", () => {
    const entries = parseEnvFile('FOO="bar"\nBAZ=\'qux\'\n');
    expect(entries).toEqual([
      { key: "FOO", value: "bar" },
      { key: "BAZ", value: "qux" },
    ]);
  });

  it("handles values with embedded spaces", () => {
    const entries = parseEnvFile('FOO="hello world"\n');
    expect(entries).toEqual([{ key: "FOO", value: "hello world" }]);
  });

  it("supports export prefix with only key", () => {
    const entries = parseEnvFile("export FOO\n");
    expect(entries).toEqual([{ key: "FOO", value: "" }]);
  });

  it("handles empty values", () => {
    const entries = parseEnvFile("EMPTY=\n");
    expect(entries).toEqual([{ key: "EMPTY", value: "" }]);
  });

  it("strips quotes from continued quoted values", () => {
    const entries = parseEnvFile('FOO="a\\\nb"\n');
    expect(entries).toEqual([{ key: "FOO", value: "ab" }]);
  });

  it("handles single-quoted continuation", () => {
    const entries = parseEnvFile("FOO='a\\\nb'\n");
    expect(entries).toEqual([{ key: "FOO", value: "ab" }]);
  });

  it("returns empty array for empty input", () => {
    expect(parseEnvFile("")).toEqual([]);
    expect(parseEnvFile("   \n# comment\n")).toEqual([]);
  });

  it("strips trailing comment from unquoted values", () => {
    const entries = parseEnvFile("API_KEY=abc123 # prod key\n");
    expect(entries).toEqual([{ key: "API_KEY", value: "abc123" }]);
  });

  it("preserves hash inside quoted values", () => {
    const entries = parseEnvFile('MSG="value # not a comment"\n');
    expect(entries).toEqual([{ key: "MSG", value: "value # not a comment" }]);
  });

  it("keeps hash without preceding whitespace", () => {
    const entries = parseEnvFile("HASH=value#nospace\n");
    expect(entries).toEqual([{ key: "HASH", value: "value#nospace" }]);
  });

  it("strips comment after closing quote", () => {
    const entries = parseEnvFile('KEY="abc" # comment\n');
    expect(entries).toEqual([{ key: "KEY", value: "abc" }]);
  });
});

describe("isSensitiveKey", () => {
  it("matches whole sensitive words", () => {
    expect(isSensitiveKey("GITHUB_TOKEN")).toBe(true);
    expect(isSensitiveKey("API_KEY")).toBe(true);
    expect(isSensitiveKey("DB_PASSWORD")).toBe(true);
    expect(isSensitiveKey("CLIENT_SECRET")).toBe(true);
    expect(isSensitiveKey("STRIPE_API_KEY")).toBe(true);
  });

  it("rejects plain keys", () => {
    expect(isSensitiveKey("DATABASE_URL")).toBe(false);
    expect(isSensitiveKey("LOG_LEVEL")).toBe(false);
    expect(isSensitiveKey("PORT")).toBe(false);
  });

  it("rejects partial-word matches", () => {
    expect(isSensitiveKey("KEYBOARD_LAYOUT")).toBe(false);
    expect(isSensitiveKey("MONKEY_BUSINESS")).toBe(false);
    expect(isSensitiveKey("TOKENIZATION")).toBe(false);
    expect(isSensitiveKey("PASSWORDLESS")).toBe(false);
    expect(isSensitiveKey("KEYSTORE")).toBe(false);
  });

  it("matches concatenated names closing at end", () => {
    expect(isSensitiveKey("STRIPEAPIKEY")).toBe(true);
    expect(isSensitiveKey("CLIENTPASSWORD")).toBe(true);
    expect(isSensitiveKey("MYAPIKEY")).toBe(true);
    expect(isSensitiveKey("JWTACCESSTOKEN")).toBe(true);
  });
});
