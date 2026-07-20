---
description: Force the Wiki Agent to write a wiki page for the current session right now
agent: build
---
Determine the current session ID (the session this command is running in) and
call the `openwiki_write` tool with the `sessionId` set to that value.

This forces the Wiki Agent to evaluate the current session and, if it's worth
documenting, create or update a page under `wiki/pages/` and the `INDEX.md`
entry. If the session already has a page, it will be updated in place.

Report back whether a page was written or updated, or if the session was
skipped (trivial exchange, quick question, etc.).
