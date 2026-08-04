---
title: Create LLM test script
date: 2026-02-26
type: implementation
status: resolved
session_id: -
services: [groq, prompts]
branch: -
tickets: [MNT-41]
tags: [llm, groq, parsing, testing]
related: []
---

# Create LLM test script

## TL;DR

A script was added to test how different LLMs extract questions from a markdown file. It reads three inputs — example markdown, a parsing prompt, and a list of LLMs — and, using LangChain + Groq with different output parsers, runs every LLM, extracts the questions, and writes `output/<llm-name>_<parser>.md` for each combination. This fed the design of the question-extraction and plan-summarization chains (MNT-61, MNT-98).

---

## Overview

MNT-41 is a benchmark harness, not production code: it empirically compares LLM × output-parser combinations on the question-extraction task so the later chains are built on data.

## Step 1 — Inputs

The script reads three inputs:

- an example markdown file to parse
- a parsing prompt (instructions for extracting questions)
- a list of LLMs to test

## Step 2 — Run every LLM with every parser

Using LangChain with Groq as the provider, the script iterates over the configured output parsers and runs each LLM through each parser to extract questions from the example markdown.

## Step 3 — Write per-combination output

**File:** `output/<llm-name>_<parser>.md`

For every `(llm, parser)` pair, the extracted questions are written to its own markdown file for comparison.

## Step 4 — Feed the chain design

The comparison results directly informed the design of:

- the question-extraction chain (MNT-61)
- the plan-summarization chain (MNT-98)

## Test Results

Manual inspection of the generated `output/` files across LLM × parser combinations; no persistent test suite (the script is a research tool).

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-41
