# Postmortems

Blameless incident postmortems, written in the style of Google's SRE postmortem
culture (https://sre.google/sre-book/postmortem-culture/).

Conventions:

- File name: `YYYY-MM-DD-<topic>.md`, where the date is the day the incident
  started (or the incident's headline date), not the day the document was written.
- The record is assumed to hold the incident (the system failed in a way that
  a human was forced to spend time on) and documents it for future reference:
  what happened, why it happened, the impact, the timeline of events, and the
  actions a human enacts so on it does not repeat, or is less painful when it does.
- Blameless: no "if only X hadn't..." — root causes are system and
  configuration conditions, not individual mistakes.
- Required sections (see the first postmortem for the shape): `TL;DR`,
  `Summary`, `Impact`, `Root cause`, `Timeline`, `Detection`,
  `Lessons learned`, `Action items`, `Supporting information`.

Postmortems in this directory are not listed in `wiki/INDEX.md`; they are an
audit record, not session pages. They may cross-link wiki pages with the usual
`[[...]]` notation.

## Contents

- [2026-11-09-econnreset-incident-postmortem.md](2026-11-09-econnreset-incident-postmortem.md)
