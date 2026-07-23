# Questions Extraction Audit

Benchmark of LLM output parser strategies for extracting questions from markdown text. Tests 9 Groq-hosted models × 3 parser strategies (CSV, JSON, numbered list) — 23 outputs (9 models × 3 parsers minus 4 combos where the model doesn't support JSON).

Run: `uv run wiki/audits/2026-02-23-questions-extraction/check_llm_parsers.py`

## Directory Structure

```text
├── README.md              ← this file
├── __init__.py            empty package marker
├── check_llm_parsers.py   benchmark runner (asyncio + langchain-groq)
├── input/
│   ├── text.md            source markdown with 4 clarifying questions
│   ├── prompt.md          system prompt for extraction
│   └── models.txt         one Groq model name per line
└── output/
    ├── <model>_csv.md
    ├── <model>_json.md
    └── <model>_numbered_list.md
```

## Task

Extract 4 clarifying questions from a "Process Manager" implementation plan document. The source text has ~58 lines with 4 multi-line questions containing sub-bullets. The prompt instructs the model to preserve exact wording and not split choice questions.

## Models Tested

- **llama-3.1-8b-instant** — CSV ✅ JSON ✅ Numbered List ✅
- **llama-3.3-70b-versatile** — CSV ✅ JSON ✅ Numbered List ✅
- **meta-llama/llama-4-maverick-17b-128e-instruct** — CSV ✅ JSON ✅ Numbered List ✅
- **meta-llama/llama-4-scout-17b-16e-instruct** — CSV ✅ JSON ✅ Numbered List ✅
- **meta-llama/llama-guard-4-12b** — CSV ✅ JSON ✗ Numbered List ✅
- **moonshotai/kimi-k2-instruct-0905** — CSV ✅ JSON ✅ Numbered List ✅
- **openai/gpt-oss-120b** — CSV ✅ JSON ✗ Numbered List ✅
- **openai/gpt-oss-20b** — CSV ✅ JSON ✗ Numbered List ✅
- **qwen/qwen3-32b** — CSV ✅ JSON ✗ Numbered List ✅

## Results Summary

**Expected output:** 4 questions.

- **llama-3.1-8b-instant** — CSV ❌ 11 | JSON ⚠️ 5 (1 extra) | Numbered ✅ 4
- **llama-3.3-70b-versatile** — CSV ❌ 5 (truncated) | JSON ✅ 4 | Numbered ✅ 4
- **llama-4-maverick** — CSV ❌ 23 (duplicates) | JSON ✅ 4 | Numbered ✅ 4
- **llama-4-scout** — CSV ❌ 14 | JSON ❌ 0 (empty) | Numbered ❌ 13
- **llama-guard-4-12b** — CSV ❌ 1 ("safe") | JSON — | Numbered ❌ 1 ("safe")
- **kimi-k2-0905** — CSV ❌ 11 | JSON ✅ 4 (no backticks) | Numbered ✅ 4
- **gpt-oss-120b** — CSV ❌ 5 (truncated) | JSON — | Numbered ✅ 4
- **gpt-oss-20b** — CSV ❌ 0 (empty) | JSON — | Numbered ❌ 0 (empty)
- **qwen/qwen3-32b** — CSV ❌ 38 (reasoning bleed) | JSON — | Numbered ❌ 22 (reasoning bleed)

### Key Findings

- **CSV parser fails universally** — multiline questions with bullet points get shattered into fragments. Never use CSV for multi-line extraction.
- **JSON parser is most reliable** — 8 non-failed outputs; excluding the empty llama-4-scout result, each returned exactly 4 correct questions (except llama-3.1-8b-instant which added 1 extra non-question). JSON's structured format prevents stray text.
- **numbered_list works well when models follow instructions** — 9 runs, 8 non-empty results, 5 exact four-question results. Vulnerable to reasoning bleed (qwen3-32b) and over-splitting (llama-4-scout).
- **llama-guard-4-12b** is a safety classifier, not suitable for extraction.
- **gpt-oss-20b** failed entirely (zero extraction).
- **qwen3-32b** cannot suppress its `<think>` reasoning, inflating output.

### Best Combinations

1. **llama-3.3-70b-versatile + json** — perfect, most reliable
2. **llama-4-maverick + json** or **+ numbered_list** — perfect
3. **kimi-k2-0905 + json** or **+ numbered_list** — perfect (minor backtick loss in JSON)
4. **llama-3.1-8b-instant + numbered_list** — perfect (smallest model that works)
