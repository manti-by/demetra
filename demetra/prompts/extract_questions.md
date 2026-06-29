Extract open questions from planning agent output into a deduplicated numbered list. This is EXTRACTION only — never
invent, infer, rephrase, answer, or summarize questions into existence.

Include a line ONLY if it literally ends with `?` in the source, is a standalone open question from a trailing
"Open Questions" list (not part of the plan), and is specific/answerable about this task or codebase. Exclude
everything else: the chosen approach, numbered build STEPS, verification notes, section headers, code blocks,
sentences with `?` in passing, rhetorical/embedded questions, generic thinking questions ("What is the current
structure?", "What are the project requirements?"), and terminal markers ("Ready to proceed to build.", "Please check
my questions above."). Never turn build steps into questions.

When in doubt, do NOT output a question — a fabricated question is worse than a missed one.

Output: plain numbered list (`1. Question text`), verbatim wording with trailing `?`. Keep choice questions
(containing "or"/"and") as single items — do not split. No headers, intro, commentary, or explanation. If the text
contains "Ready to proceed to build." or has no trailing list of `?`-terminated questions, output NOTHING — silence
is correct, fabrication is not.
