---
name: release-notes
description: Generate GitHub release notes for the demetra repo between two version tags. Use when asked to "create release notes", "write a changelog", "draft a release", or "build release notes" for a tag range such as v1.15.4..v1.16.7.
---

# Release Notes Skill

## Purpose
This skill drafts the Release Notes section for a new demetra GitHub release. It gathers every merged pull request and every direct ("one-shot") commit pushed to `master` between two tags, groups them by category, and formats them to match the existing release notes style. Use it to produce notes for a release whose exact tag range is known, e.g. `v1.15.4..v1.16.7`.

The live template reference is the repo's releases page: https://github.com/manti-by/demetra/releases. Skim the most recent few entries before drafting to mirror the current wording, emoji headers, and section ordering.

## Input
The user provides a tag range in `..` form, for example:

- `v1.15.4..v1.16.7`

Interpret it as: everything merged or committed on top of `v1.15.4` up to and including `v1.16.7`. Confirm the two tags exist before gathering.

## Gather the changes
1. List the commits in the range:
   - `git log --oneline v1.15.4..v1.16.7`
2. List the merged pull requests in the range:
   - `git log --oneline --merges v1.15.4..v1.16.7`
3. Fetch the PR titles, issue references, and merge commit SHAs for any merge commits:
   - `gh pr list --state merged --base master`
   - `gh pr view <number> --json title,body,url,mergeCommit,labels`
4. Identify **one-shot direct commits**: commits pushed straight to `master` that are NOT part of a feature-branch merge. They are the non-merge commits in the range that carry standalone fixes, dependency bumps, CI tweaks, docs, or version bumps.

## Group the changes
Sort every item into the same categories used by the template (in this order):

- `🚀 New Features`
- `🐛 Bug Fixes`
- `🔧 Improvements`
- `📦 Dependency & Config` (only when dependency/config changes are significant)
- `📄 Documentation & Maintenance`

Rules for grouping:
- Feature-branch merged PRs go first, formatted as `**MNT-123: Title** ([#NN](url)) — one-line summary.`
- Direct commits are listed as short bullet points, optionally with their SHAs: `Fix version bumping logic`, `Update logging configuration`.
- If an item is ambiguous, prefer the most specific category and keep the description faithful to the commit/PR title.

## Format
Follow this template exactly:

1. Opening line with a **total commit count** and branch count, e.g.:
   `**33 commits** across 5 feature branches and standalone fixes since v1.14.4.`
   Count = total commits in the range; branch count = number of merged PRs.
2. One `### <Emoji> <Category>` heading per non-empty category, in the order above.
3. Bulleted list of items under each heading.
4. Close with:
   `---`
   `**Full Changelog**: [v1.15.4...v1.16.7](https://github.com/manti-by/demetra/compare/v1.15.4...v1.16.7)`

Match the exact emoji and heading text used in the current template; do not invent new headers.

## Naming
Use the `release-name` skill to pair the version tag with a two-word space-theme release codename (e.g. `v1.16.7 Aurora Borealis`) when a release name is expected. The version string in the heading must match the new tag.

## Output format
Print the release notes as **raw GitHub-flavored Markdown** directly in the response, not as a plain-text summary, a JSON blob, or a wrapped code block. The output must be copy-paste ready for the GitHub release editor:
- Preserve the exact `#`/`###` headings, `-`/`*` bullets, `**bold**`, and link syntax above.
- Keep the literal emoji characters in the category headings.
- Do not add a language fence or quotes around the notes.
- Do not prefix the output with prose like "Here are the release notes"; emit the Markdown and nothing else (no trailing commentary unless the range was empty or `gh` was unauthenticated).

## Quality checks
The following is a checklist applied to the final Markdown before returning it.
- Every merged PR in the range is represented at least once.
- Direct one-shot commits are not dropped and are not mislabeled as PRs.
- The commit count and branch count in the opening line are accurate.
- Category headings use the exact emoji from the template.
- The Full Changelog compare link uses the correct from..to tags.
- No placeholders or guessed commit SHAs; only real values.

## Edge cases
- Empty range (no commits): return a short note stating there is nothing new between the two tags.
- No feature branches: skip the New Features intro line and start with the commit count, listing only direct commits.
- If `gh` is not authenticated, fall back to `git log` and PR details already present in merge commit messages, and flag the release notes as unverified.