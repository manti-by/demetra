Extract the actionable errors from a `{source}` run into a deduplicated numbered list. This is EXTRACTION only —
never invent, infer, rephrase, or fix errors into existence.

The output is either a linter (ruff) report or a pytest report:

- For a linter report, emit one entry per violation, keeping the `path/to/file.py:line:col: CODE message` text
  verbatim, including the rule code.
- For a pytest report, emit one entry per failing test, keeping the test id and the error description (the
  assertion message or the exception type and message) on a single line.

Exclude everything else: progress lines, platform and version headers, collection counts, timing and duration
lines, `=== ... ===` section banners, code snippets, tracebacks of the runner itself, and the trailing summary
counts. If an error spans several lines, keep only the meaningful description and join it onto one line.

Deduplicate: keep one verbatim entry per error; if duplicates differ in detail, keep the most specific entry —
never merge or rewrite.

When in doubt, do NOT output an entry — a fabricated error is worse than a missed one.

Output: plain numbered list (`1. Error text`), one entry per line. No headers, intro, commentary, or markdown. If
the output contains no real errors, output NOTHING — silence is correct, fabrication is not.
