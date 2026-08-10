export interface EnvFileEntry {
  key: string;
  value: string;
}

const SENSITIVE_KEY_RE = /(?:^|[\W_])(?:TOKEN|SECRET|KEY|PASSWORD)(?:[\W_]|$)/i;

/**
 * Return whether an environment key should be treated as sensitive.
 *
 * Mirrors the backend `is_sensitive_key`: whole-word TOKEN/SECRET/KEY/PASSWORD
 * delimited by start/end or a non-alphanumeric character. Matches
 * `GITHUB_TOKEN`, `API_KEY`, `DB_PASSWORD` while rejecting `KEYBOARD_LAYOUT`,
 * `MONKEY_BUSINESS` and `TOKENIZATION`.
 *
 * @param key - The environment variable name.
 * @returns True when the key matches the sensitive-key pattern.
 */
export function isSensitiveKey(key: string): boolean {
  return SENSITIVE_KEY_RE.test(key);
}

const KEY_VALUE_RE = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/;
const KEY_ONLY_RE = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)$/;

function stripQuotes(raw: string): string {
  const value = raw.trim();
  if (value.length >= 2) {
    const first = value[0];
    const last = value[value.length - 1];
    if ((first === '"' && last === '"') || (first === "'" && last === "'")) {
      return value.slice(1, -1);
    }
  }
  return value;
}

/**
 * Parse the contents of a `.env` file into KEY=VALUE entries.
 *
 * Handles blank lines, `#` comments, an optional `export ` prefix, quoted
 * values with single or double quotes, and backslash line continuations.
 * Values are returned with surrounding quotes stripped.
 *
 * @param text - The raw file contents.
 * @returns The parsed key-value entries, in file order.
 */
export function parseEnvFile(text: string): EnvFileEntry[] {
  const entries: EnvFileEntry[] = [];
  const lines = text.split(/\r?\n/);
  let pendingKey: string | null = null;
  let pendingValue = '';

  const flush = () => {
    if (pendingKey !== null) {
      entries.push({ key: pendingKey, value: pendingValue });
      pendingKey = null;
      pendingValue = '';
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (pendingKey !== null) {
      if (line.endsWith('\\')) {
        pendingValue += line.slice(0, -1);
        continue;
      }
      pendingValue += line;
      flush();
      continue;
    }

    if (line === '' || line.startsWith('#')) {
      continue;
    }

    const keyMatch = line.match(KEY_VALUE_RE);
    if (keyMatch) {
      let value = keyMatch[2];
      if (value.endsWith('\\')) {
        pendingKey = keyMatch[1];
        pendingValue = value.slice(0, -1);
      } else {
        entries.push({ key: keyMatch[1], value: stripQuotes(value) });
      }
      continue;
    }

    const keyOnlyMatch = line.match(KEY_ONLY_RE);
    if (keyOnlyMatch) {
      entries.push({ key: keyOnlyMatch[1], value: '' });
    }
  }

  flush();
  return entries;
}
